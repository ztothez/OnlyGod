# OnlyGod: technical report

Nov 9, 2026 · @Roosa Sofia Yöruusu

OnlyGod is a small statically typed language with a hand-written compiler front end in Python: a lexer, two parsers, a type checker, a tree-walking interpreter and a transpiler to Python.

## Pipeline

A program goes through the same front end every time. The last step has two alternatives, chosen with a flag on the command line.

1. **Lexer** turns the source text into tokens with line and column.
2. **Parser** turns the tokens into an AST. Either the recursive descent parser (default) or the table-driven bottom-up parser (`--bottomup`) can do this, and they produce the same tree.
3. **Type checker** reads the AST and reports every type error. If there is one, nothing runs.
4. **Back end**, one of two:
   - The **interpreter** walks the AST and runs it directly (default).
   - The **transpiler** turns the AST into Python source, which Python then runs (`--py`), or which is only printed (`--emit`).

```
python onlygod.py examples/factorial.og                 interpret
python onlygod.py --py examples/factorial.og            transpile to Python and run
python onlygod.py --emit examples/scope.og              print the generated Python
python onlygod.py --bottomup --py examples/factorial.og  bottom-up parser, then Python
```

## The language

OnlyGod is built around three ideas: errors that say where the problem is and what to try, static types with no implicit conversions, and a language small enough to explain in one page. The name comes from the code comment "only god knows how it worked". Source files use the extension `.og`.

A small program:

```
fun fact(n: int): int {
    if (n <= 1) { return 1; }
    return n * fact(n - 1);
}
let n: int = 5;
print fact(n);
```

The language has four types (`int`, `float`, `string`, `bool`), variables declared with `let`, assignment, `print`, `read`, `if` and `else`, `while`, functions with typed parameters and a return type, blocks with their own scope, and three built-ins: `toInt`, `toFloat` and `toString`.

The grammar in EBNF:

```
program     = { declaration } EOF ;
declaration = varDecl | funDecl | statement ;
varDecl     = "let" IDENT ":" type "=" expression ";" ;
funDecl     = "fun" IDENT "(" [ param { "," param } ] ")" ":" type block ;
param       = IDENT ":" type ;
type        = "int" | "float" | "string" | "bool" ;

statement   = printStmt | readStmt | ifStmt | whileStmt
            | returnStmt | block | assignStmt | exprStmt ;
printStmt   = "print" expression ";" ;
readStmt    = "read" IDENT ";" ;
ifStmt      = "if" "(" expression ")" block [ "else" block ] ;
whileStmt   = "while" "(" expression ")" block ;
returnStmt  = "return" [ expression ] ";" ;
assignStmt  = IDENT "=" expression ";" ;
exprStmt    = expression ";" ;
block       = "{" { declaration } "}" ;

expression  = logicOr ;
logicOr     = logicAnd { "or" logicAnd } ;
logicAnd    = equality { "and" equality } ;
equality    = comparison { ( "==" | "!=" ) comparison } ;
comparison  = term { ( "<" | "<=" | ">" | ">=" ) term } ;
term        = factor { ( "+" | "-" ) factor } ;
factor      = unary { ( "*" | "/" | "%" ) unary } ;
unary       = ( "-" | "not" ) unary | call ;
call        = IDENT "(" [ expression { "," expression } ] ")" | primary ;
primary     = NUMBER | STRING | "true" | "false" | IDENT
            | "(" expression ")" ;

IDENT       = letter { letter | digit | "_" } ;
NUMBER      = digit { digit } [ "." digit { digit } ] ;
STRING      = '"' { any character except '"' } '"' ;
```

Operator precedence follows the rule order: `or` binds loosest, then `and`, equality, comparison, `+ -`, `* / %`, and unary operators and calls bind tightest. All binary operators are left associative.

## Lexer

The lexer (`lexer.py`) reads the source one character at a time and produces a list of tokens. Each `Token` carries its type, the exact text it came from (`lexeme`), a converted `value` for numbers and strings, and the `line` and `col` where it starts. That position is what every later error message points at.

