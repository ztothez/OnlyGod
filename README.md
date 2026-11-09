# OnlyGod

OnlyGod is a small, statically typed programming language with its own compiler pipeline, written in Python. Source files use the `.og` extension.

It was built for a programming language course at the University of Turku. The project includes two parsers, a type checker, a tree-walking interpreter and a transpiler to Python.

```
let n: int = 5;
print "total: " + toString(n * 2);
```

## Where the idea came from

Every programmer has seen this comment, in some form, above a scary piece of code:

```
// When I wrote this, only God and I understood what I was doing.
// Now, only God knows.
```

It is funny because it is true. Most languages give you an error that says something like `SyntaxError: invalid syntax` and leave you to work out the rest, so after a few hours the only one who knows what went wrong is God.

When the course asked us to design our own language, that joke became the design brief. **OnlyGod** is the language where God is not the only one who knows:

- every error says which line and column it is on, shows the line with a caret, and says what it expected
- the type checker reports all type mistakes together, and gives a hint only when it really knows a fix
- nothing runs until the whole program has passed the checks, so there are no half-finished runs
- the pipeline is small enough to read from start to end, so the compiler itself has no secrets either

The name was checked before it was chosen. There was no existing language called OnlyGod, only unrelated projects with God in the name. The file extension is `.og`, and the one-line pitch is: *the language where only God knew why it broke, until now.*

## Quick start

Requires Python 3.10 or newer. There are no external dependencies.

```bash
python onlygod.py examples/factorial.og
```

| Command | What it does |
| --- | --- |
| `python onlygod.py file.og` | Type check, then run with the interpreter |
| `python onlygod.py --py file.og` | Type check, transpile to Python, then run the generated code |
| `python onlygod.py --emit file.og` | Print the generated Python without running it |
| `python onlygod.py --bottomup file.og` | Use the bottom-up (SLR) parser instead of the recursive descent parser |

Programs that read input work from a pipe too:

```bash
echo Roosa | python onlygod.py examples/greeting.og
```

## The language

```
# comments start with a hash
fun fact(n: int): int {
    if (n <= 1) { return 1; }
    return n * fact(n - 1);
}

let n: int = 5;
print fact(n);
```

| Feature | Syntax |
| --- | --- |
| Types | `int`, `float`, `string`, `bool` |
| Variables | `let x: int = 1;` and `x = 2;` |
| Output and input | `print expr;` and `read x;` (input is converted to the variable's type) |
| Conditions | `if (cond) { ... } else { ... }` |
| Loops | `while (cond) { ... }` |
| Functions | `fun name(a: int, b: string): bool { ... return ...; }` |
| Scope | Every `{ ... }` block has its own scope, and functions are closures |
| Operators | `+ - * / %`, `== != < <= > >=`, `and or not` |
| Built-ins | `toInt`, `toFloat`, `toString` |

Type rules:

1. There are no implicit conversions.
2. `int` with `int` gives `int`, otherwise `float`. Ints and floats can be compared with each other.
3. `+` also joins strings.
4. Conditions, `and`, `or` and `not` need `bool`.
5. Function calls and `return` must match the declared types.

## Error messages

Every error shows the line, the column, the source line and a caret. A hint appears only when a fix is known.

```
error: line 3, col 7: cannot add string to int
    print "total: " + age;
          ^
    hint: convert with toInt(...) or toString(...)
```

The type checker reports all type errors together and runs before the program starts, so a program with a type error never executes. See `examples/error_*.og` for lexical, syntax, undeclared variable and type errors.

## How it works

```
source -> Lexer -> tokens -> Parser or LRParser -> AST -> TypeChecker -> Interpreter
                                                                      \-> Transpiler -> Python
```

| File | Role |
| --- | --- |
| `lexer.py` | Turns characters into tokens with line and column |
| `ast_nodes.py` | AST node dataclasses shared by every stage |
| `parser.py` | Top-down recursive descent parser, one method per grammar rule |
| `lrparser.py` | Bottom-up SLR(1) parser, with tables generated from the grammar |
| `typechecker.py` | Static type checker with error recovery |
| `interpreter.py` | Tree-walking interpreter with scope chain and closures |
| `transpiler.py` | Generates Python, keeping block scope with unique names and `global` / `nonlocal` |
| `onlygod.py` | Command line runner |

Both parsers build exactly the same AST, line and column included, and the tests compare them node by node.

## Tests

Each stage has its own test file. Run them all with:

```bash
for t in lexer parser statements interpreter typechecker transpiler lrparser; do
  python test_$t.py
done
```

| Suite | Tests |
| --- | --- |
| `test_lexer.py` | 11 |
| `test_parser.py` | 12 |
| `test_statements.py` | 18 |
| `test_interpreter.py` | 28 |
| `test_typechecker.py` | 31 |
| `test_transpiler.py` | 28 |
| `test_lrparser.py` | 14 |
| **Total** | **142** |

## Examples

| File | Shows |
| --- | --- |
| `examples/factorial.og` | Recursive function and a `while` loop |
| `examples/fizzbuzz.og` | Loops, `if` / `else`, modulo |
| `examples/scope.og` | Nested block scope |
| `examples/greeting.og` | Strings, a function with a parameter, input |
| `examples/square.og` | Reading a number and computing with it |
| `examples/error_*.og` | One example for each kind of error |

## Known limitations

- Both parsers stop at the first syntax error. Type errors are reported together.
- A missing `;` is reported at the start of the next statement, not at the end of the previous line.

Ideas for later: several syntax errors per run by resynchronising at `;` and `}`, and a Java back end.

## Author

Roosa Yöruusu, University of Turku.
