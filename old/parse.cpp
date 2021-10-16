/**
 * Some algorithmic invariants: subparsers which operate based on a prefix
 *  expect that prefix token to already be consumed.
 * 
 * Also note: This code is written with the assumption that alloc<T>() will
 *  use zone allocation, to avoid unnecessary overhead from memory
 *  management. If zone allocation isn't used, alloc<T> should keep track of
 *  all of the memory it allocates and deallocate with the parser. The AST
 *  is an intermediate structure and won't be needed in later stages.
**/

#include <cctype>
#include <cmath>
#include <cstdio>

#define ESP_INTERNAL

#include "common.h"
#include "parse.hpp"
#include "lex.hpp"
#include "ast.hpp"

#define ERRBUFLEN 200

/**
 * Actual implementation of parsing.
**/
struct Parser {
	Lexer lex;
	Token comment;
	Token next;
	
	Parser() {
		LOG_DEBUG("Parser: init");
	}
	
	~Parser() {
		LOG_DEBUG("Parser: deinit");
	}
	
	void [[noreturn]] error(const char* f) {
		LOG_ERROR("Parser: error() = %s", f);
		throw;
	}
	
	template<typename... A>
	void [[noreturn]] error(const char* f, A... args) {
		LOG_ERROR("Parser: error() = %s")
		snprintf(errmsg, ERRBUFLEN, f, ...args);
		throw;
	}
	
	void [[noreturn]] unexpected() {
		error("Unexpected token %s", next.c_str());
	}
	
	/**
	 * Grab the next token.
	**/
	bool consume() {
		bool havetok = lex.lex(next);
		LOG_TRACE("Parser: Token %s", next.token_name());
		return havetok;
	}
	
	/**
	 * Consume the next token if it's the right type, return whether or not
	 *  a token was consumed.
	**/
	bool maybe(TokenType tt) {
		if(next.type == tt) {
			consume();
			return true;
		}
		return false;
	}
	
	/**
	 * Consume the next token if it's the right type - otherwise, error.
	**/
	void expect(TokenType tt) {
		if(next.type == tt) {
			consume();
		}
		else {
			error("%s expected, got %s",
				Token::token_name(tt), next.c_str()
			);
		}
	}
	
	/**
	 * Throw an error if the next token isn't the right type, but don't
	 *  consume it.
	**/
	void confirm(TokenType tt) {
		if(next.type != tt) expect(tt);
	}
	
	/**
	 * Return if the next token is the given token type without consuming it
	**/
	bool peek(TokenType tt) {
		return next.type == tt;
	}
	
	/**
	 * Keep allocation in one place so we can manage the memory as an arena
	 *  to deallocate all at once.
	**/
	template<typename T>
	T* alloc() { return new T(); }
	template<typename T, typename... A>
	T* alloc(A... args) { return new T(...args); }
	
	/**
	 * True if there's nothing left to parse
	**/
	bool eof() { return lex.z->eof(); }
	
	TokenType unop() {
		return isUnary(next.type)? next.type : TK_ERROR;
	}
	TokenType binop() {
		return isBinary(next.type)? next.type : TK_ERROR;
	}
	
	int unary_prec(TokenType op) { return 0; }
	int binary_prec(TokenType op) { return 0; }
	
	bool is_lassoc(TokenType op) { return true; }
	
	/**
	 * params = "(" [decl {"," decl}] ")"
	**/
	TupleLiteral* parse_params() {
		// Already parsed TK_LPAREN
		
		auto* tl = alloc<TupleLiteral>();
		
		if(maybe(TK_RPAREN)) return tl;
		
		do {
			bool rest = maybe(TK_ELLIPSIS);
			Expr* pe = parse_lvalue();
			pe->is_rest = rest;
			
			Expr* init = nullptr;
			
			if(!rest) {
				if(maybe(TK_ASSIGN)) {
					init = parse_expr();
				}
			}
			else if(peek(TK_COMMA)) {
				error("Rest parameter must be the last");
			}
			else {
				break;
			}
			
			if(init) {
				tl->push(alloc<BinaryOp>(TK_ASSIGN, pe, init));
			}
			else {
				tl->push(pe);
			}
		} while(maybe(TK_COMMA));
		
		expect(TK_RPAREN);
		
		return tl;
	}
	
