# Espresso
"Tiny language packed with flavor" (feel a better one on the tip of my tongue)
"Espress yourself"

## Design considerations
General philosophy is to reuse everything as much as possible, get as much mileage out of every feature as possible. For instance, keywords double as special method names (eg return/throw/yield for shallow coroutines), operator overload methods use the literal operator name for both lhs and rhs operand positions, and some keywords even triple as builtin namespaces (eg async.sleep). Python list comprehensions are replaced with a spread operator applied to an expression-loop which produces an immediately instantiated generator.

Take for instance the prototype declaration syntax which is inspired by JS classes: `proto Child is Parent {}` reuses two keywords where other languages usually introduce two new ones. This also adds a layer of synchronicity, where `Child is Parent` as well as instances of Child is a boolean operation returning true (working much like JS `instanceof`)

Espresso is a dynamic language, but it tries to follow the C++ zero-overhead principle as closely as is possible for a scripting language, a "minimal-overhead principle". Some features are inherent in the execution model, such as dynamic typing, but have ways to opt out (eg strict mode). Espresso has static-by-default lexical scoping which means variable names are unnecessary for lookup and only saved as debug data. Exceptions are C++-like, almost zero overhead for non-throwing code but very expensive for throwing code.

* Reuse everything as much as possible (keywords, features, syntax)
* Small core, build up with libraries
* Zero cost interfacing with native code
* Embeddability
* Generalization - especially when doing so simplifies logic
* Small code size/memory usage
* Ultimate goal of self-bootstrapping
* Exceptions are exceptional, not alternate control flow
* Stateless tokenization
* LR(1) syntax

### Design constraints
Espresso is a multi-paradigm language implemented on top of a protype system
* Language is ASCII, but UTF-8 friendly. A simple hack lets the lexer communicate character information with minimal logic and no state
* Lexer is stateless and parser never backtracks
* Prioritize ease of binding to host environment
* Reuse syntax and features wherever possible
* Prioritize reduced complexity - Lua should be an inspiration here
  - Core set of simple rules which yield arbitrary complexity
  - Functions are monomorphic/single dispatch with optional type assertions
* Exceptions are exceptional
* Design with JIT in mind
  - JavaScript is a counter-inspiration here
  - V8 is an inspiration - look at which features have the most complexity to make fast for the least benefit (eg hidden classes are completely dynamic)
  - Aim for self-hosting
* Assume static, support dynamic
  - Monkey patching is possible but expensive and meant for debugging and hacking
* Design for cache utilization
* Only implement useful features
  - eg JS string to number coercion isn't very useful and introduces tremendous complexity
* Don't blindly reimplement features from older languages - eg raw 0-prefix octal

## Comments
Comments use hashes "#" because this is generally scripty and compatible with hashbang. Multiline comments are also supported by following a similar pattern as C's comments `/* ... */`, replacing the "/" character with "#", so: `#* ... *#`. Like C, this won't nest. Finally, a nesting version of multiline comments is provided as `#{ ... }#`.

Technically using strings as comments is also supported ala Python, however these won't be respected as docstrings. These should be optimized out as dead code.

## Object syntax
* Quoted: `{"x": 10}`
* Unquoted: `{x: 10}`
* Computed: `{[x]: 10}`
* Packed: `{x, y, z}`
* Integer keys: `{0: "zero"}`
* Real keys: `{0.1: "point one"}`
* Unquoted keywords are always strings: `{none: 10} == {"none": 10}`
* Keys are still typed, though: `{[none]: 10} != {"none": 10}`

Duplicate key names are illegal. If a computed property results in an existing key, the computed property replaces the constant property. Comparison uses ==, so 0 != '0' and you can have both string and number.

