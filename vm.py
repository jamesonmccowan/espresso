import re

SOL = re.compile("^", re.M)
def indent(s, n=1):
	return SOL.sub('  '*n, s)

def color(x, c):
	def ansi(c):
		COLORS = {
			"red": 31,
			"blue": 94,
			"yellow": 93,
			"purple": 35,
			"underline": 4,
			"bold": 1,
			"reset": 0
		}
		
		if type(c) is str:
			c = [c]
		
		return f"\x1b[{';'.join(str(COLORS[x]) for x in c)}m"
	
	if c is None: return x
	return f"{ansi(c)}{x}{ansi('reset')}"

UNDEFINED = object()
class Sexp:
	def __init__(self, op, *elems, nl=None, color=None, outer=UNDEFINED):
		self.op = op
		self.elems = elems
		self.nl = nl
		self.color = color
		
		OPEN = ("", "")
		if outer is UNDEFINED:
			self.outer = OPEN if op is None else "()"
		else:
			self.outer = outer or OPEN
	
	def __str__(self):
		def join(x, sep):
			return sep.join(str(e) for e in x)
		
		op = self.op and color(self.op, ["bold", "blue"]) + " " or ""
		
		elems = self.elems
		if self.nl is all:
			elems = join(elems, '\n')
		elif self.nl is None:
			elems = join(elems, ' ')
		else:
			elems = join((join(elems[:self.nl - 1], ' '),) + elems[self.nl - 1:], '\n  ')
		
		elems = color(elems, self.color)
		
		return f"{self.outer[0]}{op}{elems}{self.outer[1]}"

def format_sexp(ast):
	match ast:
		case ['line', _, value]: return format_sexp(value)
		case ['const', int(value)]: return Sexp(None, value, color="yellow")
		case ['const', str(value)]: return Sexp(None, value, color="underline")
		case ['id', name]: return Sexp(None, name, color="purple")
		case ['list', *rest]: return Sexp(None, *map(format_sexp, elems), nl=1, outer="[]")
		case ['progn'|'block', *elems]: return Sexp(None, *map(format_sexp, elems), nl=1, outer="{}")
		
		case ['if', *rest]: return Sexp("if", *map(format_sexp, rest), nl=2)
		case ["loop", *rest]: return Sexp("loop", *map(format_sexp, rest), nl=all)
		case ['for', *rest]: return Sexp("for", *map(format_sexp, rest), nl=3)
		
		case ["object", *entries]:
			return Sexp('object', *(Sexp(None, *map(format_sexp, pair), outer="()") for pair in entries))
		
		case [str(op), *rest]: return Sexp(op, *rest)
		case _: return Sexp(repr(ast), outer=None)

def sexp(ast):
	'''Convert sexp ast to an actually readable string'''
	if ast is None:
		return "@"
	
	return str(format_sexp(ast))

def summary(ast):
	s = sexp(ast)
	if len(s) < 100:
		return s
	return s[:100] + "..."

###############
### Runtime ###
###############

def py2esp(value):
	match value:
		case None: return None
		case str(value): return EspString(value)
		case list(value): return EspList(map(py2esp, value))
		case dict(value):
			return EspObject((py2esp(k), py2esp(v)) for k, v in value)
		
		case _: return value

def esp2py(value):
	match value:
		case None: return None
		case EspString(value): return str(value)
		case EspList(value): return list(value)
		case EspObject(value):
			return dict((esp2py(k), esp2py(v)) for k, v in value)
		
		case _: return value

class EspString(str):
	def __add__(self, other):
		return EspString(str(self) + str(other))
	
	def __radd__(self, other):
		return EspString(str(other) + str(self))
	
	@property
	def length(self): return len(self)

class EspTuple(tuple):
	@property
	def length(self): return len(self)

