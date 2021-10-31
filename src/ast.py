#!/usr/bin/env python3

from runtime import EspNone
import re

def join(sep, v):
	return sep.join(str(x) for x in v if x is not None)

COLOR = True
if COLOR:
	color_op = '\033[38;5;33m%s\033[0m'
	color_str = '\033[38;5;247m%s\033[0m'
	color_list = '\033[38;5;220m%s\033[0m'
	color_num = '\033[38;5;202m%s\033[0m'
	color_none = '\033[38;5;172m%s\033[0m'
	color_var = '\033[38;5;228m%s\033[0m'
else:
	color_op = "%s"
	color_str = "%s"
	color_list = "%s"
	color_num = "%s"
	color_none = "%s"
	color_var = "%s"

SOL = re.compile(r"^", flags=re.M)
def indent(x):
	return re.sub(SOL, '  ', x)

def sexp(v):
	if type(v) is Origin:
		v = v.node
	
	if v is None:
		pass
	elif v is EspNone:
		return color_none%"none"
	elif type(v) is str:
		return color_op%v
	elif type(v) is tuple:
		before = []
		after = []
		nl = False
		
		for x in v:
			if x == ...:
				nl = True
			elif nl:
				after.append(sexp(x))
			else:
				before.append(sexp(x))
		
		b = join(' ', before)
		if nl:
			a = join('\n', after)
			return f"({b}\n{indent(a)})"
		else:
			return f"({b})"
	elif type(v) is list:
		return color_list%f"[{join(' ', (sexp(x) for x in v))}]"
	elif type(v) is Var:
		return color_var%v.name
	elif type(v) is Value:
		if type(v.value) is str:
			return color_str%repr(v.value)
		else:
			return color_num%v.value
	elif isinstance(v, Expr):
		return str(v)
	elif type(v) is int:
		return color_num%str(v)
	else:
		raise TypeError(f"Unknown value in sexp {type(v).__name__} {v}")

class Origin:
	'''
	To keep track of source code origin, wrap relevant ast nodes with an
	annotation object. Needs to be transparent enough that nodes without
	the origin wrapper behave the same
	'''
	
	__slots__ = ("node", "token")
	
	def __init__(self, node, token):
		if type(node) is Origin:
			raise ValueError("Duplicate origin")
		
		super().__setattr__("node", node)
		super().__setattr__("token", token)
	
	def __str__(self):
		return str(self.node)
	
	def __repr__(self):
		return repr(self.node)
	
	def visit(self, v):
		return self.node.visit(v)
	
	def origin(self, token):
		if token != self.token:
			raise ValueError("Applying two different origins")
	
	def __getattr__(self, name):
		return getattr(super().__getattribute__("node"), name)
	
	def __setattr__(self, name, value):
		return setattr(super().__getattribute__("node"), name, value)

class Expr:
	def __init__(self):
		self.lvalue = True
		self.rvalue = True
	
	def __repr__(self):
		return f"<noimpl {type(self).__name__}.__str__>"
	
	def visit(self, v):
		return getattr(v, f"visit_{type(self).__name__.lower()}")(self)
	
	def origin(self, token):
		return Origin(self, token)

class Statement(Expr):
	'''
	Expressions which don't automatically return if they're the last in a
	 function body.
	'''
	pass

class Value(Expr):
	'''Value'''
	
	def __init__(self, value):
		super().__init__()
		
		if isinstance(value, Expr):
			raise TypeError("Value must be a constant")
		
		self.value = value
		self.rvalue = False
	
	def __str__(self):
		return sexp(self.value)
	
	def __repr__(self):
		return f"Value({self.value!r})"

class Var(Expr):
	'''Variable'''
	
	def __init__(self, name,  mutable=True):
		super().__init__()
		
		if name and type(name) != str:
			raise TypeError(f"Var name must be str, got {type(name)}")
		
		self.name = name
		self.mutable = mutable
	
	def __str__(self):
		return sexp(self.name)
	
	def __repr__(self):
		if self.mutable:
			return f"Var({self.name!r})"
		return f"Var({self.name!r}, mutable={self.mutable!r})"

class Spread(Expr):
	'''Spread operator, has its own node because it's syntax'''
	
	def __init__(self, var):
		super().__init__()
		self.var = var
		self.lvalue = var.lvalue
		self.rvalue = False
	
	def __str__(self):
		return "..." + sexp(self.var)
	
	def __repr__(self):
		return f"Spread({self.var!r})"

