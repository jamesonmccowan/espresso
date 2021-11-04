#!/usr/bin/env python3

from multimethod import multimeta
import typing

import ast
from runtime import EspNone, EspProto, EspString, EspList, EspDict

class StackFrame:
	def __init__(self, fn, vars):
		self.fn = fn
		self.vars = vars
	
	def __str__(self):
		return "StackFrame" + str(self.vars)
	__repr__ = __str__

SIMPLE_OPS = {
	"+": lambda x, y: x + y,
	"-": lambda x, y: x - y,
	"*": lambda x, y: x * y,
	"/": lambda x, y: x / y,
	"%": lambda x, y: x % y,
	"**": lambda x, y: x ** y,
	"//": lambda x, y: x // y,
	"%%": None,
	"..": lambda x, y: range(x, y),
	"...": None,
	
	"!": lambda x, y: not y,
	"~": lambda x, y: ~y,
	"&": lambda x, y: x & y,
	"|": lambda x, y: x | y,
	"^": lambda x, y: x ^ y,
	
	"!!": lambda x, y: bool(y),
	"~~": None,
	"||": lambda x, y: x or y,
	"&&": lambda x, y: x and y,
	"^^": None,
	
	"==": lambda x, y: x == y,
	"!=": lambda x, y: x != y,
	"===": lambda x, y: x is y,
	"!==": lambda x, y: x is not y,
	"<": lambda x, y: x < y,
	"<=": lambda x, y: x <= y,
	">": lambda x, y: x > y,
	">=": lambda x, y: x >= y,
	"<>": lambda x, y: (x <= y) - (x >= y),
	"<<": lambda x, y: x << y,
	"<<<": None,
	">>": lambda x, y: x >> y,
	">>>": None
}

class Signal(Exception): pass
class BreakSignal(Signal): pass
class ContinueSignal(Signal): pass

class ReturnSignal(Signal):
	def __init__(self, value):
		self.value = value

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

class LValue:
	def __init__(self, obj, index):
		self.obj = obj
		self.index = index
		
		assert(type(index) == list)
	
	def get(self):
		try:
			return self.obj[self.index[0]]
		except (AttributeError, KeyError, TypeError) as e:
			pass
		
		if type(self.obj) == EspList:
			print(self.obj[self.index[0]])
		#print("getattr", type(self.obj), self.obj, self.index)
		return getattr(self.obj, self.index[0])
	
	def set(self, value):
		try:
			self.obj[self.index[0]] = value
			return value
		except (AttributeError, KeyError, TypeError) as e:
			pass
		
		setattr(self.obj, self.index[0], value)
		return value

class SemanticError(RuntimeError):
	def __init__(self, origin, msg):
		if origin:
			p, l, c = origin.pos, origin.line, origin.col
			msg += f" ({l}|{c}:{p})\n"
			msg += origin.src.split('\n')[l - 1].replace('\t', ' ')
			msg += f"\n{'-'*c}^"
		
		super().__init__(msg)
		self.origin = origin