### Methods
```js
{
	async* async_generator() {},
	async async_method() {},
	*generator() {},
	method() {},
	get getter() {},
	set setter() {},
	new() { #* constructor *# },
	call() { #* call operator *# },
	get() { #* getter trap *# },
	set() { #* setter trap *# },
	delete() { #* delete trap *# },
	is() { #* is trap *# },
	in() { #* in overload *# },
	
	get [x]() { #* methods can be computed too *# },
	
	with() {
		# Implementing pythonic context manager
		this.__enter__();
		try {
			return yield;
		}
		finally {
			this.__exit__();
		}
		
		this.__enter__();
		try return yield;
		finally this.__exit__();
	}
	
	+(lhs, rhs) {
		#* + operator overload *#
		#* unary + sets lhs = none and rhs = this *#
	},
	
	\<>(lhs, rhs) { #* Overload for comparison ops *# },
	>() { #* Overrides the default provided by <=> *# },
	===() { #* ERROR, can't overload id equality *# },
	
	++() { #* ERROR, can't overload count ops *# },
	&&() { #* ERROR, can't overload boolean ops *# },
	->() { #* ERROR, can't overload binding ops *# },
	bool() { #* Truthiness value *# },
	string() { #* String value *# },
	
	public x: 0, # Public properties define publicly accessible slots
	private x: 0, # Private properties can only be accessed by this.*
		# Note: Fully private properties existing within the object are
		#  definitionally impossible in a prototypical language which
		#  can always extend the existing object with a new method to
		#  return the private property. The only way to get full
		#  privacy is to use closures.
	static x: 0, # Static properties are none if not own properties
	
	public: [] #* Implicit property listing all public names. Functionally
		it's meant to preallocate slots, sort of like Python's __slots__ *#
	private: [] #* Implicit property listing all private names. Also
		allocates slots, but they're private *#
	static: [] #* Implicit property listing, acts as a filter *#
}
```

Operator overload resolution begins on an object's prototype, not the own properties. Eg `!!{bool() { false }} == true` but
`!!new {bool() { false }} == false`. The process goes as follows:

```
lhs op rhs =
	try lhs->lhs.proto.op(lhs, rhs)
	else rhs->rhs.proto.op(lhs, rhs)
```

Comparison operators also support arbitrary chaining ala Python:

`x < y < z => x < y and y < z`

## Functions
Functions can be statements or expressions. Statements define the function
(const in closed namespaces, var in open namespaces) hoisted to the containing block. Statements may not have computed names. Expressions do not define the function, but *can* have computed names, which are functionally only useful for debugging.

Function bodies have no special requirements, they follow the same rules as any other control flow operators. A return is unnecessary as the last value will be returned by default.

Function parameters support destructures, default values, and rest parameters. Optionally, `this` may be included among the parameters which will bind that parameter to `this` when the function is not called as a method. For instance,

```js
function test1(this, x, y) {
	return (x + y)*this.z;
}
function test2(x, y, this) {
	return (x + y)*this.z;
}

test1({z: 10}, 2, 3) == 50;
test2(2, 3, {z: 10}) == 50;

{z: 10}->test1(2, 3) == 50;
{z: 10}->test2(2, 3) == 50;
```

Arrow functions lexically bind `this` (unless it has `this` among its parameters) and has roughly the same syntax as JS. The parser treats it as a sort of destructuring expression to simplify the logic, resulting in a less restrictive grammar than JS arrow functions. An identifier followed by an arrow is immediately evaluated as an arrow function, so the syntax `x, y, z => z` evaluates to a tuple with the last element being the identity function whereas `(x, y, z) => z` evaluates to a tuple destructure arrow function.

Arrow functions can't be generators, in part because the syntax to express that is unclear and because this only makes sense for a blocked expression.

### Dot expressions
An additional syntax is supported for an even more terse arrow function expression. If a dot "." is encountered in a value position, this begins a dot function expression. This can be continued in two ways:
1. The next token is an identifier, and subsequent operations operate on
   the property of the first parameter of the arrow function.