class EspList(list):
	@property
	def length(self): return len(self)
	
	def __getattr__(self, name): return None
	def __getitem__(self, x):
		try:
			return list.__getitem__(self, x)
		except KeyError:
			pass
		
		if type(x) is int:
			if x <= len(self):
				return list.__getitem__(self, x)
		elif isinstance(x, str) and hasattr(self, x):
			return getattr(self, x)
	
	def push(self, x):
		self.append(x)
	
	def push_front(self, x):
		self.insert(0, x)
	
	def pop_front(self, x = 0):
		v = self[x]
		del self[x]
		return v
	
	def join(self, sep):
		return sep.join(self)
	
	def __add__(self, other):
		return EspList(super().__add__(other))
	def __iadd__(self, other):
		return EspList(super().__iadd__(other))
	
	def __mul__(self, other):
		return EspList(super().__mul__(other))
	def __rmul__(self, other):
		return EspList(super().__rmul__(other))

class EspObject(dict):
	def __getattr__(self, name): return dict.get(self, name, None)
	def __setattr__(self, name, value): dict.__setitem__(self, name, value)
	def __getitem__(self, name):
		if name in self:
			return dict.__getitem__(self, name)
		if isinstance(name, str) and hasattr(self, name):
			return getattr(self, name)
	
	def keys(self): return EspList(super().keys())
	def values(self): return EspList(super().values())

class EspError(RuntimeError):
	def __init__(self, vm, msg):
		def it_names(vm):
			yield "global"
			for sf in vm.stack[1:]:
				fn = sf.fn
				yield fn and fn.name or "?"
		
		def it_origins(vm):
			for sf in vm.stack[1:]:
				yield sf.origin
			
			if vm.origins:
				for op, origin in reversed(vm.origins):
					if origin: break
				yield origin
		
		def it_scopes(vm):
			it = iter(vm.stack)
			yield next(it).scope
			for sf in it:
				yield sf.scope[2:]
		
		names = it_names(vm)
		origins = it_origins(vm)
		scopes = it_scopes(vm)
		
		fn = []
		for name, origin, scope in zip(names, origins, scopes):
			if origin:
				ln, co = origin
				origin = f"line {ln}"
			else:
				origin = "?"
			fn.append(f"{name} ({origin}): {scope_vars(scope)}")
		
		out = "stack [\n  " + ",\n  ".join(fn) + "\n]"
		
		super().__init__(f"{msg}\nTraceback\n" + indent(out))

class EspFunc:
	def __init__(self, name, args, body, scope):
		self.name = name
		self.args = args
		self.body = body
		self.scope = scope

class EspGenerator:
	def __init__(self, vm, gen):
		self.vm = vm
		self.stack = vm.stack
		self.iter = iter(gen)
	
	def __iter__(self): return self
	
	def __next__(self):
		stack = self.vm.stack
		self.vm.stack = self.stack
		
		x = next(self.iter)
		
		self.vm.stack = stack
		
		return x

class LVAttr:
	def __init__(self, lhs, rhs):
		self.lhs = lhs
		self.rhs = rhs
	
	def __str__(self):
		lhs = str(self.lhs)
		if len(lhs) > 30:
			lhs = lhs[:30] + "..."
		return f"LVAttr({lhs}, {self.rhs})"
	
	def get(self):
		return py2esp(getattr(self.lhs, self.rhs))
	
	def set(self, value):
		return setattr(self.lhs, self.rhs, value)

class LVIndex:
	def __init__(self, lhs, rhs):
		self.lhs = lhs
		self.rhs = rhs
	
	def __str__(self):
		lhs = str(self.lhs)
		if len(lhs) > 30:
			lhs = lhs[:30] + "..."
		return f"LVIndex({lhs}, {self.rhs})"
	
	def get(self):
		return py2esp(self.lhs[self.rhs])
	
	def set(self, value):
		self.lhs[self.rhs] = value

def scope_vars(scope):
	frames = []
	for frame in scope:
		frames.append(f"{{{', '.join(frame.keys())}}}")
	return f"[{', '.join(frames)}]"

