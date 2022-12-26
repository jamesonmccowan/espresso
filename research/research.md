https://www.youtube.com/watch?v=vElZc6zSIXM
* How to make fast small data structuress
* Custom containers which store their data in the structure
* Lets you alloc on the stack and return by value
* For lists of big objects, small vector of unique ptrs (branch prediction+++)
* Pointer-like with embeddable ints in leftover bits
* Variant types between pointer and pointer to vector of pointers w/ pointer size

AsmJIT project (C++ dynamic assembler ala DynAsm without preprocessing)

fbstring
* small string representation
* small strings are 24 bytes on the stack
* Last byte is the capacity
* When capacity is 0, it doubles as null terminator

V8 invalidates the IC by keeping a reference to a boolean "validity cell", sort of like a weak reference. If it's false, the IC is flushed and slow prototype lookup is done again. This isn't too bad for V8 which creates new objects for every shape change, so the prototype/shape which is invalidated is trash. As a possible optimization for our use-case, we can use an int instead of a boolean which increments with each change to get a "version" token. If the versions differ, redo prototype lookup. This leaves an edge case, where the int would overflow - at this point we can stop incrementing the version and create a new object like V8 because if we reuse lower values, there's a (very small but nonzero) chance that a rare code path still has an older version

http://wiki.luajit.org/New-Garbage-Collector
LuaJIT GC:
* Request memory from OS called Arenas, split into 16-byte cells
* 1+ cells makes a block
* All objects in an arena are either traversable or not
* Block and mark metadata separated from data
* Huge blocks kept in separate arenas
  - Always multiples of arena size
  - No header, metadata stored in a hash table
* Quad-color local to an arena
* Newly allocated objects are grey-white, write barrier can check for just !grey
* grey-black maintains a stack, grey-white can be freed as if it were white
* Grey bit seems to act like a "dirty" bit
* Modified generational GC (triggered by high death rate for young allocs)
* Don't flip black -> white before a minor collection
  - Only newly allocated blocks and dirty objects are traversed, pure black is assumed to be reachable (regardless of mutation)
* Cell index can be derived from starting address by >>4 & LSB
* Cell index always fits in 16 bits
* Two bitmaps determine arena block status, block and mark
  - Block=1 => First cell of a block
  - Mark = white/black or padding/free
* Allocator modes switch depending on fragmentation pressure
  - Bump allocator (increment pointer)
  - Fit allocator (fill holes)
    * Setup bins for size classes using multiples of cell size -> powers of two
	* Each bin is the anchor for a list of free blocks for that size class
	* Bounded best-fit allocation first, fall back to first-fit
	* First-fit can adapt, high miss rates => higher size classes searched first, high hit rate => smaller size classes