2. The next token is an operator, in which case the dot represents the first
   parameter itself. Just a dot is a special case, representing the
   identity function.

```js
.length #* = *# x => x.length
.x + 3 and 7 #* = *# x => x.x + 3 and 7
. + 1 #* = *# x => x + 1
. #* = *# x => x
.[prop] + 1 #* = *# x => x[prop] + 1
```

Note that this syntax in most other languages would always produce parsing errors, so it's always unambiguous. Also note that this requires the operand to be the leftmost in the expression - eg there is no dot function for
`x => "prefix " + x`. This isn't really a problem because this is just a nice syntax sugar for common use-cases in functional composition.

### Prefix calling
When an identifier is followed by string, number, or object, it's invoked as a unary function with that value. This allows us to simulate idioms found in other languages, like templates in JS: `html f"<i>safe {v}</i>"`. Other literal types are excluded from this shortcut to prevent ambiguity

### Index ranges
Pythonic ranges are supported with a more generalized syntax. Getters receive parameters separated by colons, and like Python each element can contain commas to represent tuples. No inherent meaning is assigned to this syntax, but it *is* overloaded by several builtins like lists. For example:

```js
var x = [1, 2, 3];
new {
	get(...args) {
		assert
			args[0] == 1 and
			args[1] == 2 and
			args[2] == 3 and
			args[3] == 4 and
			args[4] == (5, 6, 7) and
			args[5] == 8 and
			
			# Spread operator works as if inserting the contents separated
			#  by colons
			args[6] == 1 and
			args[7] == 2 and
			args[8] == 3;
	}
}[1:2:3:4:5,6,7:8:...x]
```

As a logical consequence, `arr[]` calls the getter with no arguments.

An alternate syntax with equivalent semantics is:
```js
x.(1, 2, 3) == x[1:2:3]
```

### Tail-call recursion
PTC is tentatively supported because it feels bad to keep extra stack frames around when they're effectively only good for stack traces, which are exceptional. To prevent confusion, the calling convention distinguishes tail calls with some kind of flag so the elided frames can be replaced with something like "..."

## Everything is an expression
Without exception, everything is allowable as an expression. Some expressions have different semantics when they appear as statements, for instance loops as statements behave like normal, but as expressions they are syntax sugar for an immediately invoked generator. Here we compare Pythonic list evaluation to loop expressions:

```python
["0x" + str(x) for x in range(10)] = [...each(var x in range(10)) "0x" + x]

#* => *#
function*() {
	each(var x in range(10)) {
		yield "0x" + x;
	}
}
```

Note the preceeding ellipses, which are *not* a specialized syntax for this.
Rather, it represents a spread operator being applied to an iterable.

One consequence of this principle is that the semicolon works like how many C-like languages treat the comma operator; it evaluates the operands in order and returns the last element. For instance, `(1;2;3) == 3`. Control flow keywords execute as expected when they are evaluated, which may lead to some very nice idiomatic code: `x and return x` will only return x if it's truthy, or `isValid(x) or throw` which is comparable to the PHP idiom "x or die()".

## Namespaces
Two types of top-level namespaces are recognized: closed and open. Modules almost always have a closed namespace, which means the set of valid identifiers is known at parse time and no new ones can be added. The object returned by import is built from exported objects, not the top level namespace, so modifying the module object won't modify its namespace. An open namespace is used primarily for REPL interfaces. In these namespaces, identifiers can be added and even removed as needed (using delete, which normally won't work). Other features which are normally forbidden (global object, global := import "module", etc) are enabled.

## Control flow
### Loops
Loops in a statement position execute as normal. Loops in an expression position evaluate to an invoked generator. All loops support two additional structures, `then` and `else`, which appear in that order.

```js
while(cond) {
	# body
}
then {
	# then
}
else {
	# else
}
```

which is equivalent to the following:

```c++
_continue:
	if(cond) {
	_redo:
		// body
		goto _continue;
	_break:
		// else
	}
	else {
		// then
	}
```

