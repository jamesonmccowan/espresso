#!/usr/bin/env python3

import re
from ast import Value, Op, Var, Block, Prog, Func, Assign, Tuple, Call, Index, Branch, Loop, If, Switch, Case, Import
from runtime import EspString, EspNone

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
	"punc": r"[()\[\]{}]",
	"op": "|".join([ # Ops can be contextual identifiers, puncs can't
		r"[()\[\]{}]",
		r"[@~;,?]",
		r"[-=]>", r":=",
		r"(?P<d>[-+*/%&|^:])(?P=d)?",
		r"[<>.]{1,3}",
		r"={1,3}", r"!={,2}", r"[<>]=?"
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
	"if", "then", "else", "loop", "while", "do",
	"with", "switch", "case", "try", "finally",
	"return", "yield", "fail", "await", "break", "continue", "redo"
	"var", "const", "proto", "struct", "function",
	"async", "strict", "public", "private", "static",
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

print(TOKEN.pattern)
print(NAMES)

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
		return Value(EspNone)
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
		
		return self.cur
	
	def peek(self, value=None, type=None):
		'''Peek at the next token without consuming it'''
		
		if self.cur is None:
			return False
		
		if value:
			return self.cur.value == value
		else:
			return self.cur.type == type
	
	def maybe(self, value=None, type=None):
		'''Consume the next token if it matches the string'''
		
		v = self.peek(value, type)
		if v:
			self.consume()
		return v
	
	def expect(self, value=None, type=None):
		'''Next token must be the string or it errors'''
		
		if not self.maybe(value, type):
			raise self.expected(value or type)
	
	def expected(self, what):
		return self.error("Expected " + what)

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
			return self.cur
		else:
			raise self.expected(self.cur, "relaxed identifier")
	
	def atom(self):
		if self.cur is None:
			return None
		
		# Exceptions which shouldn't be consumed
		cur = self.cur
		val = cur.value
		ct = cur.type
		
		if val in {")", ";", "}"}:
			return None
		
		self.consume()
		
		if ct == "val":
			return Value(cur)
		elif ct == "id":
			return Var(cur)
		elif ct == "punc":
			if val == "(":
				if self.maybe(")"):
					return Tuple(cur, [])
				
				x = self.semichain()
				self.expect(")")
				return semiAsExpr(cur, x)
			#elif val == ")": pass
			#elif val == "}": pass
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
			
			elif val == "else":
				'''
				Else cannot appear on its own, but it isn't an error
				to encounter it while parsing an atom - this can
				happen while parsing the then block
				'''
				return None
			elif val == "none":
				return Value(cur, EspNone)
			elif val == "inf":
				return Value(cur, float('inf'))
			elif val == "nan":
				return Value(cur, float('nan'))
			elif val == "proto":
				if self.maybe("is") or self.peek("{"):
					name = None
				else:
					name = self.ident()
			elif val == "import":
				return Import(cur, self.expr())
			elif val == "loop":
				bl = self.block()
				if self.maybe("while"):
					cond = self.expr()
					bl = self.block()
					
					th = el = Value(EspNone)
					if self.maybe("then"):
						th = self.block()
					if self.maybe("else"):
						el = self.block()
					
					return Loop(cur, Block([
						bl, If(cond, bl, th)
					]), el=el)
			elif val == "while":
				cond = self.expr()
				bl = self.block()
				
				th = el = Value(EspNone)
				if self.maybe("then"):
					th = self.block()
				if self.maybe("else"):
					el = self.block()
				
				return Loop(cur, Block([
					If(cond, bl, th)
				]), el=el)
			elif val == "switch":
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
				
			elif val == "case":
				return None
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
					self.expectType("id")
					name = self.cur.value
					self.consume()
					
					self.addVar(Var(cur, name, mut))
					
					if self.maybe("="):
						x = self.expr()
						if x is None:
							raise self.expected("expression")
						
						group.append(Assign(None, Var(None, name), x))
					
					if not self.maybe(","):
						break
				print("group", group)
				return semiAsExpr(cur, group)
			elif val == "function":
				name = None
				if self.cur.type == "id":
					name = self.cur.value
					self.consume()
				
				args = self.lvalue()
				if type(args) is Tuple:
					args = args.elems
				else:
					args = [args]
				
				block = self.block()
				func = Func(cur, name, args, block)
				
				if name:
					self.addVar(name)
					return Assign(Var(None, name), func)
				else:
					return func
			elif val == "try":
				raise NotImplementedError("try")
			else:
				raise self.error("Unimplemented keyword " + val)
		
		raise self.error("Unknown token " + val)
	
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
		
		lhs = self.atom()
		
		while self.cur is not None:
			cur = self.cur
			op = cur.value
			
			if op == "(":
				args = []
				while True:
					args.append(self.expr(PRECS[','] + 1))
					
					if not self.maybe(","):
						break
				
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
				lhs = Assign(cur, lhs, rhs, op)
			else:
				if op == ",":
					if type(lhs) is Tuple:
						lhs.append(rhs)
					else:
						lhs = Tuple(None, lhs, rhs)
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