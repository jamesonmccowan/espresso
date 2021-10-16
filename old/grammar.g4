grammar Espresso;

MultiLineComment : '#*' .*? '*#' -> channel(HIDDEN);
SingleLineComment : '#' ~[\n] -> channel(HIDDEN);

IfStatement : 'if' Expression Statement ('else' Statement)?;

Statement : Expression ';'?;

Expression :
	Identifier |
	Literal |
	'(' Expression ')';

postfixExpr : Expression (
	'[' Expression ']' | '(' paramList ')' | '.' Identifier | ('++' | '--')
);

paramList : assignExpr (',' assignExpr);

unaryExpr : ('++' | '--')* (postfixExpr | unaryOp Expression);
unaryOp : '+' | '-' | '~' | '!' | 'not';
multiplicativeExpr :
	Expression (('*' | '/' | '%' | '//' | '%%') Expression)*;

additiveExpr :
	multiplicativeExpr (('+' | '-') multiplicativeExpr)*;

shiftExpr :
	additiveExpr (('<<' | '>>') additiveExpr)*;

cmpExpr :
	shiftExpr (('<' | '>' | '<=' | '>=' | '<=>') shiftExpr)*;
equalityExpr :
	cmpExpr (('==' | '===' | '!=' | '!==') cmpExpr)*;

andExpr :
	equalityExpr ('&' equalityExpr)*;
xorExpr :
	andExpr ('^' andExpr)*;
orExpr :
	xorExpr ('|' orExpr)*;

logicalAndExpr :
	orExpr (('&&' | 'and') orExpr)*;
logicalOrExpr :
	logicalAndExpr (('||' | 'or') logicalAndExpr)*;

assignExpr : unaryExpr assignOp assignExpr;
assignOp : '=' |
	'*=' | '/=' | '%=' | '**=' | '//=' | '%%=' | '+=' | '-=' |
	'<<=' | '>>=' | '>>>=' | '&=' | '^=' | '|=' |
	'&&=' | '||=' | ':=' | '??=';

Digit : [0-9];
IdentStart : [a-zA-Z$_];
IdentRest : IdentStart | Digit;
Identifier : IdentStart IdentRest*;

BINARY : '0b' [_01]* [01];
OCTAL : '0o' [_0-7]* [0-7];
HEX : '0x' [_0-9a-fA-F]* [0-9a-fA-F];
DECIMAL : [0-9] ([_0-9]* [0-9])?;

Integer : BINARY | OCTAL | HEX | DECIMAL;
Real : (DECIMAL '.' DECIMAL? | DECIMAL? '.' DECIMAL) ([eE] [-+]? DECIMAL)?;
Number : Integer | Real;
String : '\'' ('\\' . | ~[']) '\'';
Literal : Number | String+;