	/**
	 * objentry = (ident | string | number | "[" expr "]") ":" expr | ident
	**/
	Expr* parse_objentry() {
		auto* prop = alloc<Property>();
		Expr* name;
		Expr* value;
		TokenType nt;
		bool access = false, getter = false;
		bool async = false, gen = false;
		
		// Switch statement builds up qualifiers, then breaks to common code
		//  which handles properties and methods. There's some redundant
		//  conditions at the end which could be fixed with gotos, but it should
		//  be optimized out.
		switch(nt = next.type) {
			// Rest or spread, depending on l/rvalue
			case TK_ELLIPSIS:
				return alloc<UnaryOp>(nt, parse_expr());
			
			case KW_ASYNC:
				consume();
				// Property named "async" / method named "async"
				if(peek(TK_COLON) || peek(TK_LPAREN)) {
					name = to_ident(nt);
					break;
				}
				async = true;
				// Async method
				if(!peek(TK_STAR)) {
					name = parse_ident();
					// Only method is legal
					confirm(TK_LPAREN);
					break;
				}
				[[fallthrough]];
				
			case TK_STAR:
				consume();
				// Property named "*"
				if(peek(TK_COLON)) {
					// async *: is illegal, can't have async properties
					if(async) unexpected();
					name = to_ident(nt);
				}
				// (Async?) method named "*"
				else if(peek(TK_LPAREN)) {
					name = to_ident(nt);
				}
				// (Async?) generator method
				else {
					gen = true;
					name = parse_ident();
				}
				break;
			
			case KW_GET:
			case KW_SET:
				consume();
				access = true;
				getter = (nt == KW_GET);
				// Property named "get"/"set" / method named "get"/"set"
				if(maybe(TK_COLON) || maybe(TK_LPAREN)) {
					name = to_ident(nt);
					break;
				}
				
				[[fallthrough]];
			
			case TK_IDENT:
			case TK_STRING:
			case TK_LSQUARE:
			// Keywords and operators with no special meaning
			default:
				name = parse_ident();
				break;
		}
		
		// Whether or not this is a property (vs a method)
		bool isp = true;
		
		if(maybe(TK_COLON)) {
			value = parse_expr();
		}
		else if(maybe(TK_LPAREN)) {
			auto* fl = alloc<FunctionLiteral>();
			fl->is_async = async;
			fl->is_generator = gen;
			fl->name = name;
			fl->params = parse_params();
			fl->body = parse_block();
			
			value = fl;
			isp = false;
		}
		// {x, y, z}
		else if(nt == TK_IDENT) {
			value = alloc<Identifier>(name);
		}
		else {
			unexpected();
		}
		
		auto* prop = alloc<Property>();
		prop->name = name;
		prop->value = value;
		prop->is_accessor = access;
		prop->is_getter = getter;
		
		if(isp && maybe(TK_ASSIGN)) {
			prop->init = parse_expr();
			
			// Default values aren't valid for rvalue object literals
			prop->is_rvalue = false;
		}
		
		return prop;
	}
	
	/**
	 * list = "[" [expr {"," expr}] "]"
	**/
	ListLiteral* parse_list() {
		auto* lit = alloc<ListLiteral>();
		
		do {
			while(maybe(TK_COMMA)) {
				lit->push(alloc<NoneExpr>());
			}
			lit->push(parse_expr());
		} while(!eof() && !maybe(TK_RSQUARE));
		
		return lit;
	}
	
	/**
	 * object = "{" [objentry {"," objentry}] "}"
	**/
	ObjectLiteral* parse_object() {
		auto* val = alloc<ObjectLiteral>();
		do {
			val->push(parse_objentry());
		} while(maybe(TK_COMMA));
		
		expect(TK_RCURLY);
		
		return val;
	}
	
