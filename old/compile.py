#!/usr/bin/env python3

from ast import Expr
from codeop import Compile
import types
from multimethod import multimeta
from typing import List, Mapping, Union

import esp_ast as ast
import parse
from runtime import EspNone, EspProto, EspString, EspList, EspDict, EspIterator
#import common

from dataclasses import dataclass, field

indent = ast.indent

# Stack effects for bytecode operators
EFFECT = dict([
	*((op, 0) for op in {
		"block", "end", 'break', 'loop', 'else'
	}),
	*((op, 1) for op in {
		"dup", "load", "ldup", 'const', 'inc', 'dec', 'func'
	}),
	*((op, -1) for op in {
		'add', 'sub', 'mul', 'div', 'mod',
		'pow', 'idiv', 'mod2',
		'eq', 'ne', 'gt', 'ge', 'lt', 'le', 'ideq',
		'lsh', 'lsh3', 'rsh', 'ash',
		'inv', 'band', 'bor', 'xor',
		'inv2', 'and', 'or', 'xor2',
		'in', 'is', 'as', 'has',
		
		'store', 'stup', 'if', 'drop'
	})
])

runtime_global = {
	"iter": iter,
	"next": next,
	"print": lambda *x: print(*x, end='') or EspNone,
	"pyimport": __import__,
	"none": EspNone,
	"true": True,
	"false": False,
	"nan": float('nan'),
	"inf": float('inf'),
	"char": chr
}

OPS = {
	"+": "add", "-": "sub", "++": "inc", "--": "dec",
	"*": "mul", "/": "div", "%": "mod",
	"**": "pow", "//": "idiv", "%%": "mod2",
	"==": "eq", "!=": "ne", "===": "ideq",
	"<": "lt", "<=": "le", ">": "gt", ">=": "ge",
	"<<": "lsh", "<<<": "lsh3", ">>": "rsh", ">>>": "ash",
	"~": "inv", "&": "band", "|": "bor", "^": "xor",
	"~~": "inv2", "&&": "and", "||": "or", "^^": "xor2",
	"in": "in", "as": "as", "has": "has", "is": "is", "call": "call"
}

class EspBaseException(Exception): pass
class EspException(EspBaseException): pass

class SemanticError(EspException):
	def __init__(self, origin, msg):
		if origin:
			p, l, c = origin.pos, origin.line, origin.col
			msg += f" ({l}|{c}:{p})\n"
			msg += origin.src.split('\n')[l - 1].replace('\t', ' ')
			msg += f"\n{'-'*c}^"
		
		super().__init__(msg)
		self.origin = origin

class EspRefError(EspException):
	def __init__(self, ref):
		super().__init__(f"No such variable {ref!r}")

def expandBlock(block):
	if isinstance(block, ast.Block):
		return block.statements
	else:
		return [block]

def flatten(it):
	'''Flatten an iterable of iterables'''
	for x in it:
		yield from x

def typename(x):
	return type(x).__name__

@dataclass
class Argument:
	name: str
	validate: Union[Expr, None]
	default: Union[Expr, None]
	
	def __str__(self):
		v = f": {self.validate}" if self.validate else ""
		d = f" = {self.default}" if self.default else ""
		return f"{self.name}{v}{d}"

@dataclass
class EspFunc:
	name: Expr
	args: List[Argument]
	upvars: List[str]
	slots: List[str]
	stack: int
	blocks: int
	code: list
	
	def __str__(self):
		def _part(x):
			ind = 0
			for op, *rest in x:
				if op == "func":
					name, args, slots, stack, blocks, code = rest
					code = indent('\n'.join(_part(code)))
					yield indent(
						f"({op} {name} {args} {slots} {stack} {blocks}\n{code})", ind
					)
				else:
					if op in {"else", "end"}:
						ind -= 1
					
					yield indent(
						f"({' '.join([op, *(repr(a) for a in rest)])})", ind
					)
					
					if op in {"block", "if", "else"}:
						ind += 1
		
		name = self.name
		args = self.args
		code = indent('\n'.join(_part(self.code)))
		
		return f"(func {name} [{' '.join(args)}]\n{code})"

class EspClosure:
	func: EspFunc
	upvars: list

