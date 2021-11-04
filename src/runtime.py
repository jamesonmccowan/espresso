#!/usr/bin/env python3

class EspNoneType:
	def __getattr__(self, name):
		return self
	
	def __str__(self):
		return "none"
	__repr__ = __str__
	
	# Remove this when we stop making this mistake
	def visit(self, v):
		raise RuntimeError("none.visit()")
	
	def __add__(self, other):
		if not isinstance(other, str):
			return other
	__radd__ = __add__
	
	def __sub__(self, other):
		return -other
	
	def __rsub__(self, other):
		return other

EspNone = EspNoneType()

class EspString(str):
	def __init__(self, value):
		self.value = value
	
	def __add__(self, other):
		return EspString(str(self) + str(other))
	
	def __radd__(self, other):
		return EspString(str(other) + str(self))
	
	@property
	def length(self):
		return len(self)

class EspProto(type):
	def __new__(cls, name, bases, ns):
		slots = []
		for b in bases:
			if hasattr(b, "__slots__"):
				slots += b.__slots__
		slots += ns["public"]
		slots += ns["private"]
		
		return super().__new__(cls, name, bases, {
			"__slots__": slots,
			**{x:None for x in ns["static"]}
		})

class EspDict(dict):
	def __getattr__(self, name):
		return EspNone
	
	def __getitem__(self, name):
		return getattr(self, name)
	
	def __setitem__(self, name, value):
		setattr(self, name, value)

class EspList(list):
	@property
	def length(self):
		return len(self)
	
	def __getattr__(self, name):
		return EspNone
	
	def __getitem__(self, x):
		if type(x) is int:
			if x > len(self):
				return EspNone
			return super().__getitem__(x)
		return getattr(self, x)
	
	def push(self, x):
		self.append(x)
	
	def push_front(self, x):
		self.insert(0, x)
	
	def pop_front(self):
		x = self[0]
		del self[0]
		return x
	
	def __add__(self, other):
		return EspList(super().__add__(other))
	
	def __iadd__(self, other):
		return EspList(super().__iadd__(other))
	
	def __mul__(self, other):
		return EspList(super().__mul__(other))
	
	def __rmul__(self, other):
		return EspList(super().__rmul__(other))

"""
'__add__', '__class__', '__contains__', '__delattr__', '__delitem__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__', '__getitem__', '__gt__', '__hash__', '__iadd__', '__imul__', '__init__', '__init_subclass__', '__iter__', '__le__', '__len__', '__lt__', '__mul__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__reversed__', '__rmul__', '__setattr__', '__setitem__', '__sizeof__', '__str__', '__subclasshook__', 'append', 'clear', 'copy', 'count', 'extend', 'index', 'insert', 'pop', 'remove', 'reverse', 'sort'"""