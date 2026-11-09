"""Run with:  python test_parser.py

Tests compare the AST to a compact text form, e.g. 1 + 2 * 3 becomes
(+ 1 (* 2 3)). The brackets show you how the parser grouped things.
"""
from lexer import Lexer, T
from parser import Parser, ParseError
from ast_nodes import Literal, Variable, Unary, Binary, Call


def show(n):
    if isinstance(n, Literal):
        v = n.value
        if v is True:
            return "true"
        if v is False:
            return "false"
        if isinstance(v, str):
            return f'"{v}"'
        return str(v)
    if isinstance(n, Variable):
        return n.name
    if isinstance(n, Unary):
        return f"({n.op} {show(n.operand)})"
    if isinstance(n, Binary):
        return f"({n.op} {show(n.left)} {show(n.right)})"
    if isinstance(n, Call):
        return "(call " + " ".join([n.name] + [show(a) for a in n.args]) + ")"
    raise AssertionError(f"unknown node {n!r}")


def parse_expr(src):
    p = Parser(Lexer(src).tokenize())
    node = p.expression()
    assert p.at_end(), f"parser stopped early, next token is {p.peek().type.name}"
    return node


def check(src, want):
    got = show(parse_expr(src))
    assert got == want, f"\n source: {src}\n got:    {got}\n want:   {want}"


# ---- the worked example works already once factor() is done ------------

def test_addition_and_variables():
    check("a + 6", "(+ a 6)")


def test_left_associative():
    check("1 - 2 - 3", "(- (- 1 2) 3)")


def test_mul_binds_tighter():
    check("1 + 2 * 3", "(+ 1 (* 2 3))")
    check("10 % 3 * 2", "(* (% 10 3) 2)")


def test_parentheses():
    check("(1 + 2) * 3", "(* (+ 1 2) 3)")


def test_unary():
    check("-x", "(- x)")
    check("- -x", "(- (- x))")
    check("not a and b", "(and (not a) b)")


def test_comparison_and_equality():
    check("1 < 2 == true", "(== (< 1 2) true)")
    check("a >= b != c", "(!= (>= a b) c)")


def test_logic_precedence():
    check("a or b and c", "(or a (and b c))")


def test_literals():
    check('"hi" + "!"', '(+ "hi" "!")')
    check("3.5 * 2", "(* 3.5 2)")


def test_calls():
    check("f()", "(call f)")
    check("f(1, x + 2)", "(call f 1 (+ x 2))")
    check("1 + f(2) * 3", "(+ 1 (* (call f 2) 3))")


def test_positions():
    node = parse_expr("  a + 6")
    assert (node.line, node.col) == (1, 3), f"Binary starts at ({node.line}, {node.col})"


def test_missing_paren():
    try:
        parse_expr("(1 + 2")
    except ParseError as e:
        assert "line 1, col 7" in str(e), f"message was: {e}"
        return
    raise AssertionError("expected ParseError for missing ')'")


def test_missing_operand():
    try:
        parse_expr("1 + ")
    except ParseError as e:
        assert "col 5" in str(e) and "expression" in str(e), f"message was: {e}"
        return
    raise AssertionError("expected ParseError for missing operand")


TESTS = [
    test_addition_and_variables, test_left_associative,
    test_mul_binds_tighter, test_parentheses, test_unary,
    test_comparison_and_equality, test_logic_precedence, test_literals,
    test_calls, test_positions, test_missing_paren, test_missing_operand,
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
