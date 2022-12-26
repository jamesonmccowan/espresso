#include <iterator>

#include "value.hpp"

#include <array>
#include <stack>

namespace detail {
	enum class Tag {
		BOOL = 1<<1,
		INT = 1<<2,
		FLOAT = 1<<3,
		STRING = 1<<4,
		LIST = 1<<5,
		OBJECT = 1<<6
	};
	
	enum Op {
	#define X(name, ...) name,
		#include "opcode.def"
	#undef X
	};
}

struct Opcode {
	uint8_t tags;
	
	detail::Op op;
	
	union {
		struct {
			uint arg1;
			uint arg2;
		};
		uint index;
	};
};

class Code {
private:
	size_t size;
	Opcode* data;
	
public:
	template<typename VT>
	struct BaseIterator {
		using iterator_cateogry = std::random_access_iterator_tag;
		using difference_type = size_t;
		using value_type = VT;
		using pointer = Opcode*;
		using reference = Opcode&;
	
	private:
		pointer pc; /// Program Counter
		pointer eof; /// End of Function
};

#define _TOKCAT_IMPL(x, y) x ## y
#define TOKCAT(x, y) _TOKCAT_IMPL(x, y)
#define _VMCASE_IMPL2(br, body) \
	goto body; br: break; while(1) if(1) goto br; else body:
#define _VMCASE_IMPL1(prefix) \
	_VMCASE_IMPL2(TOKCAT(prefix, _break), TOKCAT(prefix, _body))
#define VMCASE(op) case detail::op: _VMCASE_IMPL1(TOKCAT(_L, __COUNTER__))

struct Function : public GCObject {
	Opcode* code;
	Value** upvars;
	Value* ktab;
};

struct StackFrame {
	std::array<Value, 16> regs;
	Opcode* pc;
	Function* callee;
	uint argc;
	Value* argv;
	
	StackFrame& operator=(const StackFrame& frame) {
		regs = frame.regs;
		pc = frame.pc;
		callee = frame.callee;
		argc = frame.argc;
		argv = frame.argv;
	}
};

class VM : public StackFrame {
private:
	Value A;
	std::stack<StackFrame> frames;
	
public:
	using StackFrame::operator=;
	
	void step() {
		const auto& opcode = *pc++;
		switch(opcode.op) {
			VMCASE(NOP) {}
			VMCASE(MOV) regs[opcode.arg1] = regs[opcode.arg2];
			VMCASE(LDAR) A = regs[opcode.arg1];
			VMCASE(STAR) regs[opcode.arg1] = A;
			VMCASE(CONST) A = callee->ktab[opcode.index];
			VMCASE(GET) A = regs[opcode.arg1][regs[opcode.arg2]];
			VMCASE(SET) regs[opcode.arg1][regs[opcode.arg2]] = A;
			VMCASE(DEL) regs[opcode.arg1].del(regs[opcode.arg2]);
			VMCASE(SKIP) if(A) ++pc;
			VMCASE(BR) pc = 0;
			VMCASE(CALL) {
				Function& fn = A.as<Function>();
				frames.push(*this);
				*this = StackFrame{
					{}, fn.code, &fn,
					opcode.arg2 - opcode.arg1, &regs[opcode.arg1]
				};
			}
			VMCASE(RET) {
				*this = frames.top();
				frames.pop();
			}
		}
	}
	
};