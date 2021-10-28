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

EspNone = EspNoneType()

class EspString(str):
	def __init__(self, value):
		self.value = value
	
	def __add__(self, other):
		return EspString(str(self) + str(other))
	
	def __radd__(self, other):
		return EspString(str(other) + str(self))

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