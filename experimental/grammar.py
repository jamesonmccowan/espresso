from ruleset import grammar, rule, repeat, seq, union, rule_union, ast

def _q(name, c):
	def q(beg, end):
		end = end or beg
		return f"{beg}((?:\\.|.+?)*?){end}"
	
	def qt(name, c):
		yield f"{name}_bme", q(c, c)
		yield f"{name}_b", q(c, "\\\{")
		yield f"{name}_m", q("\\}", "\\\{")
		yield f"{name}_e", q("\\}", c)
	
	yield from qt("sq", "'")
	yield from qt("sq3", "'''")
	yield from qt("dq", '"')
	yield from qt("dq3", '"""')
	yield "bq", q('`')
	yield "bq3", q('```')

parser = grammar(
	precedences={
		
	},
	tokens = {
		# Syntax "operators" which require special parsing rules
		"punc": r"[()\[\]{}]|\.(?!\.)|\.{3}|[,;:]|[-=]>",
		"cmp": r"[!=]={1,2}|[<>!]=?|<>",
		"assign": r"(?P<d0>[~*/%&|^:])(?P=d0)?=|=",
		"op": "|".join([ # Ops can be contextual identifiers, puncs can't
			r"[@~?]", # Misc syntax
			r"[-=]>", # Arrows
			r"\.\.",
			r"(?P<d1>[-+*/%&|^:!])(?P=d1)?", # Arithmetic and logical
			r"<<[<>]|[<>]>>" # Shifts
		]),
		
		"bin": r"?:0b([_01]*[01])",
		"oct": r"?:0o([_0-7]*[0-7])",
		"hex": r"?:0x([_\da-fA-F]*[\da-fA-F])",
		"flt": r"(?:\.\d[_\d]*|\d[_\d]*\.(?!\.)(?:\d[_\d]*)?)(?:e[-+]\d[_\d]*)?",
		"dec": r"\d(?:[\d_]*\d)?",
		"sq": r"?:'((?:\\.|.+?)*?)'",
		"dq": r'?:"((?:\\.|.+?)*?)"',
		"bq": r"?:`((?:\\.|.+?)*?)`",
		"sq3": r"?:'''((?:\\.|.+?)*?)'''",
		"dq3": r'?:"""((?:\\.|.+?)*?)"""',
		"bq3": r"?:```((?:\\.|.+?)*?)```",
		"id": r"[\w_][\w\d]*",
		
		"q_mid": q("\\}", "\\\\{")
		
		"sq1": q("'"), "dq1": q('"'), "bq1": q("`"),
		"sq3": q("'''"), "dq3": q('"""'), "bq3": q("```"),
		
		"q1_beg": q("['\"]", "")
		"q1_end": q("", "['\"]")
		
		"q3_beg": q("(?:'{3}|\"{3})", "")
		"q3_end": q("", "(?:'{3}|\"{3})")
	},
	rules = {
		# Token categories
		"access": {"public", "private", "static"},
		"decl": {"var", "const"},
		"literal": token({"ident", "string", "function", "list", "object"}),
		
		"int": union(
			token("bin"), token("oct"), token("dec"), token("hex")
			process=lambda tok: int(tok.value.replace("_", ""), RADIX[tok.type])
		),
		"flt": token("flt" process=lambda tok: float(tok.value.replace("_", "")))
		"str": union(
			token("sq"), token("dq"), token("bq"), token("sq3"), token("dq3"), token("bq3"),
			process=lambda tok: tok.match[1]
		),
		
		"fmt": union(
			[token("q1_beg"), *repeat(token("q1_mid")), token("q1_end")],
			[token("q3_beg"), *repeat(token("q3_mid")), token("q3_end")],
			check=lambda toks: toks[0].value[0] == toks[-1].value[-1],
			check_fail="Mismatched template quotes"
		),
		
		# Common patterns which are reused
		"thel": [["then"], "th" << rule("block"), ["else", "el" << rule("block")]],
		
		# Operator precedence hierarchies
		"stmt": rule_union("if", "loop", "while", "expr"),
		"block": ["{", "statements" << rule("semi"), "}"],
		"arrow": [rule("assign"), ["=>", "body" << rule("block")]],
		"assign": [rule("comma"), token("assign"), rule("arrow")],
		"comma": repeat(*rule("expr"), repeat(",")),
		
		"const": atom("Const", "value" << union(
			rule("int", process=lambda tok: int(tok.value, RADIX[tok.type])),
			rule("flt", process=lambda tok: float(tok.value)),
			rule("str", process=lambda tok: tok.value)
		)),
		"semi": repeat(*rule("arrow", repeat(";"))),
		"if": atom("If", ["if", "cond" << rule("expr"), rule("thel")])
	},
	atoms = {
		# Rules which produce AST nodes
		
		"Format": seq(rule(""))
		
		"Const": seq("value" << union(
			rule("int", process=lambda tok: int(tok.value, RADIX[tok.type])),
			rule("flt", process=lambda tok: float(tok.value)),
			rule("str", process=lambda tok: process_string(tok.value))
		)),
		"Semi": repeat(... << rule("arrow"), repeat(";")),
		"If": ["if", "cond" << rule("expr"), *rule("thel")],
		"Loop": ["loop", "body" << rule("block"), rule("while") | rule("thel")],
		"While": ["while", "body" << rule("block"), *rule("thel")],
		"Case": [seq("case", "cond" << rule("expr")) | "else", {":", "=>"}, "body" << rule("block")],
		"Switch": [
			"switch", "cond" << rule("expr"), "{",
				repeat(ast("Case")),
			"}", ["else", "el" << rule("block")]
		],
		"Function": ["function", *rule("callable")],
		"List": ["[", *rule("tuple"), "]"],
		"Tuple": repeat(... << rule("expr"), repeat(",")),
		"Object": ["{", repeat(["key" << rule("relaxid"), [":", "val" << (rule("expr") | rule("callable"))]], [","]), "}"],
		"Proto": ["proto", [rule("id")], ["is", rule("expr")], "{",
			repeat(
				["access" << rule("access")], ["decl" << rule("decl")], "name" << rule("name"),
				[[":", "type" << rule("expr")], ["=", "value" << (rule("expr") | rule("callable"))]]
			),
		"}"]
	}
)

