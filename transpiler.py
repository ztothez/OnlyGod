"""OnlyGod transpiler: turns the AST into Python source code.

The pipeline gets one more stage:

    tokens -> Parser -> AST -> TypeChecker -> Transpiler -> Python text -> run

Same walk as the interpreter, but instead of DOING things, every method
RETURNS TEXT (expressions) or EMITS LINES (statements).

Four problems make this more than a find-and-replace:

  1. Scopes. OnlyGod blocks have their own variables, Python blocks do not.
     `let x` inside a block must not overwrite the outer x. Fix: every
     declaration gets a UNIQUE Python name (x, x_1, x_2, ...). You also
     avoid Python keywords (a variable called `class` or `None` is legal in
     OnlyGod) and Python builtins.
  2. Assignment inside a function. Python treats `n = 1` in a function as a
     NEW local unless the function says `global n` (variable lives at module
     level) or `nonlocal n` (lives in an enclosing function).
  3. Division. int / int must give an int, anything else a float, so `/` and
     `%` become calls to small helpers in PRELUDE.
  4. Empty blocks. Python needs `pass` where OnlyGod allows `{ }`.

The type checker already ran, so this stage may assume the program is
well typed and every name is declared.
"""
import builtins
import keyword

from ast_nodes import (
    Literal, Variable, Unary, Binary, Call,
    VarDecl, Assign, Print, Read, Block, If, While, Return,
    ExprStmt, FunDecl, Program,
)

# Copied in front of every generated program. Read it: this is the runtime
# that the generated code relies on.
PRELUDE = """\
# ---- OnlyGod runtime helpers (generated) ----
def _og_show(v):
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "nothing"
    return str(v)


def _og_div(a, b):
    if b == 0:
        raise ZeroDivisionError("division by zero")
    if isinstance(a, int) and isinstance(b, int):
        return a // b
    return a / b


def _og_mod(a, b):
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a % b


def _og_read(current, name):
    # The variable's CURRENT value decides what to convert the input to.
    text = input().strip()
    if isinstance(current, bool):
        kind = "bool"
        if text in ("true", "false"):
            return text == "true"
    elif isinstance(current, int):
        kind = "int"
        try:
            return int(text)
        except ValueError:
            pass
    elif isinstance(current, float):
        kind = "float"
        try:
            return float(text)
        except ValueError:
            pass
    else:
        return text
    raise ValueError(f"expected {kind} for '{name}', got '{text}'")


def _og_toInt(v):
    try:
        return int(v)
    except ValueError:
        raise ValueError(f"toInt cannot convert '{_og_show(v)}'")


def _og_toFloat(v):
    try:
        return float(v)
    except ValueError:
        raise ValueError(f"toFloat cannot convert '{_og_show(v)}'")


def _og_toString(v):
    return _og_show(v)
# ---- end of runtime helpers ----
"""

PRELUDE_NAMES = {"_og_show", "_og_div", "_og_mod", "_og_read",
                 "_og_toInt", "_og_toFloat", "_og_toString"}
RESERVED = set(dir(builtins)) | PRELUDE_NAMES


class PyScope:
    """One OnlyGod scope. names maps the OnlyGod name to the Python name.
    `depth` is how many functions deep this scope is: 0 = module level."""

    def __init__(self, parent=None, depth=0):
        self.names = {}
        self.parent = parent
        self.depth = depth