The then block executes when the loop exits normally (and the condition is false) whereas the else block executes when the loop is exited prematurely, with no guarantee that the condition is false. Note that the "then" block fills the place of Python's loop else block while the "else" block is a new construct representing an unusual exit from the loop with break.

What is normally called "do-while" is replaced with "loop-while" extended with an additional (optional) block. This is referenced in Wikipedia as "loop with test in the middle" as proposed by Ole-Johan Dahl in 1972:

```
loop {
	# always
} while(cond) {
	# body
}
then {
	# then
}
else {
	# else
}
```

This is a generalized form of the typical do-while construction, which enables the first block to always be executed at least once, with the rest conditionally executed repeatedly. This would translate to:

```c++
_continue:
	// always
	if(cond) {
	_redo:
		// body
		goto _continue;
	_break:
		// else
	}
	else {
		// then
	}
```

Note that this is the same as the while code above, just with the "always" block inserted immediately after `_continue`. If a loop isn't followed by a while expression, it represents an infinite loop. Note that unlike other loops, there *is not* a then or else block because the only way to exit such a loop is a break.

#### Do block
A do block takes the place of the JS idiom IIFE (immediately invoked function expression). It enables a complex algorithm with scoping to be used in place of an expression. A do block acts as if its body is a function called with no arguments. `this` is lexically bound.

### Exception handling
Exceptions are considered *exceptional* and represent a state which wasn't expected to occur. Ordinarily errors aren't caught as much as they are accounted for. The thrown object can be recovered using `throw.error` and the stack is in `throw.stack`. The full try statement expression is:

```
try {
	# Code which may throw an error
}
then {
	# Try block completed with no error
}
else {
	# Try block interrupted by an error (equivalent of catch)
}
after {
	# Always executed
}
```

### Namespace
The `namespace` keyword returns an open namespace initialized using the provided block. As a statement, it's declared as a const variable using its mandatory name. As an expression, the name is optional (for debug).

Dynamic namespaces are created by enclosing the object in parentheses, like:
```js
namespace name(obj) {}
```

This has the same semantics as JS ```with``` and exists solely as a way to replicate REPL dynamic namespaces, since lexical scoping is otherwise static.

## Protocols
This section describes the various language protocols

### Iterator
Has a method named "next" which returns {value, done} where "value" is the next value and "done" is a boolean indicating whether or not this is the last value of the iterator. Calls after the first {done: true} have undefined behavior, but ideally it would just return {done: true} indefinitely.

### Iterable
Has a method named "iter" which returns an iterator. Almost always an iterator should implement iterable as well, returning itself.

### Generator
Generators are a single type for computed iterators and coroutines meant for suspending and resuming execution within the function body. They implement three methods: `yield`, `throw`, and `return`. `yield` continues execution and returns the next yielded value - if it's given arguments, these are what the yield expression evaluates to within the generator - one argument is as-is, multiple is a tuple. `throw` throws an error into the generator from the point where execution would resume. `return` stops the generator.

### With
To help with the lack of RAII, the with expression from Python is incorporated. The protocol used is like Python's context manager - a `with` method is implemented as a coroutine. `with` is first called when the with block is entered, then the coroutine is resumed with the value/error which exits the block, and finally .return() is called. Technically this means a coroutine isn't necessary, just a function which returns a function implementing the coroutine interface.

### New
When the "new" operator is called with an object, as in `new obj(...args)`, first a new object is created with slots allocated based on the public/private fields of the object. Then, its prototype is set to the original object. Finally, the `new` method is called on the newly created object.

