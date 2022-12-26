# Foreword
"Tiny language packed with flavor" (feel a better one on the tip of my tongue)
"Espress yourself"
Waste not want not

## Design considerations
General philosophy is to reuse everything as much as possible, get as much mileage out of every feature as possible. For instance, keywords double as special method names (eg return/throw/yield for coroutines), operator overload methods use the literal operator name for both lhs and rhs operand positions, and some keywords even triple as builtin namespaces (eg async.sleep). Python list comprehensions are replaced with a spread operator applied to an expression-loop which produces an immediately instantiated generator.

Take for instance the prototype declaration syntax which is inspired by JS classes: `proto Child is Parent {}` reuses a keywords where other languages usually introduce two new ones. This also adds a layer of synchronicity, where `Child is Parent` as well as instances of Child is a boolean operation returning true (working much like JS `instanceof`)

Espresso is a dynamic language, but it tries to follow the C++ zero-overhead principle as closely as is possible for a scripting language, a "minimal-overhead principle". Some features are inherent in the execution model, such as dynamic typing, but have ways to opt out (eg type annotations). Espresso has static-by-default lexical scoping which means variable names are unnecessary for lookup and only saved as debug metadata. Exceptions are C++-like, almost zero overhead for non-throwing code but very expensive for throwing code.

* Reuse everything as much as possible (keywords, features, syntax)
* Be terse, but not unreadable
* Don't repeat yourself
* Small core, build up with libraries
* Zero cost interfacing with native code
* Embeddability
* Generalization - especially when doing so simplifies logic
* Small code size/memory usage
* Fast startup
* Ultimate goal of self-bootstrapping JIT
* Exceptions are exceptional, not alternate control flow
  - Splits exceptions into failures and panics
* Stateless tokenization
* LR(1) syntax
* The compiler is Espresso. If Espresso can do it, so can Espresso.
  - "Minimize magic"

----

I would like espresso to be a delight to program in, the way Python tends to be and JS sometimes is. Python has strong opinions, but that appears to hold it back from implementing nice features for the sake of consistency (?). For example, the absolute mistake that is non-coercive string concatenation. str + int should just work, and it's surprising when you discover for the first time that it doesn't - and code was explicitly written to forbid it! Just, why? It seems almost like it was meant to emphasize a few of the early design considerations like duck typing vs dynamic typing that it crippled itself to make a point.

On the other side of things is JS, which seems to have very few opinions at all. It just sort of tentatively supports everything, and while it can be pleasing to program in it because of just how open it is, it also doesn't guide one readily to "correct" programming, and it implements features no one needs and cause errors more than they do what people want. '0' == 0 is "nice", but it confuses the types while also introducing inconsistency because, for instance, "0" == 0, 0 == "00", but "0" != "00". Rather than unimplementing features, it implements too many unnecessary or counterproductive features.

Then there's Lua, which is similarly unopinionated but for the opposite reason. It implements nothing at all, providing a core language and some bare bones functionality and requires everything else to be implemented in libraries by the end user. It would make more sense if a had a standard library or something, but it's just a collection of vaguely canonical libraries that everyone tends to use.

So, a few lessons here. Do not write code to disable a feature unless that "feature" would only cause more confusion. Do not try to be clever and do more than what the programmer is asking. And for god's sake, make the language simple but fill the toolbox with tools!

1. Code is for implementing features, not unimplementing them

### Design constraints
Espresso is a multi-paradigm language implemented on top of a protype system
* Language is ASCII, but UTF-8 friendly. A simple hack lets the lexer communicate character information with minimal logic and no ment
* Lexer is stateless and parser *never* backtracks
* Prioritize ease of binding to host environment
* Reuse syntax and features wherever possible
* Prioritize reduced complexity - Lua should be an inspiration here
  - Core set of simple rules which yield arbitrary complexity
* Exceptions are exceptional
* Design with JIT in mind
  - JavaScript is a counter-inspiration here
  - V8 is an inspiration - look at which features have the most complexity to make fast for the least benefit (eg hidden classes are completely dynamic)
  - Aim for self-hosting
* Assume static, support dynamic
  - Monkey patching is possible but expensive and meant for debugging and hacking
* Design for cache utilization
* Only implement useful features
  - eg JS string to number coercion isn't very useful
* Don't blindly reimplement features from older languages - eg 0-prefix octal

## Novel concepts
* Module scope is compile time. The return of a module import can be serialized and rehydrated to allow faster start times
  - Allows everything from config files to foreign languages to be implemented and run at compile time for import statements.
  - Imagine a hypothetical C interface where you can write `import "project.h"` and bindings are generated as part of the static bytecode
