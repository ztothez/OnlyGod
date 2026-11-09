"""OnlyGod interpreter: walks the AST and runs the program.

Two methods do all the walking:
    execute(stmt)    runs a statement (does something, returns nothing)
    evaluate(expr)   works out an expression and RETURNS its value

Variables live in an Environment. Each environment has a `parent`, so a
block or a function call can get its own scope that can still see the
scopes around it. That chain is your "nested scope" feature.
"""
from ast_nodes import (
    Literal, Variable, Unary, Binary, Call,
    VarDecl, Assign, Print, Read, Block, If, While, Return,
    ExprStmt, FunDecl, Program,
)


class OnlyGodRuntimeError(Exception):
    """A mistake found while the program runs. Same shape as LexError and
    ParseError (line and col), plus an optional hint for the programmer."""

    def __init__(self, msg, line, col, hint=None):
        super().__init__(f"line {line}, col {col}: {msg}")
        self.msg = msg
        self.line = line
        self.col = col
        self.hint = hint


class ReturnSignal(Exception):
    """Carries a return value up out of nested statements to the call."""

    def __init__(self, value, line, col):
        super().__init__("return")
        self.value = value
        self.line = line
        self.col = col


# ---- small helpers (given) ----------------------------------------------

def type_name(v) -> str:
    """The OnlyGod name of a Python value. bool is checked first because
    in Python True is also an int."""
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "string"
    return "nothing"


def is_number(v) -> bool:
    return type_name(v) in ("int", "float")


def to_text(v) -> str:
    """How a value looks when printed."""
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "nothing"
    return str(v)


def not_declared(name, line, col):
    return OnlyGodRuntimeError(
        f"'{name}' is not declared", line, col,
        f"declare it first: let {name}: <type> = ...;",
    )


class Function:
    """A user-defined function. `closure` is the environment it was
    declared in, which is what its body can see besides its own locals."""

    def __init__(self, decl, closure):
        self.decl = decl
        self.closure = closure


class Builtin:
    def __init__(self, name, arity, fn):
        self.name = name
        self.arity = arity
        self.fn = fn


def _to_int(v):
    return int(v)           # int("42") works, int("abc") raises ValueError


def _to_float(v):
    return float(v)


def _to_string(v):
    return to_text(v)


BUILTINS = [
    Builtin("toInt", 1, _to_int),
    Builtin("toFloat", 1, _to_float),
    Builtin("toString", 1, _to_string),
]


# ---- environment ---------------------------------------------------------

class Environment:
    def __init__(self, parent=None):
        self.values = {}
        self.parent = parent

    def define(self, name, value):
        # WORKED EXAMPLE: create (or overwrite) a variable in THIS scope only.
        self.values[name] = value

    def has_local(self, name):
        return name in self.values

    def get(self, name, line, col):
        if name in self.values:
            return self.values[name]
        elif self.parent is not None:
            return self.parent.get(name, line, col)
        else:
            raise not_declared(name, line, col)
        
    def assign(self, name, value, line, col):
        if name in self.values:
            self.values[name] = value
        elif self.parent is not None:
            self.parent.assign(name, value, line, col)
        else:
            raise not_declared(name, line, col)


# ---- the interpreter -----------------------------------------------------