class StackFrame:
	def __init__(self, fn, origin, scope):
		self.fn = fn
		self.origin = origin
		self.scope = scope
	
	def __str__(self):
		name = None if self.fn is None else self.fn.name
		return f"StackFrame({name}, {self.origin}, {scope_vars(self.scope)}"
	__repr__ = __str__

class Context:
	def __init__(self, stack, elem):
		self.stack = stack
		self.elem = elem
	
	def __enter__(self):
		self.stack.append(self.elem)
	
	def __exit__(self, et, err, tb):
		ob = self.stack.pop()
		assert ob is self.elem

class Signal(BaseException): pass

class BreakSignal(Signal): pass
class ContinueSignal(Signal): pass
class ReturnSignal(Signal):
	def __init__(self, value):
		super().__init__()
		self.value = value

class FailSignal(Signal):
	def __init__(self, value):
		super().__init__()
		self.value = value

class VM:
	def __init__(self, scope):
		self.origins = []
		self.stack = [StackFrame(None, None, [scope])]
		self.errlvl = 0
	
	def scope(self):
		return Context(self.stack[-1].scope, {})
	
	def print_stack(self):
		print(str(EspError(self, "print_stack")))
	
	def resolve(self, name):
		for scope in reversed(self.stack[-1].scope):
			if name in scope:
				return scope
		
		return self.stack[-1].scope[-1]
	
	def call(self, fn, this, args):
		if fn is None:
			raise ValueError("Calling none")
		
		if callable(fn):
			return py2esp(fn(*map(esp2py, args)))
		
		espargs = {"this": this}
		for a, arg in enumerate(args):
			if a < len(fn.args):
				espargs[fn.args[a]['name']] = arg
			else:
				print(f"Discarding extra parameter {a} = {arg}")
		
		for a in range(len(args), len(fn.args)):
			espargs[fn.args[a]['name']] = None
		
		scope = fn.scope.copy()
		scope.append(espargs)
		
		try:
			with Context(self.stack, StackFrame(fn, self.origins[-1][1], scope)):
				result = self.rval(fn.body)
		except ReturnSignal as r:
			result = r.value
		
		return result
	
	def unary(self, op, val):
		val = self.rval(val)
		match op:
			case "+": return +val
			case "-": return -val
			case "~": return ~val
			case "!": return not val
			case "not": return not val
			
			case _: raise NotImplementedError(f"unary op {op}")
	
	def binary(self, op, lhs, rhs):
		if op == "=":
			lhs = self.lval(lhs)
			rhs = self.rval(rhs)
			
			if isinstance(rhs, EspFunc):
				rhs.name = lhs.lhs
			
			lhs.set(rhs)
			return rhs
		
		lhs = self.rval(lhs)
		rhs = self.rval(rhs)
		match op:
			case "+": return lhs + rhs
			case "-": return lhs - rhs
			case "*": return lhs * rhs
			case "/": return lhs / rhs
			case "%": return lhs % rhs
			case "**": return lhs ** rhs
			case "//": return lhs // rhs
			
			case "===": return lhs is rhs
			case "!==": return lhs is not rhs
			case "==": return lhs == rhs
			case "!=": return lhs != rhs
			case "<": return lhs < rhs
			case "<=": return lhs <= rhs
			case ">": return lhs > rhs
			case ">=": return lhs >= rhs
			
			case "&": return lhs & rhs
			case "|": return lhs | rhs
			case "^": return lhs ^ rhs
			case "<<": return lhs << rhs
			case ">>": return lhs >> rhs
			
			case "is":
				if lhs is rhs: return True
				return isinstance(lhs, rhs)
			
			case "in": return lhs in rhs
			case "has": return hasattr(lhs, rhs)
			
			case ":=":
				lhs.update(rhs)
				return lhs
			
			case _: raise NotImplementedError(f"binary op {op}")
	
	def loop(self, ast):
		always, cond, body, th, el, *_ = ast + [None]*4
		
		while True:
			try:
				result = self.rval(always)
				if isinstance(result, EspGenerator):
					for _ in result: pass
					result = None
				
				if cond:
					if self.rval(cond):
						result = self.rval(body)
						if isinstance(result, EspGenerator):
							for _ in result: pass
							result = None
					
					else:
						self.rval(th)
						break
				
				if result is not None:
					yield result
			except BreakSignal:
				self.rval(el)
				break
			except ContinueSignal:
				continue
	
	def forloop(self, ast):
		var, it, body, th, el, *_ = ast + [None]*2
		
		var = self.lval(var)
		it = iter(self.rval(it))
		
		while True:
			try:
				var.set(next(it))
				yield self.rval(body)
			except StopIteration:
				self.rval(th)
			except BreakSignal:
				self.rval(el)
			except ContinueSignal:
				continue
			break
	
	def lval(self, ast):
		match ast:
			case ['id', name]:
				return LVIndex(self.resolve(name), name)
			
			case ['.', lhs, rhs]:
				lhs = self.rval(lhs)
				rhs = self.rval(rhs)
				return LVAttr(lhs, rhs)
			
			case ['[]', lhs, rhs]:
				lhs = self.rval(lhs)
				rhs = self.rval(rhs)
				return LVIndex(lhs, rhs)
			
			case _: raise EspError(self, f"Not an lvalue: {sexp(ast)}")
	
	def rval(self, ast):
		if ast is None: return
		
		try:
			result = None
			match ast:
				case ['line', line, op]:
					with Context(self.origins, [op[0], line]):
						result = self.rval(op)
				
				case ['var', vars]:
					for name, value in vars:
						match name:
							case ['id', name]:
								if value is None:
									result = None
								else:
									result = self.rval(value)
								self.stack[-1].scope[-1][name] = result
							
							case _:
								raise NotImplementedError(f"var {name}")
				
				case ['const', value]: result = py2esp(value)
				case ['id'|'.'|'[]', *_]: result = self.lval(ast).get()
				
				case ['break']: raise BreakSignal()
				case ['continue']: raise ContinueSignal()
				case ['fail', value]:
					raise FailSignal(EspError(self, self.rval(value)))
				case ['return', value]:
					raise ReturnSignal(self.rval(value))
				
				case ['prog', body]: result = self.rval(body)
				
				case ['block', body]:
					with self.scope():
						for stmt in body:
							tmp = self.rval(stmt)
							if isinstance(tmp, EspGenerator):
								for _ in tmp: pass
								result = None
							else:
								result = tmp
				
				case ['cond', cs, th, el]:
					with self.scope():
						cond = self.rval(cond)
						
						i = 0
						de = None
						ft = False
						try:
							while True:
								op, value, fts, body = cs
								
								if ft or op == "case" and self.rval(value) == cond:
									result = self.rval(body)
									ft = (fts == ":")
									if not ft: break
								else:
									de = i
								
								i += 1
								
								# Fell off the end
								if i >= len(cs):
									# Without default
									if ft or de is None:
										break
									i = de
									ft = True
							self.rval(th)
						except BreakSignal:
							self.rval(el)
							pass
				
				case ['loop', *_]:
					result = EspGenerator(self, self.loop(ast))
				
				case ['for', *_]:
					result = EspGenerator(self, self.forloop(ast))
				
				case ['try', body, err, handler, th, el, fin]:
					with self.scope():
						try:
							result = self.rval(body)
						except EspError as e:
							self.lval(err).set(e.value)
							result = self.rval(handler)
							result = self.rval(el)
						else:
							result = self.rval(th)
						finally:
							result = self.rval(fin)
				
				case ['tuple', *elems]:
					result = EspTuple(self.rval(e) for e in elems)
				
				case ['list', *elems]:
					result = EspList(self.rval(e) for e in elems)
				
				case ['object', *elems]: ###TODO: Object -> ObjectEntry
					result = EspObject((self.rval(k), self.rval(v)) for k, v in elems)
				
				case ['fn', ['const', name], args, body]:
					result = EspFunc(name, args, body, self.stack[-1].scope.copy())
				
				case ['call', ['.'|'[]', this, fn], args]:
					this = self.rval(this)
					fn = self.rval(fn)
					if ast[1][0] == ".":
						fn = getattr(this, fn)
					else:
						fn = this[fn]
					result = self.call(fn, this, list(map(self.rval, args)))
				
				case ['call', fn, args]:
					fn = self.rval(fn)
					result = self.call(fn, None, list(map(self.rval, args)))
				
				case ['if', cond, th, el]:
					with self.scope():
						if self.rval(cond):
							result = self.rval(th)
						else:
							result = self.rval(el)
				
				case ["and"|"&&", lhs, rhs]:
					result = self.rval(lhs) and self.rval(rhs)
				case ["or"|"||", lhs, rhs]:
					result = self.rval(lhs) or self.rval(rhs)
				case ["after", lhs, rhs]:
					result = self.rval(lhs)
					self.rval(rhs)
				
				case [op, [value]]: result = self.unary(op, value)
				case [op, [lhs, rhs]]: result = self.binary(op, lhs, rhs)
				
				case _: raise NotImplementedError(summary(ast))
			
			return result
		except Exception:
			if self.errlvl == 0:
				self.print_stack()
			
			if self.errlvl < 3:
				print("Error from", summary(ast))
				self.errlvl += 1
				
			raise
	
	def eval(self, expr):
		try:
			result = self.rval(expr)
		except FailSignal as sig:
			print("Error:", sig.value)
			result = None
		
		return result
	
