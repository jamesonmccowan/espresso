#!/usr/bin/env python3.10

import parse
import eval
import vm
import compile
import pprint
import argparse

ap = argparse.ArgumentParser(description="Test VM for Espresso")
ap.add_argument('-c', '--compile', help="Compile the program")
ap.add_argument('-f', '--file', help="Execute the given file")
ap.add_argument('-t', '--tokens', help="Print the token stream", action="store_true")
ap.add_argument('-p', '--print', help="Print the AST", action="store_true")
ap.add_argument('-r', '--raw', help="Print the raw representation", action="store_true")
ap.add_argument('-x', '--exec', help="Execute the source (default if not printing)", action="store_true")
ap.add_argument("-v", "--value", help="Output the return value of the program", action="store_true")

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
	
	if args.file is not None:
		src = open(args.file).read()
	else:
		print("Give either a command or a file")
		exit()
	
	if args.tokens:
		for tok in tokstream(src):
			print(tok)
	
	if args.print or args.raw or args.compile or args.exec:
		prog = parse.parse(src)
	
	if args.print:
		print(str(prog))
		#print(ast.PrettyPrinter().visit(prog))
	
	if args.raw:
		print(pprint.pformat(prog.statements))
	
	if args.compile:
		bc = compile.compile(prog)
		print('bc', bc)
	
	if args.exec:# or not args.print:
		val = vm.eval(bc)
		'''
		val = eval.eval(prog)
		
		if args.value or args.cmd:
			pprint.pp(val)
		'''
	
	return

if __name__ == "__main__":
	main()
