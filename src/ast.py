#!/usr/bin/env python3

from runtime import EspNone, EspList, EspString, EspDict
import re
from multimethod import multimethod

def join(sep, v):
	return sep.join(str(x) for x in v if x is not None)

COLOR = True
if COLOR:
	num = '\033[38;5;202m%s\033[0m'
	color = {
		str: '\033[38;5;247;4m%r\033[0m',
		EspString: '\033[38;5;247m%r\033[0m',
		bool: '\033[38;5;202m%s\033[0m',
		int: num, float: num,
		type(EspNone): '\033[38;5;172m%s\033[0m',
		"var": '\033[38;5;228m%s\033[0m',
		"op": '\033[38;5;33m%s\033[0m'
	}
else:
	color = {
		str: "%s", bool: "%s", int: "%s", float: "%s",
		type(EspNone): "%s", "var": "%s"
	}

SOL = re.compile(r"^", flags=re.M)
def indent(x):
	return re.sub(SOL, '  ', x)

def subsexp(ex, before, after):
	nl = False
	for x in ex:
		if x == ...:
			nl = True
		elif nl:
			after.append(sexp(x))
		else:
			before.append(sexp(x))
	
	b = join(' ', before)
	if len(after):
		a = indent(join('\n', after))
		ba = join('\n', [b, a]) if a else b
	else:
		ba = b
	return ba

def sexp(v):
	ex = v.sexp() if isinstance(v, Expr) else v
	tex = type(ex)
	
	if ex is None:
		pass
	elif tex is str:
		return color[str]%ex
	elif tex is EspString:
		return color[EspString]%ex
	elif tex in color:
		return color[tex]%ex
	elif tex is tuple:
		# Special colorations
		if ex:
			if ex[0] == "var":
				return color['var']%ex[1]
			
			before = [color['op']%ex[0]]
		else:
			before = []
		after = []
		
		return f"({subsexp(ex[1:], before, after)})"
	elif tex is list or tex is EspList:
		return f"[{subsexp(tuple(ex), [], [])}]"
	else:
		raise TypeError(f"Unknown value in sexp {type(v).__name__} {v}")

def is_expr(*x):
	return all(isinstance(e, Expr) for e in x)

class Expr:
	def __init__(self):
		self.lvalue = True
		self.rvalue = True
		
		self.token = None
	
	def __repr__(self):
		raise NotImplementedError("__repr__")
	
	def visit(self, v):
		# Give it a name for better stack traces
		visit_method = getattr(v, f"visit_{type(self).__name__.lower()}")
		return visit_method(self)
	
	def origin(self, token):
		self.token = token
		return self
	
	def sexp(self):
		'''
		Return the expression as an S-expression. Ellipses are used to
		 indicate where the rest of the arguments should be separated by
		 newlines
		'''
		raise NotImplementedError("sexp")

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
		assert(not is_expr(value))
		
		# Convert Pythonic values to espresso values
		tv = type(value)
		if value is None:
			value = EspNone
		elif tv is str:
			value = EspString(value)
		elif tv is list:
			value = EspList(value)
		elif tv is dict:
			value = EspDict(value)
		
		self.value = value
		self.lvalue = False
	
	def __str__(self):
		return sexp(self.value)
	
	def __repr__(self):
		return f"Value({self.value!r})"
	
	def sexp(self):
		#raise ValueError("Sexp")
		return self.value

class Var(Expr):
	'''Variable'''
	
	def __init__(self, name,  mutable=True):
		super().__init__()
		
		if name and type(name) != str:
			raise TypeError(f"Var name must be str, got {type(name)}")
		
		self.name = name
		self.mutable = mutable
	
	def __str__(self):
		return sexp(self)
	
	def __repr__(self):
		if self.mutable:
			return f"Var({self.name!r})"
		return f"Var({self.name!r}, mutable={self.mutable!r})"
	
	def sexp(self):
		return ("var", self.name, self.mutable or None)

