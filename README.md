# Foreword
"Tiny language packed with flavor" (feel a better one on the tip of my tongue)
"Espress yourself"

## Design considerations
General philosophy is to reuse everything as much as possible, get as much mileage out of every feature as possible. For instance, keywords double as special method names (eg return/throw/yield for shallow coroutines), operator overload methods use the literal operator name for both lhs and rhs operand positions, and some keywords even triple as builtin namespaces (eg async.sleep). Python list comprehensions are replaced with a spread operator applied to an expression-loop which produces an immediately instantiated generator.

Take for instance the prototype declaration syntax which is inspired by JS classes: `proto Child is Parent {}` reuses two keywords where other languages usually introduce two new ones. This also adds a layer of synchronicity, where `Child is Parent` as well as instances of Child is a boolean operation returning true (working much like JS `instanceof`)

Espresso is a dynamic language, but it tries to follow the C++ zero-overhead principle as closely as is possible for a scripting language, a "minimal-overhead principle". Some features are inherent in the execution model, such as dynamic typing, but have ways to opt out (eg strict mode). Espresso has static-by-default lexical scoping which means variable names are unnecessary for lookup and only saved as debug metadata. Exceptions are C++-like, almost zero overhead for non-throwing code but very expensive for throwing code.

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
* Lexer is stateless and parser *never* backtracks
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

# Syntax

## Comments
Comments use hashes "#" because this is generally scripty and compatible with hashbang. Multiline comments are also supported by following a similar pattern as C's comments `/* ... */`, replacing the "/" character with "#", so: `#* ... *#`. Like C, this won't nest. Finally, a nesting version of multiline comments is provided as `#{ ... }#`.

Technically using strings as comments is also supported ala Python, however these won't be respected as docstrings. These should be optimized out as dead code.

## Operators
The defined operators are those typical of a C-family language with some extra operators which have no assigned meaning for consistency. These are:
* `+ - * / % ** // %%`
  - `//` is the pythonic integer-divide operator
* `== === != !== > >= < <= <>`
  - `<>` is what other languages call the spaceship operator `<=>`, meaning ternary comparison
* `<< <<< <<>` `>> >>> <>>`
  - `<<>` and `<>>` are new operators meaning "rotate shift left" and "rotate shift right", respectively.
* `! ~ & | ^ !! ~~ && || ^^`
  - `!!` is the boolean operator
* `in is as not has`
  - `in` and `not` have pythonic semantics, including using `not` as a meta-operator, as with `is not`
  - `is` is the type checking operator, equivalent to JS `instanceof`
    * The `===` operator ("id equality") has python `is` semantics
  - `as` is a coercion operator, primarily for use in strict code
  - `has` is like `in`, but checks own properties by default
    * Compare this to the JS idiom `if('x' in y) return y.x`. This feels jarring because the normal relationship, `y.x` is inverted with `'x' in y`. `has` keeps this ordering to be easier to read, as in `y has 'x'`
* `= :=`
  - `:=` is the emplacement operator with similar semantics to JS `Object.assign`
* `++ --`
  - C-like semantics
  - Applied to r-values, simply increments/decrements without assignment eg `--1<<3` shifts 1 left by 3 then decrements, a common pattern for creating bit masks
* `??`
  - Null coalescing operator
  - Boolean short-circuiting
  - `x ?? y` = `if(x is none) y else x`
* `..`
  - Range operator, `x .. y` yields a range `[x, y)` useful for iteration
  - As a unary operator, `..y` is a range `[0, y)`
* `...`
  - Spread operator
  - Generally iterates over rhs and emplaces them in the particular construct
  - eg `var x = [1, 2, 3]; [1, 2, ...x]` is `[1, 2, 1, 2, 3]`
  - Indicates rest arguments eg `function test(a, b, ...rest)`
  - Unpacks arbitrary elements eg `first, ...rest = list`
