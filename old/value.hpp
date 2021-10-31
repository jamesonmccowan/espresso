#ifndef VALUE_H
#define VALUE_H

#include "common.h"
#include "gc.hpp"

#include <cstdint>
#include <cassert>

#include <bit>

#if INTPTR_MAX == INT64_MAX
	#define ESP_BITS 64
#elif INTPTR_MAX == INT32_MAX
	#define ESP_BITS 32
#else
	#error "Unknown pointer size or missing size macros!"
#endif

#define ESP_NONE 0
#define ESP_FALSE 1
#define ESP_EMPTY 2
#define ESP_TRUE 6

#ifndef __cpp_char8_t
	#if __CHAR_BIT__ == 8
		using char8_t = char;
	#else
		using char8_t = uint8_t;
	#endif
#endif
#ifndef __cpp_char32_t
	using char32_t = uint32_t;
#endif

using hash_t = uint64_t;

/**
 * Compressed pointer, calculated as a reference relative to the value's
 *  address.
**/
template<typename T, typename BASE=uint32_t, size_t ALIGN=sizeof(void*)>
struct CPtr {
private:
	BASE ptr;
	
	/**
	 * The alignment of the target of a compressed pointer, as a pointer to
	 *  a uint8_t array of the right number of bytes.
	**/
	typedef uint8_t (*align_t)[ALIGN];
public:
	CPtr(): ptr(0) {}
	CPtr(T* p) {
		*this = p;
	}
	
	operator const T*() const {
		return ptr? (const T*)(((align_t)&ptr) + ptr) : nullptr;
	}
	operator T*() {
		return ptr? (T*)(((align_t)&ptr) + ptr) : nullptr;
	}
	
	CPtr& operator=(T* p) {
		ptrdiff_t dif = p - &ptr;
		dif = dif < 0? -dif : dif;
		
		if(dif < (1L<<sizeof(BASE))) {
			ptr = p - &ptr;
		}
		else {
			ptr = gc.alloc_longptr(p) - &ptr;
		}
		return *this;
	}
};

struct Value32;
#if ESP_BITS == 64
struct Value64;
#endif

/**
 * Values in the heap are always 32 bits. On 64-bit platforms they use
 *  object-relative addressing (ie abs = &ptr + ptr) and are otherwise the
 *  same as 32-bit platform values.
 * 
 * xxx1 = smi
 * xx00 = GCObject* (NULL = none)
 * xx10 = 
 *   0010 = false (2)
 *   0110 = true (6)
 *   1010 = empty (10)
 *   1110 = char (14)
 *  10010 = intern
 *  10110 = symbol
**/
struct Value32 {
	uint32_t _value;
	
	template<typename T>
	constexpr bool is() const noexcept;
	
	template<typename T>
	constexpr T as() const;
	
#if ESP_BITS == 64
	inline operator Value64() const {
		
	}
#endif
};

template<>
constexpr bool Value32::is<bool>() const noexcept {
	return _value == ESP_TRUE || _value == ESP_FALSE;
}
template<>
constexpr bool Value32::as<bool>() const {
	assert(is<bool>());
	return _value&(ESP_TRUE^ESP_FALSE);
}

template<>
constexpr bool Value32::is<int32_t>() const noexcept {
	return _value&1;
}
template<>
constexpr int32_t Value32::as<int32_t>() const {	
	assert(is<int32_t>());
	// Divide by 2 to ensure sign extension
	return ((int32_t)_value)/2;
}

template<>
constexpr bool Value32::is<void*>() const noexcept {
	return !(_value&3);
}
template<>
constexpr void* Value32::as<void*>() const {
	#if ESP_BITS == 64
		// Word-aligned pointer relative to the heap address
		return ((uintptr_t*)&_value) + _value;
	#else
		return (void*)_value;
	#endif
}

#if __cplusplus <= 201703L
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

