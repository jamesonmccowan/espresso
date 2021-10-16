

/**
 * Keep track of what variables are visible to a particular lexical scope
 */
 export class LexicalScope {
	parent: LexicalScope|null;
	vars: string[];
	
	constructor(parent: LexicalScope|null) {
		this.parent = parent;
		this.vars = [];
	}
}

/**
 * Generic interface for something which resolves strings to values like a
 *  scope - only findScope needs to be implemented
 */
class IScopeLike {
	findScope(name: string): Record<string, any> {
		throw new NotImplemented();
	}
	
	get(name: string): any {
		return this.findScope(name)[name] ?? None;
	}
	
	set(name: string, value: any): any {
		return this.findScope(name)[name] = value;
	}
}

class IScope {
	get(name: string): any {
		throw new NotImplemented();
	}
	
	set(name: string, value: any): any {
		throw new NotImplemented();
	}
}

class Scope extends IScope {
	parent: Scope|null;
	own: Record<string, any>;
	
	constructor(parent: Scope|null) {
		super();
		this.parent = parent;
		this.own = {};
	}
	
	/**
	 * Find the first scope which has the name, or else null
	 */
	findOrNull(name: string): Record<string, any>|null {
		if(name in this.own) return this.own;
		if(this.parent === null) return null;
		return this.parent.findOrNull(name);
	}
	
	/**
	 * Find the best scope to reference a variable
	 */
	find(name: string): Record<string, any> {
		return this.findOrNull(name) ?? this.own;
	}
	
	get(name: string): any {
		let x = this.findOrNull(name);
		if(x === null) throw new Error("Undeclared variable " + name);
		return x[name];
	}
	
	set(name: string, value: any): any {
		return this.find(name)[name] = value;
	}
}

export class EspFunc {
	name: Expr;
	args: string[];
	block: Expr;
	
	constructor(name: Expr, args: string[], block: Expr) {
		this.name = name;
		this.args = args;
		this.block = block;
	}
}

/**
 * Class for the execution context of the interpreter
 */
class Context {
	//scope: Scope;
	callstack: IScope[];
	
	constructor() {
		this.callstack = [];
	}
	
	get(name: string): any {
		return this.callstack[this.callstack.length - 1].get(name);
	}
	
	set(name: string, value: any): any {
		return this.callstack[this.callstack.length - 1].set(name, value);
	}
}

/**
 * Base interface for evaluable expressions
 */
export class Expr {
	toString(): string {
		return "<EXPR>";
	}
	
	eval(ctx: Context): any {
		throw new NotImplemented();
	}
}

/**
 * Sequence of instructions without a scope of its own
 */
export class Group extends Expr {
	statements: Expr[];
	
	constructor(stmt: Expr[]) {
		super();
		this.statements = stmt;
	}
	
	toString(): string {
		return `(group ${this.statements.join(" ")})`;
	}
	
	eval(ctx: Context): any {
		let last = None;
		for(let s of this.statements) {
			last = s.eval(ctx);
		}
		
		return last;
	}
}

/**
 * Sequence of instructions which contain a scope
 */
export class Block extends Group {
	/**
	 * Variables are hoisted to the innermost containing block
	 */
	vars: string[];
	
	constructor(stmt: Expr[], vars: string[] = []) {
		super(stmt);
		this.vars = vars;
	}
	
	toString(): string {
		return `{[${this.vars.join(' ')}] ${this.statements.join(" ")}}`;
	}
	
	eval(ctx: Context): any {
		for(let v of this.vars) {
			ctx.set(v, None);
		}
		return super.eval(ctx);
	}
}

/**
 * Basic operation based on Lisp S-expressions
 */
export class Sexp extends Expr {
	op: string;
	args: Expr[];
	
	constructor(op: string, ...args: Expr[]) {
		super();
		this.op = op;
		this.args = args;
	}
	
	toString(): string {
		return `(${[this.op, ...this.args].join(' ')})`;
	}
	
	eval(ctx: Context): any {
		if(this.op in OPEXEC) {
			return OPEXEC[this.op].apply(
				ctx, this.args.map(v => v.eval(ctx))
			);
		}
		switch(this.op) {
			case "=": {
				let [lhs, rhs] = this.args;
				if(lhs instanceof Var) {
					return ctx.set(lhs.name, rhs.eval(ctx));
				}
				else {
					throw new Error("Assigning to non-variable " + lhs);
				}
			}
			
			case "if": {
				let [cond, th, el] = this.args;
				if(cond.eval(ctx)) {
					return th.eval(ctx);
				}
				else {
					return el.eval(ctx);
				}
			}
			
			// Not implemented: Using loops as generators
			case "while": {
				let [cond, bl, th, el] = this.args;
				for(;;) {
					if(cond.eval(ctx)) {
						try {
							bl.eval(ctx);
						}
						catch(e) {
							if(e === StopIteration) {
								el.eval(ctx);
								break;
							}
							throw e;
						}
					}
					else {
						th.eval(ctx);
						break;
					}
				}
				break;
			}
				
			default: throw new NotImplemented(this.op);
		}
	}
}

/**
 * Constant evaluates to native JS value
 */
export class Const extends Expr {
	proto: Proto;
	value: any;
	
	constructor(proto: Proto, value: any) {
		super();
		this.proto = proto;
		this.value = value;
	}
	
	toString(): string {
		return JSON.stringify(this.value);
	}
	
	eval(ctx: Context): string {
		return this.value;
	}
}

/**
 * Named variable
 */
export class Var extends Expr {
	name: string;
	
	constructor(name: string) {
		super();
		this.name = name;
	}
	
	toString(): string {
		return this.name;
	}
	
	eval(ctx: Context): any {
		return ctx.get(this.name);
	}
}

/**
 * A full program to contain execution, mostly so we don't need to
 *  bxport Context
 */
export class Prog extends Expr {
	expr: Expr;
	
	constructor(expr: Expr) {
		super();
		this.expr = expr;
	}
	
	toString(): string {
		return `Prog ${this.expr}`;
	}
	
	eval(ctx: Context|null = null): any {
		if(ctx === null) ctx = new Context();
		ctx.callstack.push(new Scope(null));
		return this.expr.eval(ctx);
	}
}