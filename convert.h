#ifndef ESP_CONVERT_H
#define ESP_CONVERT_H

#include "value.h"

inline _Bool esp_bool(struct esp_Value v) {
	switch(v.type) {
		case ESP_NIL: return false;
		case ESP_BOOL: return v.val.b;
		case ESP_INT: return v.val.i == 0;
		case ESP_REAL: return v.val.f == 0.0;
		case ESP_STRING:
		case ESP_LIST:
		case ESP_OBJECT:
		case ESP_FUNCTION:
			return true;
	}
}

inline int64_t esp_int(struct esp_Value v) {
	switch(v.type) {
		case ESP_NIL: return 0;
		case ESP_BOOL: return (int64_t)v.val.b;
		case ESP_INT: return v.val.i;
		case ESP_REAL: return (int64_t)v.val.f;
		case ESP_STRING:
		case ESP_LIST:
		case ESP_OBJECT:
		case ESP_FUNCTION:
			return 0;
	}
}

inline double esp_real(struct esp_Value v) {
	switch(v.type) {
		case ESP_NIL: return 0.0;
		case ESP_BOOL: return (double)v.val.b;
		case ESP_INT: return (double)v.val.i;
		case ESP_REAL: return v.val.f;
		case ESP_STRING: return strtod(v.val.str, NULL);
		case ESP_LIST:
		case ESP_OBJECT:
		case ESP_FUNCTION:
			return NAN;
	}
}

inline struct esp_Value bool_esp(_Bool b) {
	struct esp_Value v;
	v.type = ESP_BOOL;
	v.val.b = b;
	return v;
}

inline struct esp_Value int_esp(int64_t i) {
	struct esp_Value v;
	v.type = ESP_INT;
	v.val.i = i;
	return v;
}

inline struct esp_Value real_esp(double f) {
	struct esp_Value v;
	v.type = ESP_REAL;
	v.val.f = f;
	return v;
}

#endif
