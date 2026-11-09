"""Run with:  python test_lrparser.py

Part A tests the table construction on small textbook grammars.
Part B checks the finished parser: it must build EXACTLY the same AST as your
recursive descent parser (same nodes, same line and column), and report
syntax errors.
"""
import os

from lexer import Lexer, LexError
from parser import Parser, ParseError
from lrparser import (compute_nullable_first, compute_follow, closure, goto,
                      build_tables, LRParser)

# E' -> E ; E -> E + T | T ; T -> T * F | F ; F -> ( E ) | id
EXPR = [
    ("E'", ("E",)),
    ("E", ("E", "+", "T")),      # 1
    ("E", ("T",)),               # 2
    ("T", ("T", "*", "F")),      # 3
    ("T", ("F",)),               # 4
    ("F", ("(", "E", ")")),      # 5
    ("F", ("id",)),              # 6
]
# S -> A b ; A -> a | (empty)
EMPTY = [("S'", ("S",)), ("S", ("A", "b")), ("A", ("a",)), ("A", ())]


# ---- Part A: the generator -----------------------------------------------

def test_nullable_and_first():
    nullable, first = compute_nullable_first(EMPTY)
    assert nullable == {"A"}, f"nullable was {nullable}"
    assert first["S"] == {"a", "b"}, f"first(S) was {first['S']}"
    assert first["a"] == {"a"}, "the first set of a terminal is the terminal itself"
    nullable, first = compute_nullable_first(EXPR)
    assert nullable == set()
    assert first["E"] == {"(", "id"} and first["F"] == {"(", "id"}


def test_follow():
    nullable, first = compute_nullable_first(EXPR)
    follow = compute_follow(EXPR, nullable, first)
    assert follow["E"] == {"+", ")", "EOF"}, f"follow(E) was {follow['E']}"
    assert follow["T"] == {"+", "*", ")", "EOF"}, f"follow(T) was {follow['T']}"
    nullable, first = compute_nullable_first(EMPTY)
    follow = compute_follow(EMPTY, nullable, first)
    assert follow["A"] == {"b"}, f"follow(A) was {follow['A']}"


def test_closure():
    state0 = closure({(0, 0)}, EXPR)
    assert state0 == {(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0)}, sorted(state0)


def test_goto():
    state0 = closure({(0, 0)}, EXPR)
    assert goto(state0, "E", EXPR) == {(0, 1), (1, 1)}, "after E: E' -> E .  and  E -> E . + T"
    assert goto(state0, "+", EXPR) == frozenset()
    after_paren = goto(state0, "(", EXPR)
    assert len(after_paren) == 7 and (5, 1) in after_paren, sorted(after_paren)


def test_tables_textbook_grammar():
    action, goto_table = build_tables(EXPR)
    assert len(action) == 12 and len(goto_table) == 12, f"expected 12 states, got {len(action)}"
    assert action[0]["id"][0] == "shift" and action[0]["("][0] == "shift"
    assert goto_table[0]["E"] != goto_table[0]["T"]
    accepts = [s for s, row in enumerate(action) if row.get("EOF") == ("accept",)]
    assert len(accepts) == 1, "exactly one state accepts"


def test_tables_with_empty_production():
    action, _ = build_tables(EMPTY)
    assert action[0]["b"] == ("reduce", 3), "A -> (empty) is reduced when b comes next"


def test_conflict_is_detected():
    ambiguous = [("E'", ("E",)), ("E", ("E", "+", "E")), ("E", ("id",))]
    try:
        build_tables(ambiguous)
    except ValueError as e:
        assert "conflict" in str(e)
    else:
        raise AssertionError("E -> E + E is ambiguous, build_tables should raise ValueError")


def test_onlygod_grammar_has_no_conflicts():
    from lrparser import PRODUCTIONS
    build_tables(PRODUCTIONS)


# ---- Part B: the parser --------------------------------------------------------

PROGRAMS = [
    "",
    "print 1;",
    "print 1 + 2 * 3 - 4 / 2 % 3;",
    "print 1 - 2 - 3;",
    "print (1 + 2) * 3;",
    "print -1 + -(2);",
    "print not true or false and true;",
    "print 1 < 2 == true;",
    'print "a" + "b" != "c";',
    "let x: int = 5; x = x + 1; print x;",
    "let f: float = 2.5; let s: string = \"hi\"; let b: bool = true;",
    "read x;",
    "f(); f(1); f(1, 2 + 3, g(4));",
    "return; return 1 + 1;",
    "{ }",
    "{ let x: int = 1; { print x; } }",
    "if (x > 1) { print 1; }",
    "if (x > 1) { print 1; } else { print 2; }",
    "while (i < 3) { i = i + 1; }",
    "fun f(): int { return 1; }",
    "fun add(a: int, b: float): float { return a + b; }",
    "fun outer(): int { fun inner(): int { return 1; } return inner(); }",
    "print\n  1 +\n    2;\nprint 3;",
]


def tokens_of(src):
    return Lexer(src).tokenize()


def test_same_ast_as_recursive_descent():
    for src in PROGRAMS:
        expected = Parser(tokens_of(src)).parse()
        got = LRParser(tokens_of(src)).parse()
        assert got == expected, f"different AST for: {src!r}\n expected {expected}\n got      {got}"


def test_same_ast_for_example_programs():
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
    if not os.path.isdir(folder):
        return
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".og"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            src = f.read()
        try:
            tokens = tokens_of(src)
        except LexError:
            continue
        assert LRParser(tokens).parse() == Parser(tokens_of(src)).parse(), f"{name}: AST differs"


def syntax_error(src):
    try:
        LRParser(tokens_of(src)).parse()
    except ParseError as e:
        return e
    raise AssertionError(f"expected a ParseError for: {src!r}")


def test_error_unexpected_token():
    e = syntax_error("print 1 +;")
    assert "unexpected ';'" in str(e) and (e.line, e.col) == (1, 10), str(e)


def test_error_lists_what_was_expected():
    e = syntax_error("let x int = 1;")
    assert "unexpected 'int'" in str(e) and "':'" in str(e), str(e)
    assert (e.line, e.col) == (1, 7), str(e)


def test_error_at_end_of_input():
    e = syntax_error("print 1")
    assert "unexpected end of input" in str(e), str(e)


def test_error_unclosed_block():
    e = syntax_error("if (true) { print 1;")
    assert "unexpected end of input" in str(e), str(e)


TESTS = [
    test_nullable_and_first, test_follow, test_closure, test_goto,
    test_tables_textbook_grammar, test_tables_with_empty_production,
    test_conflict_is_detected, test_onlygod_grammar_has_no_conflicts,
    test_same_ast_as_recursive_descent, test_same_ast_for_example_programs,
    test_error_unexpected_token, test_error_lists_what_was_expected,
    test_error_at_end_of_input, test_error_unclosed_block,
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
