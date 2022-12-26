/**
 * @file macro.h
 * 
 * http://jhnet.co.uk/articles/cpp_magic
 * 
 * Collection of general-purpose macros
 */
#ifndef ESP_MACRO_H
#define ESP_MACRO_H

/**
 * Map a macro m to every subsequent value in the argument list
 */
#define MAP(m, x, ...) m(x) IF(HAS_ARGS(__VA_ARGS__))( \
	DEFER2(_MAP)()(m, __VA_ARGS__))( /* do nothing */ )
#define _MAP() MAP

/**
 * Evaluate m while the condition is true
 */
#define WHILE(cond, m, ...) IF(cond(__VA_ARGS__))( \
	OBSTRUCT(_WHILE)()(cond, m, m(__VA_ARGS__)), __VA_ARGS__)

/**
 * Evaluates to 0 if the argument list is empty, otherwise 1
 */
#define HAS_ARGS(...) BOOL(ARG1(_END_OF_ARGS_ __VA_ARGS__)())
#define _END_OF_ARGS_() 0

/**
 * WHEN(condition)(only when cond is true)
 */
#define WHEN(c) IF(c)(EVAL1, EMPTY)

/**
 * IF(condition)(then, else)
 */
#define IF(cond) _IF_(BOOL(cond))
#define _IF_(cond) _IF_##cond

#define _IF_0(t, ...) __VA_ARGS__
#define _IF_1(t, ...) t

/**
 * Boolean and operation
 */
#define AND(x, y) _AND_(BOOL(x), BOOL(y))
#define _AND_(x, y) _CAT_(_AND_, x)(y)
#define _AND_0(y) 0
#define _AND_1(y) y

/**
 * Boolean or operation
 */
#define OR(x, y) _OR_(BOOL(x), BOOL(y))
#define _OR_(x, y) _CAT_(_OR_, x)(y)
#define _OR_0(y) y
#define _OR_1(y) 0

#define BOOL(x) COMPL(NOT(x))

/**
 * 1 if x is 0 and 0 for any other token
 */
#define NOT(x) CHECK(NOT_ ## x)
#define NOT_0 PROBE()

/**
 * Inner logic which checks for the probe
 */
#define CHECK(...) ARG1(__VA_ARGS__, 0,)
#define PROBE() ~, 1

/**
 * Complement of 0 or 1
 */
#define COMPL(b) _CAT_(_COMPL_, b)
#define _COMPL_0 1
#define _COMPL_1 0

/**
 * Evaluates to 1 if x is a parenthesized expression, else 0
 */
#define IS_PAREN(x) CHECK(IS_PAREN_PROBE x)
#define IS_PAREN_PROBE(...) PROBE()

/**
 * Get the argument at a certain position
 */
#define ARG0(_0, ...) _0
#define ARG1(_0, _1, ...) _1
#define ARG2(_0, _1, _2, ...) _2
#define ARGN(n, ...) CAT(ARG, n)(__VA_ARG__)

/**
 * Concatenate tokens
 */
#define CAT(a, b) _CAT_(a, b)
#define CAT3(a, b, c) CAT(a, CAT(b, c))
#define _CAT_(a, b) a ## b

/**
 * Compare two identifier tokens. Note that one must be predefined as
 *  COMPARE_*** otherwise this is always 0
 */
#define _COMPARE_(x, y) IS_PAREN( \
	COMPARE_##x(COMPARE_##y)(()))
#define IS_COMPARABLE(x) IS_PAREN(CAT(COMPARE_, x)(()))
#define NOT_EQUAL(x, y) _IF_(_AND_(IS_COMPARABLE(x), IS_COMPARABLE(y)))( \
	PRIMITIVE_COMPARE, 1 EMPTY)(x, y)
#define EQUAL(x, y) COMPL(NOT_EQUAL(x, y))

#define COMMA() ,

#define OBSTRUCT(...) __VA_ARGS__ DEFER1(EMPTY)()
#define DEFER1(m) m EMPTY()
#define DEFER2(m) m EMPTY EMPTY()()
#define DEFER3(m) m EMPTY EMPTY EMPTY()()
#define DEFER4(m) m EMPTY EMPTY EMPTY EMPTY()()
#define EMPTY(...)

#define EVAL(...) EVAL1024(__VA_ARGS__)
#define EVAL1024(...) EVAL256(EVAL256(EVAL256(EVAL256(__VA_ARGS__))))
#define EVAL256(...) EVAL64(EVAL64(EVAL64(EVAL64(__VA_ARGS__))))
#define EVAL64(...) EVAL16(EVAL16(EVAL16(EVAL16(__VA_ARGS__))))
#define EVAL16(...) EVAL4(EVAL4(EVAL4(EVAL4(__VA_ARGS__))))
#define EVAL4(...) EVAL1(EVAL1(EVAL1(EVAL1(__VA_ARGS__))))
#define EVAL1(...) __VA_ARGS__
#define EXPAND(...) __VA_ARGS__

#endif
