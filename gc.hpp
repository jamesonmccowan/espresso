/**
 * Rough implementation of Mike Pall's cache-friendly quad-color incremental
 *  mark-and-sweep GC algorithm designed for LuaJIT 3.0, as detailed here:
 * 
 * http://wiki.luajit.org/New-Garbage-Collector
**/
#ifndef ESP_GC_HPP
#define ESP_GC_HPP

#include <bitset>
#include <type_traits>
#include <queue>
#include <array>
#include <set>

#include <cstdint>
#include <cstddef>

#include "common.h"

/**
 * Object sizes are fixed at creation, and can be allocated compactly.
**/
struct ObjectArena;
/**
 * Sequences are allocated as far apart as possible to make realloc easier.
**/
struct SequenceArena;
/**
 * Allocate immutable string data and index it via a lookup table.
**/
struct DataArena;
struct ArenaHandle;

constexpr uint size2cell(uint size) {
	return (size + 7)/8;
}

constexpr uint cell2size(uint cell) {
	return cell*8;
}

/**
 * Cells are the basic memory unit of an arena, ideally set to the size of
 *  the smallest valid GCObject. In the original algorithm this was set to
 *  16 bytes, possibly because Lua uses tagged unions which have a minimum
 *  alignment of 2*sizeof(uintptr_t) on 64-bit machines.
 * 
 * Here we'll just use GCObject directly as cells
 * 
 * GCHeader has to be word aligned because we want to support direct pointers
 *  in certain gc objects.
 * 
 * GCHeader memory layout is:
 * 
 * uint16_t size
 * uint5_t type
 * bool immortal = allocated outside of managed memory
 * bool moved
 * bool dirty
 * bool here
**/
struct GCHeader {
	enum Type {
		// Leaves
		FLOAT,
		LONG, // size, data...
		STRING, // size, data...
		ROPE, // Concatenation of strings
		BYTES, // size, data...
		BUFFER, // size, capacity, data
		
		// Sequence
		TUPLE, // size, data...
		LIST, // size, capacity, data
		
		// Dict
		SET, // (DictKeys) size, usable, used, indices..., data...
		OBJECT, // shape, slots
		PROTO, // proto, shape, slots...
		STRUCT, // Typed structure with unwrapped data from the host
		WRAPPED, // Typed pointer from the host
		OPAQUE, // Untyped pointer from the host, no valid operations
		
		// Functions
		FUNCTION, // ktab, code...
		CLOSURE, // func, upvals...
		EXTENSION,
		NATIVE, // metadata, impl, schema...
		
		USERDATA
	};
	
	uintptr_t _value;
	
	GCHeader() = default;
	
	/**
	 * Constructor for building a GC Object from within the GC
	**/
	inline GCHeader(uint size, Type type) {
		_value = size<<8 | type&0x1f | 0<<2 | 0<<1 | 0<<0;
	}
	
	inline uint cells() const noexcept {
		return _value>>8;
	}
	
	inline Type type() const noexcept {
		return (Type)((_value>>3)&0x1f);
	}
	
	inline bool is_here() const noexcept {
		return _value&(1<<0);
	}
	
	inline bool is_dirty() const noexcept {
		return _value&(1<<1);
	}
	
	inline void mark_dirty() noexcept {
		_value |= 1;
	}
	
	inline bool is_moved() const noexcept {
		return _value&(1<<2);
	}
};

/**
 * Represents an object managed by the garbage collector with a GCHeader
 *  allocated immediately before it.
**/
struct GCObject {
	/**
	 * Recover the GCHeader (immediately before `this`)
	**/
	inline GCHeader& gco() {
		return *(GCHeader*)(((uint8_t*)this) - sizeof(GCHeader));
	}
	inline const GCHeader& gco() const {
		return const_cast<GCObject*>(this)->gco();
	}
	
	/**
	 * Object is allocated in the GC heap, deletion is invalid until we can
	 *  prove there's no valid references - and even then we handle that
	 *  ourselves.
	**/
	void operator delete(void*) = delete;
};

namespace {
	// Compare so top() is the smallest (least number of f)
	constexpr bool arena_cmp(ArenaHandle* a, ArenaHandle* b) {
		return a->unused() < b->unused();
	}
}

struct GC {
	std::priority_queue<
		ArenaHandle*,
		std::array<ArenaHandle*, 4>
	> arenas;
	std::priority_queue<ObjectArena*> dirty;
	
	std::set<Value*> roots;
	
	inline void register_root(Value* v) {
		roots.insert(v);
	}
	
	inline void remove_root(Value* v) {
		roots.erase(v);
	}
	
	template<typename T>
	T& alloc(size_t bytes) {
		LOG_DEBUG("GC: Alloc %d bytes as %s", bytes, typeid(T).name());
		return *new(arenas.top()->alloc(bytes)) T(bytes);
	}
	
	GCObject* alloc_raw(size_t bytes); {
		LOG_DEBUG("GC: Alloc %d bytes as raw", bytes);
		GCObject* p = arenas.top()->alloc(bytes);
		new (p) GCObject(bytes, GCObject::USERDATA);
	}
};

thread_local GC gc;

#endif
