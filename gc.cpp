#include "gc.hpp"

#include <utility>
#include <cstring>
#include <cassert>
#include <cstring>

#include <cstdio>
#include "common.h"

#ifndef ARENA_SIZE
#define ARENA_SIZE (1<<16)
#endif

static constexpr int celldiv = sizeof(GCObject)*8;

template<typename T>
void set_bit(T& x, int off, bool b) {
	uint64_t mask = 1L<<(i%celldiv);
	if(b) {
		x |= mask;
	}
	else {
		b &= ~mask;
	}
}

template<typename T>
bool get_bit(T& x, int off) {
	return x & 1L<<(i%celldiv);
}

/**
 * Call any finalizer methods of the object. This isn't a virtual method,
 *  finalization is "overrided" via the object structure. It also isn't on
 *  GCObject itself to make the interface cleaner.
**/
static void GCObject_finalize(GCObject* self) {
	LOG_DEBUG("GC: Finalizing @%p", self);
	switch(self->gco.type) {
		case GCObject::LONG:
		case GCObject::BYTES:
		case GCObject::TUPLE:
		case GCObject::ARRAY:
		case GCObject::PROTO:
		case GCObject::STRUCT:
		case GCObject::WRAPPED:
		case GCObject::FUNCTION:
		case GCObject::CLOSURE:
		case GCObject::NFUNCTION:
			// Nothing to finalize
			return;
		
		case GCObject::BUFFER:
		case GCObject::LIST:
		case GCObject::OBJECT:
			/* TODO */
			LOG_WARN("TODO: No finalizer for object which needs one");
			return;
	}
}

// Typedefs to make intent clear
typedef uint sizeclass_t; // quipu head index
typedef uint blocksize_t; // size of a cell
/**
 * Index of a cell used internally
**/
typedef uint16_t cellid_t;

/**
 * Alias structure for GCObject which makes it easier to understand the code
 *  in the Quipu structure.
 * 
 * As a quick note, Cell* is readily castable to and from Cell** which is
 *  used to make quipu logic easier to read.
**/
struct Cell {
	Cell* next;
	Cell* rest[];
	
	Cell*& prev(blocksize_t size) {
		assert(size > 1);
		return rest[size - 2];
	}
	
	bool is_zeroed(blocksize_t sz) const {
		if(next) return true;
		
		for(int i = 0; i < sz - 1; ++i) {
			if(rest[i]) return false;
		}
		return true;
	}
};

/**
 * blocks/markmap 1 bit per cell
 * 
 * 32-bit and 64-bit use word-sized cells. Both use 4-byte values, but
 *  64-bit needs 8-byte alignment to ensure data alignment
 * 
 * bit blocks[x]
 * bit markmap[x]
 * word cells[x]
 * 
 * size = 2x/8 + sizeof(word)*x // formal description of size
 * 8size = 2x + 8sizeof(word)*x
 * x = 8size/(2 + 8sizeof(word))
 * 
 * Assume metadata section is 1/64 of size?
 * 
 * So say, size=4096 => 64 bytes => 512 bits => 256 cells/words, 256*8 = 2048
 * size=65536 => 1024 bytes => 8192 bits => 4096 cells/words, 4096*8 = 32768
 * 
 * LuaJIT 3.0 GC got the 1/64 number from cells being two words
**/
template<size_t SIZE>
struct Arena {
	uintptr_t blocks[SIZE/(sizeof(uintptr_t)*8)];
	uintptr_t markmap[SIZE/(sizeof(uintptr_t)*8)];
};

constexpr int x = sizeof(Arena<4096>::blocks)/sizeof(uintptr_t);
constexpr int y = sizeof(Arena<4096>);

/**
 * An arena for GCObjects. Garbage collection is done per-arena, with arenas
 *  being sized to approximately a page of cache memory. 1/64th of the total
 *  data is used for cell metadata, enabling better branch prediction.
**/
struct ObjectArena {
	/**
	 * Bitmap of whether or not the represented cell is the first cell of a
	 *  block. Used for sweep phase.
	**/
	uintptr_t blocks[512];
	
	/**
	 * Bitmap of the white/black bit which defines reachability (by
	 *  convention, white is "maybe garbage" and black is "probably not
	 *  garbage" set. After a full sweep, we can guarantee anything not part
	 *  of the white set is garbage)
	**/
	uintptr_t markmap[512];
	
