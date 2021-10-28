#!/usr/bin/env python3

import re
from ast import Value, Op, Var, Block, Prog, Func, Assign, Tuple, Call, Index, Branch, Loop, If, Switch, Case, Import, Proto, ObjectLiteral, ForLoop, Format
from runtime import EspString, EspNone, EspDict

class ParseError(RuntimeError):
	def __init__(self, msg, pre, p, l, c):
		super().__init__(f"{msg} ({l}|{c}:{p})\n{pre}")
		
		self.pos = p
		self.line = l
		self.col = c

DEC = re.compile(r"\d([\d_]*\d)?")
# Token regex, organized to allow them to be indexed by name
PATS = {
	"bin": r"0b[_01]*[01]",
	"oct": r"0o[_0-7]*[0-7]",
	"hex": r"0x[_\da-fA-F]*[\da-fA-F]",
	"flt": r"(?:\.\d[_\d]*|\d[_\d]*\.(?:\d[_\d]*)?)(?:e[-+]\d[_\d]*)?",
	"dec": r"\d+",
	"sq": r"'(?:\\.|.+?)*?'",
	"dq": r'"(?:\\.|.+?)*?"',
	"bq": r"`(?:\\.|.+?)*?`",
	"sq3": r"'''(?:\\.|.+?)*?'''",
	"dq3": r'"""(?:\\.|.+?)*?"""',
	"bq3": r"```(?:\\.|.+?)*?```",
	"id": r"[\w][\w\d]*",
	"punc": r"[()\[\]{}]|\.{1,3}",
	"op": "|".join([ # Ops can be contextual identifiers, puncs can't
		r"[@~;,?]",
		r"[-=]>", r":=",
		r"={1,3}", r"!={,2}", r"[<>]=?",
		r"(?P<d>[-+*/%&|^:!])(?P=d)?",
		r"<<[<>]|<>|[<>]>>"
	])
}
# Operators which can't be overloaded because they encode syntax
SYNTACTIC = [
	",", "=", "...", ".", ":", "&&", "||", "===", "!==", "++", "--"
]
PRECS = {
	",": 1,
	"=": 2,
	"..": 3, "...": 3,
	"||": 3, "^^": 4, "&&": 5, "|": 6, "^": 7, "&": 8,
	"==": 9, "!=": 9, "===": 9, "!==": 9,
	"<": 10, "<=": 10, ">": 10, ">=": 10, "<>": 10,
	"<<": 11, "<<<": 11, ">>": 11, ">>>": 11,
	"!": 12, "~": 13, "+": 14, "-": 14,
	"*": 15, "/": 15, "%": 15,
	"**": 16, "//": 16, "%%": 16,
	".": 17
}

# Right-associative operators
RIGHT = [
	"**"
]

KW = [
	"if", "then", "else", "loop", "while", "do", "for",
	"with", "switch", "case", "try", "finally",
	"return", "yield", "fail", "await", "break", "continue", "redo"
	"var", "const", "proto", "struct", "function",
	"async", "strict", "public", "private", "static", "var", "const"
	"this", "super", "none", "inf", "nan",
	"new", "delete", "in", "is", "as", "has"
]

RADIX = {
	"bin": 2,
	"oct": 8,
	"dec": 10,
	"hex": 16
}

NAMES = list(PATS.keys())
TOKEN = re.compile(f"({')|('.join(PATS.values())})", re.M)
COMMENT = re.compile(r"\s*(#\*(?:.|\n)+\*#\s*|#\{|#.*$)", re.M)
RECURSIVE_COMMENT = re.compile(r"#\{|#\}", re.M)
NEWLINE = re.compile("\n")
SPACE = re.compile(r"\s+", re.M)
WORD = re.compile(r'\S+')

class Token:
	def __init__(self, v, t, p, l, c):
		self.value = v
		self.type = t
		self.pos = p
		self.line = l
		self.col = c
		
		self.assign = False
	
	def __str__(self):
		return f"{self.type}:{self.value}"

def semiAsExpr(cur, block):
	'''
	Convert a list of expressions to a single expression, possibly a Block
	'''
	if len(block) == 0:
		return Value(cur, EspNone)
	elif len(block) == 1:
		return block[0]
	else:
		return Block(cur, block)