* Write barrier: if(!grey) grey = 1 and if(black) push to sequential store buffer (SSB)
* Mark bit only needs to be checked during mark phase, if collector is paused no check (since there's no black objects)
* SSB buffer holding block addresses which triggered write barrier (must have at least one free cell)
* SSB overflow -> convert addresses to cell indices and push to grey stacks
* Use of SSB prevents the cache from being thrashed by GC data while the mutator is running
* Grey stack: per-arena, cell indices of dark-grey blocks 
* Objects removed from grey stack are turned black before traversal
* Current arena processing continues until grey stack is empty
* Grey queue: priority queue of arenas with non-empty grey stack ordered by stack size
* Sweep phase has good cache locality because metadata for blocks is kept together. Don't have to traverse the actual data, just the metadata
* Bitmap tricks allow bitwise parallel operations
  - Major sweep: block' = block & mark, mark' = block^mark (free white blocks and turn black blocks into white blocks)
  - Minor sweep: block' = block & mark, mark' = block|mark (free white blocks, preserve black blocks)
  - Compare block and mark word gives status of last block in the word, eg block' < mark' => last block is free
* ---
* Write barrier triggered when an object with grey=1 is written to, and thus it needs to be revisited
* Grey seems to correspond to "dirty", whether or not it needs to be revisited
* White = maybe garbage, Black = probably not garbage
* GC sweeping is done per-arena, which at first appears to break inter-arena references. But in fact, if a major sweep is done first this will mark any objects referred to in other arenas as black, and they will remain black for each minor collection. Then, a major collection marks everything as white and traverses all arenas. The key here is not resetting black -> white between minor collections

Moving GC with conditional indirection?
* If an object is moved, replace it with a pointer to its new location marked "moved"
* If the mutator accesses it, it updates its reference to the new location
* Because the mutator never propagates the old address, we can guarantee that by the end of a full sweep the old address is garbage

My ideal GC:
* Quad-color mark and sweep kept arena-local for minor sweeps
* Lazy compaction - if an object with the right size for a hole is found, copy contents to the hole and replace the original object with a pointer to the new address. Any accesses check the MSB for 0, and perform a second dereference and update their state. This forward-pointer is then eventually collected as garbage when all references are updated
  - Problem: Needs a grey bit to participate in GC, right?
  - Except, it can be considered as having "no children", so any access marks it black and the grey bit is redundant
* Quipu structure to keep track of the holes
* Prefer exact fit to bump
* Need a way to recover the bump block

Apparently V8 can get equal performance with pointer compression, using effectively half the memory. I want that. JerryScript goes even crazier by supporting 16 bit cptrs by default. Considering the level of repetition between the primitives, I think I'll try to abstract it one level further to a lower level

Base memory footprints:
* Lua = 20 kB / 10 MB? 500 kB static library
* Python = 10 MB
* V8 = 34 MB

https://github.com/nicolasbrailo/cpp_exception_handling_abi

https://www.youtube.com/watch?v=XRAP3lBivYM
* Mesh compaction
* Requires objects have no overlaps
* Compact physical memory by meshing virtual memory pages onto the same physical page
* Offsets in pages randomized to improve meshability
* github.com/emergyberger/Heap-Layers

https://xtclang.blogspot.com/2021/08/its-little-things.html XVM Integer Packing XIP - encodes 64 bit integers in a stream of variable length integers such that the size is determined by the first byte which makes it cache friendlier

https://www.youtube.com/watch?v=raB_289NxBk
Herb Sutter came up with features for C++ which I already added to espresso, and then some

I've been giving a lot of thought lately to generators and promises lately due to these articles:
* https://journal.stuffwithstuff.com/2015/02/01/what-color-is-your-function/
* https://journal.stuffwithstuff.com/2013/02/24/iteration-inside-and-out-part-2/

https://www.youtube.com/watch?v=5iTkA3LoCG0
* Transient Typechecks are (Almost) Free
* Global subtype cache, optimizes for objects you use a lot

https://mail.python.org/pipermail/python-3000/2007-July/008663.html
* Labeled break/continue in PEP 3136 was rejected
* Cases where it's useful are rare
* It adds complexity with minimal benefit
* The feature would probably be abused more than used correctly

https://www.youtube.com/watch?v=yG1OZ69H_-o
* UB is a symptom of latent contract violations
* It is not possible, even in principle, to define all behavior - and attempting to do so pessimizes code

https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/
* Structured Concurrency
* Arbitrary forking with a complete join of all threads at the end of the block

https://blog.sunfishcode.online/no-ghosts/
* Ghost data is POD which is only meaningful with a hidden implicit context
* Eg: Passing file paths between components implicitly requires they share a filesystem
* Counter-example: Passing around a file handle, but not a root directory handle so only components that actually share a filesystem have access to the file
* Signs of ghosts:
  - String parameters that don't represent user data
  - "The", making assumptions about shared state between components
  - User identity outside the UI, "handles are permissions"

Key technologies:
* HOP.js, opportunistic AOT JS compilation
* PyPy stacklets, a composable version of stackful coroutines
* Delimited coroutines are strictly more powerful than call/cc
* https://metacpan.org/pod/Keyword::Declare
* "Zero-overhead deterministic exceptions: Throwing values" by Herb Sutter
  - https://www.youtube.com/watch?v=ARYP83yNAWk
* Cecil/Vortex multimethod implementation with predicates
  - https://projectsweb.cs.washington.edu/research/projects/cecil/www/Papers/dispatching.html

https://github.com/hsutter/gcpp
* Strict superset of region-based memory allocation with optional tracing via an explicit .collect call

https://www.cs.utah.edu/~regehr/papers/undef-pldi17.pdf
* Taming Undefined Behavior in LLVM
* LLVM previously had two UB values, `undef` and `poison` with different semantics which were inconsistently implemented resulting in miscompilations
* Paper proposes removing `undef` and adding a `freeze` instruction which returns a nondeterministic value for `poison`

https://internals.rust-lang.org/t/proposal-bounded-continuations-non-local-control-flow-without-the-mess/4270/3
* Rust proposal for one-shot delimited continuations which leverage borrow-checking to ensure the continuation doesn't escape the scope
* Related JS proposal: https://github.com/macabeus/js-proposal-algebraic-effects

Hyrum's law: "With a sufficient number of users of an API, it does not matter what you promise in the contract: all observable behaviors of your system will be depended on by somebody"
* Two approaches to mitigation:
  - Chaos engineering, ie intentionally injecting "failures" to encourage the design of fault-tolerant systems
    * Example: Unspecified flag bits are randomized instead of zeroed (bonus points if the randomization is randomized)
    * At a language level, this is even more poweful (see: LLVM undef). An interface with undefined behavior and user code which handles it improperly can be intentionally poisoned and caused to fail.
  - Strong typing, limiting the number of observable behaviors which can be acted upon
    * Rust strong typing (vs C++ subvertable typing) ensures that state enumerations are exhaustive