class SwitchPredicate:
	'''
	Switch predicate expressions have the potential to be very complicated
	because they map a set of disparate predicates onto a simple range of
	jump table indices. Rather than implement all the machinery to make that
	work, we're cheating by implementing it in Python and using the py opcode
	'''
	
	__name__ = "SwitchPredicate"
	
	def __init__(self, table):
		eqtab = {}
		intab = []
		
		for i, (op, value) in enumerate(table):
			if op == "==":
				eqtab[value] = i
			elif op == "in":
				intab.append((value, i))
			else:
				raise RuntimeError(f"Unknown switch op {op}")
		
		self.eqtab = eqtab
		self.intab = intab
		self.dei = len(table)
	
	def __call__(self, vm):
		ex = vm.A
		if ex in self.eqtab:
			return self.eqtab[ex]
		
		for val, i in self.intab:
			if ex in val:
				return i
		
		return self.dei

@dataclass
class FScope:
	'''
	Function scope
	'''
	
	# Depth of the block stack
	blocks: int = 0
	# A stack of block depths for breakable blocks
	breaks: List[int] = field(default_factory=lambda: [])
	
	# Number of variable slots
	slots: int = 0
	# A stack of name:slot dictionaries composing the scope
	scope: List[Mapping[str, int]] = field(default_factory=lambda: [])

class Assembler(ast.Visitor):
	blocks: int
	stack: int
	breaks: List[int]
	slots: int
	scope: List[Mapping[str, int]]
	upvars: Mapping[str, int]
	
	maxstack: int
	maxblocks: int
	
	def __init__(self):
		self.blocks = 0
		self.stack = 0
		self.breaks = []
		self.slots = 0
		
		self.upvars = {}
		
		self.maxstack = 0
		self.maxblocks = 0
	
	def breakable(self, th, el=None):
		'''Generate a block which can accept a break from user code'''
		
		self.breaks.append(self.blocks)
		
		yield from self.block(th, el)
		
		self.breaks.pop()
	
	def block(self, th, el=None):
		'''Generate bytecode for a block, optionally with an else block'''
		
		self.blocks += 1
		
		th = list(self.sequence(th))
		
		yield ['block', len(th)]
		yield from th
		
		self.blocks -= 1
		
		if el is not None:
			el = list(self.sequence(el))
			if len(el) > 0:
				yield ['else', len(el)]
				yield from el
		
		yield ['end']
	
	def sequence(self, body):
		'''Expand bytecode generators in a list'''
		
		for b in body:
			if b is None:
				continue
			elif isinstance(b, list):
				yield b
			else:
				yield from b
	
	def condition(self, th, el):
		'''Generate bytecode for an if-else block'''
		
		th = list(self.sequence(th))
		el = list(self.sequence(el))
		
		yield ['if', len(th)]
		yield from th
		
		if len(el) > 0:
			yield ['else', len(el)]
			yield from el
		
		yield ['end']
	
	def br(self, n):
		'''Determine the branch target for a user branch'''
		
		return self.blocks - self.targets[-n - 1]
	
	def upvar(self, name):
		return name
	
	def compile(self, x):
		for bc in self.visit(x):
			op, *args = bc
			
			if op in {"call", "format"}:
				self.stack += 1 - args[0]
			elif op in EFFECT:
				self.stack += EFFECT[op]
			else:
				print("No such op", op)
				pass
			
			self.maxstack = max(self.stack, self.maxstack)
			
			if op in {"block", 'if'}:
				self.blocks += 1
			elif op == "end":
				self.blocks -= 1
			
			self.maxblocks = max(self.blocks, self.maxblocks)
			
			yield bc

class AssignVisitor(Assembler):
	def __init__(self, parent):
		super().__init__()
		
		self.parent = parent
	
	def visit(self, x):
		if x.lvalue:
			raise NotImplementedError(
				f"Compiling assignment to {type(x).__name__}"
			)
		else:
			raise ValueError(
				f"Assigning to non-lvalue {type(x).__name__}"
			)
	
	def visit(self, x: ast.Name):
		slot = self.parent.resolve(x.name)
		if slot is None:
			self.parent.upvars[x.name] = True
			yield ['stup', x.name]
		else:
			yield ['store', slot]

