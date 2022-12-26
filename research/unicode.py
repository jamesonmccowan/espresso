from collections import Counter
from collections.abc import Iterable
from functools import cache
from itertools import chain, tee, islice
import pickle
import re
from typing import TypeAlias, Optional, TypeVar, Callable

SAVE_FILE = "save.pickle"
PROCEDURAL = {
	"IDEOGRAPH",
	"COMPONENT",
	"CHARACTER",
	"DOTS",
	"SEXTANT",
	"HORIZONTAL",
	"VERTICAL",
	"SELECTOR"
}
MAX_NGRAM = 3
UCD_FILE = "ucd.pickle"
NamesList_FILE = "NamesList.txt"
NameAliases_FILE = "NameAliases.txt"
NamedSequences_FILE = "NamedSequences.txt"

Partition: TypeAlias = tuple[str, ...]
Predicate: TypeAlias = Callable[[TypeVar("T")], bool]

# Generate n-grams of a given size
def gen_ngrams(word: str, n: int) -> Iterable[str]:
	for i in range(len(word) - n + 1):
		yield word[i: i + n]

# Yield lists of n-gram sets
def gen_partitions(word: str) -> Iterable[Partition]:
	if len(word) == 0:
		yield ()
		return
	
	for i in range(1, min(MAX_NGRAM, len(word)) + 1):
		first = (word[:i],)
		for p in gen_partitions(word[i:]):
			yield first + p

@cache
def partition_score(part: tuple[str, ...]) -> int:
	return sum(ngrams[subword]*(len(subword) - 1) for subword in part)

@cache
def best_score(word: str) -> tuple[int, Partition]:
	'''
	if len(word) <= MAX_NGRAM:
		parts = skip_last(parts)
	'''
	
	a, b = tee(gen_partitions(word))
	
	return max(
		zip(map(partition_score, a), b),
		key=lambda x: x[0]
	)

def is_ucd_comment(line: str) -> bool:
	return line == "" or line.isspace() or line.startswith(("#", "@", ";", "\t"))

try:
	print("Loading UCD...")
	with open(UCD_FILE, "rb") as f:
		names, codes, aliases, seqs = pickle.load(f)
except FileNotFoundError:
	print("UCD not found, generating from text...")
	
	print("NamesList...")
	names: dict[int, str] = {}
	codes: dict[str, int] = {}
	with open(NamesList_FILE, "rt") as f:
		for line in f.readlines():
			if is_ucd_comment(line):
				continue
			
			code, name = line.strip().split('\t')
			if not name.startswith("<"):
				code = int(code, 16)
				names[code] = name
				codes[name] = code
	
	print("NameAliases...")
	aliases: dict[int, str] = []
	with open(NameAliases_FILE, "rt") as f:
		for line in f.readlines():
			if is_ucd_comment(line):
				continue
			
			code, name, category = line.strip().split(';')
			code = int(code, 16)
			
			if category == "correction":
				if code in names:
					name, names[code] = names[code], name
				else:
					names[code] = name
			
			aliases.append(name)
	
	print("NamedSequences...")
	seqs: dict[int, str] = {}
	with open(NamedSequences_FILE, "rt") as f:
		for line in f.readlines():
			if is_ucd_comment(line):
				continue
			
			name, seq = line.strip().split(';')
			seqs[name] = ''.join(chr(int(code, 16)) for code in seq.strip().split(' '))
	
	print("Saving UCD to file...")
	with open(UCD_FILE, "wb") as f:
		pickle.dump((names, codes, aliases, seqs), f)

T = TypeVar("T")
def first_of(fn: Predicate[T], it: Iterable[T]) -> T:
	return next(filter(fn, it), None)

T = TypeVar("T")
def last_of(fn: Predicate[T], it: Iterable[T]) -> T:
	save = None
	for el in it:
		if fn(el):
			save = el
		else:
			break
	return save

allcodes = list(names.keys())
def iter_codepoints(start: int) -> Iterable[int]:
	ix = first_of(lambda el: el[1] >= start, enumerate(allcodes))
	if ix is None:
		return
	
	i, x = ix
	yield from islice(allcodes, i, None)

prefixes = set()
have_nonunique = set()
def find_prefix(first: int) -> Optional[tuple[str, int, bool]]:
	if first in have_nonunique:
		return None
	
	name = names[first]
	words = name.split(' ')
	i = 1
	
	# Each iteration attempts a prefix
	while i < len(words) + 1:
		prefix = ' '.join(words[:i]) + " "
		i += 1
		
		def code_prefixed(code: int) -> bool:
			return names[code].startswith(prefix)
		
		# Make sure we don't repeat prefixes
		if prefix in prefixes:
			continue
		
		prefixes.add(prefix)
		
		# Find the last codename with the prefix
		last = last_of(code_prefixed, iter_codepoints(first))
		if last is None or last == first:
			return None
			last = first
		
		# Find the next codename with the prefix (or None)
		cursor = first_of(code_prefixed, iter_codepoints(last + 1))
		
		# No other blocks have the prefix
		if cursor is None:
			return prefix.strip(), last, True
	else:
		# Name has no unique prefix, it must be a prefix itself
		have_nonunique.update(filter(code_prefixed, iter_codepoints(first + 1)))
		return None #name, last, False

print("Generating prefix table...")
try:
	prefixtab: dict[str, tuple[int, int, bool]] = {}
	first = 0
	while first := next(iter_codepoints(first), None):
		if data := find_prefix(first):
			prefix, last, unique = data
			prefixtab[prefix] = (first, last, unique)
			print("Prefix", repr(prefix), first, last)
			
			first = last + 1
		else:
			first += 1
except KeyboardInterrupt:
	pass

print("Prefixtab", prefixtab, '\n')
exit()

try:
	print("Loading process data...")
	with open(SAVE_FILE, "rb") as f:
		words, ngrams = pickle.load(f)

except FileNotFoundError:
	print("File not found, generating...")
	
	words = Counter()
	ngrams = Counter()
	for n in chain(names, aliases, seqs.keys()):
		# Process each word separately
		for i, w in enumerate(n.split(' ')):
			# Handle procedurally generated names
			if '-' in w:
				l, *r = w.split('-')
				w = [l]
				# Add words between dashes that don't have numbers
				if l not in PROCEDURAL:
					w += r
			else:
				w = [w]
			
			for word in w:
				if re.search(r"\d", word):
					continue
				
				words[word] += 1
				
				for size in range(2, MAX_NGRAM):
					for tg in gen_ngrams(word, size):
						ngrams[tg] += 1
				
				for c in word:
					ngrams[c] += 1
	
	print("Saving data to file...")
	with open(SAVE_FILE, "wb") as f:
		pickle.dump((words, ngrams), f)

print("Begin finding the best partitions")

# Now, go over every word and determine what ngrams are useful
useful_ngrams = Counter()

for word, count in words.items():
	# Figure out the best ngram set
	
	bscore, bpart = best_score(word)
	print(word, "=", bpart)
	
	for subword in bpart:
		useful_ngrams[subword] += 1

print("Filtering ngrams...")
useful_ngrams = {ngram: count for ngram, count in useful_ngrams.items() if count > len(ngram)}

for word, count in useful_ngrams.items():
	print(word, count)
print(useful_ngrams)