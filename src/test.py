import parse
import eval
import ast
import sys
import pprint
import argparse

ap = argparse.ArgumentParser(description="Test VM for Espresso")
ap.add_argument('-c', '--cmd', help="Execute a program passed by commandline")
ap.add_argument('-f', '--file', help="Execute the given file")
ap.add_argument('-t', '--tokens', help="Print the token stream", action="store_true")
ap.add_argument('-p', '--print', help="Print the AST", action="store_true")
ap.add_argument('-r', '--raw', help="Print the raw representation", action="store_true")
ap.add_argument('-x', '--exec', help="Execute the source (default if not printing)", action="store_true")

def tokstream(src):
	p = parse.Lexer(src)
	while True:
		x = p.next()
		if x:
			yield str(x)
		else:
			break

def main():
	args = ap.parse_args()
	
	if args.cmd is not None:
		src = args.cmd
	elif args.file is not None:
		src = open(args.file).read()
	else:
		print("Give either a command or a file")
		exit()
	
	if args.tokens:
		print(list(tokstream(src)))
	
	prog = parse.Parser(src).parse()
	
	if args.print:
		print(str(prog))
		#print(ast.PrettyPrinter().visit(prog))
	
	if args.raw:
		print(repr(prog))
	
	if args.exec or not args.print:
		ev = eval.EvalVisitor()
		pprint.pp(prog.visit(ev))
	
	return

if __name__ == "__main__":
	main()
