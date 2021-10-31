#!/usr/bin/env python3

from types import SimpleNamespace

import ast
from runtime import EspNone, EspProto, EspString

class Visitor:
	def visit_const(self, v):
		raise NotImplementedError(f"{type(self).__name__}.visit_const")
	
	def visit_var(self, v):
		raise NotImplementedError(f"{type(self).__name__}.visit_var")
	
	def visit_sexp(self, v):
		raise NotImplementedError(f"{type(self).__name__}.visit_sexp")
	
	def visit_block(self, v):
		raise NotImplementedError(f"{type(self).__name__}.visit_block")
	
	def visit_prog(self, v):
		raise NotImplementedError(f"{type(self).__name__}.visit_prog")

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

class EvalVisitor(Visitor):
	def __init__(self):
		self.stack = []
	
	def lookup(self, name):
		for x in range(1, len(self.stack) + 1):
			v = self.stack[-x].vars
			if name in v:
				return v
		
		return self.stack[-1].vars
	
	def visit_if(self, v):
		if v.cond.visit(self):
			return v.th.visit(self) if v.th else EspNone
		else:
			return v.el.visit(self) if v.el else EspNone
	
	def visit_loop(self, v):
		ls = []
		try:
			while True:
				try:
					ls.append(v.body.visit(self))
				except ContinueSignal:
					pass
				
		except (BreakSignal, StopIteration):
			v.el.visit(self) if v.el else EspNone
			return ls
	
	def visit_branch(self, v):
		if v.kind == "break":
			raise BreakSignal()
		elif v.kind == "continue":
			raise ContinueSignal()
		else:
			raise NotImplementedError(v.kind)
	
	def visit_switch(self, v):
		# Evaluate the expression to switch on
		ex = v.ex.visit(self)
		
		# Find the case statement which matches
		for case in v.cs:
			val = case.value.visit(self)
			
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
				last = case.body.visit(self)
				
				case = case.next
				if case is None:
					break
		except BreakSignal:
			last = v.el.visit(self)
		except ContinueSignal:
			last = v.th.visit(self)
		
		return last
	
	def visit_return(self, v):
		raise ReturnSignal(v)
	
	def visit_op(self, v):
		#print(v.args)
		#print([repr(x.visit(self)) for x in v.args])
		return SIMPLE_OPS[v.op](*(x.visit(self) for x in v.args))
	
	def visit_value(self, v):
		return v.value
	
	def visit_var(self, v):
		return self.lookup(v.name)[v.name]
	
	def visit_assign(self, v):
		# NOTE: This doesn't handle destructuring!
		name = v.name.name
		
		if v.op:
			#print(self.stack)
			old = self.lookup(name)[name]
			val = SIMPLE_OPS[v.op](old, v.value.visit(self))
		else:
			val = v.value.visit(self)
		
		self.lookup(name)[name] = val
		return val
	
	def visit_format(self, v):
		s = ""
		for p in v.parts:
			if type(p) is str:
				s += p
			else:
				s += EspString(p.visit(self))
		
		return s
	
	def visit_block(self, v):
		last = EspNone
		for x in v.elems:
			next = x.visit(self)
			
			if isinstance(x, ast.Origin):
				x = x.node
			if not isinstance(x, ast.Statement):
				last = next
		
		return last
	
	def visit_prog(self, v):
		self.stack.append(StackFrame(None, {
			"iter": iter,
			"next": next,
			"print": lambda *x: print(*x, end='') or EspNone,
			"pyimport": __import__
		}))
		self.stack.append(StackFrame(v, {x:EspNone for x in v.vars}))
		x = self.visit_block(v)
		self.stack.pop()
		self.stack.pop()
		
		return x
	
	def visit_func(self, v):
		def pyfunc(*args):
			try:
				self.stack.append(
					StackFrame(v, dict(zip((x.name for x in v.args), args)))
				)
				val = v.body.visit(self)
				self.stack.pop()
				return val
			except ReturnSignal as ret:
				return ret
		
		return pyfunc
	
	def visit_call(self, v):
		return v.func.visit(self)(*(x.visit(self) for x in v.args))
	
	def visit_proto(self, v):
		p = (v.parent.visit(self),) if v.parent else ()
		return EspProto(v.name, p, {
			"public": v.pub,
			"private": v.priv,
			"static": v.stat
		})
	
	def visit_index(self, v):
		obj = v.obj.visit(self)
		idx = [x.visit(self) for x in v.indices]
		'''
		if len(idx) == 0:
			return obj[None]
		elif len(idx) == 1:
			return obj[idx[0]]
		else:'''
		try:
			return obj.__getitem__(idx)
		except (AttributeError, KeyError):
			pass
		
		return getattr(obj, idx[0])
	
	def visit_objectliteral(self, v):
		obj = {}
		
		for key, val in v.values:
			obj[key.visit(self)] = val.visit(self)
		
		return obj
	
	def visit_listliteral(self, v):
		return [x.visit(self) for x in v.values]
	
	def visit_forloop(self, v):
		# Doesn't account for destructuring
		itvar = v.itvar.name
		
		it = iter(v.toiter.visit(self))
		
		try:
			while True:
				self.lookup(itvar)[itvar] = next(it)
				v.body.visit(self)
				
		except StopIteration:
			v.th.visit(self) if v.th else EspNone
		
		except BreakSignal:
			v.el.visit(self) if v.el else EspNone
		
		# This is incorrect but I'm too tired to do it right (which would
		#  require proper refactoring to support generators)
		return EspNone