class Spread(Expr):
	'''Spread operator, has its own node because it's syntax'''
	
	def __init__(self, var):
		super().__init__()
		assert(is_expr(var))
		
		self.var = var
		self.lvalue = var.lvalue
		self.rvalue = False
	
	def __str__(self):
		return "..." + sexp(self.var)
	
	def __repr__(self):
		return f"Spread({self.var!r})"
	
	def sexp(self):
		return ("...", self.var)

class Assign(Statement):
	'''Assignment is syntactic too'''
	
	def __init__(self, name, value, op=""):
		super().__init__()
		assert(is_expr(name))
		assert(is_expr(value))
		assert(type(op) is str)
		
		self.name = name
		self.value = value
		self.op = op
	
	def __str__(self):
		return sexp((f"assign{self.op or ''}=", self.name, self.value))
	
	def __repr__(self):
		if self.op:
			return f"Assign({self.name!r}, {self.value!r}, {self.op!r})"
		else:
			return f"Assign({self.name!r}, {self.value!r})"
	
	def sexp(self):
		return (self.op + '=', self.name, self.value)

class Tuple(Expr):
	'''Tuple'''
	
	def __init__(self, elems):
		super().__init__()
		assert(is_expr(*elems))
		
		self.elems = elems
		self.lvalue = all(x.lvalue for x in elems)
		self.rvalue = all(x.rvalue for x in elems)
	
	def append(self, x):
		self.elems.append(x)
	
	def __str__(self):
		return sexp((",", *self.elems))
	
	def __repr__(self):
		return f"Tuple({self.elems!r})"
	
	def sexp(self):
		return ("tuple", *self.elems)

class Call(Expr):
	'''Call a function'''
	
	def __init__(self, func, args):
		super().__init__()
		assert(is_expr(func))
		assert(is_expr(*args))
		
		self.func = func
		self.args = args
	
	def __str__(self):
		return sexp(("call", self.func, *self.args))
	
	def __repr__(self):
		return f"Call({self.func!r}, {self.args!r})"
	
	def sexp(self):
		return ("call", self.func, *self.args)

class Index(Expr):
	'''Index a value'''
	
	def __init__(self, obj, indices):
		super().__init__()
		assert(is_expr(obj))
		assert(is_expr(*indices))
		
		self.obj = obj
		self.indices = indices
	
	def __str__(self):
		return sexp((".", self.obj, [*self.indices]))
	
	def __repr__(self):
		return f"Index({self.obj!r}, {self.indices!r})"
	
	def sexp(self):
		return (".", self.obj, [*self.indices])

class After(Expr):
	def __init__(self, value, update):
		super().__init__()
		assert(is_expr(value))
		assert(is_expr(update))
		if type(value) is If:
			raise ValueError()
		self.value = value
		self.update = update
	
	def __str__(self):
		return sexp(("after", self.value, self.update))
	
	def __repr__(self):
		return f"After({self.value!r}, {self.update!r})"
	
	def sexp(self):
		return ("after", self.value, self.update)

class Bind(Expr):
	'''Binding operator ->'''
	
	def __init__(self, obj, member):
		super().__init__()
		assert(is_expr(obj))
		assert(is_expr(member))
		
		self.obj = obj
		self.member = member
	
	def __str__(self):
		return sexp(self)
	
	def __repr__(self):
		return f"Bind({self.obj!r}, {self.member!r})"
	
	def sexp(self):
		return ("->", self.obj, self.member)

class Descope(Expr):
	'''Descoping operator ::'''
	
	def __init__(self, obj, member):
		super().__init__()
		assert(is_expr(obj))
		assert(is_expr(member))
		
		self.obj = obj
		self.member = member
	
	def __str__(self):
		return sexp(self)
	
	def __repr__(self):
		return f"Descope({self.obj!r}, {self.member!r})"
	
	def sexp(self):
		return ("::", self.obj, self.member)

