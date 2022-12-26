Espresso as a language is designed to be a highly optimizable high level language. Its syntax is based around generalizing existing patterns in order to simplify the grammar: simple generalized rules, arbitrary complexity.

Part of both optimizability and simplicity is bootstrapping its own compiler. This way, its standard library serves as the defacto implementation written entirely in itself comparable to PyPy. Unlike PyPy however, we're designing the language from scratch so we don't need metatracing to make optimization possible.

Abuse a Lua-like ignorance of extended ascii, using 0x80, 0x81, and 0x82 as DLE, SO, and SI respectively. This has the benefit of a much simpler ctype check and takes care of embedding UTF-8 directly rather than trying to convert to hex. According to the UTF-8 spec, these characters can only occur in continuation bytes anyway, and so should be invalid according to UTF-8 rules normally.

GC:
* Global
* Inline - none, bool, int, real, char
* Mutable - buffer, list, dict, Long
* Fixed - object, array, wrapped
* Immutable - string/bytes, tuple, function, closure, native

Dynamic memory implemented as a binary heap with a reference to its unique owner. This allows them to be relocated at-will. Some ostensibly dynamic objects can be implemented as if they were static, eg long objects because they're defined to never have more than one reference (assignment copies memory)

Base design of the variant type on 4-byte words
* On 32-bit platforms pointers are unencoded
* On 64-bit, use cell-relative addressing (vs arena-relative addressing which uses a global address which may not be in cache. Many of the issues with cell-relative addressing are resolved simply by 1. only allowing references to objects, not cells and 2. having a heap-allocated wide pointer for references outside the range)
* This avoids excessive waste, as normal scripts shouldn't exceed even a few MB, much less 4 GB.

Strings are split between two different cases - interned, and normal. Interned strings are expected to never go away and include documentation, metadata, and keys. They're specifically for cases where we don't care about the contents of the field, only the identity. Normal strings are for everything else, from ordinary string literals to concatenations and formattings. Basically anywhere we're dealing with the contents and not the identity.

Destructuring syntax implemented naively would have infinite lookahead, which is unacceptable for the language's design. A much better solution is to parse a destructuring expression as an object, keeping track of whether or not it's a valid lvalue, and deciding after the following token whether or not it's going to be used as one. A similar issue is encountered with arrow functions. If we parse it like JS, we don't need lookahead per-se, but we still need an intermediate structure which is converted at the end to either function parameters or a parenthesized tuple. However, if we use the same construction as destructuring this becomes similarly trivial - the only side effect is that it's more permissive than JS

Observation: Function declarations are almost never reassigned, and there's already an available sytnax for making a reassignable function (var x = function() {} or even var function() {}). Having function declarations be const by default enables a lot of optimizations without costing anything. Basically, type information can propagate without having to account for the underlying function being replaced.

Take a page from C#, have an "unsafe" context as well as "strict" (which C# doesn't have, it's always strict) - unsafe enables pointer types and operations. A file containing unsafe code MUST be imported using "unsafe import" or else precompiled with an unsafe flag

Object model notes
* Types are reified and have their own operators, but the current algorithm is:
  - lhs->lhs.proto::op(lhs, rhs)
* Operators are looked up on the prototype in part as a safety feature to prevent passing malicious dict with operator properties eg {"+"() doEvil()}
* Prototypes are used as a generic delegation pattern. If a property isn't found on an object, its prototype is checked as a backup. The equivalent of a parent class is a prototype, but this simplification also means that prototypes are technically instances of their own prototypes and inherit all the same operators

We can get C++ concepts basically for free using operator overloading on metatypes and allowing arbitrary predicates rather than restricting it to the particular class hierarchy

Function predicate composition is trivial if we treat functions as their bodies eg:

`x + y == (...args) => x(...args) + y(...args)`

We want type predicates to have two basic properties:
1. overload "is" operator acting as the predicate
2. overload "as" operator to convert a value to one which satisfies the predicate

It's really surprising just how much can fit this definition unambiguously. For instance, literals like integers overload both representing comparison and a function returning the number. Lists call each recursively via iteration and destructuring rules, so using [a, b] just works as you'd expect.

Optimization opportunities arise with shadow state - that is, state that can't be seen by the runtime. We do need to sculpt this state carefully to ensure we don't hide state we might want to reflect on in common or useful cases. This is the line between static and dynamic code which we're carefully skirting. Making module global variables shadow state by default, requiring explicit exports to be exposed, is a big part of this.

Increasing the number of latent variables is a big influence on the decision to have a default-static namespace. Latent variables are only ever accessed within a scope, so their access can be reduced to slot accesses and even further reduced to stack or register allocation. It lets us trivially guarantee that we know everywhere the variable is accessed, unlike a dynamic scope where it's always possible that a variable could be accessed by code which has access to the scope

One property I'd like to have is for modules to effectively be self-compiling. That is to say, when a module is imported for the first time its top level code is executed, then whatever is returned can be serialized and used not just as a cached value, but in a totally new VM instance ala an object file. Python just caches the bytecode of a module, not its result, so the top level has to execute every time a new VM is started. We could potentially also use this mechanism to store profiling information so the JIT doesn't start cold

I thought of a good name for this, in line with C++ idioms: "execution is compilation", or maybe "import is compilation". Anything in the global scope of a module is executed at "compile time", and things which are naturally deferred (function bodies, constants, etc) are the "runtime".

The mental model I'm using for module construction is that export (public?) statements define the own properties of the module, and the object returned is set as the module's prototype

static/inline blocks. That binds the result of an expression at parse time. eg, 

function meta_add(c) {
	return function add(x) x + c;
}

... due to the identifier c never being reassigned and being trapped in the scope,

function meta_add(c) {
	return function add(x) x + static c;
}

though this might suggest that the constant be baked into the code rather than as a closure. This also suggests the reverse, a dynamic keyword which basically escapes the code to be executed at runtime. Alternatively we have \(...) with similar semantics as :(...) in Julia

function(d) static {
	const c = do_something(d);
	\(x + static c)
}

Value/literal types like int, bool, string, etc could have .call implemented to just return `this`, making them essentially self-evaluating functions. This is useful for a pattern like ls->map(true) which will replace all entries with "true" unconditionally. Eg true() === true

public: Enumerable, accessible on object
protected: Non-enumerable, accessible on object
private: Non-enumerable, only accessible on this or obj->. and implicitly declares a symbol

namespace name { ... } declares and executes the body and puts the resulting namespace in name
namespace(obj) { ... } has JS `with` semantics, execute the body with obj as the namespace

both in expression form will return the result of the body with equivalent block value semantics (return or last-value)

obj->define("name") {
	public: bool,
	const: bool,
	property: bool,
	value: any
}

The prototype chain should be immutable, as mutable prototypes confuses the semantics and has minimal usage while simultaneously requires a massive amount of complexity to keep consistent with the optimizer. This also guarantees prototypes form a DAG

This indicates to me that there's a case to be made for not having the : syntax for type annotations, but just use `is`

Keep thinking metadata should be stored in a completely separate pool which points to its owner rather than owner pointing to the data. That way, the owner object doesn't need to maintain the reference internally and getting rid of the data has no effect on other parts of the code. func.docstring vs docstring_table[func]. This is also more wasteful of memory however, as references to the owning object are less localized and thus take more bits to represent and at best it keeps the object's namespace more clear. Why not just make it a protected property with some protocol symbol? Good reason, it requires injecting documentation data into an object while it's being created, while an external registry can have it added after the object is created.

I think we should have a yield keyword, and a yield method (more keyword reuse). Yield keyword inside a function makes a stackless coroutine, which is useful for iteration. Stackful coroutines switch via the yield method which is called on a coroutine instance (either coro.yield or coro->yield). Thus we can keep the performance benefits of stackless coroutines, which are much lighter-weight and useful for applications like iteration (where yielding in a function call makes much less sense) while also providing support for stackful coroutines without needing special syntax for specifying their target (which is just the `this` parameter).

To further drive the point home, don't have special methods or syntax for iteration (python's iter and next). Rather, call the stackless coroutine to instantiate it, then subsequent calls on that object return the value of the next yield. This means the language treats it like a normal functon rather than something special, all while using only one method we already had (call) rather than introducing two brand new methods (iter and yield). In this way, a generator can be considered a kind of stateful function which returns different values on each subsequent invocation. This should make composition MUCH more powerful.

---

