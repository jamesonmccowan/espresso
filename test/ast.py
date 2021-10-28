import unittest
from src import ast

class Test(unittest.TestCase):
	def test_sexp_sane(self):
		sexp = ast.sexp
		
		self.assertEqual(
			sexp("x", "y", "z", None), "(x y z)"
		)
		self.assertEqual(
			sexp(("x", None, "y", "z"), "(x y z)")
		)
		self.assertEqual(
			sexp(['x', 'y', None, 'z'], "[x y z]")
		)
	
	def test_sexp_error(self):
		sexp = ast.sexp
		
		with self.assertRaises(TypeError):
			sexp(1, 2, 3)
		
		with self.assertRaises(TypeError):
			sexp('x', 'y', 3)
		
		with self.assertRaiases(TypeError):
			sexp(('x', 'y', 3))
	
	def test_sexp_edge(self):
		sexp = ast.sexp
		
		self.assertEqual(sexp(), "")
		self.assertEqual(sexp([], ""))
		self.assertEqual(sexp(()), "()")
	
	def test_str(self):
		Expr = ast.Expr
		
		all_expr = [x for x in ast if Expr in x.__bases__]
		
		# Make sure all str and repr are implemented
		for x in all_expr:
			self.assertNotEqual(x.__str__, Expr.__str__)
			self.assertNotEqual(x.__repr__, Expr.__repr__)

if __name__ == "__main__":
	Test().main()