class Assign(Statement):
	'''Assignment is syntactic too'''
	
	def __init__(self, name, value, op=""):
		super().__init__()
		self.name = name
		self.value = value
		self.op = op
	
	def __str__(self):
		return sexp((f"{self.op or ''}=", self.name, self.value))
	
	def __repr__(self):
		if self.op:
			return f"Assign({self.name!r}, {self.value!r}, {self.op!r})"
		else:
			return f"Assign({self.name!r}, {self.value!r})"

class Tuple(Expr):
	'''Tuple'''
	
	def __init__(self, elems):
		super().__init__()
		self.elems = elems
		self.lvalue = all(x.lvalue for x in elems)
		self.rvalue = all(x.rvalue for x in elems)
	
	def append(self, x):
		self.elems.append(x)
	
	def __str__(self):
		return sexp((",", *self.elems))
	
	def __repr__(self):
		return f"Tuple({self.elems!r})"

class Call(Expr):
	'''Call a function'''
	
	def __init__(self, func, args):
		super().__init__()
		self.func = func
		self.args = args
	
	def __str__(self):
		return sexp(("call", self.func, *self.args))
	
	def __repr__(self):
		return f"Call({self.func!r}, {self.args!r})"

class Index(Expr):
	'''Index a value'''
	
	def __init__(self, obj, indices):
		super().__init__()
		self.obj = obj
		self.indices = indices
	
	def __str__(self):
		return sexp((".", self.obj, [*self.indices]))
	
	def __repr__(self):
		return f"Index({self.obj!r}, {self.indices!r})"

class Loop(Statement):
	'''All loop types simplify to this node, an infinite loop'''
	
	def __init__(self, body, el=Value(EspNone)):
		super().__init__()
		self.body = body
		self.el = el
	
	def __str__(self):
		return sexp(("loop", ..., self.body, self.el and ("else", self.el)))
	
	def __repr__(self):
		return f"Loop({self.body!r}, {self.el!r})"

class If(Statement):
	'''if statement'''
	
	def __init__(self, cond, th, el):
		super().__init__()
		
		self.cond = cond
		self.th = th
		self.el = el
	
	def __str__(self):
		return sexp(("if", self.cond,
			...,
			self.th and ("then", self.th),
			self.el and ("else", self.el)
		))
	
	def __repr__(self):
		return f"If({self.cond!r}, {self.th!r}, {self.el!r})"

class Branch(Statement):
	'''Base class for branching in blocks'''
	
	def __init__(self, kind, level=0):
		super().__init__()
		self.kind = kind
		self.level = level
		
		if type(level) != int:
			raise TypeError("Branch.level must be int!")
	
	def __str__(self):
		return sexp((self.kind, self.level))
	
	def __repr__(self):
		return f"Branch({self.kind!r}, {self.level!r})"

class Op(Expr):
	'''Simple operation, evaluates to a value'''
	
	def __init__(self, op, *args):
		super().__init__()
		
		self.op = op
		if type(op) is not str:
			raise RuntimeError("op must be string!")
		
		for x in args:
			if not (isinstance(x, Expr) or isinstance(x, Origin)):
				print(type(x), x)
				raise RuntimeError("Non-expression in op!")
		
		self.args = args
		self.lvalue = False # ops are always r-value
	
	def __str__(self):
		return sexp((self.op, *self.args))
	
	def __repr__(self):
		return f"Op({self.op!r}, {self.args!r}, {self.lvalue!r})"

class Import(Expr):
	'''Import statement, for now just support builtin libraries'''
	
	def __init__(self, name):
		super().__init__()
		self.name = name
	
	def __str__(self):
		return sexp(("import", self.name))
	
	def __repr__(self):
		return f"Import({self.name!r})"

class Proto(Expr):
	'''Proto expression'''
	
	def __init__(self, name, parent, pub, priv, stat):
		super().__init__()
		
		self.name = name
		self.parent = parent
		self.pub = pub
		self.priv = priv
		self.stat = stat
	
	def __str__(self):
		return sexp(("proto",
			self.name and f":{self.name}",
			self.parent and ("is", self.parent),
			...,
			self.pub and ("public", self.pub),
			self.priv and ("private", self.priv),
			self.stat and ("static", self.stat)
		))
	
	def __repr__(self):
		return f"Proto({self.name!r}, {self.parent!r}, {self.pub!r}, {self.priv!r}, {self.stat!r})"

