#ifndef ESP_AST_HPP
#define ESP_AST_HPP

#include <vector>

/**
 * ASTNode
 *   Expr
 *     Literal
 *     Container
 *       ListLiteral
 *       ObjectLiteral
 *       ProtoLiteral
 *     UnaryOp
 *     BinaryOp
 *     FunctionLiteral
 * 
 *   Property
 *     ObjectLiteralProperty (const, computed, getter, setter, spread)
 * 
 *   Statement
 *     Declaration
 *     JumpStatement
 *       BreakStatement
 *       ContinueStatement
**/

struct ASTNode;
	struct Statement;
		struct Declaration;
		struct Expr;
			struct Block;
			struct NoneExpr;
			struct BoolExpr;
			struct ControlExpr;
				struct IfExpr;
				struct LoopExpr;
					struct WhileExpr;
						struct DoWhileExpr;
					struct ForExpr;
					struct EachExpr;
			struct TryExpr;
			struct Identifier;
			struct Rest;
			struct Literal;
			struct UnaryOp;
				struct CountOp;
			struct BinaryOp;
			struct AggregateLiteral;
				struct TupleLiteral;
				struct ListLiteral;
				struct ObjectLiteral;
	struct Property;

template<typename T>
using ZoneList = std::vector<T>;

struct ASTNode {
	bool is_lvalue;
	bool is_rvalue;
	bool is_computed;
	
	enum Type {
		NONE, FALSE, TRUE
	} _type;
};

/**
 * Statements are anything that can appear in a statement list
**/
struct Statement : public ASTNode {
};

/**
 * ("var" | "const") (identifier | destructure) ["=" expr]
**/
struct Declaration : public Statement {
	bool is_mutable;
	bool is_declaration; // Whether or not var or const was used
	
	enum Which {
		IDENT, LSDES, OBDES
	} which;
	union {
		Identifier* ident;
		ListLiteral* listdes;
		ObjectLiteral* objdes;
	};
	
	Expr* init;
};

/**
 * Most nodes are expressions, the only ones that aren't MUST appear in a
 *  statement list and nowhere else.
**/
struct Expr : public Statement {
	bool is_rest;
	bool is_computed;
	
	/**
	 * Used to propagate information about whether or not a list/object
	 *  construction is a valid destructuring target.
	**/
	virtual bool isLValue() const { return false; }
	
	/**
	 * Used to detect invalid usages of rest parameters
	**/
	virtual bool isRest() const { return false; }
	
	/**
	 * Expression is allowed as the argument list of an arrow function
	**/
	virtual bool isArrowHead() const { return false; }
};

struct Block : public Expr {
	ZoneList<Statement*> elems;
	
	void push(Statement* s) {
		elems.push_back(s);
	}
};

struct DoBlock : public Expr {
	// Not necessarily a block, could just be a normal expression
	Expr* body;
};

using NoneExpr = Expr;
using ThisExpr = Expr;

struct BoolExpr : public Expr {
	bool value() { return _type == TRUE; }
};

struct ControlExpr : public Expr {
	Expr* then;
	Expr* _else;
};

struct IfExpr : public ControlExpr {
	Expr* cond;
};

struct LoopExpr : public ControlExpr {
	Expr* body;
};

struct WhileExpr : public LoopExpr {
	Expr* cond;
};

struct DoWhileExpr : public WhileExpr {
	Expr* always;
};

struct ForExpr : public LoopExpr {
	Expr* init;
	Expr* cond;
	Expr* iter;
};

struct EachExpr : public LoopExpr {
	union {
		Declaration* decl;
		Identifier* ident;
	};
	
	Expr* iter;
};

struct TryExpr : public Expr {
	Expr* expr;
	Expr* _else;
};

struct Identifier : public Expr {
	String* str;
	
	explicit Identifier(String* s): str(s) {}
	
	virtual bool isLValue() const { return true; }
	virtual bool isArrowHead() const { return true; }
};

struct Literal : public Expr {
	union {
		int ival;
		double rval;
		String* str;
	};
	
	enum Type {
		INT, REAL, STR
	} _type;
	
	explicit Literal(int64_t v): _type(INT), ival(v) {}
	explicit Literal(double v): _type(REAL), rval(v) {}
	explicit Literal(String* v): _type(STR), str(v) {}
};

struct FunctionLiteral : public Expr {
	bool is_async;
	bool is_generator;
	bool is_arrow;
	
	Expr* name;
	Expr* params;
	Expr* body;
};

struct UnaryOp : public Expr {
	TokenType op;
	Expr* expr;
	
	virtual bool isRest() const {
		return op == TK_ELLIPSIS;
	}
	
	UnaryOp(TokenType op, Expr* ex): op(op), expr(ex) {}
};

struct CountOp : public UnaryOp {
	bool is_prefix;
	
	CountOp(TokenType op, Expr* ex, bool p):
		UnaryOp(op, ex), is_prefix(p) {}
	
	bool isPrefix() const { return is_prefix; }
	bool isSuffix() const { return !is_prefix; }
};

struct BinaryOp : public Expr {
	TokenType op;
	Expr* lhs;
	Expr* rhs;
	
	BinaryOp(TokenType op, Expr* lhs, Expr* rhs):
		op(op), lhs(lhs), rhs(rhs) {}
};

struct Property : public Expr {
	bool is_accessor;
	bool is_getter;
	
	Expr* name;
	Expr* value;
	Expr* init;
};

struct AggregateLiteral : public Expr {
	bool has_rest;
	ZoneList<Expr*> elems;
	
	void push(Expr* ex) {
		elems.push_back(ex);
		
		if(ex->isRest()) {
			// Multiple rests can't appear in a destructuring
			if(has_rest) {
				is_lvalue = false;
			}
			else {
				has_rest = true;
			}
		}
		// lvalue must be recursively valid
		else if(!ex->is_lvalue) {
			is_lvalue = false;
		}
		// rvalue must be recursivelyTFCZAQ2WQ ``
		else if(!ex->is_rvalue) {
			is_rvalue = false;
		}
	}
};

struct TupleLiteral : public AggregateLiteral {
};

struct ObjectLiteral : public AggregateLiteral {
	
};

struct ListLiteral : public AggregateLiteral {
};

#endif