class CompileVisitor(Assembler):
	def __init__(self, parent=None):
		super().__init__()
		
		self.scope = [{}]
		self.parent = parent
	
	def assign(self, lv):
		'''Compile code to assign TOS to the given lvalue'''
		
		return AssignVisitor(self).visit(lv)
	
	def resolve(self, name):
		'''Resolve a name to its slot index'''
		
		cur = self
		while cur is not None:
			for scope in cur.scope:
				if name in scope:
					return scope[name]
			
			cur = cur.parent
		
		return None
	
	def define(self, name: str):
		'''Define a variable in the current block scope'''
		
		self.scope[0][name] = self.slots
		self.slots += 1
	
	def statement(self, x):
		'''Handle statements and make sure the stack is reset by the end'''
		
		last = None
		for bc in self.visit(x):
			last = bc
			yield bc
		
		if last is not None:
			op = last[0]
			if op in {"store", "stup"}:
				return
			
			if op == "call" or EFFECT[op] != 0:
				yield ['drop']
	
	def visit_block(self, block):
		'''Visit subexpressions to expand into a block'''
		
		for b in expandBlock(block):
			yield from self.statement(b)
	
	def visit(self, x):
		raise NotImplementedError(f"CompileVisitor({type(x)})")
	
	def visit(self, x: None):
		yield from ()
	
	def visit(self, x: ast.Prog):
		for decl in x.decls:
			self.define(decl.name)
			
		for statement in x.statements:
			yield from self.statement(statement)
	
	def visit(self, x: ast.Block):
		self.scope.insert(0, {})
		
		for decl in x.decl:
			self.define(decl.name)
		
		yield from self.block([
			# Block expands generators as bytecode
			flatten(self.statement(v) for v in x.statements)
		])
		
		del self.scope[0]
	
	def visit(self, x: ast.Func):
		if not isinstance(x.name, ast.Const):
			raise NotImplementedError(f"Variable function name {x.name}")
		
		#self.define(x.name.value)
		
		subc = CompileVisitor(self)
		
		for name in x.args:
			subc.define(name.name)
		
		fnbody = subc.visit(x.body)
		
		yield ['func', x.name, x.args, subc.slots, subc.stack, subc.blocks, list(fnbody)]
		yield from self.assign(ast.Name(x.name.value))
	
	def visit(self, x: ast.If):
		yield from self.visit(x.cond)
		yield from self.condition(
			[self.visit(x.th)],
			[self.visit(x.el)]
		)
	
	def visit(self, x: ast.Loop):
		# (loop always cond body then else)
		
		yield from self.breakable([
			self.visit(x.always),
			self.visit(x.cond),
			self.condition([
			# then
				self.visit_block(x.body),
				['break', 1]
			], [
			# else
				self.visit_block(x.th),
				['loop', 1]
			])
		], [
			self.visit_block(x.el)
		])
	
	def visit(self, x: ast.ForLoop):
		yield from [
			['const', EspNone],
			self.upvar('iter'),
			self.visit(x.iter),
			['call', 1], # TOS = iter(x.iter)
			self.breakable([
				['dup'],
				['const', 'next'],
				['method', 0], # value = TOS.next()
				['dup'],
				['const', 'unknown'],
				['ideq'], # if(value === unknown)
				self.condition([
					self.visit(x.th),
					['break', 1]
				], [
					# Unpack TOS into the itvar
					self.assign(x.itvar),
					self.visit(x.body)
				]),
				['loop', 0]
			], [
				self.visit(x.el)
			])
		]
	
	def visit(self, x: ast.Branch):
		if x.kind == "break":
			yield ['break', self.br(x.level)]
		elif x.kind == 'continue':
			yield ['loop', self.br(x.level)]
	
	def visit(self, x: ast.Const):
		yield ['const', x.value]
	
	def visit(self, x: ast.Name):
		slot = self.resolve(x.name)
		if slot is None:
			self.upvars[x.name] = self.upvars.get(x.name, False)
			yield ['ldup', x.name]
		else:
			yield ['load', slot]
	
	def visit(self, x: ast.Op):
		op = x.op
		if op in {"--", "++"}:
			lhs, rhs = x.elems
			val = lhs or rhs
			
			#lhs ++ rhs
			
			if rhs is None:
				yield ['const', None]
			
			yield from self.visit(val)
			
			# Suffix form, dup the original value
			if rhs is None:
				yield ['dup']
			else:
				yield ['const', None]
			
			yield [OPS[op]]
			
			# Prefix form, dup the result of the inc/dec
			if lhs is None:
				yield ['dup']
			
			yield from self.assign(val)
		elif op == "after":
			yield from self.visit(x.elems[0])
			yield from self.visit(x.elems[1])
			yield ["drop"]
		elif op == "format":
			for part in x.elems:
				yield from self.visit(part)
			
			yield ["format", len(x.elems)]
		else:
			for el in x.elems:
				yield from self.visit(el)
			
			if op == "call":
				yield ['call', len(x.elems) - 1]
			else:
				yield [OPS[op]]
	
	def visit(self, x: ast.Assign):
		yield from self.visit(x.rhs)
		yield from self.assign(x.lhs)

