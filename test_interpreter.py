"""Run with:  python test_interpreter.py

Each test runs a tiny OnlyGod program and compares what it PRINTS (a list of
lines) to what it should print. The fake input/output means no typing needed.
"""
from lexer import Lexer
from parser import Parser
from interpreter import Interpreter, OnlyGodRuntimeError


def run(src, inputs=()):
    out = []
    pending = iter(inputs)

    def fake_input():
        try:
            return next(pending)
        except StopIteration:
            raise EOFError

    program = Parser(Lexer(src).tokenize()).parse()
    Interpreter(input_fn=fake_input, output_fn=out.append).run(program)
    return out


def check(src, want, inputs=()):
    got = run(src, inputs)
    assert got == want, f"\n source: {src}\n got:    {got}\n want:   {want}"


def expect_error(src, *fragments, hint=None, inputs=()):
    try:
        run(src, inputs)
    except OnlyGodRuntimeError as e:
        for f in fragments:
            assert f in str(e), f"message was: {e}   (missing {f!r})"
        if hint is not None:
            assert e.hint and hint in e.hint, f"hint was: {e.hint!r}   (missing {hint!r})"
        return
    raise AssertionError(f"expected an OnlyGodRuntimeError for: {src!r}")


# ---- expressions, variables, state ----------------------------------------

def test_arithmetic():
    check("print 1 + 2 * 3;", ["7"])


def test_variables():
    check("let x: int = 5; print x + 3;", ["8"])


def test_assignment():
    check("let x: int = 1; x = x + 1; print x;", ["2"])


def test_strings():
    check('print "hi" + "!";', ["hi!"])


def test_division_and_modulo():
    check("print 7 / 2; print 7.0 / 2; print 10 % 3;", ["3", "3.5", "1"])


def test_booleans_and_comparison():
    check("print 1 < 2; print not true; print 3 == 3;", ["true", "false", "true"])


def test_short_circuit():
    # the right side would crash with division by zero if it were evaluated
    check("print false and (1 / 0 == 1); print true or (1 / 0 == 1);",
          ["false", "true"])


def test_builtins():
    check('print toInt("42") + 1; print toString(3) + "x";', ["43", "3x"])


# ---- control flow ---------------------------------------------------------

def test_if_else():
    check('let x: int = 5; if (x > 3) { print "big"; } else { print "small"; }',
          ["big"])


def test_while_loop():
    check("let i: int = 0; let sum: int = 0; "
          "while (i < 5) { i = i + 1; sum = sum + i; } print sum;", ["15"])


def test_read_input():
    check("let n: int = 0; read n; print n * 2;", ["42"], inputs=["21"])


# ---- functions --------------------------------------------------------------

def test_function_call():
    check("fun add(a: int, b: int): int { return a + b; } print add(2, 3);", ["5"])


def test_recursion():
    check("fun fact(n: int): int { if (n <= 1) { return 1; } return n * fact(n - 1); } "
          "print fact(5);", ["120"])


def test_function_sees_globals():
    check("let g: int = 10; fun f(): int { return g + 1; } print f();", ["11"])


def test_function_statement_call():
    check('fun hello(): int { print "hi"; return 0; } hello();', ["hi"])


# ---- nested scope -----------------------------------------------------------

def test_block_shadowing():
    check("let x: int = 1; { let x: int = 2; print x; } print x;", ["2", "1"])


def test_block_changes_outer_variable():
    check("let x: int = 1; { x = 5; } print x;", ["5"])


def test_function_locals_do_not_leak():
    expect_error("fun f(): int { let secret: int = 1; return secret; } f(); print secret;",
                 "'secret' is not declared")


# ---- errors: line, column and a useful message --------------------------------

def test_error_type_mismatch():
    expect_error('let count: int = 1; print count + "5";',
                 "line 1, col 27", "cannot add int to string", hint="toString")


def test_error_undeclared_variable():
    expect_error("print y;", "line 1, col 7", "'y' is not declared", hint="let y")


def test_error_redeclared_variable():
    expect_error("let x: int = 1; let x: int = 2;",
                 "line 1, col 17", "already declared")


def test_error_division_by_zero():
    expect_error("print 1 / 0;", "line 1, col 7", "division by zero")


def test_error_compare_mixed_types():
    expect_error('print 1 == "1";', "cannot compare int with string")


def test_error_wrong_argument_count():
    expect_error("fun f(a: int): int { return a; } print f(1, 2);",
                 "line 1, col 40", "f expects 1 argument", "got 2")


def test_error_condition_not_bool():
    expect_error("if (1) { print 1; }", "line 1, col 5", "the condition must be bool, got int")


def test_error_bad_read_input():
    expect_error("let n: int = 0; read n;", "line 1, col 17", "expected int", "abc",
                 inputs=["abc"])


def test_error_return_outside_function():
    expect_error("return 1;", "line 1, col 1", "return outside a function")


def test_error_not_a_function():
    expect_error("let x: int = 1; x();", "line 1, col 17", "x is not a function")


TESTS = [
    test_arithmetic, test_variables, test_assignment, test_strings,
    test_division_and_modulo, test_booleans_and_comparison, test_short_circuit,
    test_builtins, test_if_else, test_while_loop, test_read_input,
    test_function_call, test_recursion, test_function_sees_globals,
    test_function_statement_call, test_block_shadowing,
    test_block_changes_outer_variable, test_function_locals_do_not_leak,
    test_error_type_mismatch, test_error_undeclared_variable,
    test_error_redeclared_variable, test_error_division_by_zero,
    test_error_compare_mixed_types, test_error_wrong_argument_count,
    test_error_condition_not_bool, test_error_bad_read_input,
    test_error_return_outside_function, test_error_not_a_function,
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
