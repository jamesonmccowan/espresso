#ifndef VALUE_H
#define VALUE_H

#include "common.h"
#include "gc.hpp"

#include <cstdint>
#include <cassert>

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
		typedef char char8_t;
	#else
		typedef uint8_t char8_t;
	#endif
#endif

typedef uint64_t hash_t;
typedef Value(*CFunction)(Value, int, Value*);

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

/**
 * Values in the heap are always 32 bits. On 64-bit platforms they use
 *  object-relative addressing (ie abs = &ptr + ptr) and are otherwise the
 *  same as 32-bit platform values.
 * 
 * xxx1 = smi
 * xx00 = GCObject*
 * xx10 = 
 *   0010 = false (2)
 *   0110 = true (6)
 *   1010 = empty (10)
 *   1110 = string (14)
**/
struct HeapValue {
	uint32_t _value;
	
	inline Value proto() const {
		if(_value&1) {
			return proto_int;
		}
		if(_value&2) {
			return proto_bool;
		}
		
		return asGCO()->proto();
	}
	
	inline bool isNone() const noexcept {
		return _value == ESP_NONE;
	}
	inline bool isEmpty() const noexcept {
		return _value == ESP_EMPTY;
	}
	
	inline operator bool() const noexcept {
		return isBool()? asBool() : proto()->callMethod("bool");
	}
	
	inline bool isBool() const {
		return _value == ESP_TRUE || _value == ESP_FALSE;
	}
	inline bool asBool() const {
		return _value&(ESP_TRUE^ESP_FALSE);
	}
	
	inline bool isInt() const {
		return _value&1;
	}
	inline int64_t asInt() const {
		return ((int32_t)_value)>>1;
	}
	
	inline bool isReal() const {
		return false;
	}
	inline double asReal() const {
		return NAN;
	}
	
	//CONVERSION(Opaque);

	inline bool isPtr() const {
		return !(_value&3);
	}
	
	inline void* asPtr() {
	#if ESP_BITS == 64
		// Word-aligned pointer relative to the heap address
		return ((uintptr_t*)&_value) + _value;
	#else
		return (void*)_value;
	#endif
	}
	
	inline GCObject* asGCO() {
		return (GCObject*)asPtr();
	}
};

#if ESP_BITS == 64
/**
 * "Live" value type for on-stack manipulation which is as big as the
 *  platform's word. Unlike HeapValue, pointers use absolute addressing.
 *  On 32-bit platforms, this is just an alias for the HeapValue. On 64-bit
 *  platforms, a variant of NaN tagging is used to make good use of the
 *  available bits. Doubles are encoded by inverting their bits. Integers
 *  are signed inverted signalling NaNs with 51 bits of significant digits.
 *  Other values are encoded as unsigned inverted signalling NaNs. The high
 *  3 bits of the 51 bit payload is used as a type tag, the lower 48 bits
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
 * For reference:
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
 *     uint head : 12 = 0;
 *     uint value : 51;
 *   };
 *   
 *   // 000 = simple/object
 *   // 001 = char
 *   // 010 = cstring
 *   // 011 = smallstr
 *   // 100 = 
 *   // 101 = 
 *   // 110 = extension
 *   // 111 = opaque
 *   struct other {
 *     uint head : 13 = 0;
 *     uint tag : 3;
 *     union {
 *       none = 0;
 *       empty = 10;
 *       false = 2;
 *       true = 6;
 *       
 *       GCObject* gco;
 *       const char* cstr; // NULL = empty string
 *       char32_t codepoint;
 *       char smallstr[6];
 *       void* opaque;
 *       Value(*extension)(Value, int, Value*);
 *     } payload : 48;
 *   };
 * };
**/
struct Value {
	uintptr_t _value;
	
	inline Value proto() const {
		if(isReal()) return real_proto;
		if(isInt()) return int_proto;
		if(isBool()) return bool_proto;
		if(_value == ESP_NONE || _value == ESP_EMPTY) return ESP_NONE;
		if(_value&1) {
			return proto_int;
		}
		if(_value&2) {
			return proto_bool;
		}
		
		return asGCO()->proto();
	}
	
	inline bool isNone() const noexcept {
		return _value == ESP_NONE;
	}
	inline bool isEmpty() const noexcept {
		return _value == ESP_EMPTY;
	}
	
	inline operator bool() const noexcept {
		return isBool()? asBool() : proto()->callMethod("bool");
	}
	
	inline bool isBool() const {
		return _value == ESP_TRUE || _value == ESP_FALSE;
	}
	inline bool asBool() const {
		return _value&(ESP_TRUE^ESP_FALSE);
	}
	
	inline bool isInt() const {
		// Sign=1, Exp=0, Frac MSB=0 (signed inverted signaling NaN)
		constexpr uint64_t ipre = 0x8008<<48, mask = 0xfff8<<48;
		return (_value&mask) == ipre;
	}
	inline int64_t asInt() const {
		return ((int64_t)((_value&((1<<51) - 1))<<13))>>13;
	}
	
