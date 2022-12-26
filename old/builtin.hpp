#ifndef ESP_BUILTIN_HPP
#define ESP_BUILTIN_HPP

/// Warning: Mutual inclusion for "Value" dependency
#include "value.hpp"

#define X_arith(name) Value op_##name(Value lhs, Value rhs);
#define X_bool(name) X_arith(name)
#define X_bit(name) X_arith(name)
#define X_unary(name) Value op_##name(Value v);
#define X(name, mnem, op, type) X_##type(mnem)

#include "opcode.def"

#endif
