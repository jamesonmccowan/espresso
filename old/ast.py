from dataclasses import dataclass, astuple, field, fields
from re import A
from typing import Any, GenericAlias

class Token: ...

OPS = {}

def decode(ast):
	op, *args = ast
	if op in OPS:
		return OPS[op](args)
	return Op(op, args)

@dataclass(kw_only=True)
class AST:
	op: str = None
	
	def __init_subclass__(cls):
		super().__init_subclass__()
		if type(cls) != field:
			OPS[cls.op] = cls
	
	def origin(self, tok):
		return Meta(self, tok)
	
	def to_json(self):
		sexp = astuple(self)
		out = [sexp[0]]
		for i, field in enumerate(fields(self)):
			sx = sexp[i + 1]
			if sx is None:
				out.append(None)
			
			elif isinstance(field, GenericAlias):
				if field.__origin__ == list:
					out.append([*map(AST.to_json, sx)])
				else:
					raise NotImplementedError("AST type " + field.__name__)
			else:
				out.append(sx)
		
		return out
	
	def is_func(self): return False

@dataclass
class Meta(AST):
	op = "line"
	origin: Token
	target: AST
	
	def __getattr__(self, name):
		return getattr(self.target, name)
	
	def is_func(self): return self.value.is_func()

@dataclass
class Block(AST):
	op = "block"
	elems: list[AST]

@dataclass
class Prog(AST):
	op = "progn"
	elems = list[AST]

@dataclass
class Const(AST):
	op = "const"
	value: Any

@dataclass
class Ident(AST):
	op = "id"
	name: str

@dataclass
class Decl(AST):
	op = "decl"
	name: str
	value: AST | None = None

@dataclass
class Var(AST):
	op = "var"
	vars: list[Decl]

@dataclass
class Tuple(AST):
	op = "tuple"
	elems: list[AST]

@dataclass
class List(AST):
	op = "list"
	elems: list[AST]

@dataclass
class ObjectEntry(AST):
	op = ":"
	key: AST
	value: AST

@dataclass
class Object(AST):
	op = "object"
	elems: list[ObjectEntry]

@dataclass
class Call(AST):
	op = "call"
	fn: AST
	args: list[AST]

@dataclass(init=False)
class Op(AST):
	op: str = field(kw_only=False)
	args: list[AST]
	
	def __init__(self, op, *args):
		self.op = op
		self.args = args

@dataclass
class Try(AST):
	op = "try"
	body: AST
	error: AST | None = None
	handler: AST | None = None
	th: AST | None = None
	el: AST | None = None
	fin: AST | None = None

@dataclass
class If(AST):
	op = "if"
	cond: AST
	th: AST
	el: AST | None = None

@dataclass
class Loop(AST):
	op = "loop"
	always: AST | None = None
	cond: AST | None = None
	body: AST | None = None
	th: AST | None = None
	el: AST | None = None

@dataclass
class ForLoop(AST):
	op = "for"
	var: AST
	iter: AST
	body: AST
	th: AST | None = None
	el: AST | None = None

@dataclass
class Case(AST):
	op = "case"
	value: AST | None
	ft: bool
	body: AST

@dataclass
class Switch(AST):
	op = "switch"
	cond: AST
	cases: list[Case]
	th: AST | None = None
	el: AST | None = None

@dataclass
class Function(AST):
	op = "fn"
	name: AST | None
	args: list[AST]
	body: AST
	
	def is_func(self): return True

@dataclass
class Proto(AST):
	op = "proto"
	name: AST | None
	parent: AST | None
	fields: Object