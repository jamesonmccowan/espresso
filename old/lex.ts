import {
	BoolProto, IntProto, FloatProto, StringProto,
	None, Expr, Block, Sexp, Const, Var, Prog, Group, EspFunc
} from "./vm";

function unreachable(): never {
	throw new Error("Unreachable code execution path");
}

export class ParseError extends Error {
	msg: string;
	pos: number;
	line: number;
	col: number;
	
	constructor(msg: string, pre:string, p: number, l:number, c:number) {
		super(`${msg} (${l}|${c}:${p})\n${pre}`);
		this.msg = msg;
		this.pos = p;
		this.line = l;
		this.col = c;
	}
}

const raw = String.raw;
const DEC = raw`\d[\d_]*`;
// Token regex, organized to allow them to be indexed by name
const PATS = {
	"bin": raw`0b[_01]*[01]`,
	"oct": raw`0o[_0-7]*[0-7]`,
	"hex": raw`0x[_\da-fA-F]*[\da-fA-F]`,
	"flt": raw`(?:\.\d[_\d]*|\d[_\d]*\.(?:\d[_\d]*)?)(?:e[-+]\d[_\d]*)?`,
	"dec": raw`\d+`,
	"sq": raw`'(?:\\.|.+?)*?'`,
	"dq": raw`"(?:\\.|.+?)*?"`,
	"bq": raw`\`(?:\\.|.+?)*?\``,
	"sq3": raw`'''(?:\\.|.+?)*?'''`,
	"dq3": raw`"""(?:\\.|.+?)*?"""`,
	"bq3": raw`\`\`\`(?:\\.|.+?)*?\`\`\``,
	"id": raw`[\w][\w\d]*`,
	"punc": raw`[()\[\]{}]`,
	"op": [
		raw`[@~;,?]`,
		raw`[-+*/%&|^:]{1,2}`,
		raw`[<>.]{1,3}`,
		raw`={1,3}`, raw`!={,2}`, raw`[<>]=?`
	].join("|")
};
// Operators which can't be overloaded because they encode syntax
const SYNTACTIC = [
	",", "=", "...", ".", ":", "&&", "||", "===", "!==", "++", "--"
];
const PRECS: Record<string, number> = {
	",": 1,
	"=": 2,
	"..": 3, "...": 3,
	"||": 3, "^^": 4, "&&": 5, "|": 6, "^": 7, "&": 8,
	"==": 9, "!=": 9, "===": 9, "!==": 9,
	"<": 10, "<=": 10, ">": 10, ">=": 10, "<>": 10,
	"<<": 11, "<<<": 11, ">>": 11, ">>>": 11,
	"!": 12, "~": 13, "+": 14, "-": 14,
	"*": 15, "/": 15, "%": 15,
	"**": 16, "//": 16, "%%": 16,
	".": 17
};

// Low level token type enumeration corresponding to distinct subpatterns
//  within the token regex
type LLTOK = keyof typeof PATS;

// High level token type enumeration, combines multiple patterns into
//  higher level interpretations and constants
type HLTOK = "int"|"flt"|"str"|"id"|"kw"|"op"|"punc";

// Right-associative operators
const RIGHT = [
	"**"
];

const KW = [
	"if", "then", "else", "return", "while", "var"
];

