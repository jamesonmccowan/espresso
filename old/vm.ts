export class NotImplemented extends Error {
	constructor(what: string|null = null) {
		if(what === null) super("Method not implemented");
		else super("Method not implemented: " + what);
	}
}

const OPS = [
	// 0000 +0
		"unreachable", "nop", "block", "loop", "if", "else", "try", "throw", "end",
		"br", "br_if", "br_table", "return", "throw", "yield", "await",
		"drop", "select", "const",
		"call", "get", "set", "delete",
		"local.get", "local.set", "upvar.get", "upvar.set",
		
		"==", "!=", "<", ">", "<=", ">=", "===", "<>",		
		
		"+", "-", '*', '**', '/', '//', '%', '%%',
		"~", "&", "|", "^", "<<", "<<<", ">>", ">>>", "<<>", "<>>",
	// 0001 +16
		"~~", "&&", "||", "bool", "in", "is", "as", "..",
		"!", "!!",
	
	// 0010 +32
		"closure", "proto", "typeof", ":=",
	
	// first bit is whether or not there's an immediate 
	// 1000 +128
		
		"none", "false", "true"
];

const IMMOPS = [
	"br", "br_if", "br_table",
	"call", "get", "set", "delete", "const"
];

const OPNAME = Object.freeze(Object.fromEntries(
	OPS.map((x, y) => [y, x])
));

class EspRange {
	constructor(
		public lo: number, public hi: number, public step: number = 1) {}
}

// Ops which use Pythonic operator overloading
const SIMPLE_OPS : Record<string, (x: any, y: any) => any> = {
	"+"(lhs, rhs) { return lhs + rhs },
	"-"(lhs, rhs) { return lhs - rhs },
	"*"(lhs, rhs) { return lhs * rhs },
	"/"(lhs, rhs) { return lhs / rhs },
	"%"(lhs, rhs) { return lhs % rhs },
	"**"(lhs, rhs) { return lhs ** rhs },
	"//"(lhs, rhs) { return (lhs / rhs)|0 },
	"%%"(lhs, rhs) { throw new NotImplemented("operator %%") },
	
	"<"(lhs, rhs) { return lhs < rhs },
	"<="(lhs, rhs) { return lhs <= rhs },
	">"(lhs, rhs) { return lhs > rhs },
	">="(lhs, rhs) { return lhs >= rhs },
	"=="(lhs, rhs) { return lhs == rhs },
	"!="(lhs, rhs) { return lhs != rhs },
	"==="(lhs, rhs) { return lhs === rhs },
	"<>"(lhs, rhs) { return (lhs >= rhs?1:0) - (lhs <= rhs?1:0) },
	
	"~"(lhs, rhs) {
		if(lhs !== none) throw new NotImplemented("binary operator ~");
		return ~rhs;
	},
	"&"(lhs, rhs) { return lhs & rhs },
	"|"(lhs, rhs) { return lhs | rhs },
	"^"(lhs, rhs) { return lhs ^ rhs },
	"<<"(lhs, rhs) { return lhs << rhs },
	"<<<"(lhs, rhs) { throw new NotImplemented("operator <<<") },
	">>"(lhs, rhs) { return lhs >> rhs },
	">>>"(lhs, rhs) { return lhs >>> rhs },
	"<<>"(lhs, rhs) { throw new NotImplemented("operator <<>") },
	"<>>"(lhs, rhs) { throw new NotImplemented("operator <>>") },
	".."(lhs, rhs) { return new EspRange(lhs, rhs) },
	
	"&&"(lhs, rhs) { return lhs && rhs },
	"||"(lhs, rhs) { return lhs || rhs },
	"^^"(lhs, rhs) { throw new NotImplemented("operator ^^") },
	"~~"(lhs, rhs) { return new NotImplemented("operator ~~") }
}

export const none = new Proxy({}, {
	get(target, prop, recv) {
		if(prop === Symbol.toPrimitive) {
			return () => null;
		}
		return recv;
	},
	set(target, prop, value, recv) {
		throw new Error("Assigning property to none");
	},
	deleteProperty(target, prop) {
		return true;
	},
	has(target, prop) {
		return false;
	}
});

class Bytecode {
	constructor(public op: string, public imm: number|null, public size: number) {}
}

function leb128(src: Uint8Array, x: number): [number, number] {
	const HI1 = 1<<7, LO7 = HI1 - 1;
	
	let val = 0, y = x, b;
	do {
		if(x >= src.length) throw new Error("leb128 EOF");
		
		b = src[x++];
		
		val <<= 7;
		val |= b&LO7
	} while(b&HI1);
	
	return [val, x - y];
}

class Code {
	/**
	 * Raw bytecode, a sequence of leb128 integers (almost always bytes)
	 */
	code: Uint8Array;
	/**
	 * Constant table, accessed by index
	 */
	ktab: any[];
	