class EvalVisitor(metaclass=multimeta):
	def __init__(self):
		self.stack = []
	
	def lookup(self, name):
		for x in range(1, len(self.stack) + 1):
			v = self.stack[-x].vars
			if name in v:
				return v
		
		return self.stack[-1].vars
	
	def lvalue(self, x):
		'''Evaluate x as an l-value'''
		if not x.lvalue:
			raise SemanticError(x.origin, "Not an l-value")
		
		return self.lvisit(x)
	
	def rvalue(self, x):
		'''Evaluate x as an r-value'''
		if not x.rvalue:
			raise SemanticError(x.origin, "Not an r-value")
		
		return self.rvisit(x)
	
	def lvisit(self, v: ast.If):
		x = v.th if self.rvalue(v.cond) else v.el
		return self.lvalue(x) if x else EspNone
	def rvisit(self, v: ast.If):
		if self.rvalue(v.cond):
			return self.rvalue(v.th) if v.th else EspNone
		else:
			return self.rvalue(v.el) if v.el else EspNone
	
	def rvisit(self, v: ast.Loop):
		ls = []
		try:
			while True:
				try:
					ls.append(self.rvalue(v.body))
				except ContinueSignal:
					pass
				
		except (BreakSignal, StopIteration):
			self.rvalue(self) if v.el else EspNone
			return ls
	
	def rvisit(self, v: ast.Branch):
		if v.kind == "break":
			raise BreakSignal()
		elif v.kind == "continue":
			raise ContinueSignal()
		else:
			raise NotImplementedError(v.kind)
	
	def rvisit(self, v: ast.Switch):
		# Evaluate the expression to switch on
		ex = self.rvalue(v.ex)
		
		# Find the case statement which matches
		for case in v.cs:
			val = self.rvalue(case.value)
			
			if case.op == "=":
				if ex == val:
					break
			elif case.op == "in":
				if ex in val:
					break
			else:
				raise NotImplementedError("switch case " + case.op)
		else:
			case = v.de
		
		try:
			last = EspNone
			while True:
				last = self.rvalue(case.body)
				
				case = case.next
				if case is None:
					break
		except BreakSignal:
			last = self.rvalue(v.el)
		except ContinueSignal:
			last = self.rvalue(v.th)
		
		return last
	
	def rvisit(self, v: ast.Return):
		raise self.rvalue(ReturnSignal(v))
	
	def rvisit(self, v: ast.Op):
		return SIMPLE_OPS[v.op](*(self.rvalue(x) for x in v.args))
	
	def rvisit(self, v: ast.Value):
		return v.value
	
	def lvisit(self, v: ast.Var):
		return LValue(self.lookup(v.name), [v.name])
	def rvisit(self, v: ast.Var):
		return self.lvalue(v).get()
	
	def lvisit(self, v: ast.After):
		x = self.lvalue(v.value)
		self.rvalue(v.update)
		return x
	def rvisit(self, v: ast.After):
		x = self.rvalue(v.value)
		self.rvalue(v.update)
		return x
	
	def rvisit(self, v: ast.Assign):
		var = self.lvalue(v.name)
		if type(self.rvalue(v.value)) == list:
			print("assign", var, v.value)
			raise ValueError()
		
		if v.op:
			#print(self.stack)
			#print('var', v.name, v.op+'=', v.value)
			old = var.get()
			val = SIMPLE_OPS[v.op](old, self.rvalue(v.value))
		else:
			val = self.rvalue(v.value)
		
		x = var.set(val)
		return x
	
	def rvisit(self, v: ast.Format):
		s = ""
		for p in v.parts:
			if type(p) is str:
				s += p
			else:
				s += self.rvalue(EspString(p))
		
		return s
	
	def visit_block(self, v):
		self.stack.append(StackFrame(v, {x.name:EspNone for x in v.vars}))
		
		last = EspNone
		for x in v.elems:
			next = self.rvalue(x)
			
			if not isinstance(x, ast.Statement):
				last = next
		
		self.stack.pop()
		return last
	
	def rvisit(self, v: ast.Block):
		return self.visit_block(v)
	
	def rvisit(self, v: ast.Prog):
		self.stack.append(StackFrame(None, runtime_global))
		self.stack.append(StackFrame(v, {x.name:EspNone for x in v.vars}))
		x = self.visit_block(v)
		self.stack.pop()
		self.stack.pop()
		
		return x
	
	def rvisit(self, v: ast.Func):
		def pyfunc(*args):
			try:
				self.stack.append(
					StackFrame(v, dict(zip((x.name for x in v.args), args)))
				)
				val = self.rvalue(v.body)
				self.stack.pop()
				return val
			except ReturnSignal as ret:
				return ret
		
		return pyfunc
	
	def rvisit(self, v: ast.Call):
		return self.rvalue(v.func)(*(self.rvalue(x) for x in v.args))
	
	def rvisit(self, v: ast.Proto):
		p = (self.rvalue(v.parent),) if v.parent else ()
		return EspProto(v.name, p, {
			"public": v.pub,
			"private": v.priv,
			"static": v.stat
		})
	
	def lvisit(self, v: ast.Index):
		return LValue(self.rvalue(v.obj), list(map(self.rvalue, v.indices)))
	def rvisit(self, v: ast.Index):
		return self.lvalue(v).get()
	
	def rvisit(self, v: ast.ObjectLiteral):
		return {self.rvalue(key):self.rvalue(val) for key, val in v.values}
	
	def rvisit(self, v: ast.ListLiteral):
		return EspList(self.rvalue(x) for x in v.values)
	
	def rvisit(self, v: ast.ForLoop):
		# Doesn't account for destructuring
		itvar = v.itvar.name
		
		it = self.rvalue(iter(v.toiter))
		
		try:
			while True:
				self.lookup(itvar)[itvar] = next(it)
				self.rvalue(v.body)
				
		except StopIteration:
			self.rvalue(v.th) if v.th else EspNone
		
		except BreakSignal:
			self.rvalue(v.el) if v.el else EspNone
		
		# This is incorrect but I'm too tired to do it right (which would
		#  require proper refactoring to support generators)
		return EspNone
	
	def visit(self, v):
		return self.rvalue(v)