'''
+ - * / % ++ -- ** // %%
~ & | ^ << <<< <<> >> >>> <>>
! < <= > >= != == !== === <=>
in is as has new delete
ldarg starg ldvar stvar ldup stup
getitem setitem delitem getattr setattr delattr
return fail yield br br_if
call tcall mcall mtcall iter
const this super
list object tuplen
if else block loop switch case end
unreachable nop

Activation record:
this params locals f_back func pc tmps

function callconv upvars params this locals tmps length
...
end

which(x) {
	case a: A
	case b: B
	case: C
}

x
lookup(a, b, 2)
switch {
case { A br 1 }
case { B br 1 }
case { C }
}

loop A while(B) C then D else E

block {
	loop {
		A
		B
		if {
			C
			drop/yield
			br 1
		}
		else {
			D
			drop
			br 2
		}
	}
	E
}

for(var x in y) z then a else b

y
iter
{
	dup
	call 0
	dup
	const undefined
	ideq
	if {
		stvar x
		z
		drop/yield
		continue 1
	}
	else {
		drop
		a
		drop
		break 1
	}
	b
}
drop
'''

add sub mul div mod pow idiv rem
not inc dec inv and ior xor car
shl sal rol ror shr sar
lt le gt ge eq ne ideq cmp
in is as has new del
ldarg starg ldvar stvar ldup stup
getitem setitem delitem getattr setattr delattr
return fail yield br br_if
call tcall mcall mtcall iter
const this super
list object tuple
if else block loop switch case end
unreachable nop dup drop