	inline bool isReal() const {
		// NaN boxing is done by encoding the double bit inverted, and non-
		//  double values have Exp=0 and Frac MSB=0 representing an
		//  (inverted) signalling NaN. Sign bit not included in check
		return !(_value&(0xfffL<<51));
	}
	inline double asReal() const {
		union { uint64_t i; double f; };
		i = ~_value;
		return f;
	}

	inline bool isPtr() const {
		return !(_value&3);
	}
	
	inline void* asPtr() {
		return (void*)_value;
	}
	
	inline GCObject* asGCO() {
		return (GCObject*)asPtr();
	}
};
#else
// Live values are the same as heap values on 32-bit platforms
using Value = HeapValue
#endif

/**
 * CRTP template for commonly reused methods.
 * 
 * Some accessor methods are defined with prefixes "is", "as", and "to".
 *  Respectively, these test the type, cast it while assuming the type is
 *  correct, and attempt to convert to the type.
**/
template<typename T>
struct Handle {
private:
	uint64_t& _value {
		return static_cast<T*>(this)->value();
	}
	
	const uint64_t& _value const {
		return static_cast<const T*>(this)->value();
	}
	
	uint8_t _tag() {
		return (_value>>48)&0xF;
	}
	
public:
	bool isNone() const {
		return _value == ESP_NONE;
	}
	bool isEmpty() const {
		return _value == ESP_EMPTY;
	}
	bool isError() const {
		return _value == ESP_ERROR;
	}
	
	operator bool() const {
		return toBool();
	}
	
	bool isBool() const {
		auto& data = _value;
		return data == ESP_TRUE || data == ESP_FALSE;
	}
	bool asBool() const {
		return _value&(ESP_TRUE^ESP_FALSE);
	}
	bool toBool() const {
		return proto().callMethod("bool");
	}

	bool isInt() const {
		return _tag() == TAG_INT;
	}
	int64_t asInt() const {
		// MSB = 1, sign extend by XNORing the sign bit with MSB
		return data^((~data&(1L<<62))<<1);
	}
	int64_t toInt() const {
		return proto().callMethod("int");
	}

	bool isReal() const {
		return _tag() == TAG_REAL;
	}
	double asReal() const {
		union {
			uint64_t u;
			double d;
		};
		u = ~data;
		return d;
	}
	double toReal() const {
		return proto().callMethod("real");
	}

	bool isSmallString() const {
		return (((data>>49)&((1<<15) - 1)) == 1) && 
	}

	bool isCString() const;
	const char* asCString() const;


	bool isChar() const {
		return _tag() == TAG_CHAR;
	}
	bool asChar() const {
		return data&(ESP_TRUE^ESP_FALSE);
	}
	bool toChar() const {
		return proto().callMethod("char");
	}
		
	bool isCFunc() const;
	esp_CFunc asCFunc() const;

	bool isLeaf() const;
	bool isImmutable() const;

	//CONVERSION(Opaque);

	bool isPtr() const;
	GCObject* asPtr() const;
	
	Value proto() const {
		if(isReal()) return &real_proto;
		if(isInt()) return &int_proto;
		if(isBool()) return &bool_proto;
		if(isNone() || isEmpty()) return ESP_NONE;
		
		switch(_tag()) {
			case TAG_CHAR: return &char_proto;
			case TAG_STRING: return &string_proto;
			case TAG_BYTES: return &bytes_proto;
			case TAG_SYMBOL: return &symbol_proto;
		}
	}
};

/**
 * Handle which keeps values alive while they're only referred to in native
 *  code. These are kept as a pool in the GC acting as roots for mark and
 *  sweep.
**/
struct Var : Value {
	inline Var() {
		gc.register_root(this);
	}
	
	inline ~Var() {
		gc.remove_root(this);
	}
};

struct Builtin {
	Dict* shape; // {"add": offsetof(add)} 26 ~ 64
	Extension
		add, sub, mul, div, mod, pow, idiv,
		band, bor, bxor, lsh, ash, rsh,
		lt, le, gt, ge, eq, ne, cmp,
		call, get, set, del, has, init;
};

/**
 * Provides a way for native objects to be managed by the runtime.
**/
struct Userdata : public GCObject {
	virtual ~Userdata() = default;
};

struct Real : public GCObject {
	double value;
};

struct Int : public GCObject {
	intmax_t value;
};

/**
 * Immutable text data with a known encoding (UTF-8)
 * 
 * http://www.utf8everywhere.org/
**/
struct String : public GCObject {
	union {
		struct {
			hash_t hash;
			uint32_t length;
		};
		uint64_t hashlen;
	};
	char8_t data[0];
	
	template<typename V>
	void gc_visit(V& v) {}
};

/**
 * Immutable data with no specified encoding.
**/
struct Bytes : public GCObject {
	size_t size;
	uint8_t* data;
	
	template<typename V>
	void gc_visit(V& v) {}
};

