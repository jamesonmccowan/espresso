import parse
import eval
import sys
import pprint

if len(sys.argv) == 1:
	print("Call with a program")
	exit()

if sys.argv[1] == "-c":
	if len(sys.argv) == 2:
		print("Need a string")
		exit()
	src = sys.argv[2]
else:
	src = open(sys.argv[1]).read()

def tokstream(src):
	p = parse.Lexer(src)
	while True:
		x = p.next()
		if x:
			yield str(x)
		else:
			break

pprint.pp(list(tokstream(src)))

prog = parse.Parser(src).parse()

print(prog)
pprint.pp(prog)

ev = eval.EvalVisitor()

pprint.pp(prog.visit(ev))