class Interpreter:
    def __init__(self, input_fn=input, output_fn=print):
        # input_fn() returns one line typed by the user.
        # output_fn(text) shows one line. The tests swap both for fakes.
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.globals = Environment()
        self.env = self.globals          # the scope we are currently in
        for b in BUILTINS:
            self.globals.define(b.name, b)

    def run(self, program):
        try:
            for stmt in program.statements:
                self.execute(stmt)
        except ReturnSignal as r:
            raise OnlyGodRuntimeError("return outside a function", r.line, r.col)

    # ---- helpers (given) -------------------------------------------------

    def error(self, msg, node, hint=None):
        """Build an error positioned at `node`. Use:  raise self.error(...)"""
        return OnlyGodRuntimeError(msg, node.line, node.col, hint)

    def require_bool(self, value, node, what):
        """Conditions and logic must be bool. No silent conversions."""
        if not isinstance(value, bool):
            raise self.error(f"{what} must be bool, got {type_name(value)}", node)
        return value

    def execute_block(self, statements, env):
        """Run `statements` with `env` as the current scope, then ALWAYS go
        back to the old scope (try/finally), even if an error or a return
        jumps out of the middle of the block."""
        previous = self.env
        self.env = env
        try:
            for stmt in statements:
                self.execute(stmt)
        finally:
            self.env = previous

    # ---- dispatch (given): pick the right method for each node type ------

    def execute(self, stmt):
        if isinstance(stmt, Print): return self.exec_print(stmt)
        if isinstance(stmt, VarDecl): return self.exec_var_decl(stmt)
        if isinstance(stmt, Assign): return self.exec_assign(stmt)
        if isinstance(stmt, Read): return self.exec_read(stmt)
        if isinstance(stmt, Block): return self.exec_block(stmt)
        if isinstance(stmt, If): return self.exec_if(stmt)
        if isinstance(stmt, While): return self.exec_while(stmt)
        if isinstance(stmt, Return): return self.exec_return(stmt)
        if isinstance(stmt, ExprStmt): return self.exec_expr_stmt(stmt)
        if isinstance(stmt, FunDecl): return self.exec_fun_decl(stmt)
        raise AssertionError(f"unknown statement node {stmt!r}")

    def evaluate(self, expr):
        if isinstance(expr, Literal):
            return expr.value                              # WORKED EXAMPLE
        if isinstance(expr, Variable):
            return self.env.get(expr.name, expr.line, expr.col)
        if isinstance(expr, Unary): return self.eval_unary(expr)
        if isinstance(expr, Binary): return self.eval_binary(expr)
        if isinstance(expr, Call): return self.eval_call(expr)
        raise AssertionError(f"unknown expression node {expr!r}")

    # ---- WORKED EXAMPLE statement ----------------------------------------

    def exec_print(self, stmt):
        value = self.evaluate(stmt.value)
        self.output_fn(to_text(value))

    # ---- statements: YOUR TURN -------------------------------------------

    def exec_var_decl(self, stmt):
        if self.env.has_local(stmt.name):
            raise self.error(f"'{stmt.name}' is already declared in this scope", stmt)
        value = self.evaluate(stmt.init)
        self.env.define(stmt.name, value)

    def exec_assign(self, stmt):
        value = self.evaluate(stmt.value)
        self.env.assign(stmt.name, value, stmt.line, stmt.col)

    def exec_read(self, stmt):
        current = self.env.get(stmt.name, stmt.line, stmt.col)
        try:
            text = self.input_fn().strip()
        except EOFError:
            raise self.error("no input left to read", stmt)
        kind = type_name(current)
        try:
            if kind == "int":
                converted = int(text)
            elif kind == "float":
                converted = float(text)
            elif kind == "string":
                converted = text
            elif kind == "bool":
                if text == "true":
                    converted = True
                elif text == "false":
                    converted = False
                else:
                    raise ValueError
            else:
                raise ValueError
        except ValueError:
            raise self.error(f"expected {kind} for '{stmt.name}', got '{text}'", stmt)
        self.env.assign(stmt.name, converted, stmt.line, stmt.col)

    def exec_expr_stmt(self, stmt):
        self.evaluate(stmt.expr)

    def exec_block(self, stmt):
        self.execute_block(stmt.statements, Environment(self.env))

    def exec_if(self, stmt):
        cond = self.require_bool(self.evaluate(stmt.cond), stmt.cond, "the condition")
        if cond:
            self.execute_block(stmt.then_block.statements, Environment(self.env))
        elif stmt.else_block is not None:
            self.execute_block(stmt.else_block.statements, Environment(self.env))

    def exec_while(self, stmt):
        while True:
            cond = self.require_bool(self.evaluate(stmt.cond), stmt.cond, "the condition")
            if not cond:
                break
            self.execute_block(stmt.body.statements, Environment(self.env))

    def exec_return(self, stmt):
        value = None if stmt.value is None else self.evaluate(stmt.value)
        raise ReturnSignal(value, stmt.line, stmt.col)

    def exec_fun_decl(self, stmt):
        self.env.define(stmt.name, Function(stmt, self.env))

    # ---- expressions: YOUR TURN ------------------------------------------

    def eval_unary(self, e):
        value = self.evaluate(e.operand)
        if e.op == "-":
            if not is_number(value):
                raise self.error(f"cannot negate {type_name(value)}", e)
            return -value
        elif e.op == "not":
            self.require_bool(value, e.operand, "the operand of 'not'")
            return not value
        else:
            raise self.error(f"unknown unary operator '{e.op}'", e)

    def eval_binary(self, e):
        left = self.evaluate(e.left)
        if e.op in ("and", "or"):
            left_bool = self.require_bool(left, e.left, f"the left side of '{e.op}'")
            if (e.op == "and" and not left_bool) or (e.op == "or" and left_bool):
                return left_bool
            right = self.evaluate(e.right)
            return self.require_bool(right, e.right, f"the right side of '{e.op}'")
        right = self.evaluate(e.right)
        if e.op in ("==", "!="):
            if type_name(left) != type_name(right):
                raise self.error(f"cannot compare {type_name(left)} with {type_name(right)}", e)
            return left == right if e.op == "==" else left != right
        if e.op in ("<", "<=", ">", ">="):
            if (is_number(left) and is_number(right)) or (isinstance(left, str) and isinstance(right, str)):
                if e.op == "<":
                    return left < right
                elif e.op == "<=":
                    return left <= right
                elif e.op == ">":
                    return left > right
                elif e.op == ">=":
                    return left >= right
            else:
                raise self.error(f"cannot compare {type_name(left)} with {type_name(right)}", e)
        if e.op == "+":
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            elif is_number(left) and is_number(right):
                return left + right
            else:
                raise self.error(f"cannot add {type_name(left)} to {type_name(right)}", e,
                                 "convert with toInt(...) or toString(...)")
        if e.op in ("-", "*", "/", "%"):
            if not (is_number(left) and is_number(right)):
                raise self.error(f"cannot use '{e.op}' on {type_name(left)} and {type_name(right)}", e)
            if e.op == "/":
                if right == 0:
                    raise self.error("division by zero", e)
                return left // right if isinstance(left, int) and isinstance(right, int) else left / right
            elif e.op == "%":
                if right == 0:
                    raise self.error("division by zero", e)
                return left % right
            elif e.op == "-":
                return left - right
            elif e.op == "*":
                return left * right
        raise self.error(f"unknown binary operator '{e.op}'", e)

    def eval_call(self, e):
        callee = self.env.get(e.name, e.line, e.col)
        args = [self.evaluate(a) for a in e.args]
        if isinstance(callee, Builtin):
            if len(args) != callee.arity:
                raise self.error(f"{e.name} expects {callee.arity} argument(s), got {len(args)}", e)
            try:
                return callee.fn(*args)
            except ValueError:
                raise self.error(f"{e.name} cannot convert '{to_text(args[0])}'", e)
        elif isinstance(callee, Function):
            expected = len(callee.decl.params)
            if len(args) != expected:
                raise self.error(f"{e.name} expects {expected} argument(s), got {len(args)}", e)
            local = Environment(callee.closure)
            for param, arg in zip(callee.decl.params, args):
                local.define(param.name, arg)
            try:
                self.execute_block(callee.decl.body.statements, local)
            except ReturnSignal as r:
                return r.value
            return None
        raise self.error(f"{e.name} is not a function", e)
