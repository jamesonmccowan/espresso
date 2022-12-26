/**
 * @file object.hpp
 * 
 * Define the structures of objects allocated in memory
 */
#ifndef ESP_OBJECT_HPP
#define ESP_OBJECT_HPP

#include "value.hpp"

using CFunction = Value(*)(Value, int, Value(*)[]);

struct Float : public GCObject {
	double value;
	
	
};

struct Long : public GCArray<uint> {
	
};

struct String : public GCArray<uint8_t> {
	uint length() const {
		uint len = GCArray<uint8_t>::length();
		if(len == 0) return 0;
		
		// Last cell is padded with nulls
		return len/sizeof(uintcell_t) - __builtin_ctz(cells[len - 1])/8;
	}
};

struct Rope : public GCObject {
	uint len;
	Value32 left, right;
	
	uint length() const {
		return len;
	}
};

struct Bytes : public GCObject {
	uint len;
	uint8_t data[0];
};

template<typename T>
struct HeapBuffer {
	std::unique_ptr<T> data;
};

struct Buffer : public GCObject {
	HeapBuffer<uint8_t[]> data;
};

struct Tuple : public GCArray<HeapValue> {
	
};

struct List : public GCObject {
	HeapBuffer<HeapValue> data;
};

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

struct Set : public GCObject {
	
};

/**
 * Round to the next power of 2
**/
constexpr uint round_pow2(uint x) {
	return 1 << (32 - __builtin_clz(x - 1));
}

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
	/// Subtypes ///
	
	struct Property {
		bool writable : 1; // Can the value change?
		bool removable : 1; // Property can be deleted?
		bool configurable : 1; // Can the property be configured?
		bool ispublic : 1; // Property is public? (private requires this.*)
		bool isoffset : 1; // Interpret value as an offset into slots?
		bool accessor : 1; // Property is an accessor
	};
	
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
	
	template<size_t N>
	struct VarInt;
	
	using VarInt<8> = uint8_t;
	using VarInt<16> = uint16_t;
	using VarInt<32> = uint32_t;
	using VarInt<64> = uint64_t;
	
	template<size_t SIZE>
	struct HashData {
		std::array<VarInt<SIZE>, round_pow2(SIZE)> indices;
		std::array<Entry, SIZE> entries;
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
	
	/// Data members ///
	uint8_t log2_size;
	uint32_t version;
	size_t usable;
	size_t entry_count;
	
	uint8_t indices[0]; /// TODO: Incomplete ordering
	
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
	Object* proto; // Prototype shape
	Dict* shape; // Object shape
	Value slots[0];
};

/**
 * Native pointer associated with metadata
 */
struct Wrapped : public GCObject {
	
};

/**
 * Native pointer with no metadata
 */
struct Opaque : public GCObject {
	
};

/**
 * Espresso function
 */
struct Function : public GCObject {
	
};

/**
 * An instantiated function closure with upvars
 */
struct Closure : public GCObject {
	
};

/**
 * Native function following a standard calling convention
 */
struct Extension : public GCObject {
	
};

/**
 * Native function with typing metadata
 */
struct Native : public GCObject {
	
};

#endif
