#include <math.h>

#include "interp.h"
#include "op-defs.h"
#include "common.h"
#include "convert.h"

static struct esp_Value bool_op(enum esp_Op op, struct esp_Value lhs, struct esp_Value rhs) {
	switch(op) {
		case ESP_ADD: return int_esp(lhs.val.b + rhs.val.b);
		case ESP_SUB: return int_esp(lhs.val.i - rhs.val.i);
		case ESP_MUL: return bool_esp(lhs.val.b && rhs.val.b);
		case ESP_POW: return 
		case ESP_DIV:
		case ESP_IDIV:
		case ESP_MOD:
		case ESP_IMOD:
		
		case ESP_BITAND:
		case ESP_BITOR:
		case ESP_LSH:
		case ESP_ASH:
		case ESP_RSH:
		case ESP_XOR:
		case ESP_INV:
		
		case ESP_AND:
		case ESP_OR:
		case ESP_NOT:
		case ESP_CMP:
		case ESP_HAS:
		case ESP_AS:
	}
}

static struct esp_Value _const(struct esp_CallFrame* frame, int idx) {
	return frame->values[idx];
}

static struct esp_Value _pop(struct esp_CallFrame* frame) {
	struct esp_Value v = frame->vs->value;
	struct esp_ValueFrame* vf = frame->vs;

	frame->vs = vf->next;
	free(vf);

	return v;
}

static void _push(struct esp_CallFrame* frame, struct esp_Value val) {
	struct esp_ValueFrame* vf = malloc(sizeof(struct esp_ValueFrame));
	vf->value = val;
	vf->next = frame->vs;
	frame->vs = vf;
}

#define EITHER(t) (frame->vs->value.type == ESP_##t || frame->vs->next->value.type == ESP_##t)
struct esp_Value esp_exec(struct esp_Env* env) {
	struct esp_CallFrame* frame = env->cs;

	for(;;) {
		switch(*frame->pc++) {
			case ESP_NOP: continue;
			case ESP_CONST:
				_push(frame, _const(frame, _pop(frame)));
				break;
			
			case ESP_LOAD:
				_push(frame, frame->vars[*frame->pc++]);
				break;
			case ESP_STORE:
				frame->vars[*frame->pc++] = _pop(frame);
				break;
			case ESP_LOADATTR:
			case ESP_STOREATTR:
			case ESP_GET:
			case ESP_SET:

			case ESP_AGG:

			case ESP_BOOL:
				_push(frame, esp_toBool(_pop(frame)));
				break;
			case ESP_INT:
				_push(frame, esp_toInt(_pop(frame));
				break;
			case ESP_REAL:
				_push(frame, esp_toReal(_pop(frame));
				break;
			case ESP_STRING:
				_push(frame, esp_toString(_pop(frame)));
				break;
			
			case ESP_BOOL_AND:
				_push(frame, bool_esp(_pop(frame).val.b && _pop(frame).val.b));
				break;
			case ESP_BOOL_OR:
				_push(frame, bool_esp(_pop(frame).val.b || _pop(frame).val.b));
				break;
			case ESP_BOOL_NOT:
				_push(frame, bool_esp(!_pop(frame).val.b));

			case ESP_ADD:
				struct esp_Value lhs = _pop(frame), rhs = _pop(frame);
				if(lhs.type == ESP_OBJECT) {
					if(esp_has(lhs, "+")) {
						return esp_method(lhs, lhs, rhs);
					}
				}
				if(rhs.type == ESP_OBJECT) {
					if(esp_has(rhs, "+")) {
						return esp_method(rhs, lhs, rhs);
					}
				}
				if(lhs.type == ESP_ARRAY) {
					if(rhs.type == ESP_ARRAY) {
						return esp_concatArray(lhs, rhs);
					}
				}
				if(lhs.type == ESP_STRING || rhs.type == ESP_STRING) {
					return esp_concatString(esp_toString(lhs), esp_toString(rhs));
				}
				if(lhs.type == ESP_REAL || rhs.type == ESP_REAL) {
					return real_esp(esp_real(lhs) + esp_real(rhs));
				}
				return int_esp(esp_int(lhs) + esp_int(rhs));
			case ESP_INC:
			case ESP_SUB:
			case ESP_DEC:
			case ESP_MUL:
			case ESP_POW:
			case ESP_DIV:
			case ESP_IDIV:
			case ESP_MOD:
			case ESP_IMOD:
			
			case ESP_BITAND:
			case ESP_BITOR:
			case ESP_LSH:
			case ESP_ASH:
			case ESP_RSH:
			case ESP_XOR:
			case ESP_INV:
			
			case ESP_AND:
			case ESP_OR:
			case ESP_NOT:
			case ESP_CMP:
			case ESP_HAS:
			case ESP_AS:
			
			case ESP_IF:
			case ESP_ELSE:
		}
	}
}