* `=>`
  - Lambda operator with JS-like semantics
  - Strictly syntax, not overloadable
  - Unpacks lhs and executes rhs with that context (as a lambda function)
  - More permissive than JS because lhs can be any arbitrary l-value
  - Also has semantics within switch expressions, where the rhs is evaluated with an implicit `break` to avoid having `break` after every `case`. C-like `:` after cases is also supported with the same semantics (fallthrough)
* `->`
  - Application operator
  - Get or call rhs as if lhs was `this`
  - Useful for generic functions, eg `x->join(', ')` to avoid reimplementing `join` on all iterables
  - Allows one to access `private` variables, which are meant to be implementation details and not security-constrained
* `::`
  - Descoping operator
  - Call or access rhs without applying lhs as `this`
  - First parameter of a function is made into a `this` parameter
  - Combined with `->`, this can apply arbitrary member functions to arbitrary objects, which is especially useful when implementing the global operator overload functions eg `x->x.proto::+(x, y)` meaning "get `+` from `x.proto`, then call it with `x` as `this`". This is necessary because `x.+(x, y)` has different semantics, calling `+` from the object itself rather than its prototype. For security purposes, operator overloading needs to be from the prototype, not the object.
  - A special syntax is permitted for computed properties, `::[expr]`. `::(expr)` is also valid
  - As a unary operator, `::func` adds a `this` parameter to the beginning of the parameter list *unless* a `this` parameter already exists.
* `,`
  - Comma is actually syntax, not an operator
  - In an expression, it denotes a tuple (or list etc depending on context)
  - Subexpressions may be omitted, ala `x, , y = z`. As unpacking, it means "ignore the missing value". As a tuple expression, it means "implied none". One exception is in tuple expressions with a trailing comma, which is ignored.
* `;`
  - Most languages consider this syntax
  - This is reconceptualized as a non-overloadable "operator" which evaluates and discards lhs and returns rhs
    * In the future this may be overloadable to express what happens when an expression is ignored by it, justifying statement vs expression forms of control flow as having the `;` operator overloaded to iterate the expression form and discard the results, equivalent to statement form
  - Mostly equivalent to C's usage of the `,` operator
  - No special restrictions on where this can appear, including within parentheses ala `(a; b; c)` which will evaluate `a` and `b`, then return `c`
  - This has the lowest possible precedence