	/**
	 * Stack of cell ids which are black and have their dirty bit set.
	**/
	GCObject* dirty;
	
	/**
	 * Top index of the dirty stack
	**/
	GCObject* dirty_top;
	
	/**
	 * All the cells in the arena. The actual array is defined to have
	 *  exactly enough elements to fill out the rest of the required Arena
	 *  size.
	**/
	GCObject cells[(ARENA_SIZE - (
		sizeof(blocks)*2 + sizeof(dirty) +
		sizeof(dirty_top)
	))/sizeof(GCObject)];
	
	static_assert(
		sizeof(blocks) == sizeof(markmap),
		"Block and mark bitmaps aren't the same size"
	);
	
	static_assert(
		sizeof(blocks)*8 >= sizeof(cells)/sizeof(GCObject),
		"Bitmaps aren't large enough to cover all cells"
	);
	
	ObjectArena() {
		LOG_INFO("GC: ObjectArena alloc @%p (%d)", this, sizeof(*this));
		
		// Set all cells to empty
		for(auto& x : blocks) {
			x = 0L;
		}
		for(auto& x : markmap) {
			x = ~0L;
		}
	}
	
	~ObjectArena() {
		LOG_INFO("GC: ObjectArena dealloc @%p (%d)", this, sizeof(*this));
	}

	bool get_block(cellid_t i) const {
		return get_bit(blocks[i/celldiv], i%celldiv);
	}
	void set_block(cellid_t i, bool v) {
		return set_bit(blocks[i/celldiv], i%celldiv, v);
	}
	
	bool get_mark(cellid_t i) const {
		return get_bit(markmap[i/celldiv], i%celldiv);
	}
	void set_mark(cellid_t i, bool v) {
		return set_bit(markmap[i/celldiv], i%celldiv, v);
	}
	
	void set_blockmark(cellid_t i, bool b, bool m) {
		set_block(i, b);
		set_mark(i, m);
	}

	/**
	 * GC keeps bitmaps of the allocation status of every cell. Together these
	 *  form a differential encoding with some nice bit fiddling properties.
	 * 
	 * Block | Mark |   Meaning
	 * 0       0      Block extent
	 * 0       1      Free/empty block
	 * 1       0      White block
	 * 1       1      Black block
	**/

	void white(cellid_t i) {
		set_blockmark(i, 1, 0);
	}
	void black(cellid_t i) {
		set_blockmark(i, 1, 1);
	}
	void empty(cellid_t i) {
		set_blockmark(i, 0, 1);
	}
	void extent(cellid_t i) {
		set_blockmark(i, 0, 0);
	}
	
	bool is_extent(cellid_t i) const {
		return !get_block(i) && !get_mark(i);
	}
	bool is_empty(cellid_t i) const {
		return !get_block(i) && get_mark(i);
	}
	
	Cell* first_cell() {
		return (Cell*)&cells[0];
	}
	Cell* last_cell() {
		return (Cell*)&cells[last_id()];
	}
	
	cellid_t first_id() const {
		return 0;
	}
	cellid_t last_id() const {
		return sizeof(cells)/sizeof(cells[0]) - 1;
	}
	
	/**
	 * Convert a raw pointer to a 16 bit cellid_t
	**/
	cellid_t addr2index(GCObject* ob) {
		return (cells - ob)&~ARENA_SIZE;
	}
};

/**
 * Cell alignment must be preserved to enable address compression in the
 *  form of cellid_t.
**/
static_assert(
	offsetof(ObjectArena, cells)%sizeof(GCObject) == 0,
	"ObjectArena cells are out of alignment"
);

static_assert(sizeof(ObjectArena) == ARENA_SIZE);

/**
 * More than 1 MB requires a larger cellid_t, doubling the memory usage of
 *  the dirty stack.
**/
static_assert(
	sizeof(ObjectArena) <= 1024*1024*1024,
	"ObjectArena is too big - must be no larger than 1 MB"
);