class Loop(Statement):
	'''All loop types simplify to this node, an infinite loop'''
	
	def __init__(self, body, el=None):
		super().__init__()
		assert(is_expr(body))
		assert(is_expr(el) or el is None)
		
		self.body = body
		self.el = el
	
	def __str__(self):
		return sexp(("loop", ..., self.body, self.el and ("else", self.el)))
	
	def __repr__(self):
		return f"Loop({self.body!r}, {self.el!r})"
	
	def sexp(self):
		return ("loop", ...,
			self.body, self.el and ("else", self.el))

class If(Statement):
	'''if statement'''
	
	def __init__(self, cond, th, el):
		super().__init__()
		assert(is_expr(cond))
		assert(is_expr(th) or th is None)
		assert(is_expr(el) or el is None)
		
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
	
	def sexp(self):
		return ("if", self.cond, ...,
			self.th and ("then", self.th),
			self.el and ("else", self.el))

class Branch(Statement):
	'''Base class for branching in blocks'''
	
	def __init__(self, kind, level=0):
		super().__init__()
		assert(type(kind) is str)
		assert(type(level) is int)
		
		self.kind = kind
		self.level = level
	
	def __str__(self):
		return sexp((self.kind, self.level))
	
	def __repr__(self):
		return f"Branch({self.kind!r}, {self.level!r})"
	
	def sexp(self):
		return (self.kind, self.level)

class Op(Expr):
	'''Simple operation, evaluates to a value'''
	
	def __init__(self, op, *args):
		super().__init__()
		assert(type(op) is str)
		assert(is_expr(*args))
		
		self.op = op
		
		self.args = args
		self.lvalue = False # ops are always r-value
	
	def __str__(self):
		return sexp((self.op, *self.args))
	
	def __repr__(self):
		return f"Op({self.op!r}, {self.args!r}, {self.lvalue!r})"
	
	def sexp(self):
		return (self.op, *self.args)

class Import(Expr):
	'''Import statement, for now just support builtin libraries'''
	
	def __init__(self, name):
		super().__init__()
		assert(is_expr(name))
		
		self.name = name
	
	def __str__(self):
		return sexp(("import", self.name))
	
	def __repr__(self):
		return f"Import({self.name!r})"
	
	def sexp(self):
		return ("import", self.name)

class Proto(Expr):
	'''Proto expression'''
	
	def __init__(self, name, parent, pub, priv, stat):
		super().__init__()
		assert(is_expr(name))
		assert(is_expr(parent) or parent is None)
		assert(is_expr(*pub))
		assert(is_expr(*priv))
		assert(is_expr(*stat))
		
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
	
	def sexp(self):
		return ("proto", self.name, self.parent and ("is", self.parent),
			...,
			self.pub and ("public", self.pub),
			self.priv and ("private", self.priv),
			self.stat and ("static", self.stat)
		)

class Return(Statement):
	'''Return statement'''
	
	def __init__(self, value):
		super.__init__()
		assert(is_expr(value))
		
		self.value = value
	
	def __str__(self):
		return sexp(("return", self.value))
	
	def __repr__(self):
		return f"Return({self.value!r})"
	
	def sexp(self):
		return ("return", self.value)

class Format(Expr):
	'''Formatted string expression'''
	
	def __init__(self, parts):
		super().__init__()
		assert(is_expr(*parts))
		
		self.parts = parts
	
	def __str__(self):
		return sexp(("format", ..., *(
			repr(x) if type(x) is str else x for x in self.parts
		)))
	
	def __repr__(self):
		return f"Format({self.parts!r})"
	
	def sexp(self):
		return ("format", ..., *(
			repr(x) if type(x) is str else x for x in self.parts
		))

class Case(Expr):
	def __init__(self, op, value, body, next):
		super().__init__()
		assert(type(op) is str)
		assert(is_expr(value))
		assert(is_expr(body))
		
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
	
	def sexp(self):
		return ("case" + self.op, self.value,
			self.body, self.next and "..."
		)

