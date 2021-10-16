#include "buffer.h"

#include <string.h>

static void grow(esp_Buffer* buf) {
	assert(buf != NULL);
	
	uint32_t capacity = buf->capacity;
	if(buf->size + 1 >= capacity) {
		// 1.5x growth rate
		capacity += capacity/2 + 1;
		
		buf->data = espM_mutable_realloc(capacity);
		buf->capacity = capacity;
	}
}

void esp_Buffer_init(esp_Buffer* buf, uint32_t capacity) {
	assert(buf != NULL);
	
	buf->data = espM_mutable_alloc(capacity);
	buf->capacity = capacity;
	buf->size = 0;
}

void esp_Buffer_free(esp_Buffer* buf) {
	assert(buf != NULL);
	
	espM_mutable_free(buf->data);
	buf->data = NULL;
	buf->capacity = 0;
	buf->size = 0;
}

uint32_t esp_Buffer_push(esp_Buffer* buf, uint8_t d) {
	assert(buf != NULL);
	
	grow(buf);
	buf->data[buf->size++] = d;
	return buf->size;
}

int esp_Buffer_pop(esp_Buffer* buf) {
	assert(buf != NULL);
	
	if(buf->size == 0) return -1;

	return buf->data[--buf->size];
}

uint32_t esp_Buffer_unshift(esp_Buffer* buf, uint8_t d) {
	assert(buf != NULL);
	
	grow(buf);
	memmove(buf->data + 1, buf->data, 1);
	buf->data[0] = d;
	++buf->size;
}

int esp_Buffer_shift(esp_Buffer* buf) {
	assert(buf != NULL);
	
	memmove(buf->data, buf->data + 1, buf->size--);
}

void esp_Buffer_clear(esp_Buffer* buf) {
	assert(buf != NULL);
	
	buf->size = 0;
}

esp_String* esp_Buffer_decode_utf8(esp_Buffer* buf) {
	return espGC_new_string_sz(buf->data, buf->size);
}