#if ESP_BITS == 64
/**
 * "Live" value type for on-stack manipulation which is as big as the
 *  platform's word. Unlike HeapValue, pointers use absolute addressing.
 *  On 32-bit platforms, this is just an alias for the HeapValue. On 64-bit
 *  platforms, a variant of NaN tagging is used to make good use of the
 *  available bits. Doubles are encoded by inverting their bits. Integers
 *  are signed inverted signalling NaNs with 52 bits of significant digits.
 *  Other values are encoded as unsigned inverted signalling NaNs. The high
 *  4 bits of the 52 bit payload is used as a type tag, the lower 48 bits
 *  are the actual value. This was chosen as it's enough to cover most
 *  in-practice addressing for pointers.
 * 
 * Inverting the bits of double was chosen because pointers have higher
 *  utility unencoded, and this way non-double is an easy boolean check of
 *  the 12 bits after the sign bit (signalling NaN would be all 1s, so
 *  inverted it's all 0s unless it's double)
 * 
 * Special values none, empty, false, and true have the same integer value
 *  as in HeapValue, which is achieved by taking advantage of the LS 3 bits
 *  which are normally 0 for alignment. The bit pattern of none was carefully
 *  chosen to be equivalent to NULL, which aids in quick checks.
 * 
 * Pointers are designed to have minimal overhead. Provided they're normal/
 *  native pointers, they can be dereferenced directly. Other pointer types
 *  are included for bare host pointers to avoid heap allocation.
 * 
 * The semantics of the different types is different interpretations of the 
 *  bits, so GC objects (which must contain their own metadata to enable
 *  walking the GC liveness graph) aren't enumerated.
 * 
 * Different heap arena types:
 *  - bytes table, simple bump allocator with no deallocations
 *  - arena managed by quipu
 *  - binary heap allocation to optimize realloc
 *  - big objects use malloc
 * 
 * Ok we actually have a good restriction for where type data can reside:
 *  HeapValue can't store type information for the most part, so we know
 *  for a fact that types unrepresented by it must have a presence in the
 *  GCObject header
 * 
 * For reference:
 * 
 * s xxxf ffff ffff ffff
 * 
 * union Value {
 *   uintptr_t base;
 *   
 *   struct ieee_binary64 { // bits inverted
 *     bool sign : 1;
 *     uint exp : 11;
 *     uint frac : 52;
 *   };
 *   
 *   struct int51 {
 *     bool sign : 1 = 1;
 *     uint head : 12 = 0; // MSB of frac must be zero to be a signaling NaN
 *     uint value : 51;
 *   };
 *   
 *   // 000 = simple/symbol/GCOject
 *       simple =
 *        000 none (NULL pointer, otherwise GCObject)
 *        001 empty
 *        010 false
 *        011 true
 *        100 char
 *        101 
 *        110 intern (rest of payload is the hash))
 *          interns can be made unique and guaranteed promoted from strings,
 *          thus their hashes are identities allowing equality testing without
 *          accessing the string from memory
 *        111 symbol (rest of payload is the unique id)
 * 
 *   // 001 = external
 *        000 = opaque
 *        001 = cstring
 *   // 010 = array
 *        000 = i8[]
 *        001 = i16[]
 *        010 = i32[]
 *        011 = i64[]
 *        100 = f32[]
 *        101 = f64[]
 *        110 = any[]
 *        111 = object[]
 *   // 010 = callable
 *        000 = CFunction
 *        001 = Bytecode
 *   // 011 = dict
 *   // 100 = 
 *   // 101 = 
 *   // 110 = 
 *   // 111 = 
 *   struct other {
 *     uint head : 13 = 0;
 *     uint tag : 3;
 *     byte payload[] : 48;
 *   };
 * };
**/
struct Value64 {
	uintptr_t _value;
	
	enum class Tag {
		SIMPLE = 0,
		CHAR,
		CSTRING,
		INTERN,
		RESERVED1,
		RESERVED2,
		EXTENSION,
		OPAQUE,
		
		NONE,
		EMPTY,
		FALSE,
		TRUE,
		FLOAT,
		INT,
		LONG,
		
	};

private:
	
	constexpr bool sign() const noexcept {
		return _value>>63;
	}
	
	constexpr int head() const noexcept {
		return (_value>>52)&0xfff;
	}
	
	constexpr int exponent() const noexcept {
		return head()&0x7ff;
	}
	
	constexpr int rawtag() const noexcept {
		return (_value>>48)&0xf;
	}
	
	constexpr uint64_t low52() const noexcept {
		return _value&((1<<52) - 1);
	}
	
	constexpr uint64_t low48() const noexcept {
		return _value&((1<<48) - 1);
	}

public:	
	constexpr Tag tag() const noexcept {
		// Float has non-zero exponent field
		if(exponent()) return Tag::FLOAT;
		// Integer is signed signaling NaN
		if(sign()) return Tag::INT;
		// Everything else is unsigned signaling NaN
		Tag t = static_cast<Tag>(rawtag());
		// Check simple values
		if(t == Tag::SIMPLE)
			return static_cast<Tag>((_value&7) + (int)Tag::NONE);
		return t;
	}
	
	template<typename T>
	constexpr bool is() const {}
	
	template<typename T>
	constexpr T as() const {}
	
	operator bool() const {
		switch(tag()) {
			case Tag::NONE:
			case Tag::EMPTY:
				return false;
			
			case Tag::BOOL:
				return _value == ESP_TRUE;
			
			case Tag::INT:
				return _value << 1;
			
			case Tag::FLOAT:
				return bit_cast<double>(~_value) == 0.0;
			
			case Tag::INTERN: // intern id 0 is the empty string
			case Tag::CHAR: // \0 char
				return _value>>3;
			
			// Non-interned string are always not-empty and so truthy
			case Tag::STRING:
			// 0 is always smi, so long is always truthy
			case Tag::LONG:
			// NULL pointers are none, not opaque
			case Tag::OPAQUE:
				return true;
			
			case Tag::DICT:
				return as<Dict>().length();
			
			case Tag::OBJECT:
				return as<Object>().to<bool>();
		}
	}
};

template<>
constexpr bool Value64::is<void>() const noexcept {
	return _value == ESP_NONE;
}
	
