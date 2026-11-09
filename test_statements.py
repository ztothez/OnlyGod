"""Run with:  python test_statements.py

Statements are compared to a compact text form, for example:
    let x: int = 5;          ->  (let x int 5)
    x = x + 1;               ->  (set x (+ x 1))
    while (i < 3) { ... }    ->  (while (< i 3) (block ...))
Expressions inside use the same bracket form as test_parser.py.
"""
from lexer import Lexer
from parser import Parser, ParseError
from ast_nodes import (
    Literal, Variable, Unary, Binary, Call,
    VarDecl, Assign, Print, Read, Block, If, While, Return, ExprStmt,
    FunDecl, Program,
)


def show_expr(n):
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
        return f"({n.op} {show_expr(n.operand)})"
    if isinstance(n, Binary):
        return f"({n.op} {show_expr(n.left)} {show_expr(n.right)})"
    if isinstance(n, Call):
        return "(call " + " ".join([n.name] + [show_expr(a) for a in n.args]) + ")"
    raise AssertionError(f"unknown expression node {n!r}")


def show(n):
    if isinstance(n, Program):
        return "(program" + "".join(" " + show(s) for s in n.statements) + ")"
    if isinstance(n, VarDecl):
        return f"(let {n.name} {n.type_name} {show_expr(n.init)})"
    if isinstance(n, Assign):
        return f"(set {n.name} {show_expr(n.value)})"
    if isinstance(n, Print):
        return f"(print {show_expr(n.value)})"
    if isinstance(n, Read):
        return f"(read {n.name})"
    if isinstance(n, ExprStmt):
        return f"(expr {show_expr(n.expr)})"
    if isinstance(n, Return):
        return "(return)" if n.value is None else f"(return {show_expr(n.value)})"
    if isinstance(n, Block):
        return "(block" + "".join(" " + show(s) for s in n.statements) + ")"
    if isinstance(n, If):
        out = f"(if {show_expr(n.cond)} {show(n.then_block)}"
        if n.else_block is not None:
            out += " " + show(n.else_block)
        return out + ")"
    if isinstance(n, While):
        return f"(while {show_expr(n.cond)} {show(n.body)})"
    if isinstance(n, FunDecl):
        params = " ".join(f"{p.name}:{p.type_name}" for p in n.params)
        return f"(fun {n.name} ({params}) {n.return_type} {show(n.body)})"
    raise AssertionError(f"unknown statement node {n!r}")


def parse_program(src):
    return Parser(Lexer(src).tokenize()).parse()


def check(src, want):
    got = show(parse_program(src))
    assert got == "(program " + want + ")" or got == "(program)" and want == "", (
        f"\n source: {src}\n got:    {got}\n want:   (program {want})"
    )


def expect_error(src, *fragments):
    try:
        parse_program(src)
    except ParseError as e:
        for f in fragments:
            assert f in str(e), f"message was: {e}   (missing {f!r})"
        return
    raise AssertionError(f"expected a ParseError for: {src!r}")


# ---- simple statements ---------------------------------------------------

def test_var_decl():
    check("let x: int = 5;", "(let x int 5)")


def test_assign():
    check("x = x + 1;", "(set x (+ x 1))")


def test_print():
    check("print a + 6;", "(print (+ a 6))")


def test_read():
    check("read n;", "(read n)")


def test_expression_statement():
    check("f(1);", "(expr (call f 1))")
    check("x == 1;", "(expr (== x 1))")      # '==' is NOT an assignment


# ---- blocks and control flow ---------------------------------------------

def test_block():
    check("{ print 1; print 2; }", "(block (print 1) (print 2))")


def test_if():
    check("if (x < 3) { print x; }", "(if (< x 3) (block (print x)))")


def test_if_else():
    check("if (x) { print 1; } else { print 2; }",
          "(if x (block (print 1)) (block (print 2)))")


def test_while():
    check("while (i < 3) { i = i + 1; }",
          "(while (< i 3) (block (set i (+ i 1))))")


# ---- functions -----------------------------------------------------------

def test_fun():
    check("fun add(a: int, b: int): int { return a + b; }",
          "(fun add (a:int b:int) int (block (return (+ a b))))")


def test_fun_no_params_bare_return():
    check("fun nothing(): int { return; }",
          "(fun nothing () int (block (return)))")


# ---- whole programs and positions ----------------------------------------

def test_program_of_several_statements():
    check("let x: int = 5; print x + 3;",
          "(let x int 5) (print (+ x 3))")


def test_nested_scopes_parse():
    check("{ let x: int = 1; { print x; } }",
          "(block (let x int 1) (block (print x)))")


def test_node_positions():
    prog = parse_program("\n  let x: int = 1;")
    node = prog.statements[0]
    assert (node.line, node.col) == (2, 3), f"VarDecl starts at ({node.line}, {node.col})"


# ---- error messages ------------------------------------------------------

def test_missing_semicolon():
    expect_error("print 1", "line 1, col 8", "';'")


def test_missing_type():
    expect_error("let x = 5;", "line 1, col 7", "':'", "type")


def test_unclosed_block():
    expect_error("{ print 1;", "line 1, col 11", "'}'", "line 1, col 1")


def test_if_without_paren():
    expect_error("if x < 3 { }", "line 1, col 4", "'('")


TESTS = [
    test_var_decl, test_assign, test_print, test_read,
    test_expression_statement, test_block, test_if, test_if_else,
    test_while, test_fun, test_fun_no_params_bare_return,
    test_program_of_several_statements, test_nested_scopes_parse,
    test_node_positions, test_missing_semicolon, test_missing_type,
    test_unclosed_block, test_if_without_paren,
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
