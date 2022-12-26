#include <stdbool.h>
#include <stdint.h>
#include <uchar.h>

struct esp_State {
	esp_GC* gc;
}

struct esp_tuple* esp_new_tuple();
struct esp_list* esp_new_list();
struct esp_object* esp_new_object();

bool esp_cast_bool(value_t v);
int esp_cast_int(value_t v);
double esp_cast_float(value_t v);
char32_t esp_cast_char(value_t v);
void* esp_cast_ptr(value_t v);
const char* esp_cast_cstring(value_t v);

value_t esp_add(value_t lhs, value_t rhs);
value_t esp_sub(value_t lhs, value_t rhs);
value_t esp_mul(value_t lhs, value_t rhs);
value_t esp_div(value_t lhs, value_t rhs);
value_t esp_mod(value_t lhs, value_t rhs);
value_t esp_pow(value_t lhs, value_t rhs);
value_t esp_idiv(value_t lhs, value_t rhs);
value_t esp_rem(value_t lhs, value_t rhs);

value_t esp_shl(value_t lhs, value_t rhs);
value_t esp_sl3(value_t lhs, value_t rhs);
value_t esp_shr(value_t lhs, value_t rhs);
value_t esp_sha(value_t lhs, value_t rhs);
value_t esp_rol(value_t lhs, value_t rhs);
value_t esp_ror(value_t lhs, value_t rhs);

value_t esp_not(value_t value);
value_t esp_inv(value_t value);
value_t esp_and(value_t lhs, value_t rhs);
value_t esp_ior(value_t lhs, value_t rhs);
value_t esp_xor(value_t lhs, value_t rh);

value_t esp_lt(value_t lhs, value_t rhs);
value_t esp_le(value_t lhs, value_t rhs);
value_t esp_gt(value_t lhs, value_t rhs);
value_t esp_ge(value_t lhs, value_t rhs);
value_t esp_eq(value_t lhs, value_t rhs);
value_t esp_ne(value_t lhs, value_t rhs);
value_t esp_ideq(value_t lhs, value_t rhs);
value_t esp_cmp(value_t lhs, value_t rhs);

value_t esp_in(value_t lhs, value_t rhs);
value_t esp_is(value_t lhs, value_t rhs);
value_t esp_as(value_t lhs, value_t rhs);
value_t esp_has(value_t lhs, value_t rhs);
value_t esp_call(value_t lhs, value_t rhs);

value_t esp_getattr(value_t self, value_t name);
value_t esp_setattr(value_t self, value_t name, value_t value);
value_t esp_delattr(value_t self, value_t name);
value_t esp_getitem(value_t self, value_t name);
value_t esp_setitem(value_t self, value_t name);
value_t esp_delitem(value_t self, value_t name);