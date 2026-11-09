"""Run with:  python test_lexer.py

Each test prints PASS, FAIL, or TODO (lexer not written yet).
The tests are ordered the same way as the steps in lexer.py.
"""
from lexer import Lexer, LexError, T


def lex(src):
    return Lexer(src).tokenize()


def types(src):
    return [t.type for t in lex(src)]


# ---- step: single-character tokens -------------------------------------

def test_single_chars():
    got = types("(){},:;+-*/%")
    want = [T.LPAREN, T.RPAREN, T.LBRACE, T.RBRACE, T.COMMA, T.COLON,
            T.SEMI, T.PLUS, T.MINUS, T.STAR, T.SLASH, T.PERCENT, T.EOF]
    assert got == want, f"got {[t.name for t in got]}"


def test_whitespace_and_comments_skipped():
    got = types("  ( # a comment\n  ) ")
    assert got == [T.LPAREN, T.RPAREN, T.EOF], f"got {[t.name for t in got]}"


def test_line_and_col_tracking():
    toks = lex("(\n  )")
    assert (toks[0].line, toks[0].col) == (1, 1), "first token position"
    assert (toks[1].line, toks[1].col) == (2, 3), "second token position"


# ---- step: one-or-two-character tokens ---------------------------------

def test_two_char_operators():
    got = types("= == != < <= > >=")
    want = [T.EQ, T.EQEQ, T.BANGEQ, T.LT, T.LE, T.GT, T.GE, T.EOF]
    assert got == want, f"got {[t.name for t in got]}"


# ---- step: strings -----------------------------------------------------

def test_string():
    t = lex('"hi there"')[0]
    assert t.type == T.STRING
    assert t.value == "hi there", f"value was {t.value!r}"
    assert t.lexeme == '"hi there"', f"lexeme was {t.lexeme!r}"


def test_unterminated_string():
    try:
        lex('"hello')
    except LexError as e:
        assert "line 1" in str(e), f"message was: {e}"
        return
    raise AssertionError("expected LexError for unterminated string")


# ---- step: numbers -----------------------------------------------------

def test_numbers():
    a, b = lex("5 3.14")[:2]
    assert a.type == T.NUMBER and a.value == 5 and isinstance(a.value, int)
    assert b.type == T.NUMBER and b.value == 3.14 and isinstance(b.value, float)


# ---- step: identifiers and keywords ------------------------------------

def test_keywords_vs_identifiers():
    got = types("let letter fun print while")
    want = [T.LET, T.IDENT, T.FUN, T.PRINT, T.WHILE, T.EOF]
    assert got == want, f"got {[t.name for t in got]}"


def test_type_names():
    got = types("int float string bool")
    want = [T.TYPE_INT, T.TYPE_FLOAT, T.TYPE_STRING, T.TYPE_BOOL, T.EOF]
    assert got == want, f"got {[t.name for t in got]}"


# ---- step: errors ------------------------------------------------------

def test_unknown_character():
    try:
        lex("let x = @;")
    except LexError as e:
        assert "col 9" in str(e), f"message was: {e}"
        return
    raise AssertionError("expected LexError for '@'")


# ---- the whole thing ---------------------------------------------------

def test_full_statement():
    toks = lex("let x: int = 5 + 3;")
    got = [(t.type.name, t.lexeme, t.line, t.col) for t in toks]
    want = [
        ("LET", "let", 1, 1), ("IDENT", "x", 1, 5), ("COLON", ":", 1, 6),
        ("TYPE_INT", "int", 1, 8), ("EQ", "=", 1, 12), ("NUMBER", "5", 1, 14),
        ("PLUS", "+", 1, 16), ("NUMBER", "3", 1, 18), ("SEMI", ";", 1, 19),
        ("EOF", "", 1, 20),
    ]
    assert got == want, f"\n got:  {got}\n want: {want}"


TESTS = [
    test_single_chars, test_whitespace_and_comments_skipped,
    test_line_and_col_tracking, test_two_char_operators, test_string,
    test_unterminated_string, test_numbers, test_keywords_vs_identifiers,
    test_type_names, test_unknown_character, test_full_statement,
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
