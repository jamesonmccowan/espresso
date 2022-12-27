#!/usr/bin/python3.10

import re, traceback

class ParseError(RuntimeError):
	def __init__(self, msg, ctx):
		l = ctx.line
		c = ctx.col
		p = ctx.pos
		super().__init__(f"{msg} ({l}|{c}:{p})")
		
		self.ctx = ctx

KW = [
	"and", "or", "not", "in", "is", "new",
	"function", "new", "var", "proto",
	"if", "then", "else", "loop", "while", "for",
	"switch", "case", "return", "fail", "break", "continue"
]
KWBOP = ['and', 'or', 'in', 'is']
KWUOP = ['not']

SC = r"(?:(?!\\\{)\\.|.+?)*?"
# Token regex, organized to allow them to be indexed by name
PATTERNS = {
	# Syntax "operators" which require special parsing rules
	"punc": r"[\(\)\[\]\{\}]|\.(?!\.)|\.{3}|[,;:]|=>",
	"cmp": r"[<>!=]=|[<>!]",
	"op": r"[-+=]",
	"dec": r"\d+",
	"sq": rf"'({SC})'", "dq": rf'"({SC})"', "bq": rf"`({SC})`",
	"id": r"[_\w][_\w\d]*"
}

TOKEN = re.compile(f"({')|('.join(PATTERNS.values())})", re.M)

# Map Match.lastindex to (name, groupcount)
TG = {}

# Matches an even number of backslashes, but not odd
EVEN_SLASH = re.compile(r'\\{2}')
RE_CLASS = re.compile(r"(?<!\\)\[(?:\\.|[^\[]+)*\\]")
RE_GROUP = re.compile(r'(?<!\\)\((?!\?(?!P<))')
index = 1
for name, pat in PATTERNS.items():
	pat = EVEN_SLASH.sub("", pat)
	pat = RE_CLASS.sub("", pat)
	count = len(RE_GROUP.findall(pat))
	
	for index in range(index, index + count + 1):
		TG[index] = name, count
	index += 1

CMP = re.compile(r"[<>!=]=")
COMMENT = re.compile(r"\s*(#\*(?:.|\n)*?\*#\s*|#.*$)", re.M)
NEWLINE = re.compile("\n")
SPACE = re.compile(r"\s+", re.M)

class Context:
	def __init__(self, pos, line, col):
		self.pos = pos
		self.line = line
		self.col = col
	
	def to_json(self):
		return [self.line, self.col]

class Token:
	def __init__(self, m, t, ctx):
		self.match = m
		self.value = m[0]
		self.type = t
		self.ctx = ctx
	
	def __repr__(self):
		return f"Token({self.type!r}, {self.value!r})"

def to_json(ast):
	if isinstance(ast, AST):
		return ast.to_json()
	elif isinstance(ast, list):
		return list(map(to_json, ast))
	elif isinstance(ast, dict):
		return dict((to_json(k), to_json(v)) for k, v in ast.items())
	else:
		return ast

class AST:
	def __init__(self, op, *args):
		self.op = op
		self.args = args
		self.token = None
	
	def __str__(self):
		return f"({self.op} {' '.join(repr(x) for x in self.args)})"
	__repr__ = __str__
	
	def origin(self, tok):
		self.token = tok
		return self
	
	def to_json(self):
		out = [self.op, *map(to_json, self.args)]
		
		if self.token:
			out = ['line', self.token.ctx.line, out]
		return out

# Each operator is its own precedence class
def separate(*v):
	return [[x] for x in v]

def build_precs(precs):
	p = 0
	for ops in precs:
		for op in ops:
			yield op, p
		p += 1

PRECS = dict(build_precs([
	# Loosest binding strength
	[';'],
	['='],
	[',', ":"],
	['after'],
	["||", "or"],
	["&&", "and"],
	["==", "!="],
	["<", "<=", ">", ">=", "<=>"],
	["in", "is", "new"],
	["!", "not"],
	["+", "-"],
	["(", "[", "{"],
	['.', '->', "::"]
	# Tightest binding strength
]))

OPNAMES = {
	"(": "lparen", "[": "lbrack", "{": "lbrace",
	",": "comma", "after": "after",
	
}

UNARY = {"!"}
RIGHT = {"**"}

def stresc(s):
	return s.replace("\\t", "\t").replace("\\n", "\n").replace("\\r", "\r")