# Context-less stream of tokens to be fed to the parser
class Lexer:
	def __init__(self, src):
		self.src = src
		self.pos = 0
		self.line = 1
		self.col = 0
		self.indent = 0
		
		self.la = None
		self.cur = None
	
	def log(self, *args):
		print(' '*self.indent, *args)
	
	def error(self, tok, msg=None):
		'''
		Build an error based on the current parser state. Tok is the Token
		object which caused the error, or None if it's a parsing error
		
		tok is optional, if the function is called with only one parameter
		it's assumed to be None
		'''
		
		if msg is None:
			tok, msg = None, tok
		
		src = tok or self
		
		pos, line, col = src.pos, src.line, src.col
		
		# Want to build a preview, extract the start of line
		sol = self.src.rfind('\n', 0, pos)
		if sol == -1:
			sol = 0
		left = pos - 60 # Prioritize before over after
		if left < 0:
			left = 0
		
		# Cutoff at 80 chars or the end of the line
		pre = self.src[left:80].split('\n')[0]
		# Point to the error
		pre += f"\n{'-'*(pos - left)}^"
		
		# DEBUG
		pre += f"\n{self.src[pos:]}"
		
		return ParseError(msg, pre, pos, line, col)
		
	def match(self, reg):
		'''Utility to match arbitrary regexes at the current index'''
		return reg.match(self.src, self.pos)
	
	# Adjust the parser position based on the token match
	def repos(self, m):
		'''Reposition the parser based on the token match'''
		
		self.pos += len(m[0])
		lines = NEWLINE.split(m[0])
		if len(lines) > 1:
			self.line += len(lines) - 1
			self.col = len(lines[-1])
		else:
			self.col += len(m[0])
	
	def next(self):
		'''Get the next token after discarding whitespace and comments'''
		
		if self.pos >= len(self.src):
			return None
		
		while True:
			comment = self.match(COMMENT)
			if comment is None: break
			
			self.repos(comment)
			# Recursive comment parsing
			if comment[1] == "#{":
				level = 1
				while True:
					m = self.match(RECURSIVE_COMMENT)
					if m is None:
						raise self.error("Unexpected EOF")
					if m[0] == "#{":
						level += 1
					else: # }#
						level -= 1
		
		# Clean up ordinary space without comments
		m = self.match(SPACE)
		if m is not None:
			self.repos(m)
		
		# If the token regex doesn't match, we've run out
		m = self.match(TOKEN)
		if m is None:
			return None
		
		# Find the first match to determine which token type it is
		g = m.groups()
		
		# Named matches are ignored, but they're included in .groups() so we
		#  need to explicitly skip them
		skip = TOKEN.groupindex.values()
		
		x = 0
		for i in range(len(g)):
			if i not in skip:
				tok = g[i]
				if tok: break
				x += 1
		
		tt = NAMES[x]
		
		if tt == "id":
			if tok in KW:
				tt = "kw"
			val = tok
		elif tt in RADIX:
			r = RADIX[tt]
			if r != 10:
				tok = tok[2:]
			tt = "val"
			val = int(tok.replace("_", ""), r)
		elif tt == "flt":
			tt = "val"
			val = float(tok.replace("_", ""))
		elif tt in {"sq", "dq", "bq"}:
			tt = "str"
			val = EspString(tok[1:-1])
		elif tt in {"sq3", "dq3", "bq3"}:
			tt = "str"
			val = EspString(tok[3:-3])
		elif tt == "op":
			val = tok
		elif tt == "punc":
			val = tok
		else:
			raise self.error(f"Unimplemented token {tt}:{tok}")
		
		ncur = Token(val, tt, self.pos, self.line, self.col)
		
		self.repos(m)
		
		return ncur
	
	def consume(self):
		'''LR(1) tokenization to derive meta-operators'''
		
		if self.la:
			self.cur = self.la
			self.la = None
		else:
			self.cur = self.next()
			
			if self.cur and self.cur.value in PRECS:
				self.la = self.next()
				if self.la and self.la.value == "=":
					self.cur.assign = True
					self.la = None
		
		if self.cur and self.cur.value == "=":
			self.cur.assign = True
		
		return self.cur
	
	def peek(self, value=None, type=None):
		'''
		Peek at the next token without consuming it, returning the token or None
		'''
		
		if self.cur is None:
			return None
		
		if value:
			if value.__class__ is set:
				if self.cur.value in value:
					return self.cur
			else:
				if self.cur.value == value:
					return self.cur
		else:
			if self.cur.type == type:
				return self.cur
		
		return None
	
	def maybe(self, value=None, type=None):
		'''
		Consume the next token if it matches the string, returning the token,
		else return None
		'''
		
		v = self.peek(value, type)
		if v:
			self.consume()
		return v
	
	def expect(self, value=None, type=None):
		'''Next token must be the string or it errors'''
		
		m = self.maybe(value, type)
		if m is None:
			raise self.expected(value or type)
		return m
	
	def expected(self, tok, what):
		return self.error(tok, "Expected " + what)

