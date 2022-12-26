#!/usr/bin/python3.10

tpl = '''
import re, lex
TOKEN = re.compile(r{token_re!r})
class Parser(lex.Lexer):
	def __init__(self, src):
		super(src)
		self.token_re = TOKEN
		self.patterns = {patterns!r}
		self.targets = []
	
	def expr(self, min_prec=0):
		"""
		Uses precedence climbing
		"""
		
		lhs = self.atom()
		
		while self.cur:
			cur = self.cur
'''

class _CodeGen:
	def __init__(self):
		self.ast_types = []
		self.processing = {}
	
	def body(precs, tokens, rules):
		yield tpl.format({
			"token_re": ')|('.join(tokens.values()),
			"patterns": list(tokens.keys())
		})
	
	def head(self):
		'''Only run after body so ast_types is populated'''
		
		for at in self.ast_types:
			yield f"{at.name} = make_dataclass({at.name!r}, {at.fields!r})"

def grammar(precedences, tokens, rules):
	gen = _CodeGen()
	
	code = '\n'.join(gen.body(precedences, tokens, rules))
	code = '\n'.join(gen.head()) + '\n' + code
	
	return exec(code, {
		"_processing": gen.processing
	})

def _build_grammar(*rules):
	'''Decode syntax sugar into their corresponding rule types'''
	
	for rule in rules:
		if isinstance(rule, str):
			yield rule
		elif isinstance(rule, list):
			yield optional(*rule)
		elif isinstance(rule, set):
			yield union(*rule)
		else:
			yield rule

def _grammar_union(l, r):
	lu = isinstance(l, union)
	ru = isinstance(r, union)
	
	if lu or ru:
		rules = []
		if lu: rules += l.rules
		if ru: rules += r.rules
	else:
		rules = [l, r]
	
	return union(*rules)

class _grammar_rule:
	'''
	Base class for all grammar rules which includes syntax sugar
	'''
	
	def __rlshift__(self, other):
		assert type(other) == str
		
		return field(other, self)
	
	def __iter__(self):
		yield spread(self)
	
	def __or__(self, other):
		return _grammar_union(self, other)
	
	def __ror__(self, other):
		return _grammar_union(other, self)
	
	def visit(self, visitor):
		return getattr(visitor, f"visit_{type(self).__name__}")(self)

class Visitor:
	def visit_atom(self, v): pass
	def visit_spread(self, v): pass
	def visit_field(self, v): pass
	def visit_seq(self, v): pass
	def visit_rule(self, v): pass
	def visit_union(self, v): pass
	def visit_optional(self, v): pass

class FieldFinder(Visitor):
	def __init__(self, gen):
		super()
		
		self.gen = gen
	
	def visit_spread(self, v):
		if isinstance(v.rule, atom):
			for r in v.rule.rules:
				r.visit(v)
	
	def visit_field(self, v):
		self.fields.append(v.name)
	
	def visit_seq(self, v):
		for r in v.rules:
			

class AtomBuilder(Visitor):
	def __init__(self, gen):
		super()
		
		self.gen = gen
	
	def visit_atom(self, v):
		self.atoms[v.name] = type(v.name, (Expr,), {
			"__slots__": FieldFinder().visit(v)
		})
		return super().visit_atom(v)

class atom(_grammar_rule):
	def __init__(self, *rules):
		super()
		
		self.rules = list(_build_grammar(rules))
		self.fields = [f for r in self.rules for f in r.fields()]
	
	def __call__(self, gen):
		yield f"self.targets.append({gen.current_rule}())"
		
		for rule in self.rules:
			yield rule(gen)
		
		yield "self.targets.pop()"

class process(_grammar_rule):
	def __init__(self, rules, processing):
		self.rules = _grammar_rule(rules)
		self.processing = processing
	
	def __call__(self, gen):
		gen.processing[id(self.processing)] = self.processing
		for rule in self.rules:
			yield f"_processing[{id(self.processing)}](rule(gen))"

class spread(_grammar_rule):
	'''
	Use the results of the subparser for the outer parser
	'''
	
	def __init__(self, subparser):
		self.subparser = subparser
	
	def __call__(self, gen):
		yield self.subparser(gen)

class field(_grammar_rule):
	'''
	Define and assign a the results of a rule to a field
	'''
	
	def __init__(self, name, value):
		super()
		
		self.name = name
		self.value = value
	
	def __call__(self, gen):
		gen.add_field(self.name)
		
		yield f"self.targets[-1].{self.name} = {self.value(gen)}"

class seq(_grammar_rule):
	'''
	A sequence of rules
	'''
	
	def __init__(self, *rules):
		super()
		
		self.rules = list(_build_grammar(rules))
	
	def __call__(self, gen):
		for rule in self.rules:
			yield rule(gen)

class rule(_grammar_rule):
	'''
	Reference another rule as a subparser
	'''
	
	def __init__(self, name):
		super()
		
		self.name = name
	
	def __call__(self, gen):
		yield f"self.{self.name}"

class rule_union(_grammar_rule):
	'''
	Try each named rule until one works
	'''
	
	def __init__(self, *names):
		super()
		
		self.names = names
	
	def __call__(self, gen):
		for rule in self.names:
			yield f"self.{rule}()"

class union(_grammar_rule):
	'''
	Try each rule until one works
	'''
	
	def __init__(self, *rules):
		super()
		
		self.rules = list(_build_grammar(rules))
	
	def __call__(self, gen):
		for rule in self.rules:
			yield rule(gen)

class optional(_grammar_rule):
	'''
	Try the rule, but don't care if it doesn't match
	'''
	
	def __init__(self, *rules):
		super()
		
		self.rules = list(_build_grammar(rules))
	
	def __call__(self, gen):
		for rule in self.rules:
			if type(rule) == str:
				yield f"self.maybe({rule!r})"
			else:
				yield rule(gen)