* `[:]`
  - Indexing has generalized Pythonic semantics, see [below](#index-ranges)

To simplify logic, all overloadable binary operators double as unary prefix operators with the same precedence. Their overloads get `none` in as the lhs.

### Defined but unused
Some of the listed operators are defined for consistency with other operator patterns, but have no assigned use. This both simplifies parsing logic and provides users with extra operators to be overloaded. These are:
* `%%` - continuation of `**` and `//`
* `<<<` - continuation of `>>>` "logical right shift"
* `~~` and `^^` - continuations of `~` and `^`
* `~>` - continuation of `=>` and `->`

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
	async yield async_generator() {},
	async async_method() {},
	yield generator() {},
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
		after {
			this.__exit__();
		}
		
		this.__enter__();
		try return yield;
		after this.__exit__();
	}
	
	+(lhs, rhs) {
		#* + operator overload *#
		#* unary + sets lhs = none and rhs = this *#
	},
	
	\<>(lhs, rhs) { #* Overload for comparison ops *# },
	>(lhs, rhs) { #* Overrides the default provided by <=> *# },
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
		#  privacy is to use closures and symbols.
	static x: 0, # Set on the prototype
	
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

`x < y < z` = `x < y and y < z`

### Unpacking
Unpacking is a special assignment operation which assigns multiple values from a single enumerable. The semantics of this are shared with JS, Python, and C++ (among other languages) with some variations.

There are two types of unpacking:
* `x, y, z = it` or `(x, y, z) = it` or `[x, y, z] = it`
  - Sequential unpacking
  - At most one element of sequential unpacking can use the rest operator `...`
    * This can appear anywhere and will get the leftover corresponding elements after non-rest elements are unpacked

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

Optionally a declarator may be used to specify the mutability of a function. Functions are const by default.

```js
var function onload() {} # equivalent to
var onload = function onload() {}
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
["0x" + str(x) for x in range(10)] = [...for(var x in range(10)) "0x" + x]

#* => *#
function yield() {
	for (var x in range(10)) {
		yield "0x" + x;
	}
}
```

Note the preceeding ellipses, which are *not* a specialized syntax for this.
Rather, it represents a spread operator being applied to an iterable.

One consequence of this principle is that the semicolon works like how many C-like languages treat the comma operator; it evaluates the operands in order and returns the last element. For instance, `(1;2;3) == 3`. Control flow keywords execute as expected when they are evaluated, which may lead to some very nice idiomatic code: `x and return x` will only return x if it's truthy, or `isValid(x) or fail` which is comparable to the PHP idiom "x or die()".

## Namespaces
Two types of top-level namespaces are recognized: closed and open. Modules almost always have a closed namespace, which means the set of valid identifiers is known at parse time and no new ones can be added. An open namespace is used primarily for REPL interfaces. In these namespaces, identifiers can be added and even removed as needed (using delete, which normally won't work). Other features which are normally forbidden (global object, global := import "module", etc) are enabled.

### Modules
The object returned by import is built from exported objects, not the top level namespace, so modifying the module object won't modify its namespace. Modules are syntax sugar for a nullary function call.

```js
export function myFunc() { ... }

return {a: 3};
```

is roughly equivalent to

```js
function import() {
	const exports = {...};
	exports.myFunc = function myFunc() { ... }
	
	exports.proto = body();
	return exports;
}
```

The return of a module (inspired from Lua) is set as the prototype of the module object, with exports being own properties. If a return isn't specified, `none` is assumed.

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
Exceptions are considered *exceptional* and represent a state which wasn't expected to occur. Ordinarily errors aren't caught as much as they are accounted for. The thrown object can be recovered using `fail.error` and the stack is in `fail.stack`. The full try statement expression is:

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
Numbers are split between two types, int and float. Integers can be specified in base 2 with the prefix 0b, base 8 with the prefix 0o, base 16 with the prefix 0x, and all other numbers are base 10. Floats can be specified in base 10 with an optional exponent suffix, or base 16 with exponent expressed with p eg 0x123.456p-3. Both ints and floats can have their digits separated by an underscore. Numbers can also be suffixed by an identifier (with no spaces in between) which indicates a function to be called, eg 2px. Note that just a 0 prefix has no inherent meaning and is parsed as an ordinary decimal integer.

### Strings
Strings can use single quotes or double quotes which may be tripled with Pythonic semantics. Backticks are used for raw strings (escapes other than `\\` and ```\` ``` aren't processed). Single and double quoted strings are format strings by default, with string interpolation being indicated by `\{...}`. String interpolation doesn't support nesting quotations to avoid excessive complexity in the tokenizer, so strings within the braces must use a different quote type from the surroundings. Comments are not supported. Strings can also be suffixed by an identifier which is a function to be called on it (taking priority over prefix functions)

## Strict mode
Strict mode uses the same syntax with different semantics to write code which can be unambiguously compiled AOT. Opting in lets one write low level code ala Asm.js or RPython and this feature is critical to enabling Espresso to self-host.

In strict mode, typing is mandatory, operator overloads are disabled (only supporting operations between basic machine types), and values must be manually unboxed. A set of machine types is provided in strict mode specifically. Unboxing and type coercion is done via the `as` operator, which will fail if the `any` value has an incompatible type.

One possible addition is an "unsafe" mode which enables pointers and pointer arithmetic. Unsafe code would require `unsafe import` which taints the calling code as unsafe. Then a module can be compiled into a binary format which can be imported safely, ala C#'s unsafe mode and /unsafe flag. Pointers could be implemented with a parametric type `ref[T]` and dereferenced with `ptr[]` - which conveniently acts like an lvalue in normal code. In this case, `ptr[0]` and `ptr[]` would be equivalent.

# Implementation considerations
## Roadmap
* MVP interpreter written in Python
* Espresso parser written in Espresso
* C++ codegen
* JIT compilation

## C++ IR runtime
In the C++ codegen phase, a minimal runtime must be implemented in C++ (which can be used as reference for implementing that same runtime in Espresso). C++ was chosen because like Python, operator overloading is supported which makes the generated code resemble its origin more closely, and templating allows significant abstractions with minimal overhead and boilerplate.

## Boxing
### Invariants
For a boxed value, integer value 0 should be interpretable as none to simplify nullish checks.

### 32-bit
On 32 bit systems boxing must be done using pointer tagging (using the low bits to signal the encoded type). The particular implementation of value boxing is not exposed to Espresso code, and the most optimal implementation will differ between architectures, but the suggested format is:

Low 2 bits:
* x1 = 31-bit small integer (smi)
* 00 = raw pointer to GCObject (NULL pointer is none)
* 10 = simple value
  -  0010 = false (2)
  -  0110 = true (6)
  -  1010 = empty (10)
  -  1110 = char (14) (high 28 bits represent unicode codepoint)
  - 10010 = intern
  - 10110 = symbol

### 64-bit
On 64 bit systems the suggested implementation is modified NaN-boxing with some additional pointer tagging. IEEE-754 binary64 ("double") is encoded by inverting all the bits. The significance of this is that the codespace of signaling NaNs (ignored sign bit followed by fully set 11-bit exponent and the highest bit of the fractional part set) is trivial to check, giving an available codespace of 51 bits + the sign bit. Setting the sign bit indicates a 51-bit smi. Otherwise, the high 3 bits represent a high level type followed by 48 bits of payload. These types are:

* 000 = 48-bit GCObject pointer + simple values in low bits
  - Note: this means ordinary GCObject pointers are entirely unencoded and can be dereferenced as-is
  - all 0s = none (NULL pointer)
  - low 3 bits:
    * 010 = false (2)
	* 110 = true (6)
* 001 = external pointer
* 010 = array
  - Low 3 bits:
    * 000 = i8[]
	* 001 = i16[]
	* 010 = i32[]
	* 011 = i64[]
	* 100 = f32[]
	* 101 = f64[]
	* 110 = any[]
	* 111 = object[]
* 011 = callable
  - Low 3 bits:
    * C function pointer of type `LiveValue(*)(LiveValue, int, LiveValue(*)[])`
	* Bytecode
* 100 = dict
* 101 = 
* 110 = 
* 111 = 

### Live and Heap values
A distinction is made between "live" and "heap" values. Live values are in use by the VM and use the widest available format, while heap values use the smallest available format to save on memory. Tests on V8 showed that pointer compression on 64-bit architectures into 32-bit formats could nearly halve memory usage with minimal overhead.

Note that live and heap values are the same type on 32-bit systems and only differ on 64-bit systems.

### GC
The GC algorithm I hope to use is heavily inspired by [this](http://wiki.luajit.org/New-Garbage-Collector) paper on a speculative GC for LuaJit 2.0 with special considerations made for Espresso's object model. The major points are:
* 4 different allocation strategies depending on the object type
  - interning
    * "Immutable with fixed size and immortal"
    * Data which is useful more for its identity than its actual content, but which is still defined by its content
	* Never deallocated
	* Simple bump allocator
	* String keys - if strings can always be coerced into interns if they exist, intern hashes can be guaranteed unique and thus equality checks are simple hash checks without the extra equality check, which would touch nonlocal memory.
	* Metadata - rather than metadata being stored on an object, it's better to store it in an object-keyed table so it's available with some overhead. We don't care about fast metadata access, just access
	* Bytecode - immutable and immortal
	* Note: It's possible that immortality isn't necessary because most of the data here will be kept in a hash table and referred to by hash-identity rather than address. Thus, the address could theoretically change while maintaining the same identity (note: hash-identity is the result of an open address hash table algorithm)
  - static allocation
    * "Mutable with fixed size"
    * Simple bump allocator which maintains an intrusive pointer list of free blocks
	* Free blocks of N size are kept in an intrusive pointer list with heads stored in the largest free block at index N
	* Possibly support lazy moving with redirection pointers
	* Allocations are for objects of a fixed size and do not support realloc
	* Value types like string are allocated here because despite being immutable, they will be deallocated eventually so cannot be interned. Interning is also a waste of time if the string isn't going to be used as a key
	* Allocation policy: exact fit > bump allocation > best fit > new arena
  - heap (dynamic) allocation
    * "Mutable with dynamic size"
    * Binary tree with the heap property maintained over an arena to grant subblocks which maximize reallocatability (sort by size, largest on top)
	* Realloc is kept nearly free
	* Pointers always owned by an object in static allocation and heap allocation has a backreference
	* Moving is also trivial since it's isomorphic to unique_ptr
	* Intended for allocations of indeterminate length which may require realloc
  - malloc
	* Arenas themselves allocated via malloc for better embeddability
	  - See: std::aligned_alloc()
	  - GC algorithm depends on arena alignment to compress pointers into indices
    * Objects greater than an entire arena just use malloc
* 4-color lazy incremental mark and sweep
  - Novel 4-color (2 degrees of freedom) lazy mark and sweep algorithm
    * blackwhite / grey = garbage / dirty
    * white = "maybe garbage"
	* light-grey = "maybe garbage but check"
	* dark-grey = "probably not garbage but check"
	* black = "probably not garbage"
  - Lazy sweeps are done per-arena. This seems to break inter-arena references, but after a full sweep objects referred to by another arena will be marked black, "probably not garbage"
* Cache-friendly sweep metadata
  - (only applies to static allocation)
  - 2 bitmaps of metadata block and mark kept together
    * block mark
	*     0    0 = block extent
	*     0    1 = free block
	*     1    0 = white block
	*     1    1 = black block
	* (grey bit kept in cell)
* Grey queue
  - Objects marked grey stored in queue in arena for processing
* Sequential Store Buffer (SSB)
  - Holds block addresses which triggered a write barrier so they're only touched when we're in GC mode
  - When processed (or overflows), convert to arena index and push to grey queue

### Bytecode
Inevitably an IR bytecode must be developed to be 1. trivial to interpret in the Espresso runtime, 2. trivial to JIT compile, and 3. support strict mode semantics (both dynamic and strict typing). Wasm is likely to be the primary source of inspiration along with CPython. Both of these are quasi-stack machines, storing variables in slots and intermediates on a value stack.

### JIT
JIT is a hard problem here because we want to be as lightweight as possible, and available JIT libraries (LLVM, GNU libjit, etc) are not. It may be a better idea to take inspiration from LuaJIT, which uses DynAsm as an integrated dynamic assembler. That alone won't work well however because it requires a preprocessing stage, is developed with Lua specifically in mind, and has no (official) documentation. One possible library to look into is AsmJIT, though that is currently x86 only.

# Context
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

## Design notes
I originally thought `=` could be a meta-operator combining with any arbitrary binary operator to its left, such that eg `+ =` would be the same as `+=`. This is "pretty" from a high level design POV, but in implementing the parser I realized that this combined with the precedence climbing algorithm produced a fundamental contradiction. The normal operator could only be consumed if we knew its precedence was sufficiently high, but the `=` meta-operator would change its precedence to one of the lowest. Thus we need to consume the token to know its precedence, but we can't consume the token until we know its precedence. There were some "clever" hacks to try to get around this (tentatively consuming for sufficient precedence, then bailing if we parse `=` and modifying `self.cur` to semantically combine them) but the complexity grew and grew, all to implement a feature that, let's face it, has no practical value. I only thought of it in the first place because I thought it would make parsing easier, but it turns out it would require either a lot of extra code or I'd have to upgrade the parser to LR(2).