class Parser(Lexer):
	def __init__(self, src):
		super().__init__(src)
		self.scope = []
		
		self.consume()
	
	def addVar(self, var):
		print(self.scope)
		self.scope[-1].append(var)
	
	def lvalue(self):
		'''Ensure the next element is an l-value'''
		
		x = self.atom()
		if x is None:
			return None
		
		if x.lvalue:
			return x
		else:
			raise self.error(x.token, "Not an l-value")
	
	def ident(self):
		'''
		Parse an identifier with relaxed restrictions. Most token types are
		 converted to a corresponding identifier, eg "+"
		'''
		
		cur = self.cur
		val = cur.value
		ct = cur.type
		
		if ct in {"str", "id", "op"}:
			cur.type = "str"
			self.consume()
			return cur
		else:
			x = self.atom()
			if x: return x
			raise self.expected(cur, "relaxed identifier")
	
	def varlist(self):
		'''
		Parses a list of variables, possibly with defaults and unpacking
		'''
		
		vl = []
		
		while True:
			name = self.lvalue()
			
			# Todo: Type annotation using :
			
			tok = self.maybe("=")
			if tok:
				name = Assign(tok, name, self.expr())
			
			vl.append(name)
			
			if not self.maybe(","):
				break
		
		return vl
	
	def commalist(self, pat):
		v = []
		x = pat()
		while x:
			v.append(x)
			if not self.maybe(","):
				break
			
			x = pat()
		
		return v
	
	def qualifier(self):
		return self.maybe({"var", "const"})
	
	def funcargs(self):
		args = self.lvalue()
		if type(args) is Tuple:
			return args.elems
		else:
			return [args]
	
	def parse_objectliteral(self, cur):
		obj = []
		
		if self.maybe("}"):
			return Value(cur, EspDict())
		
		while not self.maybe("}"):
			tok = self.cur
			if tok.type in {"val", "id", "op"}:
				key = Value(tok, tok.value)
			elif tok.type == "kw":
				if tok.value in {"get", "set"}:
					raise NotImplementedError("get/set")
				key = Value(tok.value)
			elif tok.type == "punc":
				if tok.value == "[":
					raise NotImplementedError("Computed properties")
				raise self.error(tok, "Unexpected punctuation")
			else:
				raise self.error(tok, f"Unknown token {tok!r}")
			
			self.consume()
			
			if self.peek("("):
				# Object method
				functok = self.cur
				args = self.funcargs()
				value = Func(functok, key, args, self.block())
			elif self.maybe(":"):
				# Normal property
				value = self.expr()
			else:
				# NOTE: Doesn't work for computed properties
				value = Var(key.value)
			
			obj.append((key, value))
			
			# Should commas be optional?
			self.maybe(",")
		
		return ObjectLiteral(cur, obj)
	
	def parse_proto(self, cur):
		# TODO: anonymous proto
		
		name = self.maybe(type="id")
		
		if self.maybe("is"):
			parent = self.ident()
		else:
			parent = None
		
		self.expect("{")
		
		pub = []
		priv = []
		stat = []
		
		while not self.maybe("}"):
			qual = self.maybe({"public", "var", "private", "static"})
			mem = self.maybe(type="id")
			
			if self.maybe("("):
				params = self.commalist(self.lvalue)
				self.expect(")")
				
				body = self.block()
				
				members = [Func(mem, mem.value, params, body)]
			else:
				members = [Var(mem, mem.value)]
				
				while self.maybe(","):
					mem = self.maybe(type="id")
					if mem is None:
						raise RuntimeError("None name")
					
					members.append(Var(mem, mem.value))
			
			if not qual or qual.value in {"public", "var"}:
				pub += members
			elif qual.value == "private":
				priv += members
			elif qual.value == "static":
				stat += members
			else:
				raise RuntimeError("Shouldn't happen")
			
			while self.maybe(";"): pass
		
		name = name.value if name else None
		
		p = Proto(cur, name, parent, pub, priv, stat)
		
		if name is None:
			return p
		else:
			v = Var(cur, name, mutable=False)
			self.addVar(v)
			return Assign(cur, v, p)
	
	def maybe_while(self):
		cond = self.expr()
		bl = self.block()
		
		th, el = self.then_else()
		
		return cond, bl, th, el
	
	def parse_switch(self, cur):
		swtok = cur
		
		ex = self.expr()
		
		# List of cases clauses which will be linked after the
		#  parsing stage
		cs = []
		
		# Then, else, and default
		th = el = de = None
		
		# First, collect all the cases as separate blocks
		
		self.expect("{")
		while not self.maybe("}"):
			# Token of the case/else
			cur = self.cur
			
			# case or else clause?
			
			if self.maybe("case"):
				op = "in" if self.maybe("in") else "="
				val = self.expr()
			elif self.maybe("else"):
				op = "else"
				val = None
			else:
				raise self.expected("case or else")
			
			# Immediate or fallthrough?
			
			if self.maybe("=>"): ln = None
			elif self.maybe(":"): ln = True
			else:
				raise self.expected(": or =>")
			
			# Block of the clause
			
			bl = self.block()
			c = Case(cur, op, val, bl, ln)
			if op == "else":
				if de:
					raise self.error("Duplicate else case")
				de = c
			
			cs.append(c)
		
		# Process follow up blocks
		
		cur = self.cur
		if self.maybe("then"):
			th = Case(cur, "then", None, self.block(), None)
		
		cur = self.cur
		if self.maybe("else"):
			el = Case(cur, "else", None, self.block(), None)
		
		# Link adjacent fallthrough blocks together
		
		update = None
		
		for case in cs:
			if update:
				update.next = case
			
			update = None
			if case.next:
				update = case
		
		# Remove else-case from the case list
		if de in cs:
			cs.remove(de)
		
		return Switch(swtok, ex, cs, de, th, el)
	
	def then_else(self):
		th = el = Value(None, EspNone)
		
		if self.maybe("then"):
			th = self.block()
		if self.maybe("else"):
			el = self.block()
		
		return th, el
	
	def process_string(self, cur):
		val = cur.value
		
		# Lazy hack, there are edge cases where this would be incorrect
		val = val.replace("\\n", "\n").replace("\\t", "\t")
		
		# Scan for format strings
		parts = []
		scan = val
		upto = 0
		while True:
			x = scan.find("\\{", upto)
			if x != -1:
				y = scan.find("}", x)
				if upto != x:
					parts.append(scan[upto:x])
				sp = Parser(scan[x + 2:y]).parse()
				parts.append(Block(cur, sp.elems, sp.vars))
				upto = y + 1
			else:
				break
		
		if upto < len(val):
			parts.append(val[upto:])
		
		if len(parts) == 1:
			return Value(cur, parts[0])
		else:
			return Format(cur, parts)
	
	def atom(self):
		if self.cur is None:
			return None
		
		cur = self.cur
		val = cur.value
		ct = cur.type
		
		# Exceptions which shouldn't be consumed
		if val in {")", ";", "}", "case", "else"}:
			return None
		
		self.consume()
		
		if ct == "val":
			return Value(cur, cur.value)
		elif ct == "str":
			return self.process_string(cur)
		
		elif ct == "id":
			v = Var(cur, cur.value)
			
			# Check string call
			s = self.maybe(type="str")
			if s:
				return Call(s, v, [self.process_string(s)])
			
			return v
		elif ct == "punc":
			if val == "(":
				if self.maybe(")"):
					return Tuple(cur, [])
				
				x = self.semichain()
				self.expect(")")
				return semiAsExpr(cur, x)
			elif val == "{":
				return self.parse_objectliteral(cur)
			#elif val == ")": pass
			#elif val == "}": pass
			# TODO: dot functions
			else:
				raise NotImplementedError(val)
		elif ct == "op":
			return Op(cur, Value(None, EspNone), self.atom())
		elif ct == "kw":
			if val == "if":
				cond = self.expr()
				self.maybe("then")
				
				th = self.block()
				el = Value(None, EspNone)
				if self.maybe("else"):
					el = self.block()
				
				return If(cur, cond, th, el)
			
			elif val == "none":
				return Value(cur, EspNone)
			elif val == "inf":
				return Value(cur, float('inf'))
			elif val == "nan":
				return Value(cur, float('nan'))
			elif val == "proto":
				return self.parse_proto(cur)
				
			elif val == "import":
				return Import(cur, self.expr())
			elif val == "loop":
				always = self.block()
				
				if self.maybe("while"):
					cond, bl, th, el = self.maybe_while()
					
					return Loop(cur, Block(cur, [
						always, If(cond, bl, th)
					]), el=el)
				else:
					return Loop(cur, always)
				
			elif val == "while":
				cond, bl, th, el = self.maybe_while()
				
				# Not account for el
				return Loop(cur, Block(cur, [
					If(cur, cond, bl, Branch(cur, "break"))
				]), el=el)
			
			elif val == "for":
				self.expect("(")
				qual = self.qualifier()
				itvar = self.lvalue()
				self.expect("in")
				toiter = self.expr()
				self.expect(")")
				body = self.block()
				
				it = Var(cur, "$it")
				
				th, el = self.then_else()
				
				# TODO: n is a generalized lvalue, not a Var
				return ForLoop(cur, itvar, toiter, body, th, el)
			
			elif val == "switch":
				return self.parse_switch(cur)
			
			elif val in {"break", "continue", "redo"}:
				return Branch(cur, val)
				# Todo: targeted branches
			
			elif val in {"var", "const"}:
				'''
				Var declarations are split into two separate concerns,
				 variable name hoisting to the innermost enclosing
				 scope and assignment of the variable at the correct
				 point (by returning assignments as a group of
				 assignment s-exprs)
				'''
				
				mut = (val != "const")
				
				group = []
				while True:
					name = self.expect(type="id")
					
					v = Var(cur, name.value, mut)
					self.addVar(v)
					
					if self.maybe("="):
						x = self.expr()
						if x is None:
							raise self.expected("expression")
						
						group.append(Assign(cur, v, x))
					
					if not self.maybe(","):
						break
				return semiAsExpr(cur, group)
			
			elif val == "function":
				name = None
				if self.cur.type == "id":
					name = self.cur.value
					self.consume()
				
				args = self.funcargs()
				
				block = self.block()
				func = Func(cur, name, args, block)
				
				if name:
					self.addVar(name)
					return Assign(cur, Var(cur, name), func)
				else:
					return func
			
			elif val == "try":
				raise NotImplementedError("try")
			
			else:
				raise self.error("Unimplemented keyword " + val)
		
		raise self.error("Unknown token " + val)
	
	def atom2(self):
		'''Second-order atom parsing''' 
		
		lhs = self.atom()
		
		while True:
			dot = self.maybe(".")
			if not dot: break
			
			rhs = self.ident()
			lhs = Index(dot, lhs, [Value(rhs, rhs.value)])
		
		return lhs
	
	def block(self):
		'''
		Parses a "block", which is an expression which prioritizes curly-brace
		blocks over object literals and considers the semicolon to end the
		expression rather than continue it.
		'''
		
		cur = self.cur
		if self.maybe("{"):
			vars = []
			self.scope.append(vars)
			b = self.semichain()
			self.scope.pop()
			self.expect("}")
			
			if len(vars) > 0:
				return semiAsExpr(cur, b)
			else:
				return Block(cur, b, vars)
		else:
			x = self.expr()
			self.maybe(";")
			return x
	
	def binop(self):
		op = self.cur.value
		if op not in PRECS:
			return None, None
		
		self.consume()
		
		return op, self.maybe("=")
	
	def expr(self, min_prec=0):
		'''
		Uses precedence climbing
		'''
		
		lhs = self.atom2()
		
		while self.cur is not None:
			cur = self.cur
			op = cur.value
			
			if op == "(":
				self.consume()
				args = []
				while True:
					args.append(self.expr(PRECS[','] + 1))
					
					if not self.maybe(","):
						break
				self.expect(")")
				lhs = Call(cur, lhs, args)
				continue
			
			if op == "[":
				args = []
				while True:
					args.append(self.expr(PRECS[':'] + 1))
					
					if not self.maybe(":"):
						break
				self.expect("]")
				
				lhs = Index(cur, lhs, args)
				continue
			
			if op not in PRECS:
				break
			
			assign = self.cur.assign
			prec = assign and PRECS['='] or PRECS[op]
			
			if prec < min_prec:
				break
			
			next_min_prec = prec + (op in RIGHT)
			self.consume()
			
			rhs = self.expr(next_min_prec)
			
			if assign:
				lhs = Assign(cur, lhs, rhs, op if op != "=" else None)
			else:
				if op == ",":
					if type(lhs) is Tuple:
						lhs.append(rhs)
					else:
						lhs = Tuple(None, [lhs, rhs])
				elif op == ".":
					lhs = Index(cur, lhs, [rhs])
				else:
					lhs = Op(cur, lhs, rhs)
		
		return lhs
	
	def semichain(self):
		'''
		Parse a block as a chain of expressions possibly separated by
	 	semicolons.
		'''
		
		st = []
		while self.cur is not None:
			x = self.expr()
			if x is None:
				break
			st.append(x)
			
			while self.maybe(";"):
				pass
		
		return st
	
	def parse(self):
		vars = []
		self.scope.append(vars)
		prog = Prog(self.semichain(), vars)
		self.scope.pop()
		return prog