I realized my current idea of bootstrapping is actually ill-suited for this project. I was looking at bootstrapping in the traditional sense, where the original language is, at best, assembly and you want to write as little code in it as possible. But our original language is Python, so rather than writing the same parser a minimum of 3 times, we can write a subset and test the parsers incrementally using concrete goals:
1. Write Espresso parser in Python which outputs AST ✔️
2. Write AST interpreter in Python (in progress)
3. Write Espresso parser in Espresso which outputs AST
4. [Concrete goal]: diff AST from Espresso and Python implementations
5. Implement grammar features in both parsers concurrently
6. Write bytecode interpreter in Python
7. Write bytecode compiler in Espresso
8. [Concrete goal]: diff bytecode generated using AST interpreter and using bytecode interpreter
9. Write bytecode to assembly compiler in Espresso
10. [Concrete goal]: diff bytecode generated using bytecode and assembly
11. [Concrete goal]: diff assembly generated using bytecode and assembly

What do we actually want at the end, ultimately? A self-hosted JIT compiler for espresso with near-seamless integration with systems languages like C, C++, Go, and Rust. It is a dynamic language with the most dynamic bits people normally don't use stripped out (dynamic scope, exporting entire mutable namespaces, mutable prototype chain) - all these represent massive security surfaces, pessimize optimizations, and eat up a huge chunk of normal JIT engines. All for features with minimal usefulness and even more minimal usage. Making these static ensures that at least some code can be properly optimized without profiling. Even types can be explicitly specified so the programmer doesn't pay for dynamic typing they don't actually need (or want).

The way it should be used, as I envision it, is in one of 3 forms:
1. embedding via host language transpilation
2. host linking to AOT-compiled object files
3. as the host, linking to foreign object files (eg Python ffi)

I'm not completely sure, but I think I should be able to AOT most of espresso filling out the last most dynamic bits with a bytecode interpreter. Reason being, all the structures it uses are essentially static with dynamic behavior being implemented on top of static structures. The meta-type `var` is basically just i64 with a lot of tagged union stuff and linking to the GC.

Possible optimization issue: right now operator overloads can be any callable, but this potentially introduces arbitrary levels of delegation vs if they were restricted to just being functions. We could possibly optimistically assume they're functions and then deoptimize any time a non-function is found?

@[attribute, attribute] possible compiler attribute annotation (zero-cost signals to compiler as opposed to annotation which requires a function)

May want to consider reserving some comment formats:
* #! on line 1 should definitely be reserved for shebang
* ### Single-line documentation
* #** ... *# documentation comment using Doxygen syntax
* # -*- for emacs file variables / vim modeline

Espresso i18n can be implemented in stages:
* Per-language parsing which compiles to the common bytecode IR, high enough to decompile with debug symbols
* Static symbols and strings of a file can be automatically extracted, then manually paired with their translations in an i18n file
* Documentation comments use Doxygen format, which can also be extracted, and are referenced by the object they're attached to
* Files can have a language code to indicate the language it's written in, affecting automatic import lookup which prefers the native language first, then generic. This also allows APIs to expose different abstractions and interfaces for different languages

Generally we want to ensure only the i18n you want is handled at any given time. A French programmer has no need for the Japanese debug symbols, and it makes no sense to dedicate memory overhead and binary size to those symbols.

The generic applicator operator -> only really makes sense for function calls, so it might be a good idea for it to implicitly call with no arguments when none are provided, eg gen->iter calls iter with gen as this

https://github.com/pelotom/immutagen
* generators should be cloneable

Thought of a way to do variable function signature preprocessing/checking. The problem description is that given a function with an arbitrary number of arguments with type checks, some of those type checks/coercions may be unnecessary because of locally known type data. But we don't want to have to generate a new function call header for every combination of known types, so ideally there should be one robust function header that can handle the base case which we can modify for more specific types. We need to be able to adjust an arbitrary number of arguments in a set. Order doesn't matter, just the binary relationship of "known" vs "unknown" types. This is a bit like duff's device, where we have between 0 and n expressions we want to evaluate with minimal overhead. The best implementation I can think of is to encode the known types as a binary vector in an integer and add a jump before every section which checks the corresponding bit. Eg:

asm {
	; Testing for the first argument is unnecessary because if we jump to it, we already know it needs to be adjusted
	testb 1, %0
	jne 1f
	know_no_args:
		.adjust_arg0
	1:
	testb 2, %0
	jne 2f
	know_arg0:
		.adjust_arg1
	2:
	testb 4, %0
	jne 3f
	know_arg0_to_1:
		.adjust_arg2
	3:
	know_all_args:
		.function_body
}

This way, we have one function header which can handle any number of argument adjustments and we can optimize calls into it by jumping to the first argument that may need adjustment. For a function where all the types are known to be correct, it can jump directly to the function body. For the highest level of optimization, the caller can manually adjust the arguments and call the function directly.

If imports with very strict requirements can execute at parse time, we can add arbitrary compiler extensions (with special considerations for the safety of that). For instance, a library called "metasyntax" could implement keywords to define keywords, operators, and literals. This is highly desirable because it lets us have Julia-like flexibility for operators and names without baking those into the core language.

Assignment operator probably shouldn't be overloadable dynamically, but might be useful to implement for static type annotations.

The new operator might actually be antithetical to Espresso's values. It's nontrivial to parse (it's technically a compound prefix-infix operator because the call is part of the operator) and it provides no expressive benefit vs literally equivalent code eg `new int` vs `int->(typeof int).new()` (espresso fundamentally cannot distinguish these two forms). Thus, it's probably a better idea to go with Python/C++'s constructor call syntax with a .new method used under the hood for GC stuff (see Python's __new__). There is the detail of prototyping, where in some iterations of the semantics I consider `new` to be the prototyping operator...

Rust has quite an interesting take on variable declarations in conditions and in general. Currently in espresso, declarations evaluate to the last variable. C++ does this with one variable, and it's a syntax error for multiple variables (though a ; can be used to give a condition). In Rust, all variable declarations aren't just either a declaration or a destructuring assignment (like espresso), but rather they are *always* destructuring assignments, and it's a syntax error to have an irrefutable pattern in an if statement. In fact, initializing multiple variables is also considered a destructuring. Refutable patterns in if statements execute the block if the pattern matched, else it executes else. This is significantly more powerful than what I was doing before, and I can keep the current C++-y syntax of `let x = y` because Rust's model explicitly forbids irrefutable patterns. This is irrefutable, so instead it evaluates it as a boolean.

We can leverage this in Espresso quite nicely I think, without even necessarily changing the syntax (just a change in perspective). `let x = a, y = b, z` for instance doesn't have to be considered a special syntax because it's equivalently a destructuring expression / pattern with the "assignments" being defaults for a nonexistent rhs. Rust also supports typed pattern matching (like Python) which we could possibly include because it (just barely) doesn't conflict with the function declaration syntax, which immediately starts a block whereas type patterns would be followed by either = or ,

PEP 204 is a rejected proposal for a range syntax using the same syntax as indexing, but as an atom. This would have high value in espresso, not for expressability (we already have ..) but rather for syntax simplification, since list literals and indexing are considered separate parses.

Rust uses ! for bitwise negation, and the more I look into it the more I kind of like that, especially because of the next note. It has symmetry (I was going to define bitwise operations on booleans anyway) and means we have ~ as a totally unused character where otherwise it would be used for a pretty dumb purpose.

Rust only has && and || while I want to support keyword forms as well. I definitely don't want to require overloading them twice, but no other operator has two aliases like this and I would also like the possibility of overloading them for a numpy-esque use. Maybe && and || are overloadable, but the keywords aren't and implicitly use boolean values? This could cause confusion later though. Also the case for Numpy overloading those isn't very good, since a boolean array can just use the bitwise operators and having a whole operator just for coercion is dumb. So it's probably best to just have `&& || and or not` all as non-overloadable short-circuitng boolean operators like I was thinking before.

We could support comparison operators for metatypes to create a partial ordering, although this leads me to wonder if there would need to be (and if there exists in the literature) a "comparable" operator, that being an operator which returns a boolean whether or not the two types can be legally compared. For instance, in this case two siblings of a parent prototype would be incomparable and thus the result of their comparison is undefined by necessity.

super keyword is necessary because it's not semantically equivalent to this.proto() - it depends on the type of the enclosing prototype, not the this.

