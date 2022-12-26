#!/usr/bin/python3.10

def unreachable(msg=None):
	if msg:
		raise AssertionError(msg)
	raise AssertionError()

class ParseError(RuntimeError):
	def __init__(self, msg, pre, ctx):
		l = ctx.line
		c = ctx.col
		p = ctx.pos
		super().__init__(f"{msg} ({l}|{c}:{p})\n{pre}")
		
		self.context = ctx