* Self-hosted JIT (have yet to see this, closest is PyPy but it's not really self-hosted because RPython transpiles to C)
* `after` keyword to get rid of the common pattern `var tmp = a(); b(); return tmp`
* Loops can be expressions, evaluating to invoked generators yielding the result of their body

# Key terms
* Expression: A set of related syntax elements
* Composite expression: An expression which can be broken down into two or more valid subexpressions
* Statement: Fully qualified expression which has no tokens after it which can extend it. Semicolons can guarantee the end of an expression
* Value: A type of expression
* Lvalue: left-value is a value which can legally appear on the left hand side of an assignment. Includes destructuring
   - Plvalue: pure-lvalue, an lvalue which cannot be an rvalue, eg object literals containing defaults
* Rvalue: right-hand-value, a value which can be evaluated
  - Prvalue: pure-rvalue, an rvalue which cannot be an lvalue or a uvalue, eg primitive literals

# Syntax

## Comments
Comments use hashes "#" for a few key reasons:
* Generally more "scripty"
* Compatible with hashbang
* C-like "//" conflicts with the integer division operator

Multiline comments use `#* ... *#` similar to C-likes but using hash and also won't nest. A nesting version of multiline comments is provided as `#{ ... }`.

Technically using strings as comments is also supported ala Python, however these won't be respected as docstrings. These should be optimized out as dead code.

## Primitive literals
All primitive literals support immediate suffixes - that is, a valid identifier which follows the last valid character of the literal sequence with no whitespace. These are used for aesthetic and low-level literal handling ala C++ literal suffixes.

### Numbers
All numbers in espresso may contain `_` anywhere between two digits, not including a base prefix.

#### Integers
Integers can be binary, octal, or hexadecimal using the prefixes `0b`, `0o`, and `0x` respectively. Otherwise, they use decimal. Integers beginning with 0 have no special treatment and will use decimal.

#### Floats
Decimal floating point numbers have the following syntax:
`[int] "." [frac] ["e" {"-" | "+"} exp]`

Hexadecimal floating point numbers have the following syntax:
`"0x" [int] "." [frac] ["p" {"-" | "+"} exp]`

Note that this is a slight simplification because it technically admits "." as a valid number. A proper pattern needs to make either int or frac optional, but not both simultaneously.

### Strings
Normal strings can be denoted by `'...'` or `"..."` and contain any characters, including newlines (though some normalization may apply). A `\\` character denotes an escape sequence from this table:

| Sequence | Description           |
| -------- | --------------------- |
| \        | Backslash             |
| '        | Single quote          |
| "        | Double quote          |
| `        | Backtick              |
| n        | Newline               |
| r        | Carriage return       |
| t        | Tab                   |
| e        | Escape character      |
| 0-9      | 1-digit ASCII decimal |
| oOOO     | 3-digit ASCII octal   |
| xHH      | 2-digit ASCII hex     |
| uHHHH    | 4-digit unicode hex   |
| u{...}   | n-digit unicode hex   |
| {...}    | String interpoloation |

If a character other than one listed here follows a backslash, this is a syntax error.

All normal strings support string interpolation by default. Compare this to Python format strings, which must use an `f` prefix and interpolation does not use backslashes to signal the start of a value.

A "raw" string is denoted using backticks and may contain any characters, but all escape sequences except ``\\`` and ``\\` `` are disabled.

Both normal and raw strings support Pythonic triple quoting which generally requires less escaping when the string contains the quote character. Triple quoted normal strings will also remove prefix literal newlines and dedent based on the first line.

## Compound literals
For simplicity, compound literals are parsed while keeping track of their validity as an uvalue or an rvalue. Uvalue compound literals can be the target of destructuring, while rvalue compound literals cannot.

### Tuple
A tuple is a sequence of values separated by commas, optionally surrounded by parentheses. Values between commas may be omitted which is interpreted as `none`. As a uvalue, tuples assign each element in sequence by iterating over the assigned value. As an rvalue, tuples are an immutable sequence.

### List
A list is a sequence of values separated by commas surrounded by square brackets. Like tuples, values may be omitted which is interpreted as `none`. As a uvalue, lists work exactly like tuples. As an rvalue, lists are mutable sequences.

### Object
An object is a key:value mapping deeply integrated with the language. As such its syntax is significantly more complex:

* Key-value pair
  - Quoted: `{"x": 10}`
  - Unquoted: `{x: 10}` - includes operators
    * Unquoted keywords and even builtin constants are treated as strings
    * Keys are still typed, however: `{none: 10} != {[none]: 10}`
  - Computed: `{[x]: 10}` evaluates `x` and uses that as the key
  - Integer keys: `{0: "zero"}`
  - Real keys: `{0.1: "point one"}` - this is valid but not recommended because floating point equality is poorly defined
* Packed: `{x, y, z}` equivalent to `{x: x, y: y, z: z}`
* Method: `{key(...args) { ... }}` - key can be any of the valid keys above
  - The key can be prefixed by at most one of the accessor keywords `get`, `set`, `delete`

Any object entry may be prefixed with at most one access modifier `public` (default), `protected`, or `private`
Any object entry may be prefixed with at most one type qualifier `var` (default) or `const`

Key-value pairs may be omitted (resulting in two or more sequential commas) which has no effect.

An extended syntax is provided which makes a puvalue: A key-value entry may be followed by `= value` which provides a default value if `unpacked has value` is false.

An object literal uvalue may contain packed lvalues or key-value pairs in which the key is an lvalue and the value is a uvalue. If any other syntax is included, it is an prvalue.

Duplicate key names are illegal. If a computed property results in an existing key, the computed property replaces the constant property. Comparison uses ==, so 0 != '0' and you can have both string and number.

## Operators
### Arithmetic
* `+` addition or concatenation
* `-` subtraction
* `*` multiplication
* `/` division
* `%` modulus
* `**` power
* `//` integer division
* `%%` (unused)

### Assignment
Arithmetic operators can all be suffixed by `=` to perform them inplace. 
As well as inplace operators for all of these except `++` and `--` by appending `=`

* `=` assignment, as an rvalue it evaluates to the rhs
* `:=` emplacement operator, similar to JS's `Object.assign`

### Boolean
* `>` `>=` `<` `<=` `==` `!=` ordinary comparisons
* `===` `!==` identity equality
* `<=>` three-way comparison
* `and` or `&&` short circuiting boolean and
* `or` or `||` short circuiting boolean or
* `not` or `!` booleal not
* `!!` boolean coercion
* `??` short circuiting nullish coalescing operator

These comparison operators can be chained ala Python.

### Bitwise
* `~` bitwise not (binary form unused)
* `&` bitwise and
* `|` bitwise or
* `^` bitwise xor
* `<<` arithmetic left shift
* `>>` arithmetic right shift
* `>>>` logical right shift
* `<<>` rotate left
* `<>>` rotate right

### Keyword
* `in` boolean predicate returning whether a value is in a container
* `has` boolean predicate returning whether an object has an own property
* `is` boolean predicate of identity equality, prototype inheritance, or predicate satisfaction
* `as` coercion operator
* `after` shuffle evaluation, that is: `x() after y() === (var t = x(); y(); t)`

### Other
* `x.y` attribute
  - `x.(y)` evaluates y and uses that as the attribute name
  - `x.[y]` evaluates `[y]` and uses that
  - `x.{...}` evaluates the object and uses that
* `x[y]` index
  - `x[a:...:z]` slice indexing
* `x(y)` function call
* `@x D` or `@x(y) D` decorator (N is any dvalue)
* `..` range operator (prefix form is valid)
* `...` spread operator
  - Depending on the context, `...` can also be interpreted as a special value ala Python
* `;` procedural evaluation
* `->` generic application operator, uses lhs as `this` to call the rhs generic function
  - This allows for accessing private properties when one has the symbol, using `x->.(symbol)`
* `=>` lambda "operator", syntax for arrow functions and case expressions
* `::` binding operator, returns a function with parameters rebound
  - `::` as a unary operator adds `this` as the first parameter along with any parameter bindings
* `<:` and `:>` injection operator, `x <: y === x(y)` and `x :> y === y(x)`
* `++` `--` inc/decrement (unary prefix or suffix)
  - Applied to rvalues, effectively equivalent to `x + 1` and `x - 1`

### Unused/experimental
These are operators which may emerge from simplified regexes or look aesthetically nice without having any clear usage.

Define but not used:
* `^^` `<<<` `%%` `~~`

Aesthetically interesting:
* `~>` `->>` `=>>` `~>>` `<>`
* `?:` `??:` `@>` `+>` `><` `+/-` `-/+` `/*` `*/` `<:>`

To simplify logic, all overloadable binary operators double as unary prefix operators with the same precedence. Their overloads get `none` in as the lhs.

### Precedence
* (looser binding)
* Statement: `;`
* Separation: `,` `:`
* Keyword: `return` `yield`
* Arrow: `=>`
* Assignment: `=` and all compound assignment operators
* Nullish: `??` `?!`
* Boolean or: `||` `or`
* Boolean xor: `^^`
* Boolean and: `&&` `and`
* Equality: `==` `!=` `===` `!==`
* Relational: `<` `<=` `>` `>=` `<=>` `in` `is` `has` `as`
* Injection: `<:` `:>`
* Bitwise or: `|`
* Bitwise xor: `^`
* Bitwise and: `&`
* Bitshift: `<<` `>>` `<<<` `>>>` `<<>` `<>>`
* Additive: `+` `-`
* Multiplicative: `*` `/` `%` `//` `%%`
* Exponential: `**`
* Prefix unary: `!` `not` `~` `+` `-` `++` `--` `typeof` `delete` `await`
* Postfix unary: `++` `--`
* `new`
* Call and index: `f(...)` `f[...]`
* Application: `->`
* Access: `.` `::`
* Grouping: `(...)`
* (tighter binding)

### Special precedence
* `after` is just above `;` to the left, tighter binding to the right (and it can accept a block instead)

## Variables
`("var" | "const") uvalue [":" expr] ["=" expr]`

Variables are declared using a type qualifier and a comma-separated list of uvalues each with an optional type annotation and optional assignment. All declarations are hoisted to block scope. Variables can be used as an rvalue, in which case they evaluate to the last value.

Variable declarations are dvalue expressions, meaning they can also be decorated.

## Control flow

### If then else
`if cond ["then"] expr ["else" expr]`

Conditionally execute one block or another. As an rvalue, it evaluates to the block which executes (or `none` if the `else` block should execute but doesn't exist).

### Loops
Loops in a statement position execute as normal. Loops in an expression position evaluate to an invoked generator. All loops support two additional structures, `then` and `else`, which appear in that order. If a loop iteration evaluates to the global signal `delete`, the result is not included in the sequence.

All loops may optionally be followed by a `then` block and/or an `else` block. A `then` block executes when the loop exits normally (and the condition is false) whereas the else block executes when the loop is exited prematurely, with no guarantee that the condition is false. Note that the `then` block fills the place of Python's loop else block while the `else` block is a new construct representing an unusual exit from the loop with break.

#### Loop while
`["loop" always] ["while" cond body] ["then" then] ["else" else]`

This is equivalent to the following C:

```c
_continue:
	/* always */
	if(cond) {
		/* body */
		goto _continue;
	_break:
		/* else */
	}
	else {
		/* then */
	}
```

This two-block extended form is referenced in Wikipedia as "loop with test in the middle" as proposed by Ole-Johan Dahl in 1972. If a loop isn't followed by a while expression, it represents an infinite loop.

This feature was added because it's a much more common programming pattern than one would think. Executing code, checking for loop exit, and upkeep.

#### For in
`["for" "(" [name "in"] iter ")" body ["then" then] ["else" else]`

Iterates over `iter`, putting the result in `name` and executing `body`. Note that `name "in"` is optional, and integers in espresso are iterable (resulting in a range from 0 to the integer, exclusive). Thus, `for` can be used like some languages use `repeat` to repeat a block a certain number of times:

`for(10) fn()` will execute `fn()` 10 times.

C-like `for` loops can be approximated by including a variable, eg:

`for(var i in 10) fn(i)` similar to `for(int i = 0; i < 10; ++i) fn(i)`

### Try else
`"try" body "then" then "else" else`

Execute `body`. If it completes without failure, execute `then`. Otherwise, execute `else`. This is based on an opinionated language design that exceptions are exceptional, so the caught error isn't immediately exposed; it can be recovered using `fail.error`. The whole expression as an rvalue is the result of the last block which executed. The syntax was optimized for idiomatic usage, eg:

`try mayFail() else fallback()` that is, evaluate `mayFail()`. If it's successful, use its value, otherwise use the result of `fallback()`.

### Switch case
```ebnf
op = {"is" "not"} | {"not" "in"} | cmp
"switch" expr "{" {
	"case" [[op] value] [":" | "=>"] body
} "}" ["then" then] ["else" else]
```

Determine the first match for an expression. Evaluates to the last executed body. It uses an extended form of C-like switch-case statements. Normal cases with `:` execute as a block which falls through at the end. Cases with `=>` automatically `break` at the end of their execution. Both can surround their contents with curly braces. The default case is an empty case statement, avoiding the introduction of an extraneous keyword.

The `then` block executes when execution reaches the end of a `=>` block or falls off the end of the switch expression. The `else` block executes when a break is executed. If `then` or `else` is executed, they are its result value.

The switch expression also acts as a pattern matching syntax. If there is no op and value is a non-identifier lvalue, the pattern is checked and destructured if it matches. Destructuring and prototype-checking can be combined using the syntax `{destructure} is MyProto`. Prototypes may override the `case` operator to change their behavior in a switch expression. In the rare edge case one wants to match a value literally and not with its `case` semantics (eg range), they can surround the expression with parentheses. There is no syntax like Python's `case _:` which allows one to capture the value as a wildcard pattern.

### Statements
`"break" [label | int | kw]` breaks from the specified statement, defaulting to the innermost.
`"continue" [label | int | kw]` continues from the statement.
`"goto" label` goto a label which must be in an enclosing block. Goto statements cannot enter a block.

`break` and `continue` can optionally take a label (targeting the statement that follows it), a literal integer (relative inside-out 0-indexed block), or one of the statement keywords (`if`, `loop`, `while`, `for`, `switch`) optionally with another literal integer which only targets that kind of block. Eg, `break for 2` will break the 3rd for loop. Note that `continue` cannot target `if` or `switch`.

`goto` is specially restricted such that it cannot accept backreferences, labels are block-scoped (thus, it cannot jump into a block), and it cannot jump out of a function.

## Functions
`param = ["var" | "const"] uvalue [":" expr] ["=" expr]`

### Normal
`["var" | "const"] ["async"] "function" ["..."] [name] "(" [param {"," param}] ")" expr`

Normal functions can be statements or expressions. Statements define the function (const in closed namespaces, var in open namespaces) hoisted to the containing block. Statements may not have computed names. Expressions do not define the function, but *can* have computed names, which are functionally only useful for debugging.

Function bodies can begin and end with curly braces `{ ... }`, or they can be normal expressions. The last value will be returned by default, with some restrictions. Statements, assignments, and variable declarations will not be returned by default.

Function parameters support destructuring, default values, and rest parameters. Optionally, `this` may be included among the parameters which will bind that parameter to `this` when the function is not called as a method. This is especially useful for generic methods. For instance,

```js
function test1(this, x, y) {
	return (x + y)*this;
}
function test2(x, y, this) {
	return (x + y)*this;
}

test1(10, 2, 3) == test2(2, 3, 10)
 == 10->test1(2, 3) == 10->test2(2, 3) == 50
```

Optionally a declarator may be used to specify the mutability of a function in its scope. Functions are const by default.

### Arrow
Arrow functions lexically bind `this` (unless it has `this` among its parameters) and have roughly the same syntax as JS. The parser treats it as a sort of destructuring expression to simplify the logic, resulting in a less restrictive grammar than JS arrow functions. An identifier followed by an arrow is immediately evaluated as an arrow function, so the syntax `x, y, z => z` evaluates to a tuple with the last element being the identity function whereas `(x, y, z) => z` evaluates to a tuple destructure arrow function (aka a normal function).

### Dot
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

Note that this syntax in most other languages would always produce parsing errors, so it's always unambiguous. Also note that this requires the operand to be the leftmost in the expression - eg there is no dot function for `x => "prefix " + x`. This isn't really a problem because functions support higher order functional composition, so eg adding two functions together will produce a third function which evaluates the two subfunctions and add their results together.

Thus, `1/.length` is parsed as `1 / (.length)` and produces an equivalent arrow function `...args => 1(...args) / (x => x.length)(...args)`. Numbers used as functions evaluate to themselves, resulting in the final arrow function `x => 1/x.length`

### Prefix calling
When an identifier is followed by string, number, or object literal, it's invoked as a unary function with that value. This allows us to simulate idioms found in other languages, like templates in JS: `html"<i>safe \{v}</i>"`. If the object contained by the identifier overrides the `template` (?) operator, it is passed a list of interpolation strings followed by the values between those strings (ie `(tpl, ...values) => alternate(tpl, values)->join('')` as the default behavior) ala the JS template literal syntax.

### Trailing call
`x { ...object }`
`x(1, 2, 3) { ...object }`
`x(x, y) => { body }`

## Proto
Espresso is fundamentally a protype-based language. The core object model built into the language itself is delegated prototype chains. Objects have "own properties", which are properties on the object themselves, and "inherited properties", which are non-own properties that are an own property of an object in the prototype chain.

That being said, while prototypes themselves are not treated specially (any object can be a prototype without exception) syntax sugar is provided to define a prototype the way one might define a class in an OOP language.

`"proto" [name] ["is" parent] "{" ??? "}"`

This defines an object named `name` with `parent` as the prototype (or `none`) and with the properties defined in the following block, which has a custom syntax not found anywhere else in the language. The block is a series of entries similar to object literals which have more options for type qualification and other syntax sugar. Instead of commas, they're separated by end-of-statement and semicolons.

### Member fields
Member fields are properties which are expected to appear in prototype instantiations. There are two ways to declare them:

* `public` declares a public property
* `protected` declares a protected property, which is non-enumerable but can be accessed on any object so long as you have the key
* `private` declares a private property, which is also non-enumerable but has the additional restriction that it must be accessed using `this` or the generic function applicator `->`. By default, it additionally creates a symbol accessed in the prototype's scope as the private member's name (eg `private x` is accessed via `this.(x)` or `this[x]`).

### Static fields
Static fields are syntax sugar which is passed to the global proto operator to be a property on the prototype object itself but not on its instances. These are defined by:

`("static" ["var" | "const"] | ["var" | "const"]) decl`

### Methods
Methods are declared as either member or static, and use the same syntax as object methods.

### Prototyping
A prototype which overrides the `proto` operator can control how their children are prototyped. The operator is passed the prototype's name and a list of fields in order of declaration. `this` is the prototype, and the return value is the result of the prototyping. This mechanism is extremely powerful, as it allows prototypes to effectively work like any number of metatyping constructs found in other languages, which Espresso treats as first class values. Prototypes which override the `proto` operator are called "metatypes". Usually these will override more operators to implement type algebras.

#### Class
`class` is a metatype which composes a "class" type and behaves more or less like one would expect in an OOP language. To allow for operator overriding instances, `class` maintains two separate prototype chains with mutually references `instance` and `class`.

#### Struct
`struct` is a metatype which acts like a combination of Pythons' `dataclass`, `cffi`, and `struct.(un)pack`. All fields are typed and define the data layout.

#### Enum
`enum` is a metatype which allows one to enumerate a fixed set of values all sharing the same type.

#### Union
`union` is mostly used for type checking of values which can be one of a number of types.

#### Interface
`interface` is mostly used for validation of code correctness. It ensures objects which inherit from it have all the necessary methods for an interface, and it applies even to objects that don't inherit from it, provided they still satisfy its interface.

## Namespaces
Three types of namespaces are recognized: closed, module, and open.

### Closed
In a closed or static namespace, every variable is bound and accounted for and variable lookup is equivalent to indexing an array. Espresso by default will try to make any namespace it can closed because it lessens the level of indirection.

### Module
Module namespaces are used to solve intermodule coupling issues when star imports are involved. If there are no star imports, every variable is either bound or a syntax error (because it has no valid binding). If there is a star import, the local scope of the module depends on the scope of the imported module which cannot be determined until runtime without introducing unacceptable coupling between object files. Bound variables can still be looked up the same as in closed namespaces, but unbound variables (which may come from the star import) require a level of indirection, comparable to dynamic linking.

The equivalent is an array of pointers to variable slots. The array represents the set of unbound variables (with each index corresponding to a different unbound variable). A possible optimization in the JIT stage is to bake in these references into code rather than looking them up, since they're set once and never touched again.

The object returned by import is built from exported objects, not the top level namespace, so modifying the module object won't modify its namespace. Modules are syntax sugar for a nullary function call.

```js
export function myFunc() { ... }

return {a: 3};
```

is roughly equivalent to

```js
function import() {
	const module = {a: 3};
	const exports = new module {
		myFunc() { ... }
	}
	return exports;
}
```

The return of a module (inspired from Lua) is set as the prototype of the module object, with exports being own properties. If a return isn't specified, `none` is assumed.

### Open
Open or dynamic namespaces do not have a limit to the number or names of the variables they contain. These are primarily useful for REPLs, where names can be introduced where none existed before. As such, they must be accessed via a dictionary lookup. This mode of namespace can also be combined with a closed namespace by dynamically growing the variable register array. This is useful for functions added to the open namespace which already have all their variables bound.

### Namespace
The `namespace` keyword returns an open namespace prototyped by an optional object and initialized using the provided block. As a statement, it's declared as a const variable using its mandatory name. As an expression, the name is optional (for debug).

Dynamic namespaces are created by enclosing the object in parentheses, like:
```js
namespace name(obj) {}
```

This has the same semantics as JS ```with``` and exists solely as a way to replicate REPL dynamic namespaces, since lexical scoping is otherwise static. If `obj` is not provided, eg `namespace name { ... }`, it's a closed namespace equivalent to importing the enclosed code as a module.

# Standard library
An aim of espresso is to yield arbitrary complexity from a small set of self-consistent rules. The standard library builds on top of the base language and implements features to be used in all espresso programs. This includes operator overload protocols, second order object models, and the methods of built-in types among others.

## Protocols
This section describes the various language protocols

### Iterable
Has a method named "iter" which returns an iterator. Almost always an iterator should implement iterable as well, returning itself.

### Iterator
Considered a special case of functions which, when invoked, can return different values. If the returned value is the sentinel value StopIteration, iteration will end. Subsequent calls should be StopIteration as well.

### Generator
Generators are a single type for computed iterators and stackless coroutines meant for suspending and resuming execution within the function body. They implement three methods: `yield`, `throw`, and `return`. `yield` continues execution and returns the next yielded value - it can accept one argument, which is what the yield expression evaluates to within the generator. `throw` throws an error into the generator from the point where execution would resume. `return` stops the generator.

### With
To help with the lack of RAII, the `with` statement from Python is incorporated. The protocol used is like Python's context manager - a `with` method is implemented as a stackless coroutine. `with` is first called when the with block is entered, then the coroutine is resumed with the value/error which exits the block, and finally .return() is called. Technically this means a coroutine isn't necessary, just a function which returns a function implementing the coroutine interface.

### New
`"new" type [params]`

The `new` operator doesn't have special handling by the language, it's syntax sugar for calling the global `new` function. The standard library implements the global function as a wrapper around an operator overload, `type->object.proto(type).new(...params)`.

## Second-order object model
The standard library implements a class-like object model on top of the built in prototype object model by maintaining separate `class` and `instance` prototype chains, kept synchronized by coreferences of the same names. This enables type algebra syntaxes (including a `new` operator performed on types), as a flat prototype chain would give types the same operators their parents implement for the instances.

```
none ⟵ metaobject ⟵ class ⟵ Parent ⟵ type
 ↑                    ⥮      ⥮       ⥮
 └───────────────── {...} ⟵ {...} ⟵ {...} ⟵ new type
```

## Type hierarchy
never (type of a function which never returns)
none
	any
		primitive
			number
				int
					bool
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
array: int[]
object: {x: int, y: string, z: (int, int)}
nullable: type?
function: (int, int) => int
union: int|float
intersection: int&string (like char)

# Implementation considerations
## Roadmap
* MVP interpreter written in Python
* Espresso parser written in Espresso
* Bytecode VM
* JIT compilation

## Boxing
### Invariants
For a boxed value, integer value 0 should be interpretable as none to simplify nullish checks.

### 32-bit
On 32 bit systems boxing must be done using pointer tagging with the low bits signalling the encoded type. The particular implementation of value boxing is not exposed to Espresso code, and the most optimal implementation will differ between architectures, but the suggested format is:

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
The GC algorithm I hope to use is heavily inspired by [this](http://wiki.luajit.org/New-Garbage-Collector) quasi-paper on a speculative GC for LuaJit 2.0 with special considerations made for Espresso's object model. The major points are:
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
	* Value types are allocated here because despite being immutable, they will be deallocated eventually so cannot be interned. Interning is also a waste of time if the string isn't going to be used as a key
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
Inevitably an IR bytecode must be developed to be
1. trivial to interpret in the Espresso runtime
2. trivial to JIT compile
3. support strict mode semantics (both dynamic and strict typing)

Wasm is likely to be the primary source of inspiration along with CPython. Both of these are quasi-stack machines, storing variables in slots and intermediates on a value stack.

### JIT
JIT is a hard problem here because we want to be as lightweight as possible, and available JIT libraries (LLVM, GNU libjit, etc) are not. It may be a better idea to take inspiration from LuaJIT, which uses DynAsm as an integrated dynamic assembler. That alone won't work well however because it requires a preprocessing stage, is developed with Lua specifically in mind, and has no (official) documentation. One possible library to look into is AsmJIT, though that is currently x86 only. A long term goal could be to implement the JIT in espresso itself rather than using an external library, predicated on exposed unsafe syscalls.

# Context
## Inspirations
Quick list of languages researched for feature integration:
* JavaScript
  - JerryScript (tight constraints)
  - V8
    * Cutting edge optimizing JIT (with examples of features which add significant complexity to the JIT pipeline for minimal benefit)
	* Value boxing in 64-bit words
    * Hidden classes/shapes
	* Inline cache
	* Type inference
	* Accumulator-based register bytecode
	* Highlights the importance of multimethods, which V8 uses internally for specialized JITed functions
  - Node.js
    * Destructuring to import (`const {x, y} = require("z")`)
  - Core syntax
  - Prototype-based programming
  - Triple equals (strict comparison semantics replaced with unoverloadable identity comparison)
  - Destructuring syntax
  - Template string literals
  - Variable declaration and scoping (only let semantics using var)
  - Arrow functions (recontextualized as a special destructuring)
  - Untyped exception handling
  - Lessons in the pitfalls of too-dynamic code and too permissive auto-coercion
* TypeScript
  - Type annotation semantics
* Python
  - Expressiveness
  - `__slots__` and `__dict__`
  - Type hierarchy (esp string/bytes/buffer, tuple/list)
  - Comparison operator chaining
  - Loop-else (extended, Pythonic semantics inverted)
  - String triple quoting
  - Generalized user-defined decorators
  - Docstrings (Comments before statements) - generally, keeping documentation and debug information in a REPL environment
  - Keyword operators (`in`, `is`, `and`, `or`, `not`, ...)
    * Compound keyword operators `is not` and `not in`
  - In-place operator overloading
  - match-case pattern matching and destructuring
  - Metaclasses and inheritance hooks
  - With block (and `contextmanager`)
  - Static type annotations after 30 years indicates pure duck/dynamic typing is a bad idea
  - Annoyance with `import x` vs `from x import y` syntax inspiring Espresso's `import x as {y}` because changing `import` to `from` is annoying
  - Numpy (demonstrates highly dynamic VM tying together bare metal code is viable)
  - PyPy 
    * Lessons in self-hosting via restricted subsets of a dynamic language
	* Stacklets and continulets as a practical and composable implementation of stackful coroutines
* Lua (philosophy, implementation/internals, nil)
  - "Less is more" philosophy, especially wrt parser simplicity
  - LuaJIT (simple JIT implementation)
  - Field calling eg f{a=10, b=20} or f "string"
  - Metatables (combined with JS prototyping, operator overloading begins resolution at the prototype, not own properties)
  - Property chains for function name (eg `function a.b.c() end`)
  - Register bytecode for addressing virtual stack-allocated variables
  - Upvalues
  - Stackful coroutines via ordinary functions
  - Operator overload functions not having an explicit reversed function (ala Python's `__radd__`)
  - 1-based indexing is a bad idea
  - "Everything is a table" is a nice idea, but Lua has been slowly backtracking because it actually increases complexity and decreases performance because you effectively have to reimplement type checking
* Julia
  - Number suffixes are normal function calls (previously considered having a special namespace but Julia just uses eg 1im which is much more elegant and still easy to read)
  - Dedenting triple quoted strings
  - Strings are always formatted implicitly
  - Colon prefix to make symbols (also used in Ruby) and lispian quoting of expressions with interpolation (might use \ instead actually)
  - @ macros (composes well with the decorator syntax)
  - Implicit return of last value
  - Highlights the importance of multimethods
* Dart (concurrency model, JS concept streamlining)
* Scala (operators as valid contextual identifiers)
* Java (public/private/static)
  - Labeled blocks
* PHP (break/continue on int)
* C (syntax, string/int char)
* C++ (scope operator ::)
  - Scope operator ::
  - String suffixes
  - Operator overloading
  - `concept` generalized and expanded to anything which overrides `is` operator
  - Metaclass proposal is a big inspiration for `proto`
* Slate (Prototypes with Multi-Dispatch)

## Key assumptions
This is a list of assumptions made about the programming style and data utilization of a program in order to optimize the most common case:
* Prototypes consist primarily of a fixed set of mostly unmutated methods/properties known at compile-time
* Prototype instantiations have a similar fixed set of properties (defined by public/private keywords) which are arbitrarily mutated and rarely extended (extension is provided via the property lookup table)
* Most data has a fixed size, and dynamic sizes can be represented via references
* In general, hash tables grow and rarely have entries deleted
* The prototype of an object very rarely changes

## Design notes
I originally thought `=` could be a meta-operator combining with any arbitrary binary operator to its left, such that eg `+ =` would be the same as `+=`. This is "pretty" from a high level design POV, but in implementing the parser I realized that this combined with the precedence climbing algorithm produced a fundamental contradiction. The normal operator could only be consumed if we knew its precedence was sufficiently high, but the `=` meta-operator would change its precedence to one of the lowest. Thus we need to consume the token to know its precedence, but we can't consume the token until we know its precedence. There were some "clever" hacks to try to get around this (tentatively consuming for sufficient precedence, then bailing if we parse `=` and modifying `self.cur` to semantically combine them) but the complexity grew and grew, all to implement a feature that, let's face it, has no practical value. I only thought of it in the first place because I thought it would make parsing easier, but it turns out it would require either a lot of extra code or I'd have to upgrade the parser to LR(2).

Alternatively, this could be implemented on the tokenizer level, or a separate stage of the pipeline