def strip_lines(ast):
	if type(ast) is list:
		if ast[0] == "line":
			return strip_lines(ast[2])
		else:
			return list(map(strip_lines, ast))
	return ast

def main():
	import sys, os, json, crema, argparse
	
	ap = argparse.ArgumentParser("espresso")
	ap.add_argument("-f", "--file", nargs=2, metavar=('src', 'ast'))
	ap.add_argument("-c", "--cmd", nargs=1, metavar='cmd')
	ap.add_argument("-s", "--sexp", action="store_true")
	argv = ap.parse_args()
	
	if argv.sexp:
		print(sexp(json.loads(sys.argv[2])))
		return
	
	if argv.cmd:
		ast = crema.Parser(argv.cmd[0]).parse()
		
		print(sexp(ast.to_json()))
		return
	
	if not all(argv.file):
		ap.print_usage()
		return
	
	def mtime(fn):
		try:
			return os.path.getmtime(fn)
		except FileNotFoundError:
			return float('inf')
	
	def reparse(srcfn, astfn):
		with open(srcfn, "r") as f:
			print("Reparsing...")
			ast = crema.Parser(f.read()).parse()
		
		ast = ast.to_json()
		
		print("Saving to", astfn)
		with open(astfn, "w") as f:
			json.dump(ast, f)
		
		with open("debug.json", "w") as f:
			json.dump(strip_lines(ast), f)
		
		return ast
	
	srcfn, astfn = argv.file
	
	srcmt = mtime(srcfn)
	astmt = mtime(astfn)
	crmmt = mtime("crema.py")
	
	if srcmt <= astmt >= crmmt:
		print("Loading from", astfn)
		try:
			with open(astfn, "r") as f:
				ast = json.load(f)
		except (json.decoder.JSONDecodeError, FileNotFoundError):
			print("AST JSON corrupted")
			ast = reparse(srcfn, astfn)
	else:
		if srcmt > astmt < crmmt:
			print(f"Source changed at {srcfn} and {astfn}")
		elif srcmt > astmt:
			print(f"Source changed at {astfn}")
		else:
			print(f"Source changed at {srcfn}")
		ast = reparse(srcfn, astfn)
	
	print("Executing...")
	VM({
		"none": None,
		"true": True,
		"false": False,
		"string": EspString,
		"list": EspList,
		"import": __import__,
		"open": open,
		"print": print,
		"type": type,
		"slice": slice,
		"argv": sys.argv[3:],
		"int": int
	}).eval(ast)

if __name__ == "__main__":
	main()