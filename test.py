import parse
import eval
import sys
import pprint

if len(sys.argv) == 1:
	print("Call with a program")
	exit()

src = sys.argv[1]

def tokstream(src):
	p = parse.Lexer(src)
	while True:
		x = p.next()
		if x:
			yield str(x)
		else:
			break

pprint.pp(list(tokstream(src)))

prog = parse.Parser(sys.argv[1]).parse()

print(prog)
pprint.pp(prog)

ev = eval.EvalVisitor()

pprint.pp(prog.visit(ev))