/**
 * Array of linked lists of free blocks allocated in the largest hole (not
 *  including the bump block). Each cell is the head of a linked list through
 *  the first cell of each hole of the corresponding size (1st element is the
 *  head of a doubly linked list with the same size as head) while the last
 *  cell of every node is a backward reference (NULL for head). This was
 *  added so the bump block could grow in O(1) time by dereferencing the
 *  first empty cell it doesn't own. This structure is built by deallocations
 *  so the hole sizes are precalculated implicitly, preventing the worst case
 *  scenario of scanning the block bitmap.
 * 
 * Allocation follows this algorithm:
 *  1. If the requested size is larger than the quipu, use the bump allocator
 *  2. If the list with the exact size is NULL, use the bump allocator
 *     a. Unless the requested size is the same as the quipu, in which case
 *         move all the relevant data to the next largest hole and the old
 *         quipu becomes the new allocation. Note that the next quipu will
 *         ALWAYS be large enough, because it has at least as many cells as
 *         there are size classes.
 *  3. Pop from the corresponding list, this address is the allocation
 * 
 * If the bump allocator doesn't have enough memory, search for the best fit
 *  which can contain the size. If none exists, create a new arena.
 * 
 * As a data structure this is basically just an array of linked lists which
 *  are used as a stack, but it reminds me a lot of the Andean device which
 *  records numbers using knotted strings tied to one top string called
 *  a Quipu (or Khipu), so I'll call it that. If it's kept up to date with
 *  every deallocation, it should span every hole in the arena.
 * 
 * External fragmentation statistics are trivial to calculate, as we always
 *  know the largest hole size and can keep a counter of best fits. If these
 *  exceed a certain threshold, the structure can be rebuilt O(n).
**/
struct Quipu {
	/**
	 * Largest hole not including the bump block
	**/
	Cell** head;
	
	/**
	 * Total cells in the head block.
	**/
	blocksize_t headsize;
	
	/**
	 * Number of cells in the structure
	**/
	uint size;
	
	/**
	 * Number of single-cell free blocks, which can't be added to the quipu
	 *  and aren't generally useful anyway.
	**/
	uint frags;
	
	Quipu():head(nullptr), headsize(0), size(0), frags(0) {}
	
	/**
	 * Zero everything out
	**/
	void clear() {
		head = nullptr;
		headsize = blocksize_t(0);
		size = 0;
		frags = 0;
	}
	
	/**
	 * Give this an explicit name to make the code easier to read. Returns
	 *  the size class (index into the quipu head) given a size
	**/
	sizeclass_t size_class(blocksize_t x) const {
		return headsize - x;
	}
	
	blocksize_t class_size(sizeclass_t x) const {
		// This is an involution, but keep the name for clarity
		return headsize - x;
	}
	
	/**
	 * Pop the xth list
	**/
	Cell* pop(sizeclass_t x) {
		assert(x < headsize && head[x] != nullptr);
		
		blocksize_t cells = class_size(x);
		
		Cell* h = head[x];
		Cell* after = h->next;
		head[x] = after;
		after->prev(cells) = (Cell*)&head[x];
		size -= cells;
		
		LOG_DEBUG("GC: pop @%p (%d cells)", h, cells);
		
		return h;
	}
	
	/**
	 * Push the element into the xth list
	**/
	void push(Cell* ob, sizeclass_t x) {
		blocksize_t cells = class_size(x);
		assert(ob->is_zeroed(cells));
		
		remove(head[x], cells);
		ob->next = head[x];
		ob->prev(cells) = (Cell*)&head[x];
		
		if(head[x]) {
			head[x]->prev(cells) = ob;
			head[x] = ob;
		}
		
		size += cells;
		
		LOG_DEBUG("GC: push @%p (%d cells)", ob, cells);
	}
	
	/**
	 * Replace the head with the next largest block, returning the old head
	**/
	Cell* pop_head() {
		Cell* next;
		blocksize_t oldsize = headsize;
		
		// Last cell is a backward reference, so stop before then
		for(sizeclass_t i = 0; i < headsize - 1; ++i) {
			// Found a new hole to act as the quipu head
			if(next = head[i]) {
				/**
				 * next[0] is already linked, copy the rest
				 *        0 ... i 
				 * Head:  @ @ @ y y y y y @
				 * Next:        x x x x x x
				 *              0  ...  j
				**/
				headsize = class_size(i);
				size -= headsize;
				memcpy(&next->rest, head[i + 1], headsize - 1);
				
				// Update backreferences
				for(sizeclass_t j = 0; j < headsize - 1; ++j) {
					if(head[j]) head[j]->prev(class_size(j)) = head[j];
				}
				goto finish;
			}
		}
		// Ran out of holes
		next = nullptr;
		size = headsize = 0;
		
	finish:
		LOG_DEBUG(
			"GC: Pop quipu head @%p (%d cells) - new head @%p (%d cells)",
			head, oldsize, next, headsize
		);
		auto* old = (Cell*)head;
		head = (Cell**)next;
		return old;
	}
	