def compile(x):
	cv = CompileVisitor()
	code = list(cv.compile(x))
	return EspFunc("<program>", [], [], cv.slots, cv.maxstack, cv.maxblocks, code)

'''
# Another resurrection of this idea. Have a VM in Python that can interpret
#  a high level bytecode targeted by the early implementations of both Crema
#  and Espresso. I thought it would slightly more complex due to the lower
#  level constructs, but ultimately worth it because I wouldn't have to
#  reimplement the VM with each iteration. Turns out, a linear bytecode is
#  sufficiently non-trivial that I wouldn't want to actually implement it
#  more than once. It would be better to just add to a Python AST interpreter
#  until Espresso has enough features to implement it in itself

class Compiler:
	def visit(self, ast):
		match ast:
			case ['const', val]: yield ['const', val]
			case ['id', name]: pass
			case ['var', vars]: pass
			case ['fail', val]:
				yield from self.visit(val)
				yield ['fail']
			case ['return', val]:
				yield from self.visit(val)
				yield ['ret']
			case ['break']: yield ['break', self.br()]
			case ['continue']: yield ['loop', self.br()]
			
			case ['block', stmts]:
				self.push_block()
				yield from self.block([flatten(self.statement(v) for v in stmts)])
				self.pop_block()
			
			case ['loop', always, cond, body]:
				self.push_block()
				yield from self.breakable([
					self.visit(always),
					self.visit(cond),
					self.condition([
						self.visit(body),
						['break', 1]
					])
				])
				self.pop_block()
			
			case ['for', itvar, iter, body]:
				self.push_block()
				yield from [
					self.upvar('iter'),
					self.visit(iter),
					['call', 1], # TOS = iter(x.iter)
					self.breakable([
						['dup'],
						['const', 'next'],
						['method', 0], # value = TOS.next()
						['dup'],
						['const', StopIteration],
						['ideq'], # if(value === StopIteration)
						self.condition(['break', 1], [
							# Unpack TOS into the itvar
							self.assign(itvar),
							self.visit(body)
						]),
						['loop', 0]
					])
				]
				self.pop_block()
				
			case ['switch', cond, cases]:
				self.push_block()
				
				table = {}
				deconst = ['const', None]
				yield from [
					self.visit(cond),
					['const', table],
					['get'],
					['dup'],
					['const', esp_none],
					['ideq'],
					['if', 2],
						['drop'],
						deconst,
					['end']
				]
				
				it = iter(cases)
				index = 1
				
				op, val, body = next(it)
				table[val[1]] = 0
				first = list(self.visit(body))
				if op == "default":
					deconst[1] = 0
				
				yield ['switch', len(first)]
				
				for op, val, body in it:
					table[val[1]] = index
					body = list(self.visit(body))
					yield ['then', len(body) + 1]
					yield from body
				yield ['end']
			
			## Expressions with results ###
			
			case ['list', elems]:
				return proto_list(self.rval(el) for el in elems)
			
			case ["object", entries]:
				return proto_object((self.rval(k), self.rval(v)) for k, v in entries)
			
			case ['fn', args, body]:
				return EspFunc(args, body, self.scope)
			
			case ['call', ['.', this, fn], args]:
				this = self.rval(this)
				fn = self.rval(fn)
				result = self.call(getattr(this, fn), this, args)
			
			case ['call', fn, args]:
				fn = self.rval(fn)
				result = self.call(fn, None, args)
			
			case ['if', cond, th, el]:
				self.push_block()
				self.rval(th if self.rval(cond) else el)
				self.pop_block()
			
			case ['.', lhs, rhs]:
				result = self.lval(ast).get()
			
			case ["and", lhs, rhs]:
				result = self.rval(lhs) and self.rval(rhs)
			
			case ["or", lhs, rhs]:
				result = self.rval(lhs) or self.rval(rhs)
			
			case [op, *args]:
				if len(args) == 1:
					result = self.unary(op, *args)
				else:
					result = self.binary(op, *args)
'''