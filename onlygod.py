"""OnlyGod: run a program.

    python onlygod.py hello.og                 interpret it (tree-walker)
    python onlygod.py --py hello.og            transpile to Python, then run that
    python onlygod.py --emit hello.og          only print the generated Python
    python onlygod.py --bottomup hello.og      parse with the bottom-up (LR) parser
                                               (combine with any of the above)

Pipeline:
    source -> Lexer -> tokens -> Parser or LRParser -> AST -> TypeChecker
           -> Interpreter                       (default)
           -> Transpiler -> Python text -> run  (--py)

The type checker runs BEFORE anything executes. If it finds mistakes, they
are all printed and the program is not run at all.
"""
import sys

from lexer import Lexer, LexError
from parser import Parser, ParseError
from typechecker import TypeChecker
from interpreter import Interpreter, OnlyGodRuntimeError


def render_error(err, source_lines):
    print(f"error: {err}")                      # "line 4, col 9: message"
    if 1 <= err.line <= len(source_lines):
        print("    " + source_lines[err.line - 1])
        print("    " + " " * (err.col - 1) + "^")
    hint = getattr(err, "hint", None)
    if hint:
        print(f"    hint: {hint}")


def run_python(code):
    """Run generated Python. Runtime mistakes are shown without a traceback."""
    try:
        exec(compile(code, "<onlygod>", "exec"), {"__name__": "__onlygod__"})
    except (ZeroDivisionError, ValueError, EOFError) as e:
        print(f"runtime error: {e}")
        return 1
    return 0


def main(argv):
    flags = {a for a in argv[1:] if a.startswith("--")}
    files = [a for a in argv[1:] if not a.startswith("--")]
    known = {"--py", "--emit", "--bottomup"}
    if len(files) != 1 or not flags <= known:
        print(__doc__.split("Pipeline:")[0].strip())
        return 2
    try:
        with open(files[0], encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"cannot open {files[0]}: {e.strerror}")
        return 2

    lines = source.splitlines()
    try:
        tokens = Lexer(source).tokenize()
        if "--bottomup" in flags:
            from lrparser import LRParser
            program = LRParser(tokens).parse()
        else:
            program = Parser(tokens).parse()

        errors = TypeChecker().check(program)
        if errors:
            for err in errors:
                render_error(err, lines)
                print()
            n = len(errors)
            print(f"{n} error{'s' if n != 1 else ''} found, nothing was run.")
            return 1

        if "--emit" in flags or "--py" in flags:
            from transpiler import Transpiler
            code = Transpiler().transpile(program)
            if "--emit" in flags:
                print(code)
                return 0
            return run_python(code)

        Interpreter().run(program)
    except (LexError, ParseError, OnlyGodRuntimeError) as err:
        render_error(err, lines)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
