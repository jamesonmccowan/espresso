#ifndef ESP_LEX_H
#define ESP_LEX_H

#include <bitset>

#include "value.hpp"
#include "zio.hpp"

#ifndef ESP_INTERNAL
#error "Internal API"
#endif

/**
 * Lexically pre-sorted array of keywords. Keywords are tokens which follow
 * the same basic pattern as identifiers, but communicate special semantics.
 * 
 * Some keywords are contextual, but this enables further stages of the
 * parser to avoid unnecessary string comparisons.
**/
#define KEYWORD_LIST(V) \
	V(AND, "and", 5) \
	V(ASYNC, "async", 0) \
	V(AWAIT, "await", 0) \
	V(BREAK, "break", 0) \
	V(CASE, "case", 0) \
	V(CATCH, "catch", 0) \
	V(CONST, "const", 0) \
	V(CONTINUE, "continue", 0) \
	V(DEF, "def", 0) \
	V(DELETE, "delete", 0) \
	V(DO, "do", 0) \
	V(EACH, "each", 0) \
	V(ELSE, "else", 0) \
	V(ENUM, "enum", 0) \
	V(EXPORT, "export", 0) \
	V(FALSE, "false", 0) \
	V(FOR, "for", 0) \
	V(FUNCTION, "function", 0) \
	V(GET, "get", 0) \
	V(IF, "if", 0) \
	V(IMPORT, "import", 0) \
	V(IN, "in", 0) \
	V(INF, "inf", 0) \
	V(IS, "is", 6) \
	V(LOOP, "loop", 0) \
	V(MODULE, "module", 0) \
	V(NAN, "nan", 0) \
	V(NEW, "new", 0) \
	V(NONE, "none", 0) \
	V(NOT, "not", 0) \
	V(OR, "or", 4) \
	V(PROTO, "proto", 0) \
	V(REDO, "redo", 0) \
	V(RETURN, "return", 0) \
	V(SET, "set", 0) \
	V(STATIC, "static", 0) \
	V(SWITCH, "switch", 0) \
	V(THEN, "then", 0) \
	V(THIS, "this", 0) \
	V(THROW, "throw", 0) \
	V(TRUE, "true", 0) \
	V(TRY, "try", 0) \
	V(UNREACHABLE, "unreachable", 0) \
	V(VAR, "var", 0) \
	V(WHILE, "while", 0) \
	V(WITH, "with", 0) \
	V(YIELD, "yield", 0)

/**
 * Operators with assignment equivalents, sorted by precedence
 *   except add and sub, which must be at the end because they're
 *   also unary.
**/
#define BINARY_OP_LIST(T, E) \
	E(T, QUESTION, "?", 0) \
	E(T, NULLISH, "??", 3) \
	E(T, OR, "||", 4) \
	E(T, AND, "&&", 5) \
	E(T, BIT_OR, "|", 6) \
	E(T, BIT_XOR, "^", 7) \
	E(T, BIT_AND, "&", 8) \
	E(T, LSH, "<<", 11) \
	E(T, RSH, ">>", 11) \
	E(T, ASH, ">>>", 11) \
	E(T, STAR, "*", 13) \
	E(T, EXP, "**", 14) \
	E(T, DIV, "/", 13) \
	E(T, IDIV, "//", 13) \
	E(T, MOD, "%", 13) \
	E(T, IMOD, "%%", 13) \
	E(T, COLON, ":", 13) \
	/* Also unary so at the end */ \
	E(T, PLUS, "+", 12) \
	E(T, MINUS, "-", 12)

#define EXPAND_ASSIGN_TOKEN(T, name, str, prec) \
	T(ASSIGN_ ## name, str "=", 2)

#define EXPAND_BINOP_TOKEN(T, name, string, prec) \
	T(name, string, prec)

#define OPERATOR_LIST(T) \
	/* Property or call */ \
		/* Property */ \
			T(DOT, ".", 0) \
			T(POINT, "->", 0) \
			T(BIND, "::", 0) \
			T(LCURLY, "[", 0) \
		T(LPAREN, "(", 0) \
		T(LSQUARE, "{", 0) \
		T(PIPE, "|>", 0) \
		T(LBIND, "<:", 0) \
		T(RBIND, ":>", 0) \
	T(RCURLY, "]", 0) \
	T(RPAREN, ")", 0) \
	T(RSQUARE, "}", 0) \
	T(HAS, ".?", 0) \
	T(RANGE, "..", 0) \
	T(ELLIPSIS, "...", 0) \
	T(SEMICOLON, ";", 0) \
	/* Arrow or assignment */ \
		T(ARROW, "=>", 0) \
		/* Assignment op (isAssignmentOp() relies on this order) */ \
			T(ASSIGN, "=", 2) \
			BINARY_OP_LIST(T, EXPAND_ASSIGN_TOKEN) \
	/* Binary ops (sorted by precedence) */ \
		T(COMMA, ",", 1) \
		/* Also includes unary ops (isUnaryOp() relies on this order) */ \
			BINARY_OP_LIST(T, EXPAND_BINOP_TOKEN) \
	/* Unary ops continued */ \
		T(NOT, "!", 0) \
		T(BIT_NOT, "~", 0) \
		T(INC, "++", 0) \
		T(DEC, "--", 0) \
	/* Compare ops sorted by precedence \
	     (isCompareOp() relies on this order) */ \
		T(EQ, "==", 9) \
		T(ID_EQ, "===", 9) \
		T(NE, "!=", 9) \
		T(ID_NE, "!==", 9) \
		T(LT, "<", 10) \
		T(GT, ">", 10) \
		T(LE, "<=", 10) \
		T(GE, ">=", 10) \
		T(CMP, "<=>", 10)

enum TokenType {
#define TOKEN_DEF(x, ...) KW_ ## x,
	// Keep this at the start so the first is 0
	KEYWORD_LIST(TOKEN_DEF)
#undef TOKEN_DEF
#define TOKEN_DEF(x, ...) TK_ ## x,
	OPERATOR_LIST(TOKEN_DEF)
#undef TOKEN_DEF
	TK_INT, TK_REAL,
	TK_STRING, TK_IDENT,
	TK_COMMENT, TK_ERROR,
	
	_TK_COUNT
};

inline bool isUnary(TokenType tt) {
	return tt >= TK_PLUS && tt <= TK_DEC;
}

inline bool isBinary(TokenType tt) {
	return tt >= TK_NULLISH && tt <= TK_MINUS;
}

enum TokenFlag {
	// String flags
	TF_MLINE, TF_RAW, TF_BYTES, TF_FORMAT,
	// Number flags
	TF_IMAG, TF_BIGINT, TF_FLOAT
};

/**
 * Chunk of text which is recognized to be a single token
**/
struct Token {
	TokenType type;
	
	int line;
	int btc; // Bytes to column
	
	std::bitset<8> flags;
	
	union {
		bool multiline; // multiline comment?
		double rval;
		uint64_t ival;
		const char* msg;
		char inlmsg[4]; // Buffer for converting operators to strings
		String* str;
	};
	
	/**
	 * Convert a token to a string for use in error messages.
	**/
	const char* c_str() const;
	
	/**
	 * Convert a token type to a string for use in error messages.
	**/
	static const char* token_name(TokenType tt);
};

/**
 * Manages a stream of tokens.
**/
struct Lexer {
	ZIO* z;
	const char* error;
	
	/**
	 * Fill a token structure with the next token in the stream.
	**/
	bool lex(Token& tok);
};

#endif