	/**
	 * literal = "inf" | "nan" | "none" | int | real | str
	**/
	Expr* parse_atom()  {
		// We usually only need one of these
		union {
			Expr* ex;
			FunctionLiteral* fl;
			ControlExpr* ce;
			IfExpr* ie;
			LoopExpr* le;
			WhileExpr* we;
			ForExpr* fe;
			EachExpr* ee;
		};
		
		switch(next.type) {
			// Keyword values
			case KW_INF: ex = alloc<Literal>(INFINITY); break;
			case KW_NAN: ex = alloc<Literal>(NAN); break;
			case KW_NONE: ex = alloc<NoneExpr>(); break;
			case KW_FALSE: ex = alloc<Literal>(false); break;
			case KW_TRUE: ex = alloc<Literal>(true); break;
			case TK_INT: ex = alloc<Literal>((int64_t)next.ival); break;
			case TK_REAL: ex = alloc<Literal>(next.rval); break;
			case TK_STRING: ex = alloc<Literal>(next.str); break;
			
			case TK_PLUS: case TK_MINUS:
			case TK_BIT_NOT:
			case TK_NOT: case KW_NOT:
				ex = alloc<UnaryOp>(next.type, parse_atom());
				break;
			
			case TK_INC: case TK_DEC:
				ex = alloc<CountOp>(next.type, parse_atom(), true);
				break;
			
			case TK_IDENT:
				ex = parse_ident();
				if(maybe(TK_ARROW)) {
					goto ex_arrow;
				}
				break;
			
			case KW_THIS:
				ex = alloc<ThisExpr>();
				if(maybe(TK_ARROW)) {
					goto ex_arrow;
				}
				break;
			
			case TK_LPAREN:
				consume();
				if(maybe(TK_RPAREN)) {
					// () => ...
					if(maybe(TK_ARROW)) {
						ex = nullptr;
						goto ex_arrow;
					}
					// Empty tuple
					else {
						return alloc<TupleLiteral>();
					}
				}
				ex = parse_expr();
				if(maybe(TK_SEMICOLON)) {
					auto* b = alloc<Block>();
					b->push(ex);
					
					do {
						b->push(parse_expr());
					} while(maybe(TK_SEMICOLON));
					
					expect(TK_RPAREN);
					return b;
				}
				else if(maybe(TK_RPAREN)) {
					if(ex->isLValue()) {
						if(maybe(TK_ARROW)) {
						ex_arrow:
							auto* fl = alloc<FunctionLiteral>();
							fl->addParam(ex);
							fl->body = parse_block();
							fl->is_arrow = true;
							return fl;
						}
					}
					return ex;
				}
				else {
					unexpected();
				}
			
			case TK_LSQUARE:
				consume();
				ex = parse_list();
				expect(TK_RSQUARE);
				return ex;
			
			case TK_LCURLY:
				consume();
				ex = parse_object();
				expect(TK_RCURLY);
				return ex;
			
			case KW_FUNCTION:
				consume();
				fl = alloc<FunctionLiteral>();
				parse_params(*fl);
				fl->body = parse_block();
				return fl;
			
			case KW_IF:
				consume();
				ie = alloc<IfExpr>();
				ie->cond = parse_condition();
				ie->then = parse_block();
				
				goto finish_control;
			
			case KW_DO: {
				consume();
				ex = parse_block();
				
				if(maybe(KW_WHILE)) {
					auto* dwe = alloc<DoWhileExpr>();
					dwe->always = ex;
					dwe->cond = parse_condition();
					goto finish_loop;
				}
				else {
					return alloc<DoBlock>(ex);
				}
			}
			
			case KW_WHILE:
				consume();
				we = alloc<WhileExpr>();
				we->cond = parse_condition();
				
				goto finish_loop;
			
			case KW_FOR:
				consume();
				fe = alloc<ForExpr>();
				
				expect(TK_LPAREN);
				
				if(!maybe(TK_SEMICOLON)) {
					fe->init = parse_expr();
					expect(TK_SEMICOLON);
				}
				if(!maybe(TK_SEMICOLON)) {
					fe->cond = parse_expr();
					expect(TK_SEMICOLON);
				}
				
				if(!maybe(TK_RPAREN)) {
					fe->iter = parse_expr();
					expect(TK_RPAREN);
				}
				
				goto finish_loop;
			
			case KW_EACH:
				consume();
				ee = alloc<EachExpr>();
				
				expect(TK_LPAREN);
				
				switch(next.type) {
					case KW_VAR:
						consume();
						ee->decl = parse_lvalue();
						break;
					case KW_CONST:
						consume();
						ee->is_declaration = true;
						ee->decl = parse_decl(KW_CONST);
						break;
					
					default:
						ee->is_decl = false;
						ee->ident = parse_ident();
						break;
				}
				
				expect(KW_IN);
				
				ee->iter = parse_expr();
				
				expect(TK_RPAREN);
			
			finish_loop:
				le->body = parse_block();
				if(maybe(KW_THEN)) {
					le->then = parse_block();
				}
			finish_control:
				if(maybe(KW_ELSE)) {
					ce->_else = parse_block();
				}
				
				return ex;
		}
		
		// Literals and unop expressions
		consume();
		
		return ex;
	}
	