class Switch(Expr):
	'''
	Switch expression.
	
	This is implemented by separating the predicates from the values/bodies.
	 Predicates keep track of the comparison operation, value to compare
	 against, a body index, and a next index. Blocks 
	'''
	def __init__(self, ex, cs, de, th, el):
		super().__init__()
		assert(is_expr(ex))
		assert(is_expr(*cs))
		assert(is_expr(de) or de is None)
		assert(is_expr(th) or th is None)
		assert(is_expr(el) or el is None)
		
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
	
	def sexp(self):
		return ("switch", self.ex, ...,
			*self.cs,
			self.de and ("default", self.de),
			self.th and ("then", self.th),
			self.el and ("else", self.el)
		)

class ObjectLiteral(Expr):
	'''Object literal'''
	
	def __init__(self, obj):
		super().__init__()
		#assert(??)
		self.values = obj
	
	def __str__(self):
		return sexp(("object", ...,
			*(("pair", k, v) for k, v in self.values)
		))
	
	def __repr__(self):
		return f"ObjectLiteral({self.values!r})"
	
	def sexp(self):
		return ("object", ...,
			*(("pair", k, v) for k, v in self.values)
		)

class ListLiteral(Expr):
	'''List literal'''
	
	def __init__(self, vals):
		super().__init__()
		assert(is_expr(*vals))
		self.values = vals
	
	def __str__(self):
		return sexp(("list", *self.values))
	
	def __repr__(self):
		return f"ListLiteral({self.values!r})"
	
	def sexp(self):
		return ("list", *self.values)

class ForLoop(Statement):
	'''
	Representing for loops with Loop ends up being too complicated
	'''
	
	def __init__(self, itvar, toiter, body, th, el):
		super().__init__()
		assert(is_expr(itvar))
		assert(is_expr(toiter))
		assert(is_expr(body))
		assert(is_expr(th) or th is None)
		assert(is_expr(el) or el is None)
		
		self.itvar = itvar
		self.toiter = toiter
		self.body = body
		self.th = th
		self.el = el
	
	def __str__(self):
		return sexp(("for",
			self.itvar,
			("in", self.toiter),
			...,
			("body", self.body),
			self.th and ("then", self.th),
			self.el and ("else", self.el)
		))
	
	def __repr__(self):
		return f"ForLoop({self.itvar!r}, {self.toiter!r}, {self.body!r}, {self.th!r}, {self.el!r})"
	
	def sexp(self):
		return ("for", self.itvar, ("in", self.toiter), ...,
			("body", self.body),
			self.th and ("then", self.th),
			self.el and ("else", self.el)
		)

class Block(Statement):
	'''Sequence of expressions evaluating to the last'''
	
	def __init__(self, elems, vars=None):
		super().__init__()
		vars = vars or []
		
		assert(is_expr(*vars))
		
		se = []
		
		for e in elems:
			if type(e) is Block:
				se += e.elems
				vars += e.vars
			elif e is not None:
				se.append(e)
		
		self.elems = se
		self.vars = vars
		self.lvalue = False
	
	def __str__(self):
		#v = [x for x in self.vars if x.mutable]
		#c = [x for x in self.vars if not x.mutable]
		return sexp(("block",
			self.vars,
			...,
			#c and tuple(["const", *c]),
			*self.elems
		))
	
	def __repr__(self):
		return f"Block({self.elems!r}, {self.vars!r})"
	
	def sexp(self):
		return ("block", self.vars, ...,
			#c and tuple(["const", *c]),
			*self.elems
		)

class Prog(Block):
	def __init__(self, elems, vars=None):
		super().__init__(elems, vars)
	
	def __repr__(self):
		return f"Prog({self.elems!r}, {self.vars!r})"

class Func(Expr):
	def __init__(self, name, args, body):
		super().__init__()
		assert(is_expr(name))
		assert(is_expr(*args))
		assert(is_expr(body))
		
		self.name = name
		self.args = args
		self.body = body
	
	def __str__(self):
		return sexp(("function", self.name, self.args, ..., self.body))
	
	def __repr__(self):
		return f"Func({self.name!r}, {self.args!r}, {self.body!r}"
	
	def sexp(self):
		return ("function", self.name, self.args, ..., self.body)