const NAMES = Object.keys(PATS);
const TOKEN = new RegExp(`(${Object.values(PATS).join(")|(")})`, "gym");
const COMMENT = /\s*(#\*(?:.|\n)+\*#\s*|#\{|#.*$)/gym;
const RECURSIVE_COMMENT = /#\{|#\}/gm;
const NEWLINE = /\n/m;
const SPACE = /\s+/gym;

class Token {
	value: any;
	type: HLTOK;
	pos: number;
	line: number;
	col: number;
	
	constructor(v: any, t: HLTOK, p: number, l: number, c: number) {
		this.value = v;
		this.type = t;
		this.pos = p;
		this.line = l;
		this.col = c;
	}
}

/**
 * Context-less stream of tokens to be fed to the parser
 */
class Lexer {
	src: string;
	pos: number;
	line: number;
	col: number;
	
	indent: number;
	
	constructor(src: string) {
		this.src = src;
		this.pos = 0;
		this.line = 1;
		this.col = 0;
		this.indent = 0;
	}
	
	log(...args: any[]): void {
		console.log(' '.repeat(this.indent), ...args)
	}
	
	/**
	 * Build an error from the message at the current position
	 */
	error(msg: string): ParseError {
		// Want to build a preview, extract the start of line
		let sol = this.src.lastIndexOf('\n', this.pos);
		if(sol === -1) sol = 0;
		let left = this.pos - 60; // prioritize before over after
		if(left < sol) left = sol;
		
		// Cutoff at 80 characters or the end of the line
		let pre = this.src.substr(left, 80).split('\n')[0];
		// Point to the error
		pre += `\n${'-'.repeat(this.pos - left)}^`;
		pre += `\n${this.src.substr(this.pos)}`;
		
		return new ParseError(msg, pre, this.pos, this.line, this.col);
	}
	
	/**
	 * Utility to use different regexes at the same index
	 */
	match(re: RegExp): RegExpExecArray|null {
		re.lastIndex = this.pos;
		return re.exec(this.src);
	}
	
	/**
	 * Adjust the parser position based on the token match
	 */
	repos(m: RegExpExecArray): void {
		this.pos += m[0].length;
		let lines = m[0].split(NEWLINE);
		if(lines.length > 1) {
			this.line += lines.length - 1;
			this.col = lines[lines.length - 1].length;
		}
		else {
			this.col += m[0].length;
		}
	}
	
	/**
	 * Debug method summarizing the parser state
	 */
	state() {
		return {line: this.line, col: this.col, pos: this.pos};
	}
	
	/**
	 * Grab the next token after discarding whitespace and comments
	 */
	next(): Token|null {
		if(this.pos >= this.src.length) return null;
		
		let comment;
		while(comment = this.match(COMMENT)) {
			this.repos(comment);
			// Recursive comment parsing
			if(comment[1] === "#{") {
				let level = 1;
				do {
					let m = this.match(RECURSIVE_COMMENT);
					if(m === null) throw this.error("Unexpected EOF");
					(m[0] === "#{")? ++level : --level;
				} while(level);
			}
		}
		
		// Clean up ordinary space without comments
		let m = this.match(SPACE), i;
		if(m !== null) this.repos(m);
		
		m = this.match(TOKEN);
		if(m === null) throw this.error("Unknown token");
		
		for(i = 0; i < NAMES.length; ++i) {
			if(m[i + 1]) break;
		}
		let tok = m[i + 1], type = NAMES[i], val: any;
		
		// DRY for parsing ints with different radices
		function radixint(v: string, r: number): number {
			if(r !== 10) v = v.substr(2);
			return parseInt(v.replace("_", ""), r);
		}
		
		switch(type as LLTOK) {
			// Identifiers / keywords
			case "id":
				if(KW.includes(tok)) {
					type = "kw";
				}
				val = tok;
				break;
			
			// Integers
			case "bin":
				type = "int";
				val = radixint(tok, 2);
				break;
			case "oct":
				type = "int";
				val = radixint(tok, 8);
				break;
			case "hex":
				type = "int";
				val = radixint(tok, 16);
				break;
			case "dec":
				type = "int";
				val = radixint(tok, 10);
				break;
			
			// Floating point
			case "flt":
				val = parseFloat(val.replace("_", ""));
				break;
			
			// Strings
			case "sq": case "dq": case "bq":
				type = "str";
				val = tok.substr(1, tok.length - 2);
				break;
			case "sq3": case "dq3": case "bq3":
				type = "str";
				val = tok.substr(3, tok.length - 6);
				break;
			
			case "punc":
			case "op":
				// Do nothing, type and value are already correct
				break;
			
			default: return unreachable();
		}
		
		let ncur = new Token(tok, type as HLTOK, this.pos, this.line, this.col);
		
		this.repos(m);
		
		return ncur;
	}
}

/**
 * Convert a list of expressions to a single expression, possibly a Block
 */
function blockAsExpr(block: Expr[]): Expr {
	if(block.length === 0) {
		return None;
	}
	else if(block.length === 1) {
		return block[0];
	}
	else {
		return new Block(block);
	}
}

export class Parser extends Lexer {
	cur: Token|null;
	scope: string[][];
	
	constructor(src: string) {
		super(src);
		this.cur = this.next();
		this.scope = [];
	}
	
	topScope(): string[] {
		return this.scope[this.scope.length - 1];
	}
	
	addVar(name: string): void {
		this.topScope().push(name);
	}
	
	/**
	 * The current token's context has been identified, consume it and
	 *  advance the stream
	 */
	consume() {
		this.cur = this.next();
	}
	
	/**
	 * Check if the next token has a particular value and consume it if it
	 *  does. Otherwise do nothing but return false.
	 */
	maybe(what: string) {
		if(this.cur !== null && this.cur.value === what) {
			this.consume();
			return true;
		}
		return false;
	}
	
	expect(what: string): void {
		if(!this.maybe(what)) {
			throw this.error(`Expected ${what}`);
		}
	}
	
	expectType(type: string): void {
		if(this.cur === null || this.cur.type !== type) {
			throw this.error(`Expected ${type}`);
		}
	}
	
	idOrString(): Expr {
		switch(this.cur.type) {
			case "id": case "kw": case "str":
				return new Const(StringProto, this.cur.value);
			
			default: throw this.error("Expected identifier");
		}
	}
	
	func(): EspFunc {
		if(!(this.cur.type === "str" || this.cur.type === "id")) {
			throw this.error(`Unexpected token ${this.cur.value}`);
		}
		let name = new Const(StringProto, this.cur.value);
		
		let args = [];
		
		this.expect("(");
		while(!this.maybe(")")) {
			this.expectType("id");
			args.push(this.cur.value);
		}
		
		return new EspFunc(name, args, this.block());
	}
	
	atom(): Expr|null {
		if(this.cur === null) return null;
		
		
		// Exceptions which shouldn't be consumed
		let cur = this.cur, val = cur.value;
		switch(val) {
			case ")": return null;
		}
		
		this.consume();
		
		switch(cur.type) {
			case "int": return new Const(IntProto, val);
			case "flt": return new Const(FloatProto, val);
			case "str": return new Const(StringProto, val);
			
			case "id": return new Var(val);
			
			case "op":
				switch(cur.value) {
					/*
					case "[":
						this.advance();
						val = this.list();
						this.expect("]");
						return val;
					
					case "{":
						this.advance();
						val = this.object();
						this.expect("}");
						return val;
					
					case ".":
						this.advance();
						return this.dotfunc();
					*/
					// Unary
					default:
						return new Sexp(cur.value, None, this.atom() ?? None);
				}
			
			case "punc":
				switch(val) {
					case "(":
						let x = this.semichain();
						this.expect(")");
						return blockAsExpr(x);
					
					// Unreachable, left for clarity
					case ")": return null;
					
					default:
						throw this.error(
							`Unknown punctuation "${this.cur.value}"`
						);
				}
			
			case "kw":
				switch(cur.value) {
					case "if": {
						let cond = this.expr() ?? None;
						this.maybe("then");
						let th = this.block(), el = None;
						
						if(this.maybe("else")) el = this.block();
						return new Sexp("if", cond, th, el);
					}
					
					/**
					 * Else cannot appear on its own, but it isn't an error
					 *  to encounter it while parsing an atom - this can
					 *  happen while parsing the then block
					*/
					case "else": return null;
					
					case "while": {
						let cond = this.expr() ?? None;
						let bl = this.block(), th = None, el = None;
						if(this.maybe("then")) th = this.block();
						if(this.maybe("else")) el = this.block();
						
						return new Sexp("while", cond, bl, th, el);
					}
					
					/**
					 * Var declarations are split into two separate concerns,
					 *  variable name hoisting to the innermost enclosing
					 *  scope and assignment of the variable at the correct
					 *  point (by returning assignments as a group of
					 *  assignment s-exprs)
					 */
					case "var": {
						let group = [];
						do {
							this.expectType("id");
							let name = this.cur.value;
							this.consume();
							
							this.addVar(name);
							
							if(this.maybe("=")) {
								let x = this.expr();
								if(x === null) {
									throw this.error("Expected expression");
								}
								group.push(new Sexp("=", new Var(name), x));
							}
						} while(this.maybe(","));
						
						return new Group(group);
					}
					
					case "function": return this.func();
					
					/*
					case "try":
						this.advance();
						let tr = this.block(), th = null;
						let er = null, el = null, fin = null;
						
						if(this.maybe("then")) {
							th = this.block();
						}
						if(this.maybe("catch")) {
							if(this.maybe("(")) {
								this.expectType("id");
								err = this.cur.value;
								this.advance();
								this.expect(")");
								
								el = this.block();
							}
						}
						else if(this.maybe("else")) {
							el = this.block();
						}
						
						if(this.maybe("finally")) {
							fin = this.block();
						}
						
						return new Try(tr, th, er, el, fin);
					*/
					default:
						throw this.error(
							"Unimplemented keyword " + this.cur.value
						);
				}
		}
		
		throw this.error("Unknown token " + this.cur);
	}
	
	/**
	 * Parses a "block", which is an expression which prioritizes curly-brace
	 *  blocks over object literals and considers the semicolon to end the
	 *  expression rather than continue it.
	 */
	block(): Expr {
		if(this.maybe("{")) {
			let vars: string[] = [];
			this.scope.push(vars);
			let b = this.semichain();
			this.scope.pop();
			this.expect("}");
			
			if(vars.length > 0) {
				return blockAsExpr(b);
			}
			else {
				// If there's a var, always treat it as a block
				return new Block(b, vars);
			}
		}
		else {
			let x = this.expr();
			this.maybe(";");
			return x ?? None;
		}
	}
	
	/**
	 * Uses precedence climbing
	 */
	expr_impl(lhs: Expr, prec: number): Expr|null {
		while(this.cur !== null) {
			let op = this.cur.value, p = PRECS[op];
			this.log("Op1?", op, p);
			if(p === undefined || p < prec) break;
			this.consume();
			
			let rhs = this.atom();
			if(rhs === null) break;
			
			while(this.cur !== null) {
				let op2 = this.cur.value, p2 = PRECS[op2];
				this.log("Op2?", op2, p2);
				if(p2 === undefined) break;
				if(p2 <= p || RIGHT.includes(op2)) break;
				rhs = this.expr_impl(rhs, p + 1);
				if(rhs === null) throw this.error("null RHS");
			}
			lhs = new Sexp(op, lhs, rhs);
		}
		
		return lhs;
	}
	
	expr(): Expr|null {
		let lhs = this.atom();
		if(lhs === null) return null;
		if(this.cur === null) {
			return lhs;
		}
		return this.expr_impl(lhs, 0);
	}
	
	/**
	 * Parse a block as a chain of expressions possibly separated by
	 *  semicolons.
	 */
	semichain(): Expr[] {
		let st = [];
		do {
			let x = this.expr();
			if(x === null) break;
			st.push(x);
			while(this.maybe(";")) {}
		} while(this.cur !== null && this.cur.value !== "}");
		
		return st;
	}
	
	parse(): Prog {
		let vars: string[] = [];
		this.scope.push(vars);
		let prog = new Prog(new Block(this.semichain(), vars));
		this.scope.pop();
		return prog;
	}
}

function pretty(x: any): string {
	switch(typeof x) {
		case "string":
			return JSON.stringify(x);
		
		case "object":
			return x.toString();
		
		default:
			return x.toString();
	}
}

(() => {
	// Fuck you Typescript
	let pp = Parser.prototype as any;
	for(let fn of Object.getOwnPropertyNames(pp)) {
		let impl = pp[fn] as (...args: any[]) => any;
		
		switch(fn) {
			case "consume":
				pp[fn] = function(...args: any[]) {
					this.log(`${fn}(${args.map(pretty).join(', ')}) ${pretty(this.cur.value)}`);
					++this.indent;
					let ret = impl.apply(this, args);
					--this.indent;
					
					return ret;
				}
				break;
			
			default:
				pp[fn] = function(...args: any[]) {
					this.log(`${fn}(${args.map(pretty).join(', ')}) {`);
					++this.indent;
					let ret = impl.apply(this, args);
					--this.indent;
					
					this.log(ret === undefined? "}" : `} = ${ret}`);
					
					return ret;
				}
				break;
		}
	}
})()