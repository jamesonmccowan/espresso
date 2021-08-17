#ifndef ESP_ZIO_HPP
#define ESP_ZIO_HPP

#include <cstdint>

#include "config"

#define ESPZ_EOF 0xFF
#define ESPZ_INVALID 0xFE
#define ESPZ_STARTER 0x7F

struct ZIO {
	virtual ~ZIO() = default;
	
	virtual size_t offset() = 0;
	virtual uint8_t getc() = 0;
	virtual bool eof() = 0;
};

#endif
