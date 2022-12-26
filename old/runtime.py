#!/usr/bin/env python3

class proto_none:
	def __getattr__(self, name):
		return self
	
	def __setattr__(self, name, value):
		raise AttributeError(f"Setting property {name!r} of none")
	
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
	
	def __sub__(self, other): return -other
	def __rsub__(self, other): return other
	
	def __bool__(self): return False
	
	def __eq__(self, other): return 0 == other
	def __ne__(self, other): return 0 != other
	def __lt__(self, other): return 0 < other
	def __le__(self, other): return 0 <= other
	def __gt__(self, other): return 0 > other
	def __ge__(self, other): return 0 >= other

esp_none = proto_none()

class proto_string(str):
	def __new__(cls, value):
		return super().__new__(cls, value)
	
	def __repr__(self):
		return f"EspString({super().__repr__()})"
	
	def __add__(self, other):
		return proto_string(str(self) + str(other))
	
	def __radd__(self, other):
		return proto_string(str(other) + str(self))
	
	@property
	def length(self):
		return len(self)

class proto(type):
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
		return esp_none
	
	def __getitem__(self, name):
		return getattr(self, name)
	
	def __setitem__(self, name, value):
		setattr(self, name, value)

class EspList(list):
	@property
	def length(self):
		return len(self)
	
	def __getattr__(self, name):
		return esp_none
	
	def __getitem__(self, x):
		if type(x) is int:
			if x > len(self):
				return esp_none
			return super().__getitem__(x)
		return getattr(self, x)
	
	def push(self, x):
		self.append(x)
	
	def push_front(self, x):
		self.insert(0, x)
	
	def pop_front(self, x = 0):
		v = self[x]
		del self[x]
		return v
	
	def __add__(self, other):
		return EspList(super().__add__(other))
	
	def __iadd__(self, other):
		return EspList(super().__iadd__(other))
	
	def __mul__(self, other):
		return EspList(super().__mul__(other))
	
	def __rmul__(self, other):
		return EspList(super().__rmul__(other))

class EspIterator:
	'''Implements using loops as generator expressions'''
	
	def __init__(self, iter):
		self.iter = iter
	
	def __iter__(self):
		return self.iter
	
	def __call__(self):
		return next(self.iter)

class EspFunction:
	'''Implements espresso functions'''
	
	def __init__(self, code):
		self.code = code