	/**
	 * Table recording break points for blocks
	 */
	brtab: Record<number, number>;
	
	constructor(code: Uint8Array, ktab: any[]) {
		this.code = code;
		this.ktab = ktab;
		this.brtab = {};
		
		// Build the table
		
		let blocks : number[] = [];
		
		for(let i = 0; i < this.code.length; ++i) {
			let {op} = this.get(i), ip;
			
			switch(op) {
				case "block":
					this.brtab[i] = 0;
					blocks.push(i);
					break;
				
				case "loop":
					this.brtab[i] = i;
					blocks.push(0);
					break;
				
				case "if":
					this.brtab[i] = 0;
					blocks.push(0);
					break;
				
				case "else":
					ip = blocks.pop();
					if(ip === undefined) throw new Error("Unmatched else");
					this.brtab[ip] = i;
					blocks.push(i);
					break;
				
				case "end":
					ip = blocks.pop();
					if(ip === undefined) throw new Error("Unmatched end");
					if(ip) {
						this.brtab[ip] = i;
					}
					break;
			}
		}
	}
	
	get(ip: number): Bytecode {
		let x = ip, [op, len] = leb128(this.code, ip);
		let opn = OPNAME[op], imm = null;
		if(IMMOPS.includes(opn)) {
			let len2;
			[imm, len2] = leb128(this.code, ip + len);
			len += len2;
		}
		return new Bytecode(opn, imm, len);
	}
	
	call(...args: any[]): FrameResult {
		return new Frame(new Closure(this, []), args).exec();
	}
}

/**
 * Convert a number to a sequence of bytes encoded with leb128
 */
function* to_leb128(num: number) {
	const HI1 = 1<<7, LO7 = HI1 - 1;
	
	do {
		let b = num&LO7;
		num >>= 7;
		yield b | (num && HI1);
	} while(num);
}

const ASMRE =
	/^\$(\d+)$|^(0x[\da-f]+|\d+)$|^((?:\d*\.\d+|\d+\.\d*)(?:e[-+]?\d+)?)$/;
	
function assemble(src: string): Code {
	let bc = [], ktab = [];
	
	for(let word of src.replace(/;.+$/gm, "").split(/\s+/)) {
		if(OPS.includes(word)) {
			bc.push(...to_leb128(OPS.indexOf(word)));
			continue;
		}
		
		let m = ASMRE.exec(word);
		if(m) {
			if(m[1]) {
				bc.push(...to_leb128(parseInt(m[1])));
			}
			else if(m[2]) {
				ktab.push(parseInt(m[0]));
				bc.push(...to_leb128(ktab.length - 1));
			}
			else if(m[3]) {
				ktab.push(parseFloat(m[0]));
				bc.push(...to_leb128(ktab.length - 1));
			}
			else {
				throw new Error("Unknown regex match " + word);
			}
		}
		else {
			throw new Error("Unknown token " + word);
		}
	}
	
	return new Code(new Uint8Array(bc), ktab);
}

const SEXPR = new RegExp([
	"([()])",
	"(0x[\\da-f]+|\\d+)",
	"((?:\\d*\\.\\d+|\\d+\\.\\d*)(?:e[-+]?\\d+)?",
	"(\S+)"
].join('|'));
const SPACE = /\s+/gm;

function parse_sexpr(src: string): Code {
	SEXPR.lastIndex = 0;
	
	let level = 0, stack = [], sexpr = [], bc = [], ktab = [];
	for(;;) {
		SPACE.lastIndex = SEXPR.lastIndex;
		SPACE.exec(src);
		
		let m = SEXPR.exec(src);
		if(m !== null) throw new Error("Unknown " + src.substr(SEXPR.lastIndex));
		
		if(m[1]) {
			switch(m[0]) {
				case "(":
					++level;
					stack.push(sexpr);
					sexpr = [];
					break;
				
				case ")":
					--level;
					if(sexpr[0] in SIMPLE_OPS) {
						if(sexpr.length != 3) {
							throw new Error(`Too many arguments in (${sexpr.join(', ')})`);
						}
						
					}
					sexpr = stack.pop();
					break;
			}
		}
		else if(m[2]) {
			let x = parseInt(m[0]);
			sexpr.push(x);
			ktab.push(x);
			bc.push(OPS.indexOf("const"), x);
		}
		else if(m[3]) {
			let x = parseFloat(m[0]);
			sexpr.push(x);
			ktab.push(x);
			bc.push(OPS.indexOf("const"), x);
		}
		else if(m[4]) {
			
		}
		else {
			throw new Error("Unknown regex " + src.substr(SEXPR.lastIndex));
		}
	}
}

class Closure {
	constructor(public code: Code, public upvars: any[]) {}
}