The scanner is a loop around `scan_token`, built from four small helpers: `peek` looks at the current character without consuming it, `advance` consumes it, `match` consumes it only if it equals what is expected, and `at_end` stops the loop. The cases are:

- Whitespace and newlines are skipped, and newlines advance the line counter.
- Single-character tokens (`( ) { } , : ; + - * / %`) come from one lookup table.
- One or two characters: `=` and `==`, `!=`, `<` and `<=`, `>` and `>=`. After reading the first character, `match` decides whether a second one belongs to it.
- Numbers are digits with an optional fractional part. A dot makes the value a float, otherwise an int.
- Strings run between double quotes. A string that never closes is an error reported at its opening quote, which is where the programmer needs to look.
- Names are letters, digits and underscores. After reading one, a keyword table decides whether it is a keyword (`let`, `fun`, `if`, `while`, `and`, `int` and so on) or a plain `IDENT`.

Anything else raises a `LexError` with the position and the character, for example `unexpected character '@'`. A lone `!` gets a hint to use `not` or `!=`.

The end of the list is always an `EOF` token, so the parsers never have to check for running off the end.

## AST and the two parsers

**The AST.** Both parsers build the same tree, defined as plain dataclasses in `ast_nodes.py`. Expressions are `Literal`, `Variable`, `Unary`, `Binary` and `Call`. Statements are `VarDecl`, `Assign`, `Print`, `Read`, `Block`, `If`, `While`, `Return`, `ExprStmt` and `FunDecl`, collected in a `Program`. Every node stores the `line` and `col` where it starts, so later stages can report errors without going back to the tokens. A binary node starts where its left operand starts, and a statement starts at its first token.

**Top-down parser (`parser.py`).** This is recursive descent: every grammar rule is one method. Precedence comes from the call chain. `expression` calls `logic_or`, which calls `logic_and`, then `equality`, `comparison`, `term`, `factor`, `unary`, `call` and finally `primary`. A rule always calls the rule that binds tighter. Left associativity comes from a `while` loop in each binary level, so `a - b - c` becomes `(a - b) - c`. Statements are chosen by looking at their first token (`let`, `fun`, `print`, `if` and so on). The one place that needs a second token of lookahead is `x = 1;` against `x + 1;`, which `peek_next` resolves. Errors name what was expected, for example `expected '}' to close the block opened at line 3, col 5`.

**Bottom-up parser (`lrparser.py`).** This parser works the other way round. It reads tokens left to right, pushes them on a stack (shift), and when the top of the stack matches the right-hand side of a rule it replaces those symbols by the rule's left-hand side (reduce), building the AST node as it goes. It is table driven and the tables are generated from the grammar, not written by hand:

1. Compute which nonterminals can be empty, and the FIRST and FOLLOW sets.
2. Build the states with `closure` and `goto`. A state is a set of items, and an item is a rule with a dot marking how much of it has been seen.
3. Fill the action table (shift, reduce, accept) and the goto table. This is an SLR(1) construction, and a cell that would hold two different actions raises a conflict error, which is how an ambiguous grammar is detected.
4. A short driver loop uses the tables with a stack of states and values.

The grammar has 119 states and builds in a few milliseconds. Left recursion (`term = term + factor`) is natural here and gives left associativity directly. The test suite checks that the bottom-up parser produces exactly the same AST, including line and column, as the recursive descent parser for every test program and example. Syntax errors read like `unexpected 'int', expected ':'`. The runner uses it with `--bottomup`.

## Type checker

The type checker (`typechecker.py`) runs after parsing and before anything executes. It walks the same AST as the interpreter, but computes types instead of values: `check_expr` returns the type of an expression (`int`, `float`, `string` or `bool`) and `check_stmt` checks a statement. If it finds any error, the program is not run.

The language rules it enforces:

1. No implicit conversions. An `int` is never silently turned into a `float` or a `string`. The programmer writes `toFloat(...)`, `toInt(...)` or `toString(...)`.
2. Arithmetic on two ints gives an int. If either side is a float, the result is a float. Ints and floats can be compared with each other.
3. `+` also joins two strings. Any other use of `+` is an error.
4. Conditions, `and`, `or` and `not` need `bool`.
5. A call must match the function's parameter count and types, and a `return` must match the declared return type.