```
proto {
	var x = 20;
	public y = 30;
	private z = 40;
	
	static call() {
		new this();
	}
	public call() {
		
	}
}
==>
{
	proto: object,
	
	public: ["call", "y"],
	private: ["z"],
	
	x: 20,
	
	call() { new this(); },
	
	# New may be one of the more complicated constructions because it has
	#  a lot of code which is autogenerated from the syntax sugar, and on
	#  top of that it already has the semantics of using the return value.
	#  If there is no return (which is the vast majority of cases), we
	#  don't want to return the last value like a normal function or else
	#  `return this` will be mandatory for functional code. Maybe we could
	#  just append `return this` to the function named new in a proto
	#  expression?
	new() {
		this.y = 30;
		this.z = 40;
		this.call = function call() {}
	}
}
```

### After
The `after` keyword is a pretty exotic addition. In effect, it's a reversal of the `;` operator. The first value is the result, and the second value is evaluated afterwards, but its value is ignored. This was implemented to accomodate a common programming pattern:

```js
var tmp = this.doThing();
this.doAnotherThing();
return tmp;
```

which can be replaced with:

```js
return this.doThing() after this.doAnotherThing();
```

This is also a generalization of the `try`-`finally` construct present in many C++ descendents. Where that is ordinarily a fairly rarely used keyword with only one contextual use-case, this has broad generic meaning which is valid in both contexts. Thus

```js
try x after y
```

is actually *parsed* as

```js
(try x) after y
```

As a side note, this can also be used to swap variables:
```js
x = y after y = x
```

expanding to
```js
x = (
	var tmp = y;
	y = x;
	tmp
)
```

## Type hierarchy
never (type of a function which never returns)
none
	any
		primitive
			number
				bool
				int
					uint
						u8 u16 u32 u64
					sint
						i8 i16 i32 i64
				real
					float
						f32 f64
			string
			bytes
			tuple
		object
			buffer
			list
			proto
		callable
			function
			extension (C function called knowing espresso ABI)
			native
		opaque
		wrapped
(special)
	union (structurally like a tuple, property deferral is done in-order)
	enum (subtype of base type)
	char (subtype of int|string)
		char is int and char is string == true

We also have these types

tuple: (x, y, z)
list: int[]
object: {x: int, y: string, z: (int, int)}
nullable: type?
function: (int, int) => int
union: int|float
intersection: int&string (like char)

### Prototype syntax
Names in square brackets "[]" denote optional tokens.
```js
proto [ChildName] [is Parent ["," OtherParent]*] {
	var publicvar;
	public publicvar2;
	private privatevar;
	static varonChild;
	
	new() {
		# Constructor
		# Note that this method is treated specially by adding autogenerated
		#  code to initialize any default values
	}
	
	# The braces here are literal, ala JS
	get ["method"]() { #* method syntax is supported *# }
	
	static func() { #* static can apply to any method pattern *# }
	static async func*() { #* like this *# }
}
```

## Value types
Syntactically, there are two types of values, L-value and R-value. This enables several powerful syntax features which would otherwise be indefinite lookahead, which are destructuring, lambda functions, and immediate functions. The grammar is defined so a subtree is LR, then subgrammars may be encountered which rule out either L or R. An LR-value might be eg an identifier, whereas an L-value might be `{x=10}` (object destructuring with default) and an R-value might be `10`. Because L and R are determined recursively, the value type of the topmost node determines the value type of the whole expression.

```js
{x, y, z} = destructuring_maps
x, y, z = destructuring_sequences
x => lambda
(x, y) => lambda2
[x, y, z] => lambda_taking_list
{x, y, z} => lambda_taking_destructured_map
immediate(x, y) = _function(y, x)
```

### Numbers
Numbers are split between two types, int and float. Integers can be specified in base 2 with the prefix 0b, base 8 with the prefix 0o, base 16 with the prefix 0x, and all other numbers are base 10. Floats can be specified in base 10 with an optional exponent suffix, or base 16 with exponent expressed with p eg 0x123.456p-3. Both ints and floats can have their digits separated by an underscore. Numbers can also be suffixed by an identifier (with no spaces in between) which indicates a function to be called, eg 2px.