	/**
	 * Next item is containing a "block" - if there are no braces, it's a
	 *  statement. This is the only time an open bracket doesn't indicate
	 *  an object constructor.
	**/
	Block* parse_block() {
		if(!maybe(TK_LCURLY)) return parse_statement();
		
		Block* block = alloc<Block>();
		
		do {
			block->push(parse_statement());
		} while(!maybe(TK_RCURLY));
		
		return block;
	}
	
	/**
	 * statement = expr
	**/
	Statement* parse_statement() {
		if(maybe(TK_SEMICOLON)) {
			return alloc<NoneExpr>();
		}
		
		bool mut;
		
		switch(next.type) {
			// Variable declarations are statement-only
			case KW_VAR:
				mut = true;
				goto parse_decl;
			
			case KW_CONST:
				mut = false;
			
			parse_decl: {
				Block* block = alloc<Block>();
				consume();
				// Add each declaration as if it was declared alone
				do {
					block->push(parse_decl(mut));
				} while(maybe(TK_COMMA));
				
				return block;
			}
			
			default:
				return parse_expr();
		}
	}
	
	/**
	 * Subexpression within a given precedence (for precedence climbing)
	**/
	Expr* parse_subexpr(int prec) {
		Expr* lhs = parse_atom();
		
		// Apply suffixes
		for(;;) {
			switch(next.type) {
				case TK_INC: case TK_DEC:
					lhs = alloc<CountOp>(next.type, lhs, false);
					consume();
					continue;
			}
			
			break;
		}
		
		// Apply binary operators
		TokenType op = binop();
		while(op != TK_ERROR && binary_prec(op) >= prec) {
			int q = binary_prec(op) + is_lassoc(op);
			consume();
			lhs = alloc<BinaryOp>(op, lhs, parse_subexpr(q));
		}
		
		return lhs;
	}
	
	/**
	 * Utility to begin parsing an expression with no prior precedence
	**/
	Expr* parse_expr() { return parse_subexpr(0); }
	
	/**
	 * ident?
	**/
	Identifier* parse_ident() {
		peek(TK_IDENT);
		
		auto* id = alloc<Identifier>(next.str);
		consume();
		
		return id;
	}
	
	FunctionLiteral* parse_method();
	
	/**
	 * Shortcut for parsing a condition (expression surrounded by parentheses).
	 *  This is unconditionally parsed after a control structure, so it must
	 *  consume the first token itself.
	 * 
	 * condition = "(" expr ")"
	**/
	Expr* parse_condition() {
		expect(TK_LPAREN);
		Expr* ex = parse_expr();
		expect(TK_RPAREN);
		return ex;
	}
	
	Identifier* to_ident(TokenType tt) {
		return alloc<Identifier>(Token::token_name(tt));
	}
	
	/**
	 * Lvalues are values which can appear on the left hand side of an
	 *  assignment. This includes both identifiers and destructors - in
	 *  that case it's a complex recursively defined property, so it's
	 *  easiest to just parse it like a normal value while keeping track
	 *  of whether or not it's still qualified to be an lvalue.
	**/
	Expr* parse_lvalue() {
		Expr* ex = parse_atom();
		if(!ex->is_lvalue) {
			error("Invalid lvalue");
		}
		return ex;
	}
};

esp_Value esp_parse(const char* src) {
	Parser p;
	
	//init_lexer(&p.lex);
	
	ASTNode root;
	
	if(setjmp(p.on_error)) {
		node_free(&root);
		return ERROR();
	}
	else {
		return Parser::expr(&p, &root);
	}
}