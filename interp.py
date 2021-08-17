import re

TOKEN = re.compile(r'''
(?P<space>\s+)|
(?P<comment>\#.*$|\#\*.*\*\#)|
(?P<punc>[-+*/%<>!?=~^&|]{1,2}=?|[!=]==|[-=<]>|[()\[\]{}])|
(?P<word>\w[\w\d]*)|
'(?P<sq>(?:\\.|[^']+)*)'|"(?P<dq>(?:\\.|[^"]+)*)"|
(?P<dec>\d+)
''', re.X|re.I|re.M)

class Op:
	def __init__(self, prec, func, right=False):
		self.prec = prec
		self.func = func
		self.right = right

UNARYOPS = {"+", "-", "++", "--", "~", "!", "@"}
BINARYOPS = {
	"+": Op(0, lambda x, y: x + y),
	"-": Op(0, lambda x, y: x - y),
	"*": Op(1, lambda x, y: x * y),
	"/": Op(1, lambda x, y: x / y),
	"%": Op(1, lambda x, y: x % y),
	"//": Op(1, lambda x, y: x // y),
	"<<": Op(3, lambda x, y: x << y),
	">>": Op(3, lambda x, y: x >> y),
	""
}

class Token:
	def __init__(self, m, line, col):
		self.m = m
		self.line = line
		self.col = col
		
		tt = m.lastgroup
		
		if tt in {"sq", "dq"}:
			self.type = "value"
			self.value = m[tt]
		elif tt == "dec":
			self.type = "value"
			self.value = int(m[tt])
		elif tt in {"word", "punc"}:
			self.type = tt
			self.value = m[tt]
		else:
			self.type = None
			self.value = None

class ASTValue:
	def __init__(self, value):
		self.value = value

class ASTList:
	def __init__(self, value):
		self.value = value

class ASTOp:
	def __init__(self, op, children):
		self.op = op
		self.children = children

def tokenstream(src):
	line = col = 1
	for tok in TOKEN.finditer(src):
		lines = tok[0].split('\n')
		if len(lines) > 1:
			line += len(lines)
			col = len(lines[-1])
		
		tok = Token(tok, line, col)
		if tok.type is not None: # Automatically skip space and comments
			yield tok

class Scanner:
	def __init__(self, src):
		self.stream = tokenstream(src)
		self.cur = next(self.stream)
	
	def next(self):
		self.cur = next(self.stream)
		return self.cur
	
	def maybe(self, s):
		if self.cur.value == s:
			self.next()
			return True
		return False
	
	def atom(self):
		if self.cur.type == "value":
			return ASTValue(self.cur.value)
		elif self.cur.type == "punc":
			if self.maybe("("):
				# Assumption: Don't need empty tuples
				val = self.expr()
				self.expect(")")
				return val
			elif self.maybe("["):
				val = []
				while True:
					if self.maybe("]"): break
					val.append(self.expr())
					if not self.maybe(","):
						self.expect("]")
						break
				return ASTList(val)
			elif self.cur.value in UNARYOPS:
				return ASTOp(self.cur.value, [self.atom()])
			else:
				raise SyntaxError(f"Unexpected {self.cur.value}")
		elif self.cur.type == "word":
			pass
	
	def expr(self, prec=0):
		lhs = self.atom()
		
		while True:
			if self.cur.value not in BINARYOPS: break
			bp, ra = BINARYOPS[self.cur.value]
			if not (bp > prec or ra and bp == prec): break
			rhs = self.expr(prec + 1)
		lhs = ASTOp(op, [lhs, rhs])