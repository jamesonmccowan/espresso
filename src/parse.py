#!/usr/bin/env python3

import re
#from ast import Value, Op, Var, Block, Prog, Func, Assign, Tuple, Call, Index, Branch, Loop, If, Switch, Case, Import, Proto, ObjectLiteral, ForLoop, Format, ListLiteral
import ast
from typing import *
from runtime import EspString, EspNone, EspDict, EspList

import warnings

class ParseError(RuntimeError):
	def __init__(self, msg, pre, p, l, c):
		super().__init__(f"{msg} ({l}|{c}:{p})\n{pre}")
		
		self.pos = p
		self.line = l
		self.col = c

KW = [
	"if", "then", "else", "loop", "while", "do", "for",
	"with", "switch", "case", "try", "finally",
	"return", "yield", "fail", "await", "break", "continue", "redo"
	"var", "const", "proto", "struct", "function",
	"async", "strict", "public", "private", "static", "var", "const"
	"this", "super", "none", "inf", "nan",
	"new", "delete", "in", "is", "as", "has",
	
	"and", "or", "not", "xor"
]

KWALIASES = {
	"or": "||",
	"and": "&&",
	"not": "!",
	"xor": "^"
}

# Token regex, organized to allow them to be indexed by name
PATS = {
	"bin": r"0b[_01]*[01]",
	"oct": r"0o[_0-7]*[0-7]",
	"hex": r"0x[_\da-fA-F]*[\da-fA-F]",
	"flt": r"(?:\.\d[_\d]*|\d[_\d]*\.(?!\.)(?:\d[_\d]*)?)(?:e[-+]\d[_\d]*)?",
	"dec": r"\d+",
	"sq": r"'(?:\\.|.+?)*?'",
	"dq": r'"(?:\\.|.+?)*?"',
	"bq": r"`(?:\\.|.+?)*?`",
	"sq3": r"'''(?:\\.|.+?)*?'''",
	"dq3": r'"""(?:\\.|.+?)*?"""',
	"bq3": r"```(?:\\.|.+?)*?```",
	"kw": "|".join(KW),
	"id": r"[\w][\w\d]*",
	"punc": r"[()\[\]{}]|\.{1,3}",
	"op": "|".join([ # Ops can be contextual identifiers, puncs can't
		r"[@~;,?]", # Misc syntax
		r"[-=]>", # Arrows
		r"(?P<d0>[-+*/%&|^:])(?P=d0)?=", # Assignment ops
		r"={1,3}", r"!={,2}", r"[<>]=?", # Comparison ops
		r"(?P<d1>[-+*/%&|^:!])(?P=d1)?", # Arithmetic and logical
		r"<<[<>]|<>|[<>]>>" # Shifts
	])
}
# Operators which can't be overloaded because they encode syntax
SYNTACTIC = {
	",", "=", "...", ".", ":", "&&", "||", "===", "!==", "++", "--", "=>", "->"
}
# Reminder: Higher precedence binds more strongly
PRECS = {
	#",": 1, ":": 1,
	"=": 2,
	"..": 3, "...": 3,
	"||": 3, "^^": 4, "&&": 5, "|": 6, "^": 7, "&": 8,
	"==": 9, "!=": 9, "===": 9, "!==": 9,
	"<": 10, "<=": 10, ">": 10, ">=": 10, "<>": 10,
	"<<": 11, "<<<": 11, ">>": 11, ">>>": 11,
	"!": 12, "~": 13, "+": 14, "-": 14,
	"*": 15, "/": 15, "%": 15,
	"**": 16, "//": 16, "%%": 16,
	"++": 0, "--": 0,
	".": 17
}

# Unary operators can be prefix or postfix, but cannot be infix. All binary
#  operators can be prefix unary operators
UNARY = {
	"!", "?", "++", "--", "..."
}