/**
 * Mutable byte-aligned data
**/
struct Buffer : public GCObject {
	uint32_t size;
	uint32_t capacity;
	uint8_t* data;
	
	template<typename V>
	void gc_visit(V& v) {}
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

/**
 * This isn't a GCObject because it's allocated within the structure of
 *  DictKeys.
**/
struct DictKeyEntry {
	bool writable : 1; // Can the value change?
	bool removable : 1; // Property can be deleted?
	bool configurable : 1; // Can the property be configured?
	bool ispublic : 1; // Property is public? (private requires this.*)
	bool isoffset : 1; // Interpret value as an offset into slots?
	bool accessor : 1; // Property is an accessor
	
	/*
	private property - any possible value
	public property - any possible value
	
	hash -> index
	index -> entry (offset|value)
	
	
	*/
	
	HeapValue key;
	
	/**
	 * Only allocated when the shape is extended
	**/
	HeapValue value[0];
};

struct DictKeys : public GCObject {
	uint32_t usable; // Number of usable entries (not sync'd with used)
	uint32_t used; // Number of used entries
	
	uint8_t indices[0];
	
	template<typename V>
	void gc_visit(V& v) {}
};

struct Dict : public GCObject {
	bool ownproto : 1; // Proto is an extension of the object's own properties
	bool extended : 1; // Whether the dictionary stores values or offsets
	Value proto;
	DictKeys* keys;
	
	template<typename V>
	void gc_visit(V& v) {
		v.visit(proto);
		v.visit(*keys);
	}
};

/**
 * Immutable non-resizeable sequential type
**/
struct Tuple : public GCObject {
	Value elems[0];
	
	template<typename V>
	void gc_visit(V& v) {
		for(int i = 0; i < length(); ++i) {
			v.visit(elems[i]);
		}
	}
};

/**
 * Mutable non-resizeable sequential type
**/
struct Array : public GCObject {
	Value elems[0];
	
	template<typename V>
	void gc_visit(V& v) {
		for(int i = 0; i < length(); ++i) {
			v.visit(elems[i]);
		}
	}
};

/**
 * Mutable resizeable sequential type
**/
struct List : public GCObject {
	Array* elems;
	
	template<typename V>
	void gc_visit(V& v) {
		v.visit(*elems);
	}
};

/* Note: There is no immutable resizeable type */

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

struct UserObject : public GCObject {
	struct Interface {
		CFunction get;
		CFunction set;
		CFunction del;
		CFunction def;
	};
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

struct Accessor {
	Value get, set, del;
};

struct Wrapped : public GCObject {
	Dict* shape;
	void* data;
};

/**
 * Using a JVM/C++ exception model, where IP regions and a corresponding
 *  IP for the handler.
**/
struct EHTableEntry {
	uint16_t from, to, target;
	bool save_trace;
};
static_assert(sizeof(EHTableEntry) == sizeof(void*));

struct Function : public GCObject {
	Tuple* ktab;
	uint16_t codelen;
	uint8_t code[0];
	/**
	 * EHTableEntry eh[]
	**/
	
	/**
	 * Get the exception handler table
	**/
	constexpr const EHTableEntry* ehtab() const {
		return (EHTableEntry*)&code[size2cell(codelen)];
	}
	
	/**
	 * Get the xth exception handler
	**/
	constexpr const EHTableEntry& eh(uint x) const {
		assert(x < neh());
		return ehtab()[x];
	}
	
	/**
	 * Get the number of exception handlers
	**/
	constexpr uint neh() const {
		return ncells() - cell2size((GCObject*)ehtab() - (GCObject*)this);
	}
};

struct Closure : public GCObject {
	Function* func;
	Value* upvals[0];
	
	constexpr int nup() const {
		return ncells() - 2;
	}
};

/**
 * General structure for storing function metadata, which is immutable
**/
struct FuncMeta {
	String source;
	int line, col;
	String name;
	String doc;
	uint16_t param_count;
	String param_doc;
	Value defaults;
};

// NativeFunction is only ever created by the host program
struct NativeFunction {
	enum Flag {
		USE_THIS,
		PASS_ARRAY,
		STDCALL,
		CDECL,
		FASTCALL,
		THISCALL,
		IGNORE_BADTYPE, // use default constructor for bad types
		THROW_BADTYPE, // throw an error for bad types
		IS_VM
	} flags;
	FuncMeta meta;
	
	// Generally follows Python struct packing, but doesn't support
	//  endianness or type repetition and adds support for substructures
	const char* signature;
	/*
		' ' = skip
		'x' = pad
		"?" = bool
		'c' = char
		'b' = int8
		"B" = uint8
		'h' = int16
		"H" = uint16
		'i' = int32
		"I" = uint32
		'q' = int64
		"Q" = uint64
		'n' = ssize_t
		"N" = size_t
		'f' = float
		"d" = double
		's' = string
		'v' = Value
		'p' = buffer
		'P' = void*
		'{' = begin struct
		'}' = end struct
	*/
	void* impl;
};

#endif