Very important to record this lest I forget - the virtual behavior of objects with a static type should be determined by that type, not by the data pretending to be the type. That is to say, if I have a type annotation T, all getattr, method lookup, and general behavior should be routed through T first. That way, the overloadable behavior you get with classical type systems can still be implemented by the type opting to introspect on the data to check if it has an overload. The sticking point that is keeping me up right now is how to define a type's interface without interfering with its own methods and operator overloads. In a sense, types fulfill yet another Rustian role which we have to figure out what shape it is. Also, this needs to be opt-in such that it doesn't interfere with the predicates which enable C++-like concepts, which generally won't be able to implement any specific... implementation for the native manifestation, since they're basically just assertions/contracts.

It needs to be able to:
* Convert objects to a manifest native type known to the compiler (i32, struct, enum, etc)
  - .native() ?
* Implement all valid operations on behalf of the object via its manifest (at minimum getattr, which can bootstrap all other operations)
  - ideally separate getattr and callattr because calling methods is syntactically no different from getting an attribute, but might have wildly different implementations

Well, any of the built-in types are pass-by-value inherently. Even if you overload the methods on them, there's no way whatsoever to determine the overloaded methods except via the type. So they act as the perfect model for type-oriented behavior. That begs the question then, how does property lookup on behalf of the value via the type work when the type is itself a value? Any methods we put on the type are owned by that type and aren't appropriate to expose like that. It's sort of a unique problem that espresso has because of its prototyping, so I doubt I'll find any examples of something similar in the literature. It's a lot like the thought process which led to the split class-instance prototype chains.

Types can provide a .delegate(x) method which returns an object which all operations are delegated to. This lets us define operations and behavior differently just based on the type annotation, and allows customization of the overloadability of behavior. This is particularly of interest for the compiler intrinsic types which cannot have prototypes by definition, so they need a delegate out of necessity. Some common delegation patterns:

# Constant delegation
let delegate(x) => this.some_delegate;

# Self-delegation, default behavior for prototype-oriented programming
let delegate(x) => x

More exotic delegation models are also possible. Note how this gives us complete control over how behavior can be overridden - if I have a type which I want to treat as "closed" to extension, I can use constant delegation and at least have the guarantee by the type that it's compatible. Any behavior of a child of the prototype which it overrode the original behavior is ignored and its original behavior is used unconditionally. Thus we get something equivalent to `final` without breaking prototyping and preserving the optimizations of `final`. C++ can vaguely do this with value semantics, since those explicitly don't support virtual method overloading, with the caveat that you're passing the whole object. It might actually be a good pattern to make virtual inheritance opt-in via a `virtual[T]` template.

proto virtual[T] is T {
	delegate(x) => x;
}

The motivations for multimethod dispatch are:
* Functional styles (lacking objects and type polymorphism)
* Mathematical operations are inherently polymorphic (adding integers vs adding matrices)
* Complex extensible type interactions
* Code specialization

Rust accomplished all of these motivations through the use of trait "associated types". It distinguishes "input types", which select the implementation (and give it static multidispatch characteristics) and "output types", the "associated types", which complete a trait's interface for eg the return type of methods. There doesn't appear to be a way to use this for dynamic multidispatch, however.

Function overloading could be accomplished by, at worst, a custom trait and the function implementation. The function having a common name is mitigated by variable shadowing, so if you want a broader implementation you could simply redefine it, possibly referring to the original with a fully qualified name.

The delegate method as described above has huge implications for multidispatch in espresso. It constrains types by default, such that dispatching on normal types is a trivial comparison rather than some complex prototype lookup. That puts the onus of dispatch on the type itself, so we would want to explore how virtual[T] might implement it.

Rust explicitly removed ++ and -- because they add language complexity and require knowledge of evaluation order which may not be obvious. For instance, what is the result of `i = i++`? As a syntax sugar it saves almost no characters, has unclear semantics for anything other than integers, and most of the uses in C (pointer arithmetic and explicit iteration via for loops) are outdated. Apparently Swift added the operator and later *removed* it for similar reasons. Python never supported it for the same reasons.

Since I'm removing ++ and --, I may as well remove a few other redundant operators, `||` `&&` and `^^`. `||` and `&&` are obsoleted by `or` and `and`, I don't really miss them in Python and I do kind of miss the keywords in JS. They also suggest using `!` for boolean not, which is going to work sometimes but not always. `^^` was only added as an extension to the pattern but without any attached semantics. I might consider removing `%%`, but I kind of like the idea of using it to denote signed modulo, as opposed to % which is unsigned remainder. That's nice because for C/++ until C99/C++11 it's completely undefined which one it is, based on hardware support, then eventually % was defined as truncation (unsigned remainer). This has precedent with CoffeeScript and NASM as well. Lua and Python oddly define % as signed and have no alternate operator.

Another syntax simplification I should remember to look into is Rust's usage of the range operator `..` for slice syntax, allowing indexing to be parsed without the `:` punctuator.

`let f(x: string): string { ... }`

Rust lifetime elision will handle this because there's only one lifetime to associate the return with.

`let f(x: string, y: string): string { ... }`

Rust lifetime elision won't handle this case because x and y have different lifetimes. For instance,

```
let f(x: string, y: string) {
	if(rand() % 2) x else y;
}
```

What is the lifetime of the return value here? Dyon has a fantastic addition, the "return" lifetime specifying a lifetime which outlives the function call, effectively a shorthand for `fn f<'a>(x: &'a str, y: &'a str): &'a str { ... }`. Important note for my clarification, lifetime constraints specify that the constrainee OUTLIVES the lifetime, which makes my `..lifetime` syntax a bit counterintuitive.

let f(x: string, y: x..string) {
	
}

Rust lifetimes have different meanings in different contexts. A Rust lifetime in a type definition means an instance of that type cannot outlive that lifetime. A Rust lifetime on a variable means that variable must live at least as long as that lifetime.