class Transpiler:
    def __init__(self):
        self.lines = []            # the generated Python, one string per line
        self.indent = 0            # current indentation level
        self.used = set()          # every Python name handed out so far
        self.fn_depth = 0          # 0 = module level, 1 = inside a function, ...
        self.writes = []           # one dict per function being generated:
                                   #   python name -> "global" or "nonlocal"
        self.scope = PyScope()
        for name in ("toInt", "toFloat", "toString"):
            self.scope.names[name] = ("_og_" + name, 0)

    def transpile(self, program) -> str:
        for stmt in program.statements:
            self.stmt(stmt)
        return PRELUDE + "\n" + "\n".join(self.lines) + "\n"

    # ---- helpers (given) -------------------------------------------------

    def emit(self, text):
        """Add one line of Python at the current indentation."""
        self.lines.append("    " * self.indent + text)

    def push(self):
        self.scope = PyScope(self.scope, self.fn_depth)

    def pop(self):
        self.scope = self.scope.parent

    def declare(self, name):
        """Register `name` in the CURRENT scope and return the unique Python
        name to use for it: x, then x_1, x_2 ... never a keyword or builtin."""
        py = name
        n = 1
        while py in self.used or py in RESERVED or keyword.iskeyword(py):
            py = f"{name}_{n}"
            n += 1
        self.used.add(py)
        self.scope.names[name] = (py, self.scope.depth)
        return py

    def lookup(self, name):
        """(python_name, depth) of the nearest declaration of `name`."""
        scope = self.scope
        while scope is not None:
            if name in scope.names:
                return scope.names[name]
            scope = scope.parent
        raise ValueError(f"'{name}' is not declared (run the type checker first)")

    def read_name(self, name):
        """The Python name to READ `name` through."""
        return self.lookup(name)[0]

    def write_name(self, name):
        """The Python name to ASSIGN to `name` through. If the variable lives
        OUTSIDE the function being generated, remember that this function
        needs a `global` / `nonlocal` line for it (problem 2 above)."""
        py, depth = self.lookup(name)
        if depth < self.fn_depth:
            self.writes[-1][py] = "global" if depth == 0 else "nonlocal"
        return py

    def body(self, block):
        """Emit a block's statements ONE LEVEL DEEPER, in a new scope, adding
        `pass` if the block is empty. Use it for if / else / while bodies."""
        self.indent += 1
        start = len(self.lines)
        self.push()
        for stmt in block.statements:
            self.stmt(stmt)
        self.pop()
        if len(self.lines) == start:
            self.emit("pass")
        self.indent -= 1

    # ---- dispatch (given) ------------------------------------------------

    def stmt(self, s):
        if isinstance(s, Print): return self.s_print(s)
        if isinstance(s, VarDecl): return self.s_var_decl(s)
        if isinstance(s, Assign): return self.s_assign(s)
        if isinstance(s, Read): return self.s_read(s)
        if isinstance(s, ExprStmt): return self.s_expr_stmt(s)
        if isinstance(s, Block): return self.s_block(s)
        if isinstance(s, If): return self.s_if(s)
        if isinstance(s, While): return self.s_while(s)
        if isinstance(s, Return): return self.s_return(s)
        if isinstance(s, FunDecl): return self.s_fun_decl(s)
        raise AssertionError(f"unknown statement node {s!r}")

    def expr(self, e) -> str:
        if isinstance(e, Literal):
            return repr(e.value)                 # WORKED EXAMPLE: 5, 2.5, 'hi', True
        if isinstance(e, Variable): return self.x_variable(e)
        if isinstance(e, Unary): return self.x_unary(e)
        if isinstance(e, Binary): return self.x_binary(e)
        if isinstance(e, Call): return self.x_call(e)
        raise AssertionError(f"unknown expression node {e!r}")

    # ---- WORKED EXAMPLE statement ----------------------------------------

    def s_print(self, s):
        # OnlyGod prints true/false, Python would print True/False,
        # so printing goes through the _og_show helper.
        self.emit(f"print(_og_show({self.expr(s.value)}))")

    # ---- expressions: YOUR TURN (each RETURNS a string) ------------------

    def x_variable(self, e):
        return self.read_name(e.name)

    def x_unary(self, e):
        inner = self.expr(e.operand)
        if e.op == "-":
            return f"(-{inner})"
        elif e.op == "not":
            return f"(not {inner})"
        raise NotImplementedError

    def x_binary(self, e):
        left = self.expr(e.left)
        right = self.expr(e.right)
        if e.op == "/":
            return f"_og_div({left}, {right})"
        elif e.op == "%":
            return f"_og_mod({left}, {right})"
        else:
            return f"({left} {e.op} {right})"


    def x_call(self, e):
        name = self.read_name(e.name)
        args = ", ".join(self.expr(a) for a in e.args)
        return f"{name}({args})"


    # ---- statements: YOUR TURN (each EMITS lines) ------------------------

    def s_expr_stmt(self, s):
        value = self.expr(s.expr)
        self.emit(f"{value}")

    def s_var_decl(self, s):

        init = self.expr(s.init)
        py = self.declare(s.name)
        self.emit(f"{py} = {init}")

    def s_assign(self, s):

        value = self.expr(s.value)
        py = self.write_name(s.name)
        self.emit(f"{py} = {value}")

    def s_read(self, s):
        py = self.write_name(s.name)
        self.emit(f"{py} = _og_read({py}, {s.name!r})")

    def s_block(self, s):
        self.push()
        for stmt in s.statements:
            self.stmt(stmt)
        self.pop()

    def s_if(self, s):
        cond = self.expr(s.cond)
        self.emit(f"if {cond}:")
        self.body(s.then_block)
        if s.else_block is not None:
            self.emit("else:")
            self.body(s.else_block)

    def s_while(self, s):
        cond = self.expr(s.cond)
        self.emit(f"while {cond}:")
        self.body(s.body)

    def s_return(self, s):
        if s.value is None:
            self.emit("return")
        else:
            value = self.expr(s.value)
            self.emit(f"return {value}")

    def s_fun_decl(self, s):
        py_name = self.declare(s.name)  # Step 1
        self.fn_depth += 1              # Step 2
        self.writes.append({})
        self.push()
        params = [self.declare(p.name) for p in s.params]  # Step 3
        self.emit(f"def {py_name}({', '.join(params)}):")  # Step 4
        start = len(self.lines)         # Step 5
        self.indent += 1
        for stmt in s.body.statements:  # Step 6
            self.stmt(stmt)
        if len(self.lines) == start:
            self.emit("pass")
        writes = self.writes.pop()      # Step 7
        globals = [name for name, kind in writes.items() if kind == "global"]
        nonlocals = [name for name, kind in writes.items() if kind == "nonlocal"]
        if globals:
            inner = "    " * self.indent
            self.lines.insert(start, inner + "global " + ", ".join(globals))
            start += 1
        if nonlocals:
            inner = "    " * self.indent
            self.lines.insert(start, inner + "nonlocal " + ", ".join(nonlocals))
        self.indent -= 1                 # Step 8
        self.pop()
        self.fn_depth -= 1