access = lambda: {"public", "private", "static"},
decl = lambda: {"var", "const"},
literal = lambda: token({"ident", "string", "function", "list", "object"})
int = lambda: token({"bin", "oct", "dec", "hex"})
flt = lambda: token("flt")
str = lambda: token({"sq", "dq", "bq", "sq3", "dq3", "bq3"})
fmt = lambda: union(
	[token("q1_beg"), repeat(token("q1_mid")), token("q1_end")],
	[token("q3_beg"), repeat(token("q3_mid")), token("q3_end")],
)

thel = lambda: ["then", block], ["else", block]
stmt = lambda: union(_if, _loop, _while, _expr)
block = lambda: union(["{", semi, "}"], expr)
arrow = lambda: assign, ["=>", block]
assign = lambda: comma, token("assign"), arrow
comma = lambda: repeat(expr, repeat(","))
const = lambda: rule({"int", "flt", "str"})
semi = lambda: repeat(arrow, repeat(";"))
_if = lambda: "if", expr, thel
loop = lambda: "loop", block, union(_while, thel)
_while = lambda: "while", expr, block, thel
_case = lambda: union(["case", expr], "else"), union(":", "=>"), block
switch = lambda: "switch", expr, "{", repeat(_case), "}", thel
function = lambda: "function", "(", repeat(name, [":", expr], ["=", expr]), ")", block
_list = lambda: "[", commalist, "]"
commalist = lambda: repeat(expr, repeat(","))
object = lambda: "{", repeat(relaxid, [":", union(expr, callable)], [","]), "}"
