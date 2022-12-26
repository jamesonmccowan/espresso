#!/usr/bin/env python3

from pyrsistent import thaw
import esp_ast as ast
"""
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

class EspBaseException(BaseException): pass

class Signal(EspBaseException): pass
class BreakSignal(Signal): pass
class ContinueSignal(Signal): pass

class ReturnSignal(Signal):
	def __init__(self, value):
		self.value = value

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
"""

def brinc(block, by=1):
	'''
	Increment the labels of branch instructions. This is necessary when
	the compiler inserts blocks which aren't visible to the user code
	'''
	for b in block:
		if b[0] in {'break', 'loop'}:
			yield [b[0], b[1] + by]
		else:
			yield b

def mkblock(th, el):
	th, el = list(th), list(el)
	
	yield from [
		['block', len(th)], *th, ['else', len(el)], *el
	]

def mkif(cond, th, el):
	cond, th, el = list(cond), list(th), list(el)
	
	yield from [
		*cond, ['if', len(th)], *th, ['else', len(el)], *el, ['end']
	]

class Lower1(ast.Visitor):
	def __init__(self):
		super().__init__()
		
		self.blocks = 0
		self.targets = []
	
	def visit_subex(self, expr, inc=0):
		'''Visit a subexpression contained by one or more shadow blocks'''
		self.targets.append(self.blocks + inc)
		yield from self.visit(expr)
		self.targets.pop()
	
	def visit(self, x):
		raise NotImplemented(f"esp_lower1({type(x)})")
	
	def visit(self, x: None):
		yield from []
	
	def visit(self, x: ast.Prog):
		for statement in x.elems:
			yield from self.visit(statement)
	
	def visit(self, x: ast.Block):
		yield from self.mkblock(x.elems)
	
	def visit(self, x: ast.If):
		cond = list(self.visit(x.cond))
		
		th = list(self.visit(x.th))
		el = list(self.visit(x.el))
		yield from mkif(cond, th, el)
	
	def visit(self, x: ast.Loop):
		# (loop always cond body then else)
		
		yield from mkblock([
			*self.visit_subex(x.always),
			*mkif(self.visit_subex(self.cond), [
			# then
				*self.brinc(self.visit(x.body)), ['break', 1]
			],
			# else
				self.brinc(self.visit(x.th))
			)
		], self.visit(x.el))
	
	def visit(self, x: ast.Op):
		op = x.op
		if op == "after":
			yield from self.visit(x[0])
			yield from self.visit(x[1])
			yield ["pop"]
		elif op == "format":
			yield self.visit(x[0])
			for part in x[1:]:
				yield self.visit(part)
				yield ["add"]
		elif op == "break":
			pass
		else:
			yield from self.visit(x[0])
			yield from self.visit(x[1])
			yield [op]

def eval(x):
	print("ast", ast)
	#return EvalVisitor().visit(x)

'''
while(cond()) {
	if(test()) {
		break 0;
	}
}
loop {
	if(cond()) {
		break 1
	}
}

loop {
	always
} while(cond) {
	body
} then {
	th
} else {
	el
}

block
	always
	cond
	if
		body
	else
		th
	end
else
	el
end

for(;;) {
	always
	if(cond) {
		body
	}
	else {
		th
		goto finish
	}
}
el
finish
'''