	/**
	 * Remove a particular object from its chain
	**/
	void remove(Cell* ob, blocksize_t cells) {
		blocksize_t x = size_class(cells);
		
		Cell* before = head[x]->prev(cells);
		Cell* after = head[x]->next;
		
		if(after) after->prev(cells) = before;
		before->next = after;
	}
	
	/**
	 * Find a hole with the exact size, otherwise return null
	**/
	Cell* alloc_exact(size_t size) {
		assert(size < sizeof(ObjectArena::cells));
		
		blocksize_t cells = size2cell(size);
		
		// No holes!
		if(!head) return nullptr;
		
		// No holes big enough!
		if(cells > headsize) return nullptr;
		
		Cell* next;
		
		// Is head a candidate?
		if(cells == headsize) {
			next = head[0]? pop(0) : pop_head();
		}
		// Normal case, check for an exact fit
		else {
			next = head[size_class(cells)]? pop(size) : nullptr;
		}
		
		LOG_DEBUG("GC: Exact alloc @%p (%d)", next, size);
		
		return next;
	}
	
	/**
	 * Find a hole with the best fit, otherwise return null
	**/
	Cell* alloc_bestfit(size_t size) {
		assert(size < sizeof(ObjectArena::cells));
		
		blocksize_t cells = size2cell(size);
		
		// No holes!
		if(!head) return nullptr;
		
		// No holes big enough!
		if(cells > headsize) return nullptr;
		
		Cell* ob;
		sizeclass_t i;
		
		// Assume there's no exact fit, start -1 and check increasing sizes
		for(i = cells - 1; i > 0; --i) {
			if(head[i]) {
				ob = pop(i);
				goto finish;
			}
		}
		
		// Either use head-sized list or head
		ob = head[0]? pop(0) : pop_head();
		
	finish:
		// Fragment the block
		Cell* frag = ob + size;
		if(cells - i == 1) {
			frag->next = nullptr;
			++frags;
		}
		else {
			push(frag, size_class(cells - i));
		}
		
		// Best-fit allocations cause fragmentation, so report it
		LOG_INFO(
			"GC: Best-fit alloc @%p (%d +%d cells)",
			ob, size, cells - i
		);
		
		return ob;
	}
	
	/**
	 * Enter the deallocated object into the quipu. We own it after this
	 *  call, and it *will* have data overwritten
	**/
	void dealloc(Cell* ob, blocksize_t cells) {
		// Just zero it to avoid data leakage and make bugs fail fast
		memset(ob, 0, cells*8);
		
		// Need to setup a new head
		if(!head) {
			head = (Cell**)ob;
			headsize = cells;
			size += headsize;
		}
		// Will it fit as-is?
		else if(cells <= headsize) {
			push(ob, size_class(cells));
		}
		// cells > headsize, new head
		else {
			// Copy old data (including null backreference)
			memcpy(&ob[cells - headsize], head, headsize);
			auto* tmp = (Cell*)head;
			head = &ob->next;
			ob = tmp;
			
			std::swap(headsize, cells);
			
			// Push the old head to the right size class
			push(ob, size_class(cells));
		}
		
		LOG_DEBUG("GC: Finished dealloc @%p (%d)", ob, cells);
	}
};

struct ArenaHandle {
	ArenaHandle* next;
	ObjectArena* arena;
	
	Quipu freed;
	
	Cell* bump;
	Cell* end;
	
