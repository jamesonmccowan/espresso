#include "value.hpp"

#include <cstdlib>
#include <algorithm>
#include <cstring>

bool esp_ideq(const Value& x, const Value& y) {
	return x.raw() == y.raw();
}

struct Arguments {
	int argc;
	Value* args;
	
	Arguments(int argc, Value* args): argc(argc), args(args) {}
	
	Value operator[](int x) {
		return x < argc? args[x] : ESP_NONE;
	}
};

Value int_add(Value self, int argc, Value* args) {
	Arguments arguments(argc, args);
	
	if(esp_ideq(self, arguments[0])) {
		switch(arguments[1].type()) {
			case NONE:
				return arguments[1];
			
			case BOOL:
				return esp_int(self.asInt())
		}
	}
}