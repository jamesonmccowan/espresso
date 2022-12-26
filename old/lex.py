#!/usr/bin/python3.10

import math
import re
from common import unreachable, ParseError
from typing import Union

# Operators which can't be overloaded because they encode syntax
SYNTACTIC = {
	",", "=", "...", ".", ":", "&&", "||", "===", "!==", "++", "--", "=>", "->"
}

KW = [
	"if", "then", "else", "loop", "while", "do", "for",
	"with", "switch", "case", "try", "after",
	"return", "yield", "fail", "await", "break", "continue", "redo",
	"proto", "struct", "function",
	"async", "strict", "public", "private", "static", "var", "const",
	"this", "super",
	"import", "export",
	"new", "delete", "in", "is", "as", "has",
	"and", "or", "not", "xor"
	
	# Implemented as global constants
	#"none", "inf", "nan", "true", "false"
]

KWALIASES = {
	"or": "||",
	"and": "&&",
	"not": "!",
	"xor": "^"
}

SC = r"(?:(?!\\\{)\\.|.+?)*?"
# Token regex, organized to allow them to be indexed by name
PATTERNS = {
	# Syntax "operators" which require special parsing rules
	"punc": r"[\(\)\[\]\{\}]|\.(?!\.)|\.{3}|[,;:]|[-=]>",
	"cmp": r"[!=]={1,2}|[<>!]=?|<>",
	"assign": r"(?P<d0>[~*/%&|^:])(?P=d0)?=|=",
	"op": "|".join([ # Ops can be contextual identifiers, puncs can't
		r"[@~?]", # Misc syntax
		r"[-=]>", # Arrows
		r"\.\.",
		r"(?P<d1>[-+*/%&|^:!])(?P=d1)?", # Arithmetic and logical
		r"<<[<>]|[<>]>>" # Shifts
	]),
	
	"bin": r"0b([_01]*[01])",
	"oct": r"0o([_0-7]*[0-7])",
	"hex": r"0x([_\da-fA-F]*[\da-fA-F])",
	"flt": r"(?:\.\d[_\d]*|\d[_\d]*\.(?!\.)(?:\d[_\d]*)?)(?:[eE][-+]\d[_\d]*)?",
	"dec": r"\d(?:[\d_]*\d)?",
	
	"sq_tpl": r"('|''')((?:\\.|[^']+?)*?)\\\{",
	"dq_tpl": r'("|""")((?:\\.|[^"]+?)*?)\\\{',
	
	"sq": rf"'({SC})'",
	"dq": rf'"({SC})"',
	"bq": rf"`({SC})`",
	"sq3": rf"'''({SC})'''",
	"dq3": rf'"""({SC})"""',
	"bq3": rf"```({SC})```",
	
	"kw": "|".join(KW),
	"id": r"[\w_][\w\d]*"
}
TPL = re.compile(r"(.*?)(?:(['\"]|['\"]{3})|\\\{)", re.M)

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

COMMENT = re.compile(r"\s*(#\*(?:.|\n)+\*#\s*|#.*$)", re.M)
NEWLINE = re.compile("\n")
SPACE = re.compile(r"\s+", re.M)
WORD = re.compile(r'\S+')

class Context:
	def __init__(self, file, pos, line, col):
		self.file = file
		self.pos = pos
		self.line = line
		self.col = col

class Token:
	def __init__(self, lex, m, t, ctx):
		self.lex = lex
		self.match = m
		self.value = m[0]
		self.type = t
		self.context = ctx
	
	def __str__(self):
		return f"{self.type}:{self.value}"
	
	def __repr__(self):
		return f"Token({self.type!r}, {self.value!r})"
	
	def __eq__(self, other):
		return self.p == other.p

# Context-less stream of tokens to be fed to the parser
class Lexer:
	def __init__(self, src, file="<unknown>"):
		self.src = src
		self.context = Context(file, 0, 1, 1)
		
		self.braces = [1]
	
	def repos(self, m):
		'''
		Reposition the parser based on the token match and return the old
		context
		'''
		
		old = self.context
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
		
		self.context = Context(old.file, p, l, c)
		return old
	
	def error(self, tok, msg=None):
		'''
		Build an error based on the current parser state. Tok is the Token
		object which caused the error, or None if it's a parsing error
		
		tok is optional, if the function is called with only one parameter
		it's assumed to be None
		'''
		
		if msg is None:
			tok, msg = None, tok
		
		ctx = (tok or self).context
		
		pos, line, col = ctx.pos, ctx.line, ctx.col
		
		# Cutoff at 80 chars or the end of the line
		pre = self.src.split('\n')[line - 1].replace('\t', ' ')
		# Point to the error
		pre += f"\n{'-'*(col)}^"
		
		# DEBUG
		#pre += f"\n{self.src[pos:]}"
		
		return ParseError(msg, pre, ctx)
		
	def match(self, reg):
		'''Utility to match arbitrary regexes at the current index'''
		return reg.match(self.src, self.context.pos)
	
	def next(self):
		'''Get the next token after discarding whitespace and comments'''
		
		if self.context.pos >= len(self.src):
			return None
		
		# Skip all comments
		while comment := self.match(COMMENT):
			self.repos(comment)
		
		# Clean up ordinary space without comments
		m = self.match(SPACE)
		if m is not None:
			self.repos(m)
		
		# If the token regex doesn't match, we've run out
		m = self.match(TOKEN)
		if m is None:
			return None
		
		try:
			tt, gc = TG[m.lastindex]
			match = m.groups()[m.lastindex - 1:m.lastindex + gc]
		except:
			# Common parsing issue, give us more context
			print(list(enumerate(m.groups(), 1)))
			raise
		
		val = match[0]
		
		if tt in {"sq_tpl", "dq_tpl"}:
			self.push_state()
		elif val == "{":
			self.braces[-1] += 1
		elif val == "}":
			self.braces[-1] -= 1
		
		return Token(self, match, tt, self.repos(m))
	