	/**
	 * Deallocate a single object (assuming it belongs to this arena)
	**/
	void dealloc(GCObject* gco) {
		Cell* ob = (Cell*)gco;
		assert(ob >= arena->first_cell());
		assert(ob <= arena->last_cell());
		
		unsigned idx = arena->addr2index(gco);
		assert(idx >= arena->first_id());
		
		auto cells = gco->ncells();
		
		GCObject_finalize(gco);
		
		////////////////////////////////////////////
		// Combine with any adjacent empty blocks //
		////////////////////////////////////////////
		
		/// Before ///
		
		// Quipu head?
		if(ob == (Cell*)freed.head + freed.headsize) {
			cells += freed.headsize;
			ob = freed.pop_head();
		}
		// Empty?
		else if(ob != arena->first_cell() && arena->is_empty(idx - 1)) {
			// Cell immediately before
			Cell* b = (Cell*)&ob[-1];
			
			// Check backreference
			if(b->next) {
				// Retrieve the first cell of the block
				ob = b->next->next;
				
				// Remove it from the list
				b->next->next = ob->next;
				ob->next->prev(b - ob + 1) = b->next;
				
				cells += b - ob + 1;
			}
			// Single-cell fragment
			else {
				++cells;
				--freed.frags;
				ob = b;
				LOG_INFO("GC: Recovered single-cell fragment @%p", ob);
			}
		}
		
		Cell* end = ob + cells;
		
		/// After ///
		
		// Quipu head?
		if(end == (Cell*)freed.head) {
			LOG_INFO(
				"GC: Found adjacent free quipu block @%p (%d cells)",
				freed.head, freed.headsize
			);
			cells += freed.headsize;
			freed.pop_head();
		}
		// Empty?
		else if(end != arena->last_cell()) {
			cellid_t sc = 0;
			
			// Have to determine size class by scanning the bitmaps
			for(++idx; idx <= arena->last_id(); ++idx) {
				if(!arena->is_empty(idx)) break;
				++sc;
			}
			
			if(sc != 0) {
				if(sc == 1) {
					LOG_INFO("GC: Recovered single-cell fragment @%p", end);
					++cells;
					--freed.frags;
				}
				else {
					LOG_INFO(
						"GC: Found adjacent empty block @%p (%d cells)",
						end, sc
					);
					cells += sc;
					freed.remove(end, sc);
				}
			}
		}
		
		/// Cleanup ///
		
		// Does this grow the bump pointer?
		if(ob + cells == bump) {
			bump = ob;
		}
		// Else add it to the quipu
		else {
			freed.dealloc(ob, cells);
		}
		
		// Set the bitmaps to empty
		for(int i = 0; i < cells; ++i) {
			arena->empty(idx + i);
		}
	}
	
	int bumpsize() const {
		return end - bump;
	}

	int unused() const {
		return freed.size + bumpsize();
	}
	
	/**
	 * Allocate a block with the given number of bytes
	**/
	GCObject* alloc(uint size) {
		auto* ob = freed.alloc_exact(size);
		if(!ob) {
			// No exact fit, allocate from the bump block
			if(size >= end - bump) {
				ob = (Cell*)bump;
				bump += size;
				
				LOG_TRACE("GC: Bump alloc @%p (%dB)", ob, size);
			}
			// Bump block isn't big enough, try bestfit (worst case since
			//  this fragments the quipu)
			else {
				ob = freed.alloc_bestfit(size);
				
				// No more memory in this arena, need to allocate a new one
				if(!ob) return nullptr;
			}
		}
		
		auto* gco = (GCObject*)ob;
		auto idx = arena->addr2index(gco);
		
		// Adjust GC bitmaps
		arena->white(idx);
		for(int i = 1; i < size/8; ++i) {
			arena->extent(idx + i);
		}
		
		// Some basic initialization
		gco->gco.here = 1;
		gco->gco.dirty = 0;
		gco->gco.size = (uint32_t)size;
		
		return gco;
	}
	
	/**
	 * Deallocate any objects which are still white and set black to white.
	**/
	void major_sweep()  {
		LOG_INFO("GC: Major sweep");
		
		for(cellid_t i = 0; i < sizeof(arena->blocks)*8; ++i) {
			bool b = arena->get_block(i), m = arena->get_mark(i);
			
			// Deallocate if white
			if(b & !m) dealloc(&arena->cells[i]);
			
			arena->set_blockmark(i, b&m, b^m);
		}
		
		LOG_DEBUG("GC: Major sweep finished");
	}
	
	/**
	 * Deallocate any objects which are still white, don't change black.
	**/
	void minor_sweep() {
		LOG_INFO("GC: Minor sweep");
		
		for(cellid_t i = 0; i < sizeof(arena->blocks)*8; ++i) {
			bool b = arena->get_block(i), m = arena->get_mark(i);
			
			// Deallocate if white
			if(b & !m) dealloc(&arena->cells[i]);
			
			arena->set_blockmark(i, b&m, b|m);
		}
		
		LOG_DEBUG("GC: Minor sweep finished");
	}
};

struct SequenceArena {
	
};

/**
 * Data arenas are for leaf GCObjects and are thus only ever white or black.
**/
struct DataArena {
	uint8_t data[sizeof(ObjectArena)];
};