# Right-associative operators
RIGHT = {
	"**"
}

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
		
		# Flag indicating if this token was an operator followed by the =
		#  meta-operator. Without this, = has the lowest precedence so is
		#  likely to be less than min_prec, but the = will have already been
		#  consumed.
		self.assign = False
	
	def __str__(self):
		return f"{self.type}:{self.value}"
	
	def __repr__(self):
		return f"Token({self.type!r}, {self.value!r})"
	
	def __eq__(self, other):
		eq = (self.p == other.p)
		if eq:
			if self.line != other.line:
				warnings.warn("Two tokens at the same position have different line numbers")
			if self.col != other.col:
				warnings.warn("Two tokens at the same position have different line numbers")
		return eq

def semiAsExpr(block):
	'''
	Convert a list of expressions to a single expression, possibly a Block
	'''
	if len(block) == 0:
		return ast.Value(EspNone)
	elif len(block) == 1:
		return block[0]
	else:
		return ast.Block(block)

# Context-less stream of tokens to be fed to the parser
class Lexer:
	def __init__(self, src):
		self.src = src
		self.pos = 0
		self.line = 1
		self.col = 0
		self.indent = 0
		
		self.cur = None
	
	def log(self, *args, **kwargs):
		print(' '*self.indent, *args, **kwargs)
	
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
		left = sol - 60 # Prioritize before over after
		if left < 0:
			left = 0
		
		# Cutoff at 80 chars or the end of the line
		pre = self.src.split('\n')[line - 1].replace('\t', ' ')[left:][:80]
		# Point to the error
		pre += f"\n{'-'*(col - left)}^"
		
		# DEBUG
		#pre += f"\n{self.src[pos:]}"
		
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
		
		# Skip all comments
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
		
		# Named matches are included in .groups() so we need to explicitly
		#  skip them
		skip = TOKEN.groupindex.values()
		
		x = 0
		for i in range(len(g)):
			if i not in skip:
				val = g[i]
				if val: break
				x += 1
		
		tt = NAMES[x]
		
		if tt in RADIX:
			r = RADIX[tt]
			if r != 10:
				val = val[2:]
			tt = "val"
			val = int(val.replace("_", ""), r)
		elif tt == "flt":
			tt = "val"
			val = float(val.replace("_", ""))
		elif tt in {"sq", "dq", "bq"}:
			tt = "str"
			val = EspString(val[1:-1])
		elif tt in {"sq3", "dq3", "bq3"}:
			tt = "str"
			val = EspString(val[3:-3])
		elif tt == "kw":
			if val in KWALIASES:
				tt = "op"
				val = KWALIASES[val]
		
		# Tokens with no special postprocessing
		elif tt in {"id", "kw", "op", "punc"}:
			pass
		else:
			raise self.error(f"Unimplemented token {tt}:{val}")
		
		ncur = Token(val, tt, self.pos, self.line, self.col)
		
		self.repos(m)
		
		return ncur
	
	def consume(self):
		'''LR(1) tokenization to derive meta-operators'''
		
		self.cur = self.next()
		return self.cur
		
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
	
	def expected(self, what):
		return self.error(self.cur, f"Expected {what}, got {self.cur}")

