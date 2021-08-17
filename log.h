#ifndef ESP_DEBUG_HPP
#define ESP_DEBUG_HPP

#include <cstdio>

/**
 * Log levels
 *  0: No logging
 *  1: Error
 *  2: Warning
 *  3: Info
 *  4: Debug
 *  5: Trace
**/
#ifndef ESP_LOGLEVEL
	#define ESP_LOGLEVEL 5
#endif

// Disable logging for no-debug
#ifndef NDEBUG
	#define _ESP_S1(x) #x
	#define _ESP_S0(x) _ESP_S1(x)
	#define ESP_LOG(color, sigil, p, ...) \
		printf("\033[1;" #color "m" sigil \
			"\033[m(" __FILE__ ":" _ESP_S0(__LINE__) ") \033[0;" \
			#color "m " p "\033[m\n",##__VA_ARGS__)
#else
	#define ESP_LOG(...)
#endif

#if ESP_LOGLEVEL >= 5
	#define LOG_TRACE(...) ESP_LOG(32, "\033[7m[T]", __VA_ARGS__)
#else
	#define LOG_TRACE(...)
#endif

#if ESP_LOGLEVEL >= 4
	// Green
	#define LOG_DEBUG(...) ESP_LOG(32, "[D]", __VA_ARGS__)
#else
	#define LOG_DEBUG(...)
#endif

#if ESP_LOGLEVEL >= 3
	// Blue
	#define LOG_INFO(...) ESP_LOG(34, "[I]", __VA_ARGS__)
#else
	#define LOG_INFO(...)
#endif

#if ESP_LOGLEVEL >= 2
	// Yellow
	#define LOG_WARN(...) ESP_LOG(33, "[W]", __VA_ARGS__)
#else
	#define LOG_WARN(...)
#endif

#if ESP_LOGLEVEL >= 1
	#define LOG_ERROR(...) ESP_LOG(31, "[E]", __VA_ARGS__)
#else
	#define LOG_ERROR(...)
#endif

#endif
