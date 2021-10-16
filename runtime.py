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
		return EspString(super() + str(other))
	
	def __radd__(self, other):
		return EspString(str(other) + super())
