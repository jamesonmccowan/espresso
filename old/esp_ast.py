#!/usr/bin/env python3

from functools import singledispatchmethod
from runtime import EspNone, EspList, EspString, EspDict
import re
from dataclasses import dataclass, field, astuple
from typing import Any, Union, List, Tuple

from lex import Token

def join(sep, v):
	'''Espresso-like string join'''
	return sep.join(str(x) for x in v if x is not None)

SOL = re.compile(r"^", flags=re.M)
def indent(x, by=1):
	return re.sub(SOL, '  '*by, x)

@dataclass
class Expr:
	'''
	Base class for all nodes, because everything is an expression anyway
	'''
	lvalue: bool = field(init=False, repr=False, default=True)
	rvalue: bool = field(init=False, repr=False, default=True)
	statement: bool = field(init=False, repr=False, default=False)

@dataclass
class Literal(Expr):
	value: Any

class TupleLiteral(Literal): pass
class ListLiteral(Literal): pass
class ObjectLiteral(Literal): pass

@dataclass
class Op(Expr):
	op: str
	elems: List[Expr]

class Unary(Op): pass
class Binary(Op): pass
class Assign(Op): pass
class Call(Op): pass
class Index(Op): pass

@dataclass
class Ident(Expr):
	name: str

@dataclass
class Block(Expr):
	statements: List[Expr]

class Prog(Block): pass

@dataclass
class Arg(Expr):
	name: Expr
	value: Expr

@dataclass
class Func(Expr):
	name: Expr
	args: List[Arg]
	body: List[Expr]

@dataclass
class Case(Expr):
	value: Expr
	body: Expr
	fallthrough: bool

@dataclass
class Switch(Expr):
	cond: Expr
	cases: List[Case]

@dataclass
class If(Expr):
	cond: Expr
	th: Expr
	el: Union[Expr, None] = None

@dataclass
class Branch(Expr):
	kind: str

@dataclass
class Import(Expr):
	name: str

@dataclass
class Loop(Expr):
	always: Expr
	cond: Union[Expr, None] = None
	body: Union[Expr, None] = None

@dataclass
class ForLoop(Expr):
	itvar: Union[Expr, None]
	iter: Expr
	body: Expr

class PairMap:
	def __init__(self):
		self.map = []
	
	def __setitem__(self, key, val):
		self.map.append((key, val))
	
	def __getitem__(self, key):
		for k, v in self.map:
			if k == key:
				return v
		
		raise KeyError()
	
	def __iter__(self):
		return iter(self.map)

class MetaVisitor(type):
	def __prepare__(name, bases, **kw):
		return PairMap()
	
	def __new__(cls, name, bases, dct):
		body = {}
		for key, val in dct:
			if key == "visit":
				a = tuple(val.__annotations__.values())
				if len(a) > 0:
					if isinstance(a[0], type):
						val.__qualname__ += f":{a[0].__name__}"
					else:
						val.__qualname__ += f":{a[0]}"
				
				if key in body:
					body[key].register(val)
				else:
					body[key] = singledispatchmethod(val)
			else:
				body[key] = val
		return super().__new__(cls, name, bases, body)

class Visitor(metaclass=MetaVisitor): pass
