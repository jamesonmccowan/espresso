#ifndef ESP_COMMON_H
#define ESP_COMMON_H

#include <cstdint>
#include <cassert>
#include <cuchar>

#if INTPTR_MAX == INT64_MAX
	#define ESP_BITS 64
#elif INTPTR_MAX == INT32_MAX
	#define ESP_BITS 32
#else
	#error "Unknown pointer size or missing size macros!"
#endif

#ifndef __cpp_char8_t
	#if __CHAR_BIT__ == 8
		using char8_t = char;
	#else
		using char8_t = uint8_t;
	#endif
#endif
#ifndef __USE_ISOCXX11
	using char32_t = uint32_t;
#endif

using hash_t = uint64_t;
using uint = unsigned int;

#include <bit>

#if !__has_builtin(__builtin_bit_cast)
// Definition copied from https://en.cppreference.com/w/cpp/numeric/bit_cast
template <class To, class From>
typename std::enable_if_t<
    sizeof(To) == sizeof(From) &&
    std::is_trivially_copyable_v<From> &&
    std::is_trivially_copyable_v<To>,
    To>
// constexpr support needs compiler magic
bit_cast(const From& src) noexcept
{
    static_assert(std::is_trivially_constructible_v<To>,
        "This implementation additionally requires destination type to be trivially constructible");
 
    To dst;
    std::memcpy(&dst, &src, sizeof(To));
    return dst;
}
#else
	using std::bit_cast;
#endif

#include "log.h"

#endif
