import unicodedata as und
import sys
from collections import Counter

maxuni = 0x10FFFF

cats = {'Cn': 836601, 'Co': 137468, 'Lo': 121414, 'So': 6161, 'Ll': 2151, 'Cs': 2048, 'Mn': 1826, 'Lu': 1788, 'Sm': 948, 'No': 888, 'Nd': 630, 'Po': 588, 'Mc': 429, 'Lm': 259, 'Nl': 236, 'Cf': 161, 'Sk': 121, 'Ps': 75, 'Pe': 73, 'Cc': 65, 'Sc': 62, 'Lt': 31, 'Pd': 24, 'Zs': 17, 'Me': 13, 'Pi': 12, 'Pc': 10, 'Pf': 10, 'Zl': 1, 'Zp': 1}

bidirectional = 24
category = 30
combining = 55
decimal = 10
digit = 10
east_asian_width = 6
is_normalized = 4*2
mirrored = 2
name = "???"
numeric = 142

for x in uninames():
	

class Trie:
	def __init__(self):
		self.data = {}
	
	def add(self, key):
		d = self.data
		k = key[0]
		
		if k in d:
			d[k].add(key[1:])
		else:
			d[k] = {k: Trie(key[1:])}

def allc(cat):
	print(cat, end=": ")
	bit = True
	count = 0
	for c in range(maxuni):
		uc = und.category(chr(c))
		cc = (uc == cat)
		
		if bit ^ cc:
			print(count, end=' ')
			count = 0
			bit = not bit
		else:
			count += 1
	print()
	print()

for cat in cats:
	allc(cat)