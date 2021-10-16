#ifndef ESP_INTERP_H
#define ESP_INTERP_H

#include "value.h"

struct esp_CallFrame {
	struct esp_Function* func;
	struct esp_Value* vs;
	struct esp_Value* vstop;
	uint8_t* pc;
	struct esp_Value* vars;
	unsigned maxstack;
	unsigned nvars;

	struct esp_CallFrame* next;
};

/*
Reference types:
Eternal - no need for ref counting because it'll always exist
Escaped - created in a call frame, referenced externally
Returned - reference will be returned from the call frame
Variable - exists in call frame, no external references
Temporary - exists only in value stack
*/
struct esp_GC {
	
};

struct esp_Env {
	struct esp_CallFrame* cs;
};

struct esp_Value esp_exec(struct esp_Env* env);


#endif