I think lifetimes with the same depth as Rust are probably counterproductive for a prototype-based language, since in its conceptual memory model everything exists in the heap (this is not true for espresso, but espresso treats it as if it's true), and Rust seems to struggle with even acyclic graphs (via pointer-in-struct implementations), let alone cyclic graphs as the defining structure of the language. Everything is linked to everything else, but a key observation is that the vast majority of objects are only referenced once. A simple check of Python shows 8556/9948 (86%) have 3 references, the minimum due to incrementing in viewing the refcounts of all those objects. Only 5% have 4 references, and the rest are exponentially lower. If we could implement borrow semantics, such that we can guarantee that an object passed by borrow semantics won't have its address taken, then we could implement most objects as a one-bit refcount (one reference vs unknown references). Along the lines of mutability, it would probably be ideal to have borrowing to be the *default*, so that stealing/sharing a reference is opt-in. First example, take a constructor. It returns a unique[var T], thus the caller is considered the owner and can do whatever it wants with it.

Point.new = new(x, y): unique[var Point] => {
	gc.new(Point.sizeof()) as Point after.init(x, y);
}

This needs work though, as the call to gc.new would seem to disable RVO without some kind of compiler magic which we want to avoid. This is to be expected, because this setup is implicitly a heap allocation anyway. Even if Point is a struct, the return type would have to be unique[...var Point]. In that case, struct should probably have value semantics by default, with object being its heap version. Then the return value would be just Point. That would mean we'd want a way to allocate a struct on the stack and use it without initialization. Rust used to handle this with mem::uninitialized(), but deprecated that in favor of a safer version MaybeUninit<T>, which is implemented as a union (unsafe) of an empty struct and the type and initializing the empty struct. I think it should be fine to just ape the original as an intrinsic and implement similar semantics. So then struct implementation would be:

Point.new = new(x, y): Point => {
	let self: Point = unsafe.uninitialized();
	Point.delegate(self).init(x, y);
	return self;
}

Though in practice, struct would initialize all the fields before calling init. That can be inlined, thus eliminating the unnecessary initializations.

I keep waffling on how to handle exceptions. I like the Rust model in theory at least, and it works well for them because return types aren't optional and deliberate thought is encouraged, but when I experiment with how that feels in espresso's parser it feels like the failure handling is smeared across my code, reminiscent of "viral" async/await which I put thought into eliminating. There's another oddity too, in that I have dynamic typing available to me while Rust doesn't. What this means in practice is that two-option sum types like Option and Result aren't clearly separate, or at least don't have to be. I have none, which can easily represent Option's None() but without the typing of Some(). Thus handling an optional type tends to check for none rather than in Rust where Some is unpacked and the pattern has a boolean value.

Something we could try for Option at least is to make matching overloadable (like Python's __match_args__) and then provide a Some() pseudo-type which can unpack not-none. Thus option becomes semi-privileged in the language as a type that's almost implied by `any` (`var`?) without having to explicitly annotate everything. It also supports returning none as a valid value via Some(none).

I tried the "try expression" suggestion (section 4.5.1) from Herb Sutter's "Zero-overhead deterministic exceptions: Throwing values" and my god, it fixes everything. Just like that, I get controlled exception handling without magic and without doing it manually. The semantics for this are a bit different from the proposal, since my goal isn't C++ interoperability. The try operator, instead of a pedantic label to keep the compiler happy, is equivalent to the rust ? operator. It unboxes a result type, and if it isn't Ok it propagates the error. It's interesting to see the clear distinction between code that fails and code that doesn't. A lot less throws than I would expect. There will need to be a tiny bit of magic for proper ergonomics, because adding `| fail` to every type annotation feels silly when I can already know for sure just by checking for `try` or `fail` in the body of the function.

`try x()?.y?.z;`

This would call x, test if its result or any of the other properties are fallible, and if any are then the whole subexpression is `none`. Then, `try` would detect `none` and return, or else it would be a no-op. This would work with plain none or even errors, though it does imply that the result should be Option rather than just none. Or I guess, Result

`let Ok(b) = a else return;` or `let Ok(b) = a else Err(e) => return Err(e);`
Got this suggestion from a Rust RFC

As for the type of the return annotation, it seems like it should just be `T | fail[E]`, with this overloaded to return `Result[T, E]`. The failure annotation is implied, but we need rules to guard against when the result type is explicitly annotated (in which case the result type would have an Ok with a result type). This could just be `is Result`, but I dislike locking it to inheritance. We can't make it `has "fail"` because that would cover resumable function types or `has "try"` because we sort of want that for method calls. Maybe a marker trait? `is Fallible` or something?

Iterator interface:
iter[T]: () => () => T?

What if proto used pattern matching syntax?

proto Result[T, E] is enum {
	return(T), fail(E)
}

Note that these are not function definitions because they have no defaults (the function body)

proto Test is struct {
	x: int
	let y: string = "hello";
	@public
	z;
	a = 10
	@static
	var counter = 10;
	
	method(x: string): Token? {
		
	}
	
	let f() => {
		
	}
}

Jesus, the pattern syntax is absurdly flexible

Big note: Python actually has Rust-like traits (Haskell typeclasses) via the name Protocol.

class OldMatch:
	@classmethod
	def __match__(cls, value):
		if not isinstance(value, cls):
			return False
		
		__match_args__ = value.__match_args__
		
		while True:
			key, value = yield match
			if type(key) is int:
				key = __match_args__[key]
				assert type(key) is str
			
			if value is MatchMissing:
				match = value
			elif getattr(value, key) == value:
				match = None
			else:
				return False

Compiler primitive list (again)

none true false
bool i8 u8 i16 u16 i32 u32 i64 u64 f32 f64
fn ptr [T..n] tuple
unreachable

To implement on top of these:
object list tuple closure var char
metatype class trait enum/variant union
shared/weak = refcounted
unique = only one
box = gc managed
ref = borrowed, cannot be persisted

string might need compiler support because it's an opaque abstraction over a few different types (direct reference, interned, concatenation tree) and has a lot of syntax support

proto list[T=any] is class {
	@private
	data: unique[T..];
	
	@private
	length: usize;
	
	let len() => this.length;
	
	var push(v: T): none {
		let len = this.len();
		if(len + 1 >= this.data.len()) {
			data.realloc(len + len/2);
		}
		this.data[this.len()] = v;
		this.length += 1;
	}
	
	var pop(): T? {
		if(this.len()) none;
		else {
			this.length -= 1;
			some(this.data[this.len()]);
		}
	}
	
	let getitem(var item: i32): T? {
		if(item < 0) {
			item += this.len();
		}
		if(item > this.len()) {
			none;
		}
		else some(this.data[item]);
	}
	
	var setitem(item: i32, value: T): none {
		this.data[item] = value;
	}
}

https://www.youtube.com/watch?v=raB_289NxBk
* Pattern matching with is/as
* Subcasing: contract shared clauses

```c++
is Shape && is red => a();
is Shape && is above(x) => b();
```

can be written as:

```c++
is Shape {
	is red => a();
	is above(x) => b();
}
```

```c++
inspect(x) {
	is integral {
		i is int => { cout << "Type: int" << i; }
		is _ => { cout << "Concept: non-int integral"; }
	}
	[a, b] {
		is [int, int] => { cout << "2-tuple: " << a << " " << b; }
		is [0, even] => { cout << "[0, even]: b = " << b; }
	}
	[a, b, c] is [int, int, int] => { cout << "3-tuple: " << a << " " b << " " << c; }
	s as string => { cout << "string: " << s; }
	is _ => { cout << "no matching value"; }
}
```

Herb's proposal covers all these cases, and I'd like to investigate how I could adapt comparable syntax. He makes a big deal of how it uses exactly the same pattern as the equivalent if-else, so inspect, pattern matching, and destructuring are all isomorphic. Also note, LHS declares a name, RHS uses an existing name for both is/as.
```
which(x) {
	case is integral and {
		case i is int => console.log("Type: int \{i}");
		case => console.log("Concept: non-int integral");
	}
	case [a, b] and {
		case is [int, int] => console.log("2-tuple: \{a} \{b}");
		case is [0, even] => console.log("[0, even]: b = \{b}");
	}
	case [a, b, c] is [int]*3 => console.log("3-tuple \{a} \{b} \{c}");
	case s as string => console.log("string: \{s}");
	case => console.log("no matching values");
}
```
Note that `which` syntax is actually more general than ordinary pattern matching because it supports alternative control flow.

[x, 10, y is T, z as U in ls = default if b, predicate(x)]
{name: predicate(bind is T in ls) if bind > 10, x}

Interesting to note, : punctuator is only used for name binding and makes no sense as an alias in other pattern syntaxes. And yet, : is used to declare the type of a variable when the same is done with "is" in patterns. I would say it is nice to have as a bit of syntax sugar, saving 2 keystrokes (": " vs " is ") and reducing the cognitive overhead, specifically for irrefutable patterns. There's already a precedent for irrefutable patterns being treated differently in C++ style if variable declarations.

What if I want to use multiple predicates? Probably just use guards then tbh

and/or doesn't really make sense for patterns because they explicitly delineate separate code paths

Traits are a kind of extensible method. In Rust it's interesting because the vast majority of traits only implement a single method and are used primarily for implementing polymorphism in generic functions. Take the Copy trait for instance - all it does is say anything which implements it is copyable, and converting an object to a copyable can effectively be considered the equivalent of C++ template specializations for strategies.

trait Copy: Clone {} // Rust uses Copy as a marker trait rather than letting users overload copy behavior. All copying is bitwise. Conversely, overloadable copy behavior must be done explicitly using Clone

pub trait Clone {
	fn clone(&self) -> Self;

	fn clone_from(&mut self, source: &Self)
	where
		Self: ~const Destruct,
	{
		*self = source.clone()
	}
}

Multimethod dispatch can be done on the argument tuple, and it can be reduced to a which-case expression with pattern matching. There is no semantic difference whatsoever except that the which-case is closed while multimethods are open. It can be made more optimal using our unique treatment of type annotations as final by default and opened by virtual, thus typechecking is a simple comparison without searching the prototype chain

let iter(this as Iterable): Iterator {
	
}

let +(lhs: i8, rhs: i8) {
	
	asm {
		i8.add()
	}
}

O(N) prototype "is" dispatch: Hashtable, iterate backwards through prototype chain checking H(proto) against the hash table until a match is found or you reach the virtual root. Explicitly annotating virtual dispatching also means search is bounded to the properties we actually care about, rather than requiring to search the entire prototype chain.

Another thing we need to look into is the differences in pattern matching syntax for predicates and explicit type checks. {some(x), x is some}. One key difference, the predicate syntax can take multiple arguments which are destructureable. Arbitrary predicates might not be a good idea here then, probably just use is or guards. Also I whiffed, above I said and/or doesn't make sense in patterns, but it actually does for variants eg `'q' | "Q"`. Need to re-examine that.

Also revisiting the protocol of matching:

Thing(x, 10, [a, b]) = v

let case(v) {
	None <- yield ?? == Unknown what to yield, returns None indicating match wants the next (first) value
	Some(10) <- yield Thing.0 == Yielding Thing.0 as requested, returns 10 indicating the next value should be 10
	None <- yield ?? == Unknown what to yield, returns None indicating want next value
	?? <- yield Thing.2 == yield Thing.2 as requested, unknown return (resuming past expected pattern)
}

So, probably best then to make it yield Option on both ends.

Thing(x, 10, [a, b]) = v

let t = Thing.case(v);
if(let Some(x) = t(None)) {
	if(let None() = t(Some(10))) {
		if(let Some([a, b]) = t(None)) {
			body...
		}let a
	}
}

Let's look at list(a, b, c)
proto Option[T] is trait;

proto enum Option[T];
proto Animal;
proto[T is int] Option[T];
proto fn(int) => string;
proto[T] ref[T] reference {
	
}

proto Clone[Message] {
	
}

proto Pattern[T] is enum {
	Unpack(T),  # Match yields a value to be unpacked by the pattern
	Match(bool) # Boolean if provided value matches, if false the pattern fails
}

Option[T] yield Match[T] # Return Option[T], Some(x) for value to match and None for "provide next value"

list.case(v) {
	var result = Match(v is list); # First result is whether or not v's type is correct
	
	for(let next in v) {
		if(let Some(val) = it.next()) {
			result =
				if(let Some(value) = yield result) {
					Match(value == next);
				}
				else Unpack(next);
		}
		else break;
	}
}

There are still some pretty severe limits of this though. You can't pass compound literals to it because those would be destructuring - though a relaxed syntax could allow lhs of a call expression to be an r-value. eg `equals_list([1, 2, x, v])(x, y, z)` would evaluate `equals_list([1, 2, x, v])` first, then destructure on `(x, y, z)`.

`regex("(.)")(m0, m1)` is a good example for a use-case, arbitrary regex unpacking to its two matches (might want to pass # of unpacks to operator too)

I want to look into the type syntax for function types. We've sort of hand-waved it until now as something we could do special parsing for in the type context, but this is something that espresso generally doesn't accomodate - there isn't really supposed to be special parsing contexts where operators have different interpretations, it's supposed to use the same syntax for everything (particularly because stuff like the <> operator for types like C++ and Rust isn't possible to parse without compile-time knowledge that the lhs is a type and initiating a special parse context). This isn't possible in general even if we allowed a special parsing context because we want to support arbitrary expressions in the type annotation, so there'd be no way to tell a function type from an anonymous function being evaluated.

One possibility is we could introduce a keyword just for function type definition, something like fn(int, bool, string) => Result. This has precedence from Rust, but that keyword would be valid everywhere. Rust doesn't care since it uses fn for function declaration, but Espresso uses var/let. I could accept fn as a keyword for declaring functions as well, but then it couldn't be used for types anymore because it'd be declaring a function in the type again. The other option is a little uglier, but definitely more unambiguous - I could use fn or equivalent as the base function type template and just index it like normal, eg `fn[ret, (...params)]`. This is simple, but has a big downside which is that the parameter types and return type are in reverse order from their declaration in source. Alternatively we could use `fn[(...params), ret]` which is also fine, I think I was avoiding that because without that tuple of parameters the single return type because the "last" value which is a bad idea, but with this it's just the second parameter which is fine. It's still ugly tho... We could do something weird like `fn(...params)[ret]`? Actually both these syntax variants break on varargs. We really do need a keyword then, because there's no way to parse vararg types otherwise, they would try to unpack the type into the tuple. `fn(...params) => ret`

transcripts needed app fee, can submit fafsa app during that time

std::expected<> boost::outcome<>

re: @ and Rust macros. @name(arbitrary r-value follows) has runtime Pythonic semantics with a strong pull towards compile-time evaluation. It will try to evaluate as soon as physically possible, so just about the only thing that won't be compile-time is something like @func_parameter.

@[...] is provided for compile-time macros. Its components *cannot* be runtime because it can change the parsing arbitrarily. A @[...] construct which doesn't know all its components at compile time will fail to compile. Note that this syntax technically overlaps with Pythonic annotations, but in practice never does because there is no valid way to interpret the annotation protocol with a list literal.

`@[[...]]` is for compiler intrinsics ala C++ attributes

@(...) @{...} @"string" @0 are reserved and should fail to compile anyway
0x20-0x7E
32-128
96

\`...` interpret raw bytes as a token, should not appear in user-code and only for ASCII parser compatibility
\'...' and \"..." raw string with '/" escape semantics.
\token escapes token as a symbol, typically used for referring to keywords as identifiers. Eg \+.name == "+", without \ the + would be parsed as unary + on a dot function.
* Note that \( is reserved, to use a literal open paren as a name you would use \\`(`. \\ is not reserved, to use \ as a name you would use \`\`
\(...) expression escape, internals are parsed but not executed
\[...] token escape, internals are tokenized but not parsed
\{...} reserved, no defined semantics. Note that untokenized escapes are already encapsulated by \'...' etc
\# reserved, hard parse error (rest of the program no longer parsable)
\@ reserved

Unused ASCII characters:
* 0x7F - preferably kept reserved, possibly usable as a newline signal so our valid range is exactly 96 characters (< 0x20 is space except \n which parser needs)
* $
* ~

"Why iterators got it all wrong - and what we should use instead"
* Iterators inherit too much baggage from pointers, they really overload two distinct concepts

Borders
begin            end
  | v | v | v | v |
  { a , b , c , d }

* Borders cannot be dereferenced
* If not at begin, has element_before()
* If not at end, has element_after()
* std::range begin() and end() are borders
* All output iterators are borders

Elements
* Single entry in a container
* no end(), cannot ++ past the end
* has border_before() and border_after()
* Nullable

Robin hood hashing
```c++
template<typename T>
struct hashtable_entry {
	int8_t distance;
	/* 1, 3, or 7 bytes padding */
	union { T value; };
};
```
Google flat_hash_map uses 1 bit "empty" + 7 bit hash, 16-byte SSE, 85% utilization, and PyPy split hashmeta-keyvalue stores - performs poorly for < 400 and > 100000 on successful lookups, performs well for unsuccessful lookups (comparatively) while using 85% utilization
https://github.com/skarupke/flat_hash_map/blob/master/flat_hash_map.hpp

https://github.com/skarupke/flat_hash_map/blob/master/bytell_hash_map.hpp 93.75% load factor

We might actually need lifetimes, unless I want the reference zoo to be compiler intrinsics.

So, let's say we have 3 kinds of lifetimes: parameter lifetimes, static lifetime, and return lifetime. This is missing at least one lifetime type, the disambiguation of parameters which a function scope owns and which outlive the function. Well, no actually - we could say parameters are return-lifetime by default (they outlive the function), and if a parameter is annotated with its variable's own lifetime then the function owns the lifetime of that parameter.

We could say that ~ is the lifetime operator, has parity with C++ and has the cute interpretation of "tilde ath".

Assertion: Lifetimes unbound to the inputs/outputs of a function are functionally meaningless. Thus, there's no reason to differentiate them.

pub struct Ref<'b, T: ?Sized + 'b> {
    // NB: we use a pointer instead of `&'b T` to avoid `noalias` violations, because a
    // `Ref` argument doesn't hold immutability for its whole scope, only until it drops.
    // `NonNull` is also covariant over `T`, just like we would have with `&T`.
    value: NonNull<T>,
    borrow: BorrowRef<'b>,
}

proto Ref[T: Sized ~T] {
	value: NotNull[T];
	borrow: BorrowRef ~T;
}

What this says is Ref of T owns that T, has a pointer to it, and borrows it indefinitely

fn longest(x: &str, y: &str) -> &str {
    if x.len() > y.len() {
        x
    } else {
        y
    }
}
Invalid Rust, returning a borrowed value but we don't know its lifetime

let longest(x: &i32, y: &i32): &i32 {
	if(rand() % 2) x else y;
}

let problem() {
	let x = box.new(0);
	let y = box.new(1);
	let z = longest(&x, &y);
	steals_ref(z);
	# Do we drop x or y?
}

Here is a toy problem which should highlight the problems with lifetimes. We have two strings on stack, longest does something and returns a borrowed string. We don't know which string is borrowed, then call a function which takes ownership of that reference. At the end of the function, which string is dropped? We'll pretend they don't have static lifetimes and are owned in this function body (say, the result of an allocation).

Swift _modify accessor, uses stackless coroutines to model the inversion of control rather than C++ proxies

proto list {
	value: buffer;
	
	getitem(x: int) {
		let s = this.itemize(x);
		if(Some(n) = yield s) {
			update()
		}
	}
}

Then, `mylist[0]` desugars to `mylist.getitem(0)()` while `mylist[0] = 1` desugars to `mylist.getitem(0)(1)`

Swift supports dual parameter names, eg `func scale(by factor: Double)`, "by" is the name when using a keyword call, eg `scale(by: 10)` while "factor" is the variable name in the method body. Interesting

mydict[key] += val;

mydict[key] += val -->
gen = mydict.subscript(key); *gen.next() += val; gen.next()
gen.next()

mydict[key] += val -->
gen = mydict.subscript(key); gen.next(gen.next() + val)

let (generator, first_yield) = create_gen() # Very symmetric, the arguments passed to the generator are the equivalent of the first .next and all subsequent invocations of generator are passing arguments through yield. The main function arguments aren't actually special, each yield is effectively the start of a new function which can accept parameters. This is also nice from the standpoint of mutability in that the generator state is entirely encapsulated by the returned generator, it isn't an object which is changed mutably. One big downside however is that we're creating this state wholecloth every time when the most common use case (as an iterator/generator) throws away the old value. That is,

for(let x in y) z(); desugars to

loop { let (y, x) = y(); z(); }

noting that the old value of y is completely discarded, and there's no clear way to do some kind of move construction here, destructively constructing the new value in place of the old value.

There is a way that we can preserve the imperative style (avoiding wasting resources on needless state recreation) - the args passed to the function can be the first yield. Creating the generator would then be a call without parameters, returning the generator, then the first invocation is unpacked as the arguments. This could be surprising coming from other languages, where the arguments are directly passed to the invocation, but this can be hidden quite a bit via traits, and generators would rarely be invoked in their own right. It'd be like manual iteration in Python, which can look a bit janky. This does sort of beg the question of what should be done with the arguments which are passed to the first invocation, in which case I think we can possibly take a page from C++'s coroutines and have a kind of context manager signalled by the return value, maybe with some syntax sugar like `yield T` for the common case where it's being used like a normal generator and we want to annotate its yield. Then, the context manager is immediately invoked with the coroutine body returning a custom generator type stored in place of the function, then *that* can be invoked with the arguments creating a generator object. Oddly this suggests that the context manager annotation is a kind of metatype which creates a type, or perhaps a higher order function returning a function (or type).

In that case, there's the possibility that the default context manager could emulate this default behavior as the other languages.

proto Generator[T] {
	init(coro) {
		this.coro = coro;
		this.next = none;
	}
	
	call(...args) {
		this.coro();
	}
}
let generator[Yield, Send](coro: stackless_coroutine[Yield, Send]) {
	return (arg: Send) => Generator(coro)
	}
}

let gen(a, b, c) {
	print("A");
	let x = yield a;
}

let g = gen(1, 2, 3);
Prints "A" before halting.

g("x") passes "x" to x in the generator and returns `a` (1). In this model, the value yielded and the value provided to yield are effectively "swapped", so they cannot even in principle be causally related. This is in direct opposition to the model used by most other languages, where it's conceptually a kind of cooperative multitasking, which is also generally where coroutines as a concept came from in the first place.

We could also conceptually see the first invocation as taking no args, the result of that can be invoked N times. The first time it's invoked is the arguments passed to the function body. This is much less useful than other languages because iteration doesn't generally provide a way to pass arguments to the next method. It's also way too surprising and, at least syntactically, asymmetric.

We could have the generator invocation pass arguments like normal. The first invocation value is ignored, returning the yielded value, then subsequent invocations replace the last yield and return its yielded value. It seems like this is the only way to go without a more functional style, returning the generator 

Possibility: "proto" keyword in destructuring which means to prototype an existing value in namespace with new value?

One oddity of lifetimes, shared_ptr aliasing constructor which creates a shared pointer to an object member with the same lifetime as the primary object.

let longest(x: &string, y: &string): &string {
	if(*x > *y) x else y;
}
In all these cases, a lifetime annotation of ~return works because the reference outlives the function. This wouldn't work in general though, it only works through backwards deduction - a reference is being returned, which means it must outlive the return, which means all possible values must outlive it. Suppose for instance 

var x = 22;
let y = &x;
x += 1; # Error
print(y);

var x = SomeStruct { field: 2 }
let y = &x;
x.field += 1; # Error


Ok, how would we implement 

Polonius borrowck validates via set-subset relations for the set of possible origins a reference could come from, and the set of loans that might be valid. This enables less false negatives.

Suppose

proto Message {
	buffer: string;
	slice: &'buffer [u8];
}

Rust move semantics apply to copying and are called affine types - they can be "used" zero or one times.

proto copy[T] is trait {
	fn copy(this: T): T
}

proto ref[T] is ptr[T] {
	fn [](): never {
		panic("Move from borrowed reference");
	}
	
	fn as(t === ptr[T]) {
		panic("Casting borrowed reference to pointer");
	}
}

proto box[T] is *T {
	fn [](): &T => (this as *T)[];
}

fn test(x: Clone) {}

fn test[T](x: T has clone has copy has move) {
	clone[T](x);
}

proto slice[T] is struct {
	@private data: ref[T]
	@private size: usize;
	
	fn getitem()
}

At this rate, ref[T] may need to be a primitive too, because it's fundamental to the core language model. What is the type of `this` usually? It can't be ptr because that has unsafe semantics inherently. We could copy Rust a little bit and use & and * which are still available as prefix operators. Actually & and * can't be used because they have different semantics for types (creating the higher order type) and values (referencing/dereferencing). tbh ref is pretty good, and with keyword call syntax unobtrusive

Elsewhere Memory by Niall Douglas - attach_cast and detach_cast which start/end an object's lifetime for the duration of a reinterpret cast to bytes. Probably absolutely necessary for safe implementation of memory management. Compare to placement new.

proto[T] enum Option[T];
proto Animal;
proto[T is int] Option[T];
proto fn(int) => string;
proto[T] ref[T] reference {
	
}

proto Clone[Message] {
	
}

proto[T] Option[ptr[T]] {
	
}

Reversing the order of the proto operands like this has some interesting advantages. First, it's slightly more concise since there isn't an extra keyword, and for base types it reads like you're making a new instance of that metaclass (eg proto enum Color {}). Second, it puts the operand first rather than the name, so if the name is omitted it clearly makes an anonymous instance - before, `proto A is B` could be shortened to `proto A`, suggesting a prototype being made with... no prototype? Third, it can double as a type constructor syntax for the really hairy types so we are less burdened to ensure the type syntax has perfect parity with value syntax. Fourth, it makes the trait implementation syntax MUCH more clear without needing an extra keyword, since we can omit the name like we wanted and provide the type to specialize on. 

There is an ambiguity here, the difference between specialization and prototyping an existing generic is not clear. The only difference is the presence of a name to bind it to...

proto trait Clone {}

proto Clone[string] {} # Want this to be a specialization for the trait for string - this behavior requires special care by the trait implementation, returning a proxy which when "prototyped" actually fills itself with the prototyped data. However, the alternative is we dedicate special syntax to this which we don't generally want to do.
proto Clone[string] StringClone {} # Want this to be a prototype of Clone[string] called StringClone

There's something worse for specialization and traits, which is that it necessarily introduces mutability into our metaobject model.

For a bit I was considering implementing [] and . as single operators in their own right, like C++ does, but apparently Rust pretty explicitly uses a split model like Python. There's Index for immutable access and IndexMut was used for a while for mutable access, but they evidently switched to IndexSet, suggesting the single model caused issues. Apparently the big issue was with insertion - if you're trying to use indexing syntax to insert a new entry into a dictionary using the reference model, that entry necessarily doesn't exist and thus no reference can be produced and the code panicked. The only alternative is for the dictionary to default construct members before returning the reference. That can actually change the semantics, since it implicitly inserts nonexistent indexes.

proto[T] enum Option {}
let Option = enum.proto("Option", [TypeVar("T")], {})

proto[T] Option[T] StricterOption {}

let T = TypeVar("T");
let StricterOption = Option[T].proto("StricterOption", [T], {})

---

proto trait Clone {}
let Clone = trait.proto("Clone", [], {});

proto Clone for string {}
Clone.specialize(string, [], {});

proto[T] for Option[ptr[T]]
let T = TypeVar("T");
Option[ptr[T]].specialize(Option[ptr[T]], [T], {})

proto for Option[ptr[T]] is nullable[T] {}

I'm not sure it actually makes sense to allow specializations to choose a different prototype, because `T is T[U]` and eg a function taking just a `T` which is passed `T[U]` needs to be able to delegate property accesses correctly. One could potentially get C++ template semantics, where they can choose arbitrary parent classes, by defining a separate object model such that `T is T[U]` is not true in general and/or an unparameterized T is not a valid type. If that were the case, we'd want some way to catch those errors early because as-is it would probably silently do the wrong thing.

proto metatype template {
	proto(name, tvars, body) {
		let ops = __object_new(this, {
			getitem(...T) {
				this.specializations[...T]
			}
		});
		__object_new(ops, {
			
		})
	}
}

Here's a possibility for specialization, have a dummy metaobject called "impl"

proto[T] impl for Option[ptr[T]] {}
let T = TypeVar("T");
impl.for(Option[ptr[T]], [T], {})

It's a simple fix, but I'm not sure how much I like having an object with such a common(ish) name that has no other function... Actually, this isn't going to work because template specialization is a mutating operation on the template itself. So it would make more sense to have something like:

proto[T] Option for Option[ptr[T]] {} or maybe even
proto[T] Option for ptr[T] {} / proto[T] Option for [ptr[T]] {}

type
	void never
	struct
	i8 u8 i16 u16 ...
	ptr ref array
	module namespace
	char int long float
	string intern symbol bytes buffer cstr osstr stringview slice
	fn stacklet generator iterator
	tuple list dict object set
	template typevar typedef conditional predicated
	option (composed with ? operator in type expressions)
	Result (composed implicitly by usage of try/fail or by `| fail T`)
	class (boxed by default)
	enum (sum type following Rust semantics)
	trait (trait type following Rust semantics, can be added together)
	interface (virtual by default)
	union (non-discriminated union type composed with | operator)
	oneof (union type for values)
	intersect (intersection type composed with & operator)
	virtual (explicitly marks a function as using virtual inheritance behavior)

One big issue with our current system is that the single `is` operator gives no way to distinguish types and values. Ordinarily we've been considering this a good thing, as it allows arbitrary flexibility and metaprogrammability with our type system, but when annotating higher order function signatures that take and return types there's no clear way to distinguish that what is being passed to the function is a type and not an instance of that type. This is sort of an inverse of the problem we determined earlier that a function annotated with a type should technically accept that type object and its subtypes even though none of the operations on them would make sense. I think this was handwaved because the `as` operator which is called on all parameters by the caller would panic, eg `Dog as Animal` doesn't make sense since `as` can only really operate on instances.

The way Python handles this in the typing module is by having a `Type` type which escapes the instance semantics. We could easily do this as `type[T]`. However, Python does not have our inverse problem because it uses the isinsance as the primary function for type checking, whereas our `is` encompasses the functionality of both `isinstance` and `issubclass`. We could possibly rectify this with a similar solution, an `instance` type template which forces `isinstance` semantics added implicitly for argument type checking, with the following semantics: = true

`T is instance[type[U]] = type[T] is type[U]` - I briefly considered `instance[type[T]] = T`, and thus `T is instance[type[U]] = T is U`, but the problem here is that if `T` is an instance this could pass. What about the inverse, `type[instance[T]]`? Well, `T is type[instance[U]] = T is U` or `instance[T] is instance[U]`? Let's use a concrete type, `false is type[instance[bool]] = false is bool` or `instance[false] is instance[bool]`? Or conversely, `bool is type[instance[bool]] = bool is bool` or `instance[bool] is instance[bool]`?

Let's establish some axioms:
`T is not instance[T]`
`T is type[T]`
`T is instance[type[T]]`
`instance[T] is not type[T]`
`instance[T] is not instance[type[T]]`
`T() is instance[T]`
`T() is not type[T]`
`T is T`
`T() is T`

Interesting note, templated functions and non-annotated functions can easily diverge in semantics. Templated functions forward the type information from the call site, whereas non-annotated functions erase explicit types and rely on the dynamic types in the value.

We can provide two syntax sugar functions, `instanceof` and `typeof` which work as function versions of these two metatypes.

Templated functions have special semantics for the template parameters. They primarily import the type inference data from the caller implicitly. To do this, we need to define the semantics for method resolution, pattern destructuring of the type, and incorporation of any explicit parameters.

fn is[T, ...U](lhs: T, rhs: type[union[...U]]) => T in U;

let T = typeof lhs
let type[union[...U]] = typeof rhs

lhs is rhs = is(lhs, rhs) = is[typeof lhs, typeof rhs](lhs, rhs)

Query-based compilation?
* "What is the compiled module object for this file?"
* "What is the AST of the file?"
* Rustc doesn't seem to use demand during the actual parsing, that's a linear scan (though in a way, recursive descent is a kind of linearized demand system)
ls.flat().map(. + 3)

The compilation pipeline is somewhat complicated by the desire to have multiple endpoints for debugging purposes. The full pipeline is:

Espresso -> partial AST -> hybrid stack bytecode -> { register bytecode -> machine code }

During the bootstrapping process we can observe and interpret the stage furthest down the line, which is fine, but I've frequently found that I want access to earlier stages for debug purposes. For instance, getting both the full AST and stack bytecode. Also, note the phrase "partial AST". The stack bytecode is sufficiently high-level that it can be emitted very early, long before the full AST is realized. We effectively only need to construct the AST for incomplete expressions to check for pattern-matching. Once a pattern is ruled out or fully specified, the bytecode can be emitted. I should also note that the bytecode forms here probably shouldn't be physically realized, but instead some kind of SSA graph on which all optimizations are done before emitting the final machine code. SSA is high level enough that whether the target is stack or register doesn't really matter.

What I really want is some kind of pattern comparable to generators which can operate on recursive structures. That... might actually be a use-case for stackful coroutines. As soon as the partial AST is closed, I could say `this.downstream.yield(ast)`. What would an AST producer look like, then?

How could we support private member fields? Our current system has an approximation, non-enumerability. This can technically result in hard data privacy through the use of scope-local symbols, but our syntax as-is doesn't readily support that (the symbols have to be created out of scope and the syntax for access is special). One thing we could try is in the class creation code, annotating `this` of all the methods with a type which gives access via strings while the actual fields are backed by symbols. That's a pretty hefty rewrite though, and it doesn't compose well with eg traits.

Private members can be done using static type assertions and well-designed delegates. For instance,

proto class X {
	a: int; # Private by default
	
	method(x) {
		this.a = x;
	}
}

Here, the type of `this` is unannotated. Ordinarily this would give it either `var` typing or implicit static typing from type hints found elsewhere. As a method, we would expect the metatype to annotate it for proper optimization, which means it has a static type we don't need to know about in the method body. Thus, we can actually use a different static type (and thus use a different delegate) than the one exposed by the public type. For instance, the publicly available object might contain a `private` field indexed by a hidden symbol known only to the metatype's particular implementation. Then, it can implement a delegate which defers the lookup of private members to that private field.

Need to enumerate the rules for pattern matching, and extensions which only make sense for `which` statements.

In all of the following, `x` is a pattern or identifier which is implicitly defined, while `E` is an expression which doesn't, in general, define any variables.

General pattern matching:
* `...` irrefutable match, unbound
* `x` if it's not the first level of a `case` expression, an irrefutable match bound variable
  - If a bound variable appears later (not in a `let`/`var` binding), it matches if it has the same value. Eg `[x, x]` matches an iterable with two equal values
* `x: E` is a type assertion, equivalent to `x is E` used as a syntax sugar. The syntax is overloaded in `{...}` patterns
  - Not generally valid in the first level of pattern matching
* `let ...` explicit let binding, bound variables within it have `let` binding
* `var ...` explicit var binding, bound variables within it have `var` binding
* `0` literal integer match (float cannot be in match)
  - Literal suffixes are evaluated ahead of time
* `"..."` literal string match
* `"...\{x}..."` string interpolation match. Splits the string and matches if the string components and subcomponents match
  - This can be thought of like a regex match where the string parts are literal and the interpolations are matched against the group `(.*?)`
* `E "...\{x}..."` special string interpolation match. Allows `E` to run first on the string, then the result is queried for the values
  - This can be used for eg binding regex matches to a particular group, as in `re.case"ab(?\{x}cd)ef"` binding `x` to `"cd"`
  - ...or for string matches that are structurally equivalent, but require non-literal matching eg `html"<tag>\{x}</tag>"`
* `this` matches if the value has the same identity as `this`
* `super` matches if the value has the same identity as `super`
* `(...)` literal match, evaluates the contents and checks for a match
  - In some circumstances this will work like an iterable match if it contains an bound parameter in a tuple expression
* `[...]` iterable match, attempt to iterate over the value and match each yield
  - Empty items are skipped, `...` corresponds to any number of items, and `...x` binds those arbitrary items
* `{...}` mapping match, attempt to iterate over the value expecting `(key, value)` pairs and match against the equivalent key
  - `E: x` matches the corresponding pair, but typically `x` is used to bind `value` to a name
  - Just `x` is equivalent to `"x": x`
  - `...x` binds all other `key: value` pairs not matched to `x`
* `Name(...)` typed iterable match, iterates over the value and queries `Name` for each sequential match
  - `Name` can also be an ordinary function, in which case it acts as a predicate (this is actually a library detail, not a special case. Functions implement `case = call`)
* `Name{...}` typed mapping match, iterates expecting `(key, value)` and queries `Name` for each potential key
  - `...x` binds all other `key: value` pairs not matched to `x`
* `Name(...){...}` typed combined iterable and mapping match, used for combined Pythonic positional and keyword arguments to a typed match query
* `x is [not] E` type query, match fails if `x is not E`
* `x as E` type coercion, attempts `x as E` and the match fails if it returns `none`
* `x [not] in E` contains query, fails if `x not in E`
* `x has [not] E` possession query, fails if `x has not E`
* `x.y` and `x.[y]` attribute match, fails if the value doesn't match or `E has not x` and binds the value to `x` and `x.y` to `y`
  - The bind variable name can be changed using `x.y: z` or `x.[y: z]`
* `x[E]` item match, fails if the value doesn't match or the value doesn't have the element
  - The item can be bound to a variable using `x[E: y]`
* `x|y` alternative query, tests `x` and if it failed, tests `y`
  - Bound variables for `x` and `y` are wrapped with `optional[T]` depending on if they were matched
* `x&y` compound query, tests `x` and if that succeeded, tests `y`
  - Bound variables for `x` and `y` are wrapped with `optional[T]` depending on if they were matched
* `x^y` xor query, tests `x` and `y` and succeeds if only one succeeded
  - Bound variables for `x` and `y` are wrapped with `optional[T]` depending on if they were matched
* `!x` succeeds if `x` fails - cannot contain bound parameters
* `x?` attempts to match `x`, but does not fail the whole match if `x` fails. Wrapped with `optional[T]`
* `x == E` equality match (works for all other tests). LHS is bound, RHS is not
  - If you only want to use it as a predicate, use `... == y` or `_ == y`
  - Compound comparison matches can contain either a single bound variable or `...`, eg `1 < ... < 3`. More than 2 comparisons are an error
* `x if E` matches `x`, then fails if `E` evaluates to `false`
* `x = E` attempts to match `x` and, if it fails, assign `y` to `x` instead
* Any other operators act as if surrounded by parentheses, eg `x + y` == `(x + y)`
  - Function calls can be used as expressions as long as they are followed by one of the above patterns eg `x()(...)` will call `x` first, *then* it tries an iterable match
* `x case E` binds `x` if it matches `E`, generally equivalent to `x if E(x)`
  - Equivalent to Rust's `@` operator
  - eg `Node(leafNode case Leaf("foo"), _)`

`which`-specific matches:
* `x and {...}` matches `x`, then if it succeeds starts another `which` block with the same operand. Used for cases that share a common match predicate
* `x or {...}` matches `x`, then if it fails starts another `which` block with the same operand. Same usage as `and`

Note that all of these have something like SFINAE, eg if a predicate doesn't have an overload for a particular type, the match fails rather than panicking.

Rather than have an extra unreachable(), use never() (since that's what it means as a type and it's one less symbol)

For unparameterized object prototyping, we can use an edge case of object syntax, when a computed value is empty:
```
{[]: prototype}
```

The reason we don't want to use any kind of name or symbol here is because object prototyping is a language primitive. Getting an object's prototype necessarily requires a method other than getattr, even if utility methods are provided

## Bikeshedding for prototype syntax:

### Pythonic
```
proto[T] color(enum, ???) { ... }
proto color[T](enum, ???) { ... }
```

Pros:
* Has symmetry with typical types-as-factory-functions style
* Supports passing additional parameters to the prototype
* Supports anonymous prototypes
* Trivial to parse because the top-level syntax isn't an arbitrary expression

Cons:
* Syntactic symmetry is only superficial, it's taking a type not constructor parameters
* Additional parameters come after the prototype
* Encourages multiple inheritance
* It's possible to name a proto without a type (inherit from object?)
* Unclear how to specialize templates or trait impls

### let name proto class
```
let color = proto[T] enum[int](options) { ... }
let color[T] proto enum[int](options) { ... }
proto[T] Clone(Animal[T]) { ... } # Trait specialization
proto list[int] { ... } # Template specialization
```

Pros:
* Pattern matching is easily the most powerful and ubiquitous feature in the language, this has a lot of precedence
* Without `=`, don't need `proto[T]` syntax to introduce type parameters
* Makes `proto`'s verb status more evident
* Template specialization is obvious
* Encourages anonymous prototypes

Cons:
* Requires two keywords and `=` to prototype (verbose)
* Nontrivial to parse, top-level syntax is potentially an arbitrary expression (or restricted expression)
* Proto is a prefix, but the normal usage starts with "let" so the intent isn't known until later

### proto name is class
```
proto[T] Bear is Animal[T](options) { ... }
proto Bear[T] is Animal[T](options) { ... }
proto[T] is Clone(Animal[T]) { ... } # Trait specialization
proto is list[int] { ... } # Template specialization

proto[T] is Clone of Animal[T] { ... } # Alternate trait specialization
proto[T] is Clone for Animal[T] { ... }
```

Pros:
* Symmetry with the `is` operator
* Might not need the `proto[T]` syntax
* Supports anonymous prototypes

Cons:
* Requires two keywords (slightly verbose)
* Possible to create a proto without a type
* Nontrivial to parse (arbitrary or restricted expression)

### proto class name
```
proto[T] class[T] Animal(options?) { ... }
proto[T] class[T](options?) Animal { ... }
proto enum color { ... } # Corresponds nicely with other languages
proto Clone(Animal) { ... } # Trait specialization
proto list[int] { ... } # Template specialization
```

Pros:
* Reminiscent of normal language constructs, proto is just there to disambiguate
* Incapable of proto without a type
* Potential for options
* Template specializations and trait impls are straightforward

Cons:
* Nontrivial to parse, moreso than normal because we need to protect against keyword-calls on the instance name *and* brace suffix calls

On the note of parsing triviality, I would like to readily support Rustian if statements but naively that would run headfirst into the issue of brace calls. To compensate, we can add a parsing state that stuff like keyword calls and brace calls are disabled within these "open expressions". We might also want to make it so you can either have parentheses and no braces, or no parentheses and braces, but you can't have no parens *and* no braces. Point being, the machinery for making this work can be used anywhere else some exotic operator needs to be suppressed.

We can add first class blocks with the `do` keyword, akin to Ruby, but eliminate a class of bugs where it can be "stolen" and taken out of scope by only ever allowing it to be passed by borrow. Copying or persisting in any way thus aren't supported, so its lifetime dies with the stack frame and it's literally impossible to attempt to call it after the stack frame is invalidated. That suggests a key use-case for explicit lifetimes too, for if one wants to build structures containing that block which are themselves guaranteed to not outlive the block.

proto struct block_with_data {
	b: ref[block];
	data: int;
}

Wonder if it would be a good idea to silently promote immutable objects to a mutable prototype of the original immutable object. At the very least it would be nice to have some kind of syntax for this kind of behavior.

Hyrum's law: With a sufficient number of users of an API, it does not matter what you promise in the contract: all observable behaviors of your system will be depended on by somebody