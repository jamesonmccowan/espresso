#!/usr/bin/env python3

from ast import Var, Value, Op
from runtime import EspNone

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
		return str(self.vars)
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
	">>>": None,
	
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
		for x in range(1, len(self.stack)):
			v = self.stack[-x].vars
			if name in v:
				return v
		
		return self.stack[-1].vars
	
	def visit_if(self, v):
		if v.cond.visit(self):
			return v.th.visit(self)
		else:
			return v.el.visit(self)
	
	def visit_loop(self, v):
		ls = []
		try:
			while True:
				try:
					ls.append(v.body.visit(self))
				except ContinueSignal:
					pass
		except BreakSignal:
			v.el.visit(self)
			return ls
	
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
				print("case", case)
				print("body", case.body)
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
		return SIMPLE_OPS[v.op](*(x.visit(self) for x in v.args))
	
	def visit_value(self, v):
		return v.value
	
	def visit_var(self, v):
		return self.lookup(v.name)[v.name]
	
	def visit_assign(self, v):
		name = v.name.name
		
		if v.op:
			val = self.visit_op(
				Op(v.op, Value(self.stack[-1].vars[name], v.value))
			)
		else:
			val = v.value.visit(self)
		
		self.lookup(name)[name] = val
		return val
	
	def visit_block(self, v):
		last = None
		for x in v.elems:
			last = x.visit(self)
		
		return last
	
	def visit_prog(self, v):
		self.stack.append(StackFrame(v, {x:EspNone for x in v.vars}))
		x = self.visit_block(v)
		self.stack.pop()
		
		return x
	
	def visit_func(self, v):
		def pyfunc(*args):
			print(type(v.args), type(args))
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