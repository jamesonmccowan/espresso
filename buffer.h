/**
 * Native methods of buffer types, these are wrapped to appear in script.
**/

#ifndef ESP_BUFFER_H
#define ESP_BUFFER_H

#include "value.hpp"
#include "config"

ESP_API void esp_Buffer_init(esp_Buffer* buf, uint32_t capacity);

ESP_API void esp_Buffer_free(esp_Buffer* buf);

ESP_API uint32_t esp_Buffer_push(esp_Buffer* buf, uint8_t d);

ESP_API int esp_Buffer_pop(esp_Buffer* buf);

ESP_API uint32_t esp_Buffer_unshift(esp_Buffer* buf, uint8_t d);

ESP_API int esp_Buffer_shift(esp_Buffer* buf);

ESP_API void esp_Buffer_clear(esp_Buffer* buf);

ESP_API esp_String* esp_Buffer_decode_utf8(esp_Buffer* buf);

#endif
