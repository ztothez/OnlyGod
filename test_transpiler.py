"""Run with:  python test_transpiler.py

Each test transpiles an OnlyGod program to Python, RUNS the generated Python
with fake input, and checks what it printed. A few tests look at the
generated text itself.
"""
import os

from lexer import Lexer
from parser import Parser
from transpiler import Transpiler
from interpreter import Interpreter


def to_python(src):
    return Transpiler().transpile(Parser(Lexer(src).tokenize()).parse())


def run(src, inputs=()):
    """Transpile, run the generated Python, return the printed lines."""
    code = to_python(src)
    out = []
    feed = iter(inputs)
    namespace = {"print": out.append, "input": lambda: next(feed)}
    exec(compile(code, "<onlygod>", "exec"), namespace)
    return out


def check(src, expected, inputs=()):
    got = run(src, inputs)
    assert got == expected, f"expected {expected}, got {got}\n--- generated:\n{to_python(src)}"


# ---- expressions -----------------------------------------------------------

def test_print_and_arithmetic():
    check("print 1 + 2 * 3; print 2 * (3 + 4); print -5 + 2;", ["7", "14", "-3"])


def test_division_rules():
    check("print 7 / 2; print 7.0 / 2; print 10 % 3;", ["3", "3.5", "1"])


def test_strings_and_bools():
    check('print "a" + "b"; print not true; print 1 < 2 and 2 < 3; print 1 == 1.0;',
          ["ab", "false", "true", "true"])


def test_short_circuit():
    check("print false and 1 / 0 == 1; print true or 1 / 0 == 1;", ["false", "true"])


def test_builtins():
    check('print toInt("42") + 1; print toString(5) + "!"; print toFloat(3);',
          ["43", "5!", "3.0"])


def test_division_by_zero_is_reported():
    try:
        run("print 1 / 0;")
    except ZeroDivisionError as e:
        assert "division by zero" in str(e)
    else:
        raise AssertionError("expected a division by zero error")


# ---- statements ------------------------------------------------------------

def test_variables_and_assignment():
    check("let x: int = 1; x = x + 4; print x;", ["5"])


def test_if_else():
    check("let n: int = 5; if (n > 3) { print 1; } else { print 2; } "
          "if (n > 9) { print 3; } else { print 4; }", ["1", "4"])


def test_empty_blocks_need_pass():
    check("if (true) { } else { } while (false) { } { } print 1;", ["1"])


def test_while_loop():
    check("let i: int = 0; let sum: int = 0; while (i < 5) { i = i + 1; sum = sum + i; } print sum;",
          ["15"])


def test_read_by_type():
    check("let n: int = 0; read n; print n * 2;", ["42"], ["21"])
    check('let s: string = ""; read s; print "hi " + s;', ["hi Bob"], ["Bob"])
    check("let f: float = 0.0; read f; print f + 1.0;", ["3.5"], ["2.5"])


def test_read_bad_input():
    try:
        run("let n: int = 0; read n;", ["abc"])
    except ValueError as e:
        assert "expected int" in str(e)
    else:
        raise AssertionError("expected an error for bad input")


# ---- functions -------------------------------------------------------------

def test_function_and_return():
    check("fun add(a: int, b: int): int { return a + b; } print add(2, 3);", ["5"])


def test_recursion():
    check("fun fact(n: int): int { if (n <= 1) { return 1; } return n * fact(n - 1); } print fact(5);",
          ["120"])


def test_empty_function_body():
    check("fun f(): int { } f(); print 1;", ["1"])


# ---- scopes (problem 1) ------------------------------------------------------

def test_shadowing_in_block():
    check("let x: int = 1; { let x: int = 2; print x; } print x;", ["2", "1"])


def test_shadowing_uses_outer_value_in_initializer():
    check("let x: int = 1; { let x: int = x + 1; print x; } print x;", ["2", "1"])


def test_block_assigns_outer_variable():
    check("let x: int = 1; { x = 5; } print x;", ["5"])


def test_parameter_shadows_global():
    check("let n: int = 100; fun f(n: int): int { return n + 1; } print f(1); print n;", ["2", "100"])


def test_python_keywords_and_builtins_as_names():
    check("let lambda: int = 3; let None: int = 4; let str: int = 5; print lambda + None + str;", ["12"])


def test_name_clash_with_generated_name():
    check("let x: int = 1; { let x: int = 2; let x_1: int = 3; print x + x_1; } print x;", ["5", "1"])


# ---- global / nonlocal (problem 2) ---------------------------------------------

def test_function_writes_global():
    check("let n: int = 0; fun inc(): int { n = n + 1; return n; } inc(); inc(); print n;", ["2"])


def test_function_reads_into_global():
    check("let n: int = 0; fun load(): int { read n; return n; } load(); print n;", ["7"], ["7"])


def test_function_writes_enclosing_function_variable():
    check("fun outer(): int { let c: int = 0; fun bump(): int { c = c + 1; return c; } "
          "bump(); bump(); return c; } print outer();", ["2"])


def test_global_write_two_levels_deep():
    check("let g: int = 0; fun a(): int { fun b(): int { g = 9; return g; } return b(); } "
          "print a(); print g;", ["9", "9"])


# ---- the generated text ----------------------------------------------------------------

def test_output_is_valid_python():
    code = to_python("let x: int = 1; while (x < 3) { x = x + 1; } fun f(): int { return 1; }")
    compile(code, "<onlygod>", "exec")


def test_block_variable_gets_new_python_name():
    code = to_python("let x: int = 1; { let x: int = 2; }")
    assert "x = 1" in code and "x_1 = 2" in code, code


# ---- the real example programs: transpiled == interpreted ------------------------------------

def test_examples_match_interpreter():
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
    if not os.path.isdir(folder):
        return
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".og") or name.startswith("error"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            src = f.read()
        out = []
        feed = iter(["4"])
        Interpreter(input_fn=lambda: next(feed), output_fn=out.append).run(
            Parser(Lexer(src).tokenize()).parse())
        assert run(src, ["4"]) == out, f"{name}: transpiled output differs from the interpreter"


TESTS = [
    test_print_and_arithmetic, test_division_rules, test_strings_and_bools,
    test_short_circuit, test_builtins, test_division_by_zero_is_reported,
    test_variables_and_assignment, test_if_else, test_empty_blocks_need_pass,
    test_while_loop, test_read_by_type, test_read_bad_input,
    test_function_and_return, test_recursion, test_empty_function_body,
    test_shadowing_in_block, test_shadowing_uses_outer_value_in_initializer,
    test_block_assigns_outer_variable, test_parameter_shadows_global,
    test_python_keywords_and_builtins_as_names, test_name_clash_with_generated_name,
    test_function_writes_global, test_function_reads_into_global,
    test_function_writes_enclosing_function_variable, test_global_write_two_levels_deep,
    test_output_is_valid_python, test_block_variable_gets_new_python_name,
    test_examples_match_interpreter,
]


def main():
    passed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except NotImplementedError:
            print(f"TODO  {fn.__name__}")
        except Exception as e:
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{passed}/{len(TESTS)} passing")


if __name__ == "__main__":
    main()