It keeps a `TypeEnv` scope chain that mirrors the interpreter's `Environment`, but it stores types. A block opens a new `TypeEnv`, and a function declares itself before checking its body so that it can call itself.

**Error recovery.** The checker does not stop at the first mistake. Errors are collected in a list and the walk continues. An expression that is already wrong returns the special type `ERR`, which every rule accepts silently, so one mistake does not cause a chain of follow-up errors. For `let x: int = "a" + 1;` only the bad addition is reported, not the declaration as well.

**Hints.** A hint is only given when one conversion is known to exist. Putting a string into an `int` suggests `toInt(...)`, a float into a `string` suggests `toString(...)`. Otherwise the message states the fact and says nothing more, because a wrong suggestion is worse than none.

Example, `examples/error_types.og`, with three mistakes reported together:

```
error: line 1, col 16: cannot put string into 'age', which is int
    let age: int = "twenty";
                   ^
    hint: convert with toInt(...)

error: line 2, col 20: cannot put int into 'price', which is float
    let price: float = 5;
                       ^
    hint: convert with toFloat(...)

error: line 3, col 7: cannot add string to int
    print "total: " + age;
          ^
    hint: convert with toInt(...) or toString(...)

3 errors found, nothing was run.
```

## Interpreter and nested scope

The interpreter (`interpreter.py`) is a tree walker with two entry points: `execute(stmt)` runs a statement and returns nothing, and `evaluate(expr)` works out an expression and returns its value. Each node type has its own method, chosen by a dispatch function.

**Global state and nested scope.** Variables live in an `Environment`, which holds a dictionary and a link to its `parent`. Looking up a name walks outward through the parents until it is found. Assignment does the same, so a block can change an outer variable, while `let` always creates a variable in the current scope only, which allows shadowing. Every block, every `if` and `while` body and every function call gets a new `Environment` whose parent is the scope it was created in. `execute_block` swaps the current scope in and restores it in a `finally`, so scope is restored even when an error or a `return` jumps out of the middle of a block.

**Functions.** A `Function` value remembers the environment it was declared in (its closure). A call creates a new `Environment` on top of the closure and defines the parameters in it. `return` is implemented as an exception, `ReturnSignal`, that carries the value up out of nested statements to the call that catches it.

**Semantics worth stating.**

- `int / int` gives an `int` (integer division), any other division gives a `float`. Division by zero is a runtime error.
- `read x;` reads one line and converts it to the current type of `x`. Input that does not fit gives `expected int for 'x', got 'abc'`.
- Conditions must be `bool`, and `and` / `or` short-circuit.
- Comparing different types is an error, except that ints and floats compare with each other.

The type checker catches almost all of these before execution, so the runtime checks are a second line of defence. They are still needed for things types cannot see, such as division by zero and bad user input.

## Transpiler to Python

The transpiler (`transpiler.py`) is a second back end for the same type-checked AST. Instead of running the program it generates Python source text, which is then run by Python itself. Expression methods return strings and statement methods emit lines at the current indentation. `python onlygod.py --emit file.og` prints the generated code and `--py` runs it.

Four problems make it more than a find-and-replace:

1. **Scopes.** OnlyGod blocks have their own variables and Python blocks do not, so `let x` inside a block would overwrite the outer `x`. Every declaration therefore gets a unique Python name (`x`, `x_1`, `x_2` and so on). The transpiler keeps its own scope chain from OnlyGod names to Python names. It also avoids Python keywords and builtins, so a variable called `lambda`, `None` or `str` is still legal. In a declaration like `let x: int = x + 1;` the initializer is translated before the new name is declared, so the right-hand `x` refers to the outer one.
2. **Assignment inside a function.** In Python, `n = 1` inside a function creates a new local unless the function declares `global n` or `nonlocal n`. The transpiler records which outer variables each function assigns to (a module-level variable needs `global`, one in an enclosing function needs `nonlocal`) and inserts those lines at the top of the function body after generating it.
3. **Division and printing.** OnlyGod's `int / int` is integer division and `true` prints as `true`, so `/`, `%`, `print` and the conversions call small helpers (`_og_div`, `_og_mod`, `_og_show`, `_og_toInt` and others) that are copied in front of every generated program.
4. **Empty blocks.** Python needs `pass` where OnlyGod allows `{ }`.

