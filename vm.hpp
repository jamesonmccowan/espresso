#ifndef VM_HPP
#define VM_HPP

#include "value.hpp"

class VM {
private:
	Value self;
	Value* args;
	int nargs;
	Function* calling;
	int pc;
	
	/**
	 * Call stack
	**/
	Value* stack;
	
	/**
	 * Implicit accumulator register
	**/
	Value A;
	/**
	 * Current register file (usually a pointer into the stack)
	**/
	Value* R;
	
	/**
	 * Addressing mode of the current instruction (0 or 1)
	**/
	bool mode() const;
	
	/**
	 * A in mode 0, D in mode 1 (generally used with da())
	**/
	Value* ad();
	/**
	 * B in mode 0, A in mode 1 (generally used with cd())
	**/
	Value* ba();
	/**
	 * C in mode 0, D in mode 1 (generally used with ba())
	**/
	Value* cd();
	/**
	 * D in mode 0, A in mode 1 (generally used with ad())
	**/
	Value* da();
	
	/**
	 * 4-bit B in mode 0, 8-bit B in mode 1
	**/
	int B() const;
	int C() const;
	int D() const;
	int BC() const;
	
	/**
	 * Signed immediate, 8-bit in mode 0, 16-bit in mode 1
	**/
	int sI() const;
	
public:
	bool run(int ops);
};

#endif