template<>
constexpr bool Value64::is<bool>() const noexcept {
	Tag t = tag();
	return t == Tag::TRUE || t == Tag::FALSE;
}
template<>
constexpr bool Value64::as<bool>() const {
	assert(is<bool>());
	return _value&(ESP_TRUE^ESP_FALSE);
}

template<>
constexpr bool Value64::is<int64_t>() const noexcept {
	return tag() == Tag::INT;
}
template<>
constexpr int64_t Value64::as<int64_t>() const {
	assert(is<int64_t>());
	// Sign extend
	return (low52()<<12)/(1<<12);
}

template<>
constexpr bool Value64::is<double>() const noexcept {
	return tag() == Tag::FLOAT;
}
template<>
constexpr bool Value64::is<float>() const noexcept {
	return is<double>();
}
template<>
constexpr double Value64::as<double>() const {
	assert(is<double>());
	return bit_cast<double>(~_value);
}

template<>
constexpr bool Value64::is<char32_t>() const noexcept {
	return tag() == Tag::CHAR;
}
template<>
constexpr char32_t Value64::as<char32_t>() const {
	assert(is<char32_t>());
	return (char32_t)(low48()>>16);
}

template<>
constexpr bool Value64::is<void*>() const noexcept {
	return !head() && !(_value&3);
}
template<>
constexpr void* Value64::as<void*>() const {
	assert(is<void*>());
	return (void*)_value;
}

template<>
constexpr bool Value64::is<GCObject*>() const noexcept {
	return false;
}

template<>
constexpr bool Value64::is<const char*>() const noexcept {
	return tag() == Tag::CSTRING;
}
template<>
constexpr const char* Value64::as<const char*>() const {
	assert(is<const char*>());
	return (const char*)as<void*>();
}

template<typename T>
using HeapPtr = CPtr<T>;
using LiveValue = Value64;
using HeapValue = Value32;

#else

template<typename T>
using HeapPtr<T> = T*;
using LiveValue = Value32;
using HeapValue = Value32;

#endif

using Value = LiveValue;
using CFunction = Value(*)(Value, int, Value(*)[]);

/**
 * Handle which keeps values alive while they're only referred to in native
 *  code. These are kept as a pool in the GC acting as roots for mark and
 *  sweep.
**/
struct Var : public Value {
	inline Var() {
		gc.register_root(this);
	}
	
	inline ~Var() {
		gc.remove_root(this);
	}
};

/**
 * https://www.python.org/dev/peps/pep-0412/
 * 
 * Key-Sharing Dictionary from Python used as an optimization for prototype
 *  instantiation property offsets. A prototype instantiation by default
 *  uses a shared dictionary for property metadata and offsets with copy-
 *  on-write semantics.
 * 
 * https://morepypy.blogspot.com/2015/01/faster-more-memory-efficient-and-more.html
 * 
 * Also using the implementation of PyPy, which splits the hash table and
 *  actual keys/values using offsets into a values array. This preserves
 *  entry ordering for free and simplifies iterator logic.
**/

struct Dict : public GCObject {
	struct Key {
		bool writable : 1; // Can the value change?
		bool removable : 1; // Property can be deleted?
		bool configurable : 1; // Can the property be configured?
		bool ispublic : 1; // Property is public? (private requires this.*)
		bool isoffset : 1; // Interpret value as an offset into slots?
		bool accessor : 1; // Property is an accessor
		
		HeapValue key;
	};
	
	struct KeyValue : public Key {
		HeapValue value;
	};
	
	/**
	 * DictEntry doesn't allocate values unless the shape is extended
	**/
	union Entry {
		Key key;
		KeyValue key_value;
	};
	
	struct HashIndex : public GCObject {
		uint16_t usable; // Number of usable entries (not sync'd with used)
		uint16_t used; // Number of used entries
		
		// Width of indices determined by used
		union {
			uint8_t index8[0];
			uint16_t index16[0];
			uint32_t index32[0];
			uint64_t index64[0];
		};
		
		template<typename V>
		void gc_visit(V& v) {}
	};
	
	bool ownproto : 1; // Proto is an extension of the object's own properties
	bool extended : 1; // Whether the dictionary stores values or offsets
	HeapValue proto;
	CPtr<HashIndex> index_map;
	CPtr<Entry> entry_table;
	
	template<typename V>
	void gc_visit(V& v) {
		v.visit(proto);
		v.visit(*keys);
	}
};

/**
 * Object represents structures not expected to change, with fields
 *  allocated at creation time. Extensions are still supported via the
 *  metadata hash table.
**/
struct Object : public GCObject {
	Dict* shape;
	Value slots[0];
	
	template<typename V>
	void gc_visit(V& v) {
		v.visit(*shape);
		for(int i = 0; i < nslots(); ++i) {
			v.visit(slots[i]);
		}
	}
};

/**
 * Proto represents objects which are expected to be prototyped, so the
 *  relevant prototyping fields are stored explicitly rather than in the
 *  metadata dictionary.
**/
struct Proto : public GCObject {
	DictKeys* proto; // Prototype shape
	Dict* shape; // Object shape
	Value slots[0];
};

struct DataPool {
	
};

#endif
