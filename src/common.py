#!/usr/bin/env python3

import contextlib

@contextlib.contextmanager
def stack(ls, val):
	ls.append(val)
	yield
	ls.pop()