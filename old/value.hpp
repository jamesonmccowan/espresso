/**
 * @file value.hpp
 * 
 * Define the types and structures for dealing with values.
 */
#ifndef ESP_base_value_HPP
#define ESP_base_value_HPP

#include "common.h"
#include "gc.hpp"

#include <array>
#include <type_traits>
#include <memory>

struct Value32;

#if ESP_BITS == 64

struct Value64;
template<typename T> using HeapPtr = CPtr<T>;
using LiveValue = Value64;

#else

template<typename T> using HeapPtr<T> = T*;
using LiveValue = Value32;

#endif

using HeapValue = Value32;
using Value = LiveValue;

/// Warning: Mutual inclusion for "Value" dependency
///  (must be after Value type definition)
#include "builtin.hpp"

#define ESP_NONE (Value{})
#define ESP_FALSE (Value{false})
#define ESP_EMPTY (Value::raw(0b1010))
#define ESP_TRUE (Value{true})

#define FUNC(type, name, tags, impl) \
	type name(Value rhs) tags { return impl; }

#define ESP_OP(name) FUNC(Value, name, const, esp_##name(*this, rhs))
#define C_OP(name, op) FUNC(Value, operator op, const, name(rhs))
#define C_IOP(name, op) \
	FUNC(BaseValue<Child>&, operator op##=, , *this = name(rhs))
#define X_OP(name, op) ESP_OP(name) C_OP(name, op) C_IOP(name, op)
#define BOOL_OP(name, op) FUNC(bool, operator op, const, name(rhs))

/**
 * Base bag of methods which both value types inherit from to enable the same
 *  execution model to use different representations.
 */
template<typename Child>
struct BaseValue {
	X_OP(add, +) X_OP(sub, -) X_OP(mul, *) X_OP(div, /) X_OP(mod, %)
	ESP_OP(pow) ESP_OP(idiv) ESP_OP(mod2)
	
	X_OP(lsh, <<) X_OP(rhs, >>) ESP_OP(lsh3) ESP_OP(ash)
	X_OP(xor, ^) X_OP(band, &) X_OP(bor, |)
	
	Value inv() const { return esp_inv(*this); }
	Value operator~() const { return inv(); }
	bool operator!() const { return !(bool)*this; }
	
	BOOL_OP(gt, >) BOOL_OP(ge, >=) BOOL_OP(lt, <) BOOL_OP(le, <=)
	BOOL_OP(eq, ==) BOOL_OP(ne, !=)
	bool ideq(Value rhs) { return esp::op_ideq(*this, rhs); }
	bool idne(Value rhs) { return esp::op_idne(*this, rhs); }
	
	ESP_OP(in) ESP_OP(is) ESP_OP(as) ESP_OP(has)
	
	Value del(Value rhs) { return esp::op_del(*this, rhs); }
	
	class IndexLValue : public Child {
	private:
		Child& obj;
		Value key;
		
	public:
		Child& operator=(Value val) {
			esp::op_set(obj, key, val);
			return *this;
		}
		operator Value() const { return obj; }
	};
	
	IndexLValue operator[](Value v) {
		return {*this, v};
	}
	
	#undef FUNC
	#undef ESP_OP
	#undef C_OP
	#undef C_IOP
	#undef X_OP
	#undef BOOL_OP
};

/**
 * Values in the heap are always 32 bits. On 64-bit platforms they use
 *  object-relative addressing (ie abs = &ptr + ptr) and are otherwise the
 *  same as 32-bit platform values.
 * 
 * xxx1 = smi
 * xx00 = GCObject* (NULL = none)
 * xxx10 =
 *   0
 *    0010 = false (2)
 *    0110 = true (6)
 *    1010 = empty (10)
 *    1110 = char (14) (utf-32 encoding, only 21 bits used)
 *   1
 *    0010 = intern
 *    0110 = symbol
 *    1010 = cstring
 *    1110 = 
**/
struct Value32 : public BaseValue<Value32> {
protected:
	using value_t = uint32_t;
	value_t _base_value;
	
	static constexpr int
		none_bits = 0, true_bits = 0b0010, false_bits = 0b0110;

public:
	Value32(): _base_value(none_bits) {}
	Value32(GCObject* gco): _base_value(((size_t)gco)<<2) {}
	Value32(bool v): _base_value(v? true_bits : false_bits) {}
	
	Value32(int32_t v) {
		uint32_t uv = bit_cast<uint32_t>(v);
		_base_value = (uv < (1UL<<31))? (uv<<1)|1 : (uint32_t)&gc.alloc(v);
	}
	Value32(int64_t v) { _base_value = (value_t)&gc.alloc(v); }
	Value32(float v) { _base_value = (value_t)&gc.alloc(v); }
	Value32(double v) { _base_value = (value_t)&gc.alloc(v); }
	
	/**
	 * Convert a raw integer to a Value32
	 */
	static Value32 raw(value_t x) {
		Value32 v;
		v._base_value = x;
		return v;
	}
	
	value_t raw() const { return _base_value; }
	
	Value32& operator=(Value v) {
		_base_value = v.raw();
		return *this;
	}
	
	template<typename T>
	constexpr bool is() const noexcept;
	
	template<typename T>
	constexpr T as() const;
	
#if ESP_BITS == 64
	operator Value64() const;
#endif
};

template<>
constexpr bool Value32::is<bool>() const noexcept {
	return _base_value == true_bits || _base_value == true_bits;
}
template<>
constexpr bool Value32::as<bool>() const {
	assert(is<bool>());
	return _base_value&(true_bits^false_bits);
}

template<>
constexpr bool Value32::is<int32_t>() const noexcept {
	return _base_value&1;
}
template<>
constexpr int32_t Value32::as<int32_t>() const {	
	assert(is<int32_t>());
	// Divide by 2 to ensure sign extension
	return ((int32_t)_base_value)/2;
}

template<>
constexpr bool Value32::is<void*>() const noexcept {
	return !(_base_value&3);
}
template<>
constexpr void* Value32::as<void*>() const {
	#if ESP_BITS == 64
		// Word-aligned pointer relative to the heap address
		return ((uintcell_t*)this) + _base_value;
	#else
		return (void*)_base_value;
	#endif
}

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
struct Value64 : public BaseValue<Value64> {
protected:
	using value_t = uintptr_t;
	value_t _base_value;
	
	static constexpr int
		none_bits = 0, false_bits = 0b010, true_bits = 0b011;
	
public:
	enum class Tag {
		SIMPLE = 0,
		CHAR,
		CSTRING,
		INTERN,
		RESERVED1,
		RESERVED2,
		EXTENSION,
		OPAQUE,
		
		GCOBJECT,
		
		NONE,
		EMPTY,
		FALSE,
		TRUE,
		FLOAT,
		INT,
		LONG
		
	};
	
	Value64(): _base_value(none_bits) {}
	
	Value64(bool v): _base_value(v? true_bits : false_bits) {}
	
	Value64(int64_t v) {
		if(v < (1L<<52)) {
			// For integers, top 12 bits are filled
			_base_value = (((1L<<12) - 1)<<51) | v;
		}
		else {
			/// TODO
			_base_value = -1;
		}
	}
	Value64(double v) {
		_base_value = ~bit_cast<uint64_t>(v);
	}
	
	static Value64 raw(value_t x) {
		Value64 v;
		v._base_value = x;
		return v;
	}
	
	value_t raw() const { return _base_value; }
	
	Value64& operator=(Value v) {
		_base_value = v.raw();
		return *this;
	}
	
private:
	
	constexpr bool sign() const noexcept {
		return _base_value>>63;
	}
	
	constexpr int head() const noexcept {
		return (_base_value>>52)&0xfff;
	}
	
	constexpr int exponent() const noexcept {
		return head()&0x7ff;
	}
	
	constexpr int rawtag() const noexcept {
		return (_base_value>>48)&0xf;
	}
	
	constexpr uint64_t low52() const noexcept {
		return _base_value&((1<<52) - 1);
	}
	
	constexpr uint64_t low48() const noexcept {
		return _base_value&((1<<48) - 1);
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
			return static_cast<Tag>((_base_value&7) + (int)Tag::NONE);
		return t;
	}
	
	template<typename T>
	constexpr bool is() const { return false; }
	
	template<typename T>
	constexpr T as() const;
	
	operator bool() const {
		switch(tag()) {
			case Tag::NONE:
			case Tag::EMPTY:
				return false;
			
			case Tag::FALSE: return false;
			case Tag::TRUE: return true;
			
			case Tag::INT:
				return _base_value << 1;
			
			case Tag::FLOAT:
				return bit_cast<double>(~_base_value) != 0.0;
			
			case Tag::INTERN: // intern id 0 is the empty string
			case Tag::CHAR: // \0 char
				return _base_value>>3;
			
			// 0 is always smi, so long is always truthy
			case Tag::LONG:
			// NULL pointers are none, not opaque
			case Tag::OPAQUE:
				return true;
			
			case Tag::GCOBJECT:
				/// TODO: Doesn't respect operator overload
				return true;
				//return as<Object>().to<bool>();
		}
	}
};

template<>
constexpr bool Value64::is<void>() const noexcept {
	return _base_value == none_bits;
}
	
template<>
constexpr bool Value64::is<bool>() const noexcept {
	Tag t = tag();
	return t == Tag::TRUE || t == Tag::FALSE;
}
template<>
constexpr bool Value64::as<bool>() const {
	assert(is<bool>());
	return _base_value&(true_bits^false_bits);
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
	return bit_cast<double>(~_base_value);
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
	return !head() && !(_base_value&3);
}
template<>
constexpr void* Value64::as<void*>() const {
	assert(is<void*>());
	return (void*)_base_value;
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

#endif

constexpr auto x = Value64::pow;

#endif