class Parser:
	def __init__(self, src):
		self.src = src
		self.ctx = Context(0, 1, 1)
		self.cur = None
		self.consume()
	##############
	### Lexing ###
	##############
	
	def repos(self, m):
		if m is None: return
		
		old = self.ctx
		p = old.pos
		l = old.line
		c = old.col
		
		p += len(m[0])
		lines = NEWLINE.split(m[0])
		if len(lines) > 1:
			l += len(lines) - 1
			c = len(lines[-1])
		else:
			c += len(m[0])
		
		self.ctx = Context(p, l, c)
		return old
	
	def dump(self):
		return self.src[self.ctx.pos: self.ctx.pos + 20]
	
	def error(self, msg):
		pos = self.ctx.pos
		if self.cur is not None:
			msg += '\n' + self.src[pos - len(self.cur.value): pos + 20]
		
		return ParseError(msg, self.ctx)
		
	def match(self, reg):
		return reg.match(self.src, self.ctx.pos)
	
	def next(self):
		if self.ctx.pos >= len(self.src):
			return None
		
		# Skip all comments
		while comment := self.match(COMMENT):
			self.repos(comment)
		
		# Clean up ordinary space without comments
		self.repos(self.match(SPACE))
		
		# If the token regex doesn't match, we've run out
		m = self.match(TOKEN)
		if m is None:
			return None
		
		if m[0] in KWBOP:
			tt = "bop"
		elif m[0] in KWUOP:
			tt = "uop"
		elif m[0] in KW:
			tt = "kw"
		else:
			try:
				tt, gc = TG[m.lastindex]
				m = m.groups()[m.lastindex - 1:m.lastindex + gc]
			except:
				# Common parsing issue, give us more context
				print(list(enumerate(m.groups(), 1)))
				raise
		
		return Token(m, tt, self.repos(m))
	
	def consume(self):
		self.cur = self.next()
		return self.cur
	
	#######################
	### Generic parsing ###
	#######################
	
	def peek(self, value=None, type=None):
		def ineq(value, desc):
			if isinstance(desc, set):
				return value in desc
			return desc is None or value == desc
		
		cur = self.cur
		if cur and ineq(cur.value, value) and ineq(cur.type, type):
			return cur
	
	def maybe(self, value=None, type=None):
		v = self.peek(value, type)
		if v: self.consume()
		return v
	
	def expect(self, value=None, type=None):
		if m := self.maybe(value, type): return m
		raise self.expected(value or type)
	
	def expected(self, what):
		return self.error(f"Expected {what}, got {self.peek() or 'EOF'}")
	
	def parse(self):
		return AST("progn", *self.yield_semi())
	
	def wrap_maybe(self, pred):
		if type(pred) is str:
			return lambda: self.maybe(pred)
		return pred
		
	def yield_while(self, subparse):
		subparse = self.wrap_maybe(subparse)
		while e := subparse():
			yield e

	def yield_sep(self, subparse="expr", sep=","):
		entries = []
		while nt := self.peek():
			value = self.expr(PRECS[','])
			entries.append(value)

			if not self.peek(","):
				break

		return entries
	
	###############
	### Clauses ###
	###############
	
	def condition(self):
		if self.maybe("("):
			ex = self.expr()
			self.expect(")")
			return ex
		return self.expr()
	
	def funcargs(self):
		self.expect("(")
		args = list(self.yield_sep())
		self.expect(")")
		return args
	
	def relaxid(self):
		if tok := self.maybe(type={"id", "kw", "bop", "uop", "assign"}):
			return tok.value
		elif tok := self.maybe(type={"sq", "dq", "bq"}):
			return tok.match[1]
	
	def block(self):
		if tok := self.maybe("{"):
			x = AST("block", *self.yield_semi())
			self.expect("}")
			return x.origin(tok)
		
		x = self.expr()
		self.maybe(";")
		return x
	
	def yield_semi(self):
		while True:
			while self.maybe(";"): pass
			if stmt := self.expr():
				yield stmt
			else:
				break
	
	#########################
	### Special operators ###
	#########################
	
	def op_lparen(self, lhs):
		if lhs is None:
			lhs = self.expr() or AST("tuple")
		else:
			lhs = AST("call", lhs, *self.yield_sep())
		
		self.expect(")")
		return lhs
	
	def op_lbrack(self, lhs):
		if lhs is None:
			lhs = AST("list", *self.yield_sep())
		else:
			lhs = AST("[]", lhs, self.expr())
		
		self.expect("]")
		return lhs
	
	def op_lbrace(self, lhs):
		if lhs is None:
			entries = []
			
			while nt := self.peek():
				name = self.relaxid()
				vn = AST("id", name).origin(nt)
				
				if self.peek("("):
					args = self.funcargs()
					body = self.block()
					value = AST("fn", AST("const", name), args, body).origin(nt)
					entries.append([vn, value])
					continue
				elif self.maybe(":"):
					entries.append([vn, self.expr(PRECS[','])])
				else:
					entries.append([vn, vn])

				if not self.maybe(","):
					break
			
			lhs = AST("object", *entries)
		else:
			raise NotImplementedError("block call")
		
		self.expect("}")
		return lhs
	
	def op_comma(self, lhs):
		return AST(",", lhs, *self.yield_sep())
	
	def op_dot(self, lhs):
		return AST(".", lhs, *self.yield_sep(self.relaxid, "."))
	
	######################
	### Normal parsing ###
	######################
	
	def expr(self, min_prec=0):
		lhs = self.atom()
		
		while tok := self.peek():
			op = tok.value
			if op not in PRECS: break
			
			if op == ";": break
			
			prec = PRECS[op]
			if prec < min_prec: break
			
			self.consume()
			
			if op in OPNAMES:
				lhs = getattr(self, "op_" + OPNAMES[op])(lhs)
			else:
				rhs = self.expr(prec + (op not in RIGHT))
				if rhs is None: break
				lhs = AST(op, lhs, rhs).origin(tok)
		
		return lhs
	
	def kw_if(self):
		cond = self.condition()
		th = self.block()
		el = self.maybe("else") and self.block()

		return AST("if", cond, th, el)
	
	def kw_loop(self):
		always = self.block()
		if self.maybe("while"):
			return AST("loop", always, self.condition(), self.block())
		return AST("loop", always)
	
	def kw_while(self):
		cond = self.condition()
		body = self.block()
		el = self.maybe("else") and self.block()

		return AST("loop", None, cond, body, el)
		
	def kw_for(self):
		self.expect("(")
		self.expect("var")
		
		# Too permissive, good enough
		itvt = self.peek()
		itvar = AST("id", self.relaxid()).origin(itvt)
		self.expect("in")
		
		iter = self.expr(PRECS[','])
		self.expect(")")
		
		return AST("for", itvar, iter, self.block())
	
	def kw_break(self): return AST("break")
	def kw_continue(self): return AST("continue")
	def kw_return(self): return AST("return", self.expr())
	def kw_fail(self): return AST("fail", self.expr())
	
	def kw_var(self):
		vars = []
		while nt := self.peek():
			name = self.relaxid() or self.expected("l-value")
			vn = AST("id", name).origin(nt)
			
			if self.maybe("="):
				value = self.expr()
			elif self.peek("("):
				args = self.funcargs()
				body = self.block()
				value = AST("fn", AST("const", name), args, body)
			else:
				value = None
			
			vars.append([vn, value])
			
			if not self.maybe(","): break
		
		return AST("var", vars)
	
	def atom(self):
		cur = self.peek()
		if cur is None:
			return None
		
		ct = cur.type
		val = cur.value
		
		# Exceptions which shouldn't be consumed
		if val in {")", ']', "}", ',', ';', 'else'}:
			return None
		
		if ct == "punc":
			return None
		
		# Everything else will either consume or error
		self.consume()
		
		if ct == "dec": result = AST("const", int(cur.value, 10))
		elif ct in {"sq", "dq"}: result = AST("const", stresc(cur.match[1]))
		elif ct in {"bq"}: result = AST("const", cur.match[1])
		elif ct == "id": result = AST("id", val)
		elif ct == "uop": result = AST(val, self.expr())
		elif ct == "op" and val == "-": result = AST(val, self.expr())
		
		elif ct == "kw":
			try:
				result = getattr(self, "kw_" + val)()
			except AttributeError:
				raise self.error("Unknown keyword " + val) from None
		
		else:
			raise self.error(f"Unknown token {ct} {val}")
		
		return result.origin(cur)