class Return(Statement):
	'''Return statement'''
	
	def __init__(self, value):
		super.__init__()
		self.value = value
	
	def __str__(self):
		return sexp(("return", self.value))
	
	def __repr__(self):
		return f"Return({self.value!r})"

class Format(Expr):
	'''Formatted string expression'''
	
	def __init__(self, parts):
		super().__init__()
		self.parts = parts
	
	def __str__(self):
		return sexp(("format", ..., *(
			repr(x) if type(x) is str else x for x in self.parts
		)))
	
	def __repr__(self):
		return f"Format({self.parts!r})"

class Case:
	def __init__(self, op, value, body, next):
		super().__init__()
		
		self.op = op
		self.value = value
		self.body = body
		self.next = next
	
	def __str__(self):
		return sexp(("case", self.op, self.value,
			self.body, self.next and "..."
		))
	
	def __repr__(self):
		return f"Case({self.op!r}, {self.value!r}, {self.body!r}, {self.next!r})"

class Switch(Expr):
	'''
	Switch expression.
	
	This is implemented by separating the predicates from the values/bodies.
	 Predicates keep track of the comparison operation, value to compare
	 against, a body index, and a next index. Blocks 
	'''
	def __init__(self, ex, cs, de, th, el):
		super().__init__()
		
		self.ex = ex # EXpression
		self.cs = cs # CaseS
		self.de = de # DEfault
		self.th = th # THen
		self.el = el # ELse
	
	def __str__(self):
		return sexp(("switch", self.ex,
			...,
			*self.cs,
			self.de and ("default", self.de),
			self.th and ("then", self.th),
			self.el and ("else", self.el)
		))

	def __repr__(self):
		return f"Switch({self.ex!r}, {self.cs!r}, {self.de!r}, {self.th!r}, {self.el!r})"

class ObjectLiteral(Expr):
	'''Object literal'''
	
	def __init__(self, obj):
		super().__init__()
		self.values = obj
	
	def __str__(self):
		return sexp(("object", ...,
			*(("pair", k, v) for k, v in self.values)
		))
	
	def __repr__(self):
		return f"ObjectLiteral({self.values!r})"

class ListLiteral(Expr):
	'''List literal'''
	
	def __init__(self, vals):
		super().__init__()
		self.values = vals
	
	def __str__(self):
		return sexp(("list", *self.values))
	
	def __repr__(self):
		return f"ListLiteral({self.values!r})"

class ForLoop(Statement):
	'''
	Representing for loops with Loop ends up being too complicated
	'''
	
	def __init__(self, itvar, toiter, body, th, el):
		super().__init__()
		
		self.itvar = itvar
		self.toiter = toiter
		self.body = body
		self.th = th
		self.el = el
	
	def __str__(self):
		return sexp(("for",
			("var", self.itvar),
			("in", self.toiter),
			...,
			("body", self.body),
			self.th and ("then", self.th),
			self.el and ("else", self.el)
		))
	
	def __repr__(self):
		return f"ForLoop({self.itvar!r}, {self.toiter!r}, {self.body!r}, {self.th!r}, {self.el!r})"

class Block(Statement):
	'''Sequence of expressions evaluating to the last'''
	
	def __init__(self, elems, vars=None):
		super().__init__()
		
		if type(elems) is not list:
			raise RuntimeError("Wrong type!")
		self.elems = elems
		self.vars = vars or []
		self.lvalue = False
	
	def __str__(self):
		#v = [x for x in self.vars if x.mutable]
		#c = [x for x in self.vars if not x.mutable]
		return sexp(("block",
			self.vars and tuple(["var", *self.vars]),
			...,
			#c and tuple(["const", *c]),
			*self.elems
		))
	
	def __repr__(self):
		return f"Block({self.elems!r}, {self.vars!r})"

class Prog(Block):
	def __init__(self, elems, vars=None):
		super().__init__(elems, vars)
	
	def __repr__(self):
		return f"Prog({self.elems!r}, {self.vars!r})"

class Func(Expr):
	def __init__(self, name, args, body):
		super().__init__()
		
		self.name = name
		self.args = args
		self.body = body
	
	def __str__(self):
		return sexp(("function", self.name, self.args, ..., self.body))
	
	def __repr__(self):
		return f"Func({self.name!r}, {self.args!r}, {self.body!r}"