class Parser(Lexer):
	def __init__(self, src):
		super().__init__(src)
		self.scope = []
		self.consume()
	
	def addVar(self, var):
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
	
	def relaxid(self):
		'''
		Parse an identifier with relaxed restrictions. Most token types are
		 converted to a corresponding identifier, eg "+"
		'''
		
		cur = self.cur
		val = cur.value
		ct = cur.type
		
		if ct in {"str", "id", "op"}:
			self.consume()
			return ast.Value(val).origin(cur)
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
				name = ast.Assign(name, self.expr()).origin(tok)
			
			vl.append(name)
			
			if not self.maybe(","):
				break
		
		return vl
	
	def listing(self, sep, pat):
		v = []
		x = pat()
		while x:
			v.append(x)
			if not self.maybe(sep):
				break
			
			x = pat()
		
		return v
	
	def qualifier(self):
		return self.maybe({"var", "const"})
	
	def funcargs(self):
		args = self.lvalue()
		if type(args) is ast.Tuple:
			return args.elems
		else:
			return [args]
	
	def parse_objectliteral(self, cur):
		obj = []
		
		if self.maybe("}"):
			return ast.Value(cur, EspDict())
		
		while not self.maybe("}"):
			tok = self.cur
			if tok.type in {"val", "id", "op"}:
				key = ast.Value(tok.value)
			elif tok.type == "kw":
				if tok.value in {"get", "set"}:
					raise NotImplementedError("get/set")
				key = ast.Value(tok.value)
			elif tok.type == "punc":
				if tok.value == "[":
					raise NotImplementedError("Computed properties")
				raise self.error(tok, "Unexpected punctuation")
			else:
				raise self.error(tok, f"Unknown token {tok!r}")
			
			key = key.origin(tok)
			
			self.consume()
			
			if self.peek("("):
				# Object method
				functok = self.cur
				args = self.funcargs()
				value = ast.Func(key, args, self.block()).origin(functok)
			elif self.maybe(":"):
				# Normal property
				value = self.expr()
			else:
				# NOTE: Doesn't work for computed properties
				value = ast.Var(key.value)
			
			obj.append((key, value))
			
			# Should commas be optional?
			self.maybe(",")
		
		return ast.ObjectLiteral(obj).origin(cur)
	
	def parse_proto(self, cur):
		# TODO: anonymous proto
		
		name = self.maybe(type="id")
		
		if self.maybe("is"):
			parent = self.relaxid()
		else:
			parent = None
		
		self.expect("{")
		
		pub = []
		priv = []
		stat = []
		
		while not self.maybe("}"):
			qual = self.maybe({"public", "var", "private", "static"})
			member = self.maybe(type="id")
			
			if self.maybe("("):
				params = self.listing(",", self.lvalue)
				self.expect(")")
				
				body = self.block()
				
				members = [ast.Func(member.value, params, body).origin(member)]
			else:
				members = [ast.Var(member.value).origin(member)]
				
				while self.maybe(","):
					mem = self.maybe(type="id")
					if mem is None:
						raise RuntimeError("None name")
					
					members.append(ast.Var(mem, mem.value))
			
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
		
		p = ast.Proto(name, parent, pub, priv, stat).origin(cur)
		
		if name is None:
			return p
		else:
			v = ast.Var(name, mutable=False)
			self.addVar(v)
			return ast.Assign(cur, v, p)
	
	def parse_while(self):
		# "while" token already consumed
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
				raise self.expected(cur, "case or else")
			
			# Immediate or fallthrough?
			
			if self.maybe("=>"): ln = None
			elif self.maybe(":"): ln = True
			else:
				raise self.expected(": or =>")
			
			# Block of the clause
			
			bl = self.block()
			c = ast.Case(op, val, bl, ln).origin(cur)
			if op == "else":
				if de:
					raise self.error(cur, "Duplicate else case")
				de = c
			
			cs.append(c)
		
		# Process follow up blocks
		
		th, el = self.then_else()
		
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
		
		return ast.Switch(ex, cs, de, th, el).origin(swtok)
	
	def then_else(self):
		th = el = None
		
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
					parts.append(ast.Value(scan[upto:x]))
				sp = Parser(scan[x + 2:y]).parse()
				parts.append(semiAsExpr(sp.elems))
				upto = y + 1
			else:
				break
		
		if upto < len(val):
			parts.append(ast.Value(val[upto:]))
		
		if len(parts) == 1:
			return parts[0].origin(cur)
		else:
			return ast.Format(parts).origin(cur)
	
	def parse_if(self, cur):
		cond = self.expr()
		self.maybe("then")
		
		th = self.block()
		el = None
		if self.maybe("else"):
			el = self.block()
		
		return ast.If(cond, th, el).origin(cur)
	
	def parse_import(self, cur):
		return ast.Import(self.expr()).origin(cur)
	
	def parse_listliteral(self, cur):
		if self.maybe("]"):
			return ast.Value(EspList()).origin(cur)
		
		vals = []
		while True:
			vals.append(self.expr())
			if not self.maybe(","):
				break
		self.expect("]")
		
		return ast.ListLiteral(vals).origin(cur)
	
	def parse_unary(self, cur):
		return ast.Op(cur.value, ast.Value(EspNone), self.atom()).origin(cur)
	
	def parse_loop(self, cur):
		always = self.block()
		
		if self.maybe("while"):
			cond, bl, th, el = self.parse_while()
			
			return ast.Loop(ast.Block([
				always, ast.If(cond, bl, th)
			]), el=el).origin(cur)
		else:
			return ast.Loop(cur, always).origin(cur)
	
	def parse_for(self, cur):
		self.expect("(")
		qual = self.qualifier()
		itvar = self.lvalue()
		self.expect("in")
		toiter = self.expr()
		self.expect(")")
		body = self.block()
		
		th, el = self.then_else()
		
		# TODO: n is a generalized lvalue, not a Var
		return ast.ForLoop(itvar, toiter, body, th, el).origin(cur)
	
	def parse_decl(self, cur):
		'''
		Var declarations are split into two separate concerns,
			variable name hoisting to the innermost enclosing
			scope and assignment of the variable at the correct
			point (by returning assignments as a group of
			assignment s-exprs)
		'''
		
		mut = (cur.value != "const")
		
		group = []
		while True:
			name = self.expect(type="id")
			
			v = ast.Var(name.value, mut).origin(cur)
			self.addVar(v)
			
			if self.maybe("="):
				x = self.expr()
				if x is None:
					raise self.expected("expression")
				
				group.append(ast.Assign(v, x).origin(cur))
			
			if not self.maybe(","):
				break
		return semiAsExpr(group)
	
	def parse_funcliteral(self, cur):
		name = None
		if self.cur.type == "id":
			name = ast.Value(self.cur.value)
			self.consume()
		
		args = self.funcargs()
		
		block = self.block()
		func = ast.Func(name, args, block).origin(cur)
		
		if name:
			self.addVar(name.value)
			return ast.Assign(name, func).origin(cur)
		else:
			return func
	
	def atom(self):
		if self.cur is None:
			return None
		
		cur = self.cur
		val = cur.value
		ct = cur.type
		
		# Exceptions which shouldn't be consumed
		if val in {")", ";", "}", "]", "case", "else"}:
			return None
		
		self.consume()
		
		if ct == "val":
			return ast.Value(cur.value).origin(cur)
		elif ct == "str":
			return self.process_string(cur)
		
		elif ct == "id":
			v = ast.Var(cur.value).origin(cur)
			
			# Check string call
			s = self.maybe(type="str")
			if s:
				return ast.Call(v, [self.process_string(s)]).origin(s)
			
			return v
		elif ct == "punc":
			if val == "(":
				if self.maybe(")"):
					return ast.Tuple([]).origin(cur)
				
				x = self.semichain()
				self.expect(")")
				return semiAsExpr(x)
			elif val == "{":
				return self.parse_objectliteral(cur)
			elif val == "[":
				return self.parse_listliteral(cur)
			#elif val == ")": pass
			#elif val == "}": pass
			# TODO: dot functions
			else:
				raise NotImplementedError(val)
		elif ct == "op":
			return self.parse_unary(cur)
		elif ct == "kw":
			if val == "if":
				return self.parse_if(cur)
			elif val == "none":
				return ast.Value(EspNone).origin(cur)
			elif val == "inf":
				return ast.Value(float('inf')).origin(cur)
			elif val == "nan":
				return ast.Value(float('nan')).origin(cur)
			elif val == "proto":
				return self.parse_proto(cur)
				
			elif val == "import":
				return self.parse_import(cur)
			elif val == "loop":
				return self.parse_loop(cur)
				
			elif val == "while":
				cond, bl, th, el = self.parse_while()
				
				# Not account for el
				return ast.Loop(ast.Block([
					ast.If(cond, bl, ast.Branch("break"))
				]), el=el).origin(cur)
			
			elif val == "for":
				return self.parse_for(cur)
			
			elif val == "switch":
				return self.parse_switch(cur)
			
			elif val in {"break", "continue", "redo"}:
				return ast.Branch(val).origin(cur)
				# Todo: targeted branches
			
			elif val in {"var", "const"}:
				return self.parse_decl(cur)
			
			elif val == "function":
				return self.parse_funcliteral(cur)
			
			elif val == "try":
				raise NotImplementedError("try")
			
			else:
				raise self.error(f"Unimplemented keyword {val}")
		
		raise self.error(f"Unknown token {val}")
	
	def postfix_unary(self):
		lhs = self.atom()
		
		while True:
			op = self.peek(type="op")
			
			if op and op.value in UNARY:
				self.consume()
				lhs = ast.Op([lhs, EspNone]).origin(op)
			else:
				break
		
		return lhs
	
	def index_chain(self):
		'''Second-order atom parsing''' 
		
		lhs = self.atom()
		
		while True:
			dot = self.maybe(".")
			if not dot: break
			
			rhs = self.relaxid()
			lhs = ast.Index(dot, lhs, [rhs])
		
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
				return semiAsExpr(b)
			else:
				return ast.Block(b, vars).origin(cur)
		else:
			x = self.expr()
			self.maybe(";")
			return x
	
	def parse_call(self, lhs, cur):
		args = self.listing(",", lambda: self.expr())
		self.expect(")")
		return  ast.Call(lhs, args).origin(cur)
	
	def parse_index(self, lhs, cur):
		args = self.listing(":", lambda: self.expr())
		self.expect("]")
		
		return ast.Index(lhs, args).origin(cur)
	
	def expr(self, min_prec=0):
		'''
		Uses precedence climbing
		'''
		
		lhs = self.index_chain()
		while self.cur is not None:
			cur = self.cur
			
			if self.maybe("("):
				lhs = self.parse_call(lhs, cur)
				continue
			
			if self.maybe("["):
				lhs = self.parse_index(lhs, cur)
				continue
			
			op = cur.value
			if op.endswith('='):
				op = None if op == '=' else op[:-1]
				assign = True
			else:
				assign = False
			
			if op and op not in PRECS:
				break
			
			prec = PRECS['=' if assign else op]
			if prec < min_prec:
				break
			
			self.consume()
			
			next_min_prec = prec + (op not in RIGHT)
			
			rhs = self.expr(next_min_prec)
			
			if assign:
				lhs = ast.Assign(lhs, rhs, op).origin(cur)
			else:
				if op == ",":
					if type(lhs) is ast.Tuple:
						lhs.append(rhs)
					else:
						lhs = ast.Tuple([lhs, rhs])
				elif op == ".":
					lhs = ast.Index(lhs, [rhs])
				else:
					lhs = ast.Op(op, lhs, rhs)
		
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
		prog = ast.Prog(self.semichain(), vars)
		self.scope.pop()
		return prog

# Debug stuff

'''
def indentify(method):
	def wrap(self, *args, **kwargs):
		p = ', '.join(repr(x) for x in args) if args else ''
		k = ', '.join(f"{x}={y!r}" for x,y in kwargs.items()) if kwargs else ''
		pk = f"{p!r}, {k!r}" if p and k else p + k
		self.log(f"{method.__name__}({pk})")
		self.indent += 1
		tmp = method(self, *args, **kwargs)
		self.indent -= 1
		return tmp
	return wrap

for name in dir(Parser):
	if not name.startswith("__") and name not in {"log", "match", "next", "repos"}:
		member = getattr(Parser, name)
		if isinstance(member, type(Parser.parse)):
			setattr(Parser, name, indentify(member))
'''