Binary and unary expressions are fully parenthesised, which keeps the translation correct without reasoning about Python's precedence rules.

Example: the scope test program

```
let x: int = 1;
print x;
{ let x: int = 2; print x; }
print x;
```

transpiles to

```
x = 1
print(_og_show(x))
x_1 = 2
print(_og_show(x_1))
print(_og_show(x))
```

The test suite checks the generated program against the interpreter: every example must print exactly the same output both ways.

## Error reporting

OnlyGod's promise is that an error tells you where the problem is, what it is, and, when a fix is known, what to try. Every stage raises or collects an error with the same shape: a message, a line, a column and an optional hint. They are `LexError`, `ParseError`, `OnlyGodTypeError` and `OnlyGodRuntimeError`. The runner (`onlygod.py`) prints all of them the same way: the message with its position, the source line, a caret under the column, and the hint.

Three design rules:

- **The message states the fact, the hint offers a fix.** A hint appears only when a specific fix is known, for example `convert with toInt(...)`. A guess would be wrong often enough to be harmful.
- **Report as many errors as possible at once.** The type checker collects errors and keeps going, so one run shows every type mistake. The lexer and parsers stop at the first error, because after a syntax error the rest of the token stream cannot be trusted.
- **Point at the place the programmer should look.** An unterminated string is reported at its opening quote, and an unclosed block says where it was opened: `expected '}' to close the block opened at line 3, col 5`.

Example of a runtime error that types cannot catch:

```
error: line 2, col 7: division by zero
    print 1 / 0;
          ^
```

The bottom-up parser adds a different kind of message: because the table knows which tokens are legal in the current state, it can say what it expected, for example `unexpected 'int', expected ':'`.

## Testing

Every stage was built test first. Each stage has a test file that prints PASS, FAIL or TODO per test and a total, and all of them run with plain `python test_x.py`.

| Test file | Tests | What it covers |
| --- | --- | --- |
| `test_lexer.py` | 11 | tokens, positions, keywords, errors |
| `test_parser.py` | 12 | expressions, precedence, associativity |
| `test_statements.py` | 18 | every statement and its parse errors |
| `test_interpreter.py` | 28 | evaluation, scope, functions, input, runtime errors |
| `test_typechecker.py` | 31 | every type rule, error positions, hints, recovery |
| `test_transpiler.py` | 28 | generated code runs, scoping, global and nonlocal, output equals the interpreter |
| `test_lrparser.py` | 14 | FIRST and FOLLOW, closure and goto, tables, conflicts, AST equal to the recursive descent AST |

Two tests tie the stages together. The transpiler test runs every example both through the interpreter and through generated Python and compares the output. The bottom-up parser test compares its AST with the recursive descent parser's AST for every test program and example, including line and column numbers, which means the two parsers are interchangeable.

The `examples/` folder holds programs that are run by hand in the demo: `factorial.og`, `fizzbuzz.og`, `scope.og`, `square.og`, `greeting.og` and the error programs `error_demo.og`, `error_undeclared.og`, `error_types.og`, `error_string.og`.

## Limitations and future work

- **One error from the parsers.** The lexer and both parsers stop at the first syntax error. Resynchronising at the next `;` or `}` would let them report several. The error for a missing `;` currently points at the start of the next statement, and should point at the end of the previous one.
- **No arrays, structs or imports.** The language has four basic types and functions, which is enough for the assignment and keeps the grammar small.
- **`read` converts by the variable's current type**, a runtime rule. A typed `read` such as `read x: int;` would move the check to compile time.
- **Tree-walking speed.** The interpreter is not fast. The transpiler removes most of that cost because Python then runs the program directly.
- **Generated code is verbose.** Every expression is parenthesised and every `print` goes through a helper. A cleanup pass that drops redundant parentheses would make the output closer to hand-written Python.
- **A transpiler to Java**, and a table-driven LALR parser with better error recovery, are the natural next steps.
