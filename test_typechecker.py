"""Run with:  python test_typechecker.py

The checker never runs the program. It only reads it and returns a list of
errors, so every test is: parse a program, check it, look at the errors.
"""
import os

from lexer import Lexer
from parser import Parser
from typechecker import TypeChecker


def check(src):
    program = Parser(Lexer(src).tokenize()).parse()
    return TypeChecker().check(program)


def ok(src):
    errors = check(src)
    assert errors == [], f"expected no errors for: {src!r}\n got: {[str(e) for e in errors]}"


def bad(src, *fragments, hint=None, count=1):
    errors = check(src)
    assert len(errors) == count, (
        f"expected {count} error(s) for: {src!r}\n got {len(errors)}: {[str(e) for e in errors]}"
    )
    first = errors[0]
    for f in fragments:
        assert f in str(first), f"message was: {first}   (missing {f!r})"
    if hint is not None:
        assert first.hint and hint in first.hint, f"hint was: {first.hint!r}   (missing {hint!r})"


# ---- programs that are fine ------------------------------------------------

def test_valid_declarations():
    ok('let a: int = 1; let b: float = 2.5; let s: string = "x"; let t: bool = true;')


def test_valid_arithmetic_and_comparison():
    ok("let x: int = 1 + 2 * 3; let y: float = x + 0.5; print y; print x == 1.0; print x < y;")


def test_valid_function():
    ok("fun add(a: int, b: int): int { return a + b; } let r: int = add(1, 2); print r;")


def test_valid_recursion():
    ok("fun fact(n: int): int { if (n <= 1) { return 1; } return n * fact(n - 1); } print fact(5);")


def test_valid_scopes():
    ok('let x: int = 1; { let x: string = "s"; print x; } print x + 1;')


def test_valid_builtins():
    ok('let n: int = toInt("5") + 1; let s: string = toString(n); let f: float = toFloat(n);')


# ---- declarations and assignments -------------------------------------------

def test_declared_type_mismatch():
    bad('let x: int = "hello";', "line 1, col 14",
        "cannot put string into 'x', which is int", hint="toInt")


def test_float_into_int():
    bad("let x: int = 2.5;", "line 1, col 14", "cannot put float into 'x', which is int",
        hint="toInt")


def test_int_does_not_widen_to_float():
    bad("let f: float = 5;", "line 1, col 16", "cannot put int into 'f', which is float",
        hint="toFloat")


def test_assign_mismatch():
    bad('let x: int = 1; x = "a";', "line 1, col 21",
        "cannot put string into 'x', which is int", hint="toInt")


def test_undeclared_variable():
    bad("print y;", "line 1, col 7", "'y' is not declared", hint="let y")


def test_assign_to_undeclared():
    bad("z = 1;", "line 1, col 1", "'z' is not declared")


def test_redeclared_variable():
    bad("let x: int = 1; let x: int = 2;", "line 1, col 17", "already declared")


def test_variable_does_not_leak_out_of_block():
    bad("{ let inner: int = 1; } print inner;", "'inner' is not declared")


# ---- expressions ----------------------------------------------------------------

def test_int_plus_string():
    bad('let count: int = 1; print count + "5";', "line 1, col 27",
        "cannot add int to string", hint="toString")


def test_compare_mixed_types():
    bad('print 1 == "1";', "line 1, col 7", "cannot compare int with string")


def test_arithmetic_on_string():
    bad('print "a" - 1;', "cannot use '-' on string and int")


def test_logic_needs_bool():
    bad("print 1 and true;", "line 1, col 7", "the left side of 'and' must be bool, got int")


def test_unary_errors():
    errors = check('print -"a"; print not 1;')
    assert len(errors) == 2, f"got {[str(e) for e in errors]}"
    assert "cannot negate string" in str(errors[0]), str(errors[0])
    assert "the operand of 'not' must be bool, got int" in str(errors[1]), str(errors[1])


# ---- control flow ------------------------------------------------------------------

def test_if_condition_not_bool():
    bad("if (1) { print 1; }", "line 1, col 5", "the condition must be bool, got int")


def test_while_condition_not_bool():
    bad("while (1 + 1) { }", "line 1, col 8", "the condition must be bool, got int")


# ---- functions -------------------------------------------------------------------------

def test_wrong_argument_type():
    bad('fun f(a: int): int { return a; } print f("x");', "line 1, col 42",
        "argument 1 of f must be int, got string", hint="toInt")


def test_wrong_argument_count():
    bad("fun f(a: int): int { return a; } print f(1, 2);", "line 1, col 40",
        "f expects 1 argument, got 2")


def test_return_type_mismatch():
    bad('fun f(): int { return "s"; }', "line 1, col 23", "f must return int, got string",
        hint="toInt")


def test_bare_return_in_typed_function():
    bad("fun f(): int { return; }", "line 1, col 16", "f must return int")


def test_return_outside_function():
    bad("return 1;", "line 1, col 1", "return outside a function")


def test_not_a_function():
    bad("let x: int = 1; x();", "line 1, col 17", "x is not a function")


def test_call_undeclared_function():
    bad("print nope(1);", "line 1, col 7", "'nope' is not declared")


# ---- error recovery ----------------------------------------------------------------------------

def test_reports_all_errors_in_order():
    errors = check('let a: int = "x";\nlet b: string = 5;\nprint c;')
    assert [e.line for e in errors] == [1, 2, 3], f"got {[str(e) for e in errors]}"
    assert "cannot put string into 'a'" in str(errors[0]), str(errors[0])
    assert "cannot put int into 'b'" in str(errors[1]), str(errors[1])
    assert "'c' is not declared" in str(errors[2]), str(errors[2])


def test_no_cascading_errors():
    # one mistake in the expression must not ALSO complain about the declaration
    bad('let x: int = "a" + 1;', "cannot add string to int")


# ---- the real example programs -------------------------------------------------------------------

def test_example_programs():
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
    if not os.path.isdir(folder):
        return
    must_have_errors = {"error_demo.og", "error_undeclared.og", "error_types.og"}
    skip = {"error_string.og"}       # fails in the lexer, never reaches the checker
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".og") or name in skip:
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            errors = check(f.read())
        if name in must_have_errors:
            assert errors, f"{name} should have type errors"
        else:
            assert errors == [], f"{name} should be clean, got {[str(e) for e in errors]}"


TESTS = [
    test_valid_declarations, test_valid_arithmetic_and_comparison,
    test_valid_function, test_valid_recursion, test_valid_scopes,
    test_valid_builtins, test_declared_type_mismatch, test_float_into_int,
    test_int_does_not_widen_to_float, test_assign_mismatch,
    test_undeclared_variable, test_assign_to_undeclared,
    test_redeclared_variable, test_variable_does_not_leak_out_of_block,
    test_int_plus_string, test_compare_mixed_types, test_arithmetic_on_string,
    test_logic_needs_bool, test_unary_errors, test_if_condition_not_bool,
    test_while_condition_not_bool, test_wrong_argument_type,
    test_wrong_argument_count, test_return_type_mismatch,
    test_bare_return_in_typed_function, test_return_outside_function,
    test_not_a_function, test_call_undeclared_function,
    test_reports_all_errors_in_order, test_no_cascading_errors,
    test_example_programs,
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
