import {Parser} from "./lex";

const test = "var x = 0; while(x < 10) x = x + 1; x";
console.log("Testing", test);

let prog = new Parser(test).parse();
console.log(prog + "");
console.log(JSON.stringify(prog.eval()));

// Prog {[x] (group (= x 0)) (while (= (< x 10) (+ x 1)) (; none x) none none)}