### Strings
Strings can use single quotes or double quotes which may be tripled with Pythonic semantics. Backticks are used for raw strings (escapes other than `\\` and ```\` ``` aren't processed). Single and double quoted strings are format strings by default, with string interpolation being indicated by `\{...}`. String interpolation doesn't support nesting quotations to avoid excessive complexity in the tokenizer, so strings within the braces must use a different quote type from the surroundings. Comments are not supported. Strings can also be suffixed by an identifier which is a function to be called on it (taking priority over prefix functions)

## Inspirations
Quick list of languages researched for feature integration:
* JavaScript
  - JerryScript (tight constraints)
  - V8
    * Cutting edge optimizing JIT (with examples of features which add significant complexity to the JIT pipeline)
	* Value boxing in 64-bit words
    * Hidden classes/shapes
	* Inline cache
	* Type inference
	* Accumulator-based register bytecode
  - Core syntax
  - Prototype-based programming
  - Triple equals (strict comparison semantics replaced with unoverloadable identity comparison)
  - Destructuring syntax
  - Variable declaration and scoping (only let semantics using var)
  - Arrow functions (recontextualized as a special destructuring)
  - Untyped exception handling
* TypeScript
  - Type annotation semantics
* Python
  - Expressiveness
  - `__slots__` and `__dict__`
  - Type hierarchy (esp string/bytes/buffer, tuple/list)
  - Comparison operator chaining
  - Loop-else (extended, Pythonic semantics inverted)
  - String qualifier prefixes and triple quoting
  - Generalized user-defined decorators
  - Docstrings (Comments before statements) - generally, keeping documentation and debug information in a REPL environment
  - Parameter annotations
  - Keyword operators (in, is, as)
  - In-place operator overloading
  - With block
* Lua (philosophy, implementation/internals, nil)
  - LuaJIT (simple JIT implementation)
  - Field calling eg f{a=10, b=20} or f "string"
  - Metatables (combined with JS prototyping, operator overloading begins resolution at the prototype, not own properties)
  - Property chains for function name (eg function a.b.c() end)
  - Register bytecode for addressing virtual stack-allocated variables
  - Upvalues
  - Operator overload functions not having an explicit reversed function (ala Python's `__radd__`)
  - 1-based indexing is a bad idea
  - "Everything is a table" is a nice idea, but Lua has been slowly backtracking because it actually increases complexity and decreases performance because you effectively have to reimplement type checking
* Julia
  - Number suffixes are normal function calls (previously considered having a special namespace but Julia just uses eg 1im which is much more elegant and still easy to read)
  - String prefixes are syntax sugar for macro calls, let's use that for both string prefixes and number suffixes - wait, this would make spaces semantic, or else disable unparenthesized string function calls. Not a huge loss, the usage in Lua is unclear
  - Dedenting triple quoted strings
  - Strings are always formatted implicitly
  - Colon prefix to make symbols (also used in Ruby) and lispian quoting of expressions with interpolation (might use \ instead actually)
  - @ macros (composes well with the decorator syntax)
  - Implicit return of last value
* Dart (concurrency model, JS concept streamlining)
* Scala (operators as valid contextual identifiers)
* Java (public/private/static)
* PHP (break/continue on int)
* C (syntax, string/int char)
* C++ (scope operator ::)
  - Scope operator ::
  - String suffixes
* Ruby (redo)

## Key assumptions
This is a list of assumptions made about the programming style and data utilization of a program in order to optimize the most common case:
* Prototypes consist primarily of a fixed set of mostly unmutated methods/properties known at compile-time
* Prototype instantiations have a similar fixed set of properties (defined by public/private keywords) which are arbitrarily mutated and rarely extended (extension is provided via the property lookup table)
* Most data has a fixed size, and dynamic sizes can be represented via references
* In general, hash tables grow and rarely have entries deleted
* The prototype of an object very rarely changes