if(typeof Array.prototype.at !== "function") {
	Array.prototype.at = function at(index: number) {
		if(index < 0) {
			index += this.length;
			if(index < 0) return;
		}
		return this[index];
	}
}

declare global {
	interface Array<T> {
		at(index: number): T;
	}
}

class BlockFrame extends Array {
	constructor(public target: number) {
		super();
	}
}

type FrameResultType = "return" | "yield" | "throw" | "await" | "exec";

class FrameResult {
	constructor(public type: FrameResultType, public value: any) {}
}

class Frame {
	stack: BlockFrame[];
	slots: any[];
	code: Closure;
	pc: number;
	
	constructor(code: Closure, args: any[] = []) {
		this.stack = [new BlockFrame(code.code.code.length)];
		this.slots = args;
		this.pc = 0;
		this.code = code;
	}
	
	next(): Bytecode {
		let bc = this.code.code.get(this.pc);
		console.log("next", this.pc, bc.size);
		this.pc += bc.size;
		return bc;
	}
	
	get top() { return this.stack.at(-1); }
	
	push(val: any) { this.top.push(val); }
	pop(x: number = 0) {
		if(x) {
			let v = [];
			while(x--) v.push(this.top.pop());
			return v;
		}
		return this.top.pop();
	}
	
	br(depth: number) {
		let pc, d = depth;
		do {
			let x = this.stack.pop();
			if(x === undefined) throw new Error("br to invalid depth " + d);
			pc = x.target;
		} while(depth--);
		this.pc = pc;
	}
	
	brlookup(ip: number): number {
		return this.code.code.brtab[ip];
	}
	
	enter() {
		this.stack.push(new BlockFrame(this.brlookup(this.pc)));
	}
	
	exit() {
		let val = this.pop();
		this.stack.pop();
		this.push(val);
	}
	
	oper(op: string, imm: number|null): any {
		if(op in SIMPLE_OPS) {
			return SIMPLE_OPS[op](this.pop(), this.pop());
		}
		else {
			switch(op) {
				case "unreachable": throw new Error("UNREACHABLE");
				case "nop": break;
				
				case "block":
				case "loop":
					this.enter();
					return;
				
				case "if":
					this.enter();
					if(!this.pop()) this.br(0);
					return;
				
				case "else":
					this.exit();
					this.pc = this.brlookup(this.pc);
					return;
				
				case "try": throw new NotImplemented("try block");
				
				case "end":
					this.exit();
					return;
				
				case "br":
					this.br(imm as number);
					return;
				
				case "br_if":
					if(this.pop()) this.br(0);
					return;
				
				case "drop":
					this.pop();
					return;
				
				case "select": {
					let [c, b, a] = this.pop(3);
					return c? b : a;
				}
				
				case "const":
					console.log("const", imm, "=", this.code.code.ktab[imm as number]);
					return this.code.code.ktab[imm as number];
				
				case "call": {
					let [fn, self, ...args] = this.pop(imm as number + 2);
					return fn.call(fn, self, args);
				}
				
				case "get": {
					let [ob, ...args] = this.pop(imm as number + 1);
					if(args.length === 1) {
						return ob[args[0]];
					}
					else {
						throw new NotImplemented("Array slicing")
					}
				}
				
				case "set": {
					let [ob, val, ...args] = this.pop(imm as number + 2);
					if(args.length === 1) {
						return ob[args[0]] = val;
					}
					else {
						throw new NotImplemented("Array slice assignment")
					}
				}
				
				case "delete": {
					let [ob, ...args] = this.pop(imm as number + 1);
					if(args.length === 1) {
						delete ob[args[0]];
						return;
					}
					else {
						throw new NotImplemented("Array slice deletion")
					}
				}
				
				case "none": return none;
				case "false": return false;
				case "true": return true;
				
				case "local.get":
					return this.slots[imm as number];
				case "local.set":
					this.slots[imm as number] = this.pop();
					return;
				
				case "upvar.get":
					return this.code.upvars[imm as number];
				case "upvar.set":
					this.code.upvars[imm as number] = this.pop();
					return;
			}
		}
	}
	
	step(): FrameResult {
		let {op, imm} = this.next();
		
		switch(op) {
			case "return":
			case "yield":
			case "throw":
			case "await":
				return new FrameResult(op, this.pop());
			
			default:
				let res = this.oper(op, imm);
				if(res !== undefined) {
					this.push(res);
				}
		}
		
		return new FrameResult("exec", undefined);
	}
	
	exec(): FrameResult {
		for(;;) {
			console.log(this.stack);
			let fr = this.step();
			if(fr.type !== "exec") return fr;
		}
	}
}

let code = assemble("const 3 const 4 + return");
console.log(code.code, code.ktab);
console.log(code.call());