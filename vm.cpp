#include "vm.hpp"
#include "op-defs.hpp"

bool VM::mode() const {
	return *pc&(1<<7);
}

esp_Value* VM::ad() {
	return mode()? &A : &R[D()];
}

esp_Value* VM::ba() {
	return mode()? &R[B()] : &A;
}

esp_Value* VM::cd() {
	return mode()? &R[C()] : &R[D()];
}

esp_Value* VM::da() {
	return mode()? &R[D()] : &A;
}

int VM::B() const {
	return pc[1];
}

int VM::C() const {
	return pc[2];
}

int VM::D() const {
	return pc[1];
}

int VM::BC() const {
	return B()<<8 | C();
}

int VM::sI() const {
	return mode()? D() - 128 : BC() - (1<<15);
}

esp_Value esp_proto(esp_Value x) {
	switch(esp_type(x)) {
		case ESP_BOOL: return &esp_bool_proto;
	}
}

esp_Function* esp_getop(esp_Value x, Op op) {
	if(esp_isBuiltin(x)) {
		return x[op];
	}
	return esp_get(x, toString(op));
}

esp_Value&& op_add(esp_Value& a, esp_Value& b) {
	// bool < int < real < string
	
	auto mm = esp_getop(esp_proto(a), OP_ADD);
	if(mm != ESP_NONE) {
		return esp_call(mm, b, a, b);
	}
	
	mm = esp_getop(esp_proto(b), OP_ADD);
	if(mm != ESP_NONE) {
		return esp_call(mm, a, a, b);
	}
	
	ERROR();
}

bool VM::run(int ops) {
	for(int i = 0; i < ops; ++i) {
		switch(*pc) {
			case OP_NOP: break;
			
			case OP_LDNONE: *ad() = ESP_NONE; break;
			case OP_LDFALSE: *ad() = ESP_FALSE; break;
			case OP_LDTRUE: *ad() = ESP_TRUE; break;
			
			case OP_LOADK: *ba() = K[C()]; break;
			case OP_LOADI: A = sI(); break;
			
			case OP_ARG: *ba() = P[C()]; break;
			
			case OP_MOVE: *ba() = *cd(); break;
			
			case OP_GETUP: *ba() = U[mode() == 0? C() : D()]; break;
			case OP_SETUP: U[mode() == 0? C() : D()] = *cd(); break;
			
			case OP_ID_EQ: A = ba()->ideq(*cd()); break;
			
			case OP_ADD: A = *ba() + *cd(); break;
			case OP_SUB: A = *ba() - *cd(); break;
			case OP_MUL: A = *ba() * *cd(); break;
			case OP_DIV: A = *ba() / *cd(); break;
			case OP_MOD: A = *ba() % *cd(); break;
			case OP_POW: A = ba()->pow(*cd()); break;
			case OP_IDIV: A = ba()->idiv(*cd()); break;
			case OP_IMOD: A = ba()->imod(*cd()); break;
			
			case OP_INV: *ad() = ~*da(); break;
			case OP_AND: A = *ba() & *cd(); break;
			case OP_OR: A = *ba() | *cd(); break;
			case OP_XOR: A = *ba() ^ *cd(); break;
			case OP_LSH: A = *ba() << *cd(); break;
			case OP_ASH: A = *ba() >> *cd(); break;
			case OP_RSH: A = ba()->rsh(*cd()); break;
			
			case OP_ADD_EQ: *ba() += *cd(); break;
			case OP_SUB_EQ: *ba() -= *cd(); break;
			case OP_MUL_EQ: *ba() *= *cd(); break;
			case OP_DIV_EQ: *ba() /= *cd(); break;
			case OP_MOD_EQ: *ba() %= *cd(); break;
			case OP_POW_EQ: ba()->poweq(*cd()); break;
			case OP_IDIV_EQ: ba()->idiveq(*cd()); break;
			case OP_IMOD_EQ: ba()->imodeq(*cd()); break;
			
			case OP_AND_EQ: *ba() &= *cd(); break;
			case OP_OR_EQ: *ba() |= *cd(); break;
			case OP_XOR_EQ: *ba() ^= *cd(); break;
			case OP_LSH_EQ: *ba() <<= *cd(); break;
			case OP_ASH_EQ: *ba() >>= *cd(); break;
			case OP_RSH_EQ: ba()->rsheq(*cd()); break;
			
			case OP_LT: A = *ba() < *cd(); break;
			case OP_LE: A = *ba() <= *cd(); break;
			case OP_GT: A = *ba() > *cd(); break;
			case OP_GE: A = *ba() >= *cd(); break;
			case OP_EQ: A = *ba() == *cd(); break;
			case OP_NE: A = *ba() != *cd(); break;
			case OP_CMP: A = ba()->cmp(*cd()); break;
			case OP_BOOL: *ba() = Bool(*cd()); break;
			
			case OP_IS: A = ba()->is(*cd()); break;
			
			case OP_JT:
				if(A) {
					pc += sI();
					continue;
				}
				break;
			
			case OP_JF:
				if(!(bool)A) {
					pc += sI();
					continue;
				}
				break;
			
			case OP_JMP: pc += sI(); break;
			
			case OP_PROTO: *ba() = cd()->proto(); break;
			
			case OP_GET: A = (*ba())[*cd()]; break;
			case OP_SET: A[*ba()] = *cd(); break;
			case OP_DEL: A = ba()->del(*cd()); break;
			case OP_IN: A = ba()->in(*cd()); break;
			
			case OP_NEW:
				setupcall(ba()->getNew());
				break;
			case OP_CALL:
				setupcall(ba()->getCall());
				break;
			case OP_TAILCALL:
				cleanupcall();
				setupcall(ba()->getCall());
				break;
			
			case OP_RETURN:
				cleanupcall();
				break;
			
			case OP_YIELD:
			
			case OP_AWAIT:
			
			case OP_THROW:
			
			case OP_ASSERT:
				/* TODO */
				break;
	/*
	OP_IS, // A = (R[ba] is R[cd])
	OP_IS_NONE, // f = (A is none)
	OP_IS_BOOL, // f = (A is bool)
	OP_IS_NUM, // f = (A is number)
	OP_IS_INT, // f = (A is int)
	OP_IS_REAL, // f = (A is real)
	OP_IS_STR, // f = (A is string)
	OP_IS_LIST, // f = (A is list)
	OP_IS_OBJ, // f = (A is object)
	OP_IS_FUNC, // f = (A is function)
	
	OP_RETURN, // return a
	OP_YIELD, // A = yield R[ba]
	OP_AWAIT, // A = await R[ba]
	OP_THROW, // throw R[ad]
	OP_ASSERT, // assert R[ad]
	
	OP_LIST,
	OP_OBJECT,
	*/
		}
	}
}