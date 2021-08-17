#ifndef ESP_OP_DEFS_HPP
#define ESP_OP_DEFS_HPP

/**
 * I [B C] or I [D]
 * I = 7 bit instruction + 1 bit addressing mode
 *  mode = 0 => Two 4 bit parameters
 *  mode = 1 => Two 8 bit parameters OR one 8 bit parameter, inplace on A
 * 
 * R[x] = Register top + x
 * K[x] = Constant table entry x
 * U[x] = Upval entry x
 * P[x] = Parameter entry x
 * 
 * A = Accumulator
 * B/C = Two 8-bit operands indexing the register file
 * D = Single 8 bit operand
 * ad = A if mode 0, D if mode 1
 * ba = B if mode 0, A if mode 1
 * cd = C if mode 0, D if mode 1
 * da = D if mode 0, A if mode 1 (opposite of a)
 * 
 * Registers refer to stack-local variables indexed from the bottom of the
 *  current stack frame
 * 
 * [caller registers] [caller state] [registers]
 *  bottom of stack frame -----------^
 * 
 * Caller state consists of the data required to restore the VM to executing
 *  the caller - argument vector, `this` value, PC, function object, etc
**/

/**
 * V(name, dis, result, param 0, param 1)
**/
#define OP_LIST(V) \
	V(NOP,    "nop",     0,   0,  0) \
	V(NONE,   "none",   AD,   0,  0) /* AD = none */ \
	V(FALSE,  "false",  AD,   0,  0) /* AD = false */ \
	V(TRUE,   "true",   AD,   0,  0) /* AD = true */ \
	V(LIST,   "[]",     AD,   0,  0) /* AD = [] */ \
	V(OBJECT, "{}",     AD,   0,  0) /* AD = {} */ \
	V(LOADK,  "",       BA,  CD,  0) /* BA = K[CD] */\
	V(LOADI,  "",        A, IMM,  0) /* A = IMM */ \
	V(ARG,    "arg",    BA,  CD,  0) /* BA = P[CD] */ \
	V(MOVE,   "move",  UNK,   0,  0) /* AB = DC */ \
	V(GETUP,  "getup", UNK,   0,  0) /* BA = U[CD] */ \
	V(SETUP,  "setup", UNK,   0,  0) /* U[BA] = CD */ \
	V(IDEQ,   "ideq",    A,  BA, CD) /* A = (BA === CD) */ \
	V(PROTO,  "proto",   A,  BA,  0) /* A = BA.proto */ \
	/* Overloadable operators */ \
	V(LOP,    "lop",     A,  BA, CD) \
	V(ROP,    "rop",     A,  BA, CD) \
	V(BOOL,   "bool",   AD,  DA,  0) \
	V(ADD,    "add",     A,  BA, CD) \
	V(SUB,    "sub",     A,  BA, CD) \
	V(MUL,    "mul",     A,  BA, CD) \
	V(DIV,    "div",     A,  BA, CD) \
	V(MOD,    "mod",     A,  BA, CD) \
	V(POW,    "pow",     A,  BA, CD) \
	V(IDIV,   "idiv",    A,  BA, CD) \
	V(INV,    "inv",    AD,  DA,  0) \
	V(AND,    "and",     A,  BA, CD) \
	V(OR,     "or",      A,  BA, CD) \
	V(XOR,    "xor",     A,  BA, CD) \
	V(LSH,    "lsh",     A,  BA, CD) \
	V(ASH,    "ash",     A,  BA, CD) \
	V(RSH,    "rsh",     A,  BA, CD) \
	V(CMP,    "cmp",     A,  BA, CD) \
	V(GT,     "gt",      A,  BA, CD) \
	V(GE,     "ge",      A,  BA, CD) \
	V(LT,     "lt",      A,  BA, CD) \
	V(LE,     "le",      A,  BA, CD) \
	V(EQ,     "eq",      A,  BA, CD) \
	V(NE,     "ne",      A,  BA, CD) \
	V(IS,     "is",      A,  BA, CD) \
	V(IN,     "in",      A,  BA, CD) \
	V(AS,     "as",      A,  BA, CD) \
	V(GET,    "get",   UNK,   0,  0) /* A = B[...B+C] */ \
	V(SET,    "set",   UNK,   0,  0) /* A[...B+C] = B */ \
	V(DEL,    "del",   UNK,   0,  0) /* A = delete B[...B+C] */ \
	V(NEW,    "new",   UNK,   0,  0) /* A = new B(...B+C) */ \
	V(CALL,   "call",  UNK,   0,  0) /* A = B(...B+C) */ \
	/* Control flow */ \
	V(TAIL,   "tail",  UNK,   0,  0) /* return B(...B+C) */ \
	V(RETURN, "return", AD,   0,  0) /* return AD */ \
	V(YIELD,  "yield",  AD,  DA,  0) /* AD = yield DA */ \
	V(AWAIT,  "await",  AD,  DA,  0) /* AD = await DA */ \
	V(THROW,  "throw",  AD,   0,  0) /* throw AD */ \
	V(ASSERT, "assert", AD,   0,  0) /* assert AD */
	

#define TEST(a, b, c, d, e) OP_##a,

typedef enum Op {
	OP_LIST(TEST)
	OP_LT, // A = R[ba] < R[cd]
	OP_LE, // A = R[ba] <= R[cd]
	OP_GT, // A = R[ba] > R[cd]
	OP_GE, // A = R[ba] >= R[cd]
	OP_EQ, // A = R[ba] == R[cd]
	OP_NE, // A = R[ba] != R[cd]
	
	
	OP_JT, // if(bool(A)) jmp D or BC
	OP_JF, // if(!bool(A)) jmp D or BC
	OP_JMP, // Unconditional jump D or BC
	
	// Prefix opcodes
	
	OP_LONG, // Next instruction uses 8-bit operands
	
	_OP_LAST
	
/////////////////////////////////////////////
	/*
	Builtins types:
	none bool int real char string bytes buffer tuple list object proto function
	opaque wrapped cfunction nfunction
	
	"" + myType()
	
	any = proto {
		<=>(lhs, rhs) {
			throw NotImplemented;
		}
		<(lhs, rhs) {
			return (lhs <=> rhs) < 0;
		}
		<=(lhs, rhs) {
			return (lhs <=> rhs) <= 0;
		}
		>(lhs, rhs) {
			return (lhs <=> rhs) > 0;
		}
		>=(lhs, rhs) {
			return (lhs <=> rhs) >= 0;
		}
		==(lhs, rhs) {
			return lhs === rhs or (lhs <=> rhs) == 0;
		}
		!=(lhs, rhs) {
			return !(lhs == rhs) or (lhs <=> rhs) != 0;
		}
		
		is(cls) {
			if(cls is none) return false;
			return proto === cls or proto is not none and proto is cls;
		}
		
		bool() {
			return true;
		}
		
		real() {
			return nan;
		}
		
		string() {
			return f"[any {proto.name}]";
		}
	}
	
	function any.+(lhs, rhs) {
		try {
			lhs->lhs.proto.+(lhs, rhs)
		}
		else {
			rhs->rhs.proto.+(lhs, rhs)
		}
	}
	
	function string.+(lhs, rhs) {
		if(this === lhs) {
			# Check for rhs specialization
			return try {
				rhs->rhs.proto.+(lhs, rhs)
			}
			else {
				scat(lhs, rhs.string())
			}
		}
		else {
			# rhs call implies lhs is not specialized
			return scat(lhs.string(), rhs);
		}
	}
	
	function real.+(lhs, rhs) {
		if(this === lhs) {
			switch(rhs.proto) {
				case bool:
				case int:
				case real:
				case char:
					return fadd(lhs, rhs.real());
				
				default:
					return NotImplemented;
			}
		}
		else {
			switch(lhs.proto) {
				case bool:
				case int:
				case real:
				case char:
					return fadd(lhs.real(), rhs);
			}
		}
	}
	
	method +(lhs: string, rhs: any) {
		try rhs.+(lhs, rhs) else scat(lhs, rhs.string())
	}
	method +(lhs: any, rhs: string) {
		scat(lhs.string(), rhs)
	}
	
	method +(lhs: real, rhs: any)
	
	Operators need to be dispatched by specificity - but this can't be based on prototype depth or something. Speaking ideally, rhs should only be called if it's expressly meant to overload the default behavior of lhs.
	
	string + real => no real.+(string, real), use default behavior
	real + string => string.+(real, string) is defined
	bool + real => bool.+(bool, real) is not defined, real.+(bool, real) is
		=> call bool.real() + real
	int + real => int.+(int, real) is defined, real.+(int, real) is defined
		=> int.real() and real.int() are both defined
		=> need some way to make real "win" without losing generality
	real + int => real.+(real, int) is defined, int.+(real, int)... defined?
		=> naively it should be defined. if it isn't, 
	
	This implementation always defers to RHS if RHS has an implementation
	So what is the difference from starting with RHS and then calling LHS?
	function int.+(lhs, rhs) {
		if(this === lhs) {
			try {
				return rhs->rhs.proto::+(lhs, rhs)
			}
			else {
				return iadd(lhs, rhs.int())
			}
		}
		else {
			switch(lhs.proto) {
				case bool:
				case int:
					return iadd(lhs.int(), rhs)
			}
			# Two scenarios:
			#  1. LHS has a default implementation but deferred to RHS in case it was more specialized
			#  2. LHS has no implementation and so RHS was called
			Generality is very important here, so we don't have to enumerate every LHS type which we *don't* support
		}
	}
	
	Simplest operator resolution: lhs operator always, deferral to rhs is lhs's responsibility
	 * Functionally equivalent to Lua and Python's lhs.__magic__ or rhs.__magic__ if we set any.__magic__ to defer to rhs
	
	function string.+(lhs, rhs) {
		if(this === lhs) {
			# Check for rhs specialization
			return try {
				rhs->rhs.proto::+(lhs, rhs)
			}
			else {
				scat(lhs, rhs.string())
			}
		}
		else {
			# rhs call implies lhs is not specialized
			return scat(lhs.string(), rhs);
		}
	}
	
	function real.+(lhs, rhs) {
		if(this === lhs) {
			when(rhs) {
				case is bool:
				case is int:
				case is real: {
					return fadd(lhs, rhs.real());
				}
			}
			switch(rhs.proto) {
				case bool:
				case int:
				case real:
					return fadd(lhs, rhs.real());
				
				default:
					return rhs->rhs.proto::+(lhs, rhs);
					(-> rhs (:: (. rhs proto) +) (lhs, rhs))
			}
		}
		else {
			switch(lhs.proto) {
				case bool:
				case int:
				case real:
					return fadd(lhs.real(), rhs);
				
				default:
					throw NotImplemented;
			}
		}
	}
	
	function int.+(lhs, rhs) {
		if(this === lhs) {
			switch(rhs.proto) {
				case bool:
				case int:
					return iadd(lhs, rhs.int());
				
				default:
					return rhs->rhs.proto::+(lhs, rhs);
			}
		}
		else {
			switch(lhs.proto) {
				case bool:
				case int:
					return iadd(lhs.int(), rhs);
				
				default:
					throw NotImplemented;
			}
		}
	}
	
	function bool.+(lhs, rhs) {
		if(this === lhs) {
			switch(rhs.proto) {
				case bool:
					return iadd(lhs, rhs.int());
				
				default:
					return rhs->rhs.proto::+(lhs, rhs);
			}
		}
		else {
			switch(lhs.proto) {
				case bool:
					return iadd(lhs.int(), rhs);
				
				default:
					throw NotImplemented;
			}
		}
	}
	
	ob has "test"
	
	*/
} Op;

#endif
