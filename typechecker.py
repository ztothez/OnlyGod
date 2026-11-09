"""OnlyGod static type checker: finds type mistakes BEFORE the program runs.

It walks the same AST as the interpreter, but works with TYPES instead of
values. check_expr(e) returns the type of an expression as a string:
"int", "float", "string" or "bool". check_stmt(s) checks a statement.

THE RULES OF THE LANGUAGE (these are your design decisions):
  1. No implicit conversions. An int is never silently turned into a float
     or a string. The programmer writes toFloat(...), toInt(...), toString(...).
  2. Arithmetic on two ints gives an int. If either side is a float, the
     result is a float. ints and floats can be compared with each other.
  3. + also joins two strings. Any other use of + is an error.
  4. Conditions, and, or, not all need bool.
  5. A call must match the function's parameter count and types, and a
     `return` must match the declared return type.

ERROR RECOVERY: the checker does not stop at the first mistake. It records
every error in self.errors and keeps going. When an expression is already
wrong it returns the special type ERR, which every rule accepts silently.
That stops one mistake from causing a chain of confusing follow-up errors.
"""
from ast_nodes import (
    Literal, Variable, Unary, Binary, Call,
    VarDecl, Assign, Print, Read, Block, If, While, Return,
    ExprStmt, FunDecl, Program,
)
from interpreter import type_name

ERR = "?"          # "this expression is already known to be wrong"
ANY = "any"        # only used for the parameter of built-in functions


class OnlyGodTypeError(Exception):
    """Same shape as the other errors: line, col, optional hint."""

    def __init__(self, msg, line, col, hint=None):
        super().__init__(f"line {line}, col {col}: {msg}")
        self.msg = msg
        self.line = line
        self.col = col
        self.hint = hint


class FunType:
    """The type of a function: its parameter types and its return type."""

    def __init__(self, name, params, ret):
        self.name = name
        self.params = params
        self.ret = ret


class TypeEnv:
    """Like Environment in the interpreter, but it stores TYPES."""

    def __init__(self, parent=None):
        self.types = {}
        self.parent = parent

    def define(self, name, t):
        self.types[name] = t

    def has_local(self, name):
        return name in self.types

    def lookup(self, name):
        """The type of `name`, looking outwards through the parents.
        Returns None when the name is not declared anywhere."""
        env = self
        while env is not None:
            if name in env.types:
                return env.types[name]
            env = env.parent
        return None


# ---- small helpers (given) ----------------------------------------------

def is_num(t) -> bool:
    return t in ("int", "float")


def assignable(target, actual) -> bool:
    """Can a value of type `actual` go where `target` is expected?
    Rule 1: only the same type, no widening. ERR and ANY accept anything."""
    return actual == ERR or target == ERR or target == ANY or target == actual


def conversion_hint(actual, expected):
    """A hint that is only given when we KNOW which conversion exists."""
    if expected == "int" and actual in ("float", "string"):
        return "convert with toInt(...)"
    if expected == "float" and actual in ("int", "string"):
        return "convert with toFloat(...)"
    if expected == "string" and actual in ("int", "float", "bool"):
        return "convert with toString(...)"
    return None


# ---- the checker ---------------------------------------------------------

class TypeChecker:
    def __init__(self):
        self.errors = []
        self.scope = TypeEnv()
        self.current_fn = None        # (name, return_type) inside a function, else None
        self.scope.define("toInt", FunType("toInt", [ANY], "int"))
        self.scope.define("toFloat", FunType("toFloat", [ANY], "float"))
        self.scope.define("toString", FunType("toString", [ANY], "string"))

    def check(self, program):
        """Check the whole program. Returns the list of errors (maybe empty)."""
        for stmt in program.statements:
            self.check_stmt(stmt)
        return self.errors

    # ---- helpers (given) -------------------------------------------------

    def error(self, msg, node, hint=None):
        """Record an error at `node` and keep going (no raise)."""
        self.errors.append(OnlyGodTypeError(msg, node.line, node.col, hint))

    def report_undeclared(self, name, node):
        self.error(f"'{name}' is not declared", node,
                   f"declare it first: let {name}: <type> = ...;")

    # ---- dispatch (given) ------------------------------------------------

    def check_stmt(self, s):
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

    def check_expr(self, e):
        if isinstance(e, Literal):
            return type_name(e.value)                      # WORKED EXAMPLE
        if isinstance(e, Variable):                        # WORKED EXAMPLE
            t = self.scope.lookup(e.name)
            if t is None:
                self.report_undeclared(e.name, e)
                return ERR
            if isinstance(t, FunType):
                self.error(f"'{e.name}' is a function, call it with ()", e)
                return ERR
            return t
        if isinstance(e, Unary): return self.e_unary(e)
        if isinstance(e, Binary): return self.e_binary(e)
        if isinstance(e, Call): return self.e_call(e)
        raise AssertionError(f"unknown expression node {e!r}")

    # ---- WORKED EXAMPLE statement ----------------------------------------

    def s_print(self, s):
        self.check_expr(s.value)       # print accepts any type, but the
                                       # expression inside must be valid

    # ---- statements: YOUR TURN -------------------------------------------

    def s_expr_stmt(self, s):
        self.check_expr(s.expr)

    def s_var_decl(self, s):
        init_t = self.check_expr(s.init)
        if self.scope.has_local(s.name):
            self.error(f"'{s.name}' is already declared in this scope", s)
        if not assignable(s.type_name, init_t):
            self.error(f"cannot put {init_t} into '{s.name}', which is {s.type_name}",
                       s.init, conversion_hint(init_t, s.type_name))
        self.scope.define(s.name, s.type_name)

    def s_assign(self, s):
        value_t = self.check_expr(s.value)
        declared = self.scope.lookup(s.name)
        if declared is None:
            self.report_undeclared(s.name, s)
            return
        if isinstance(declared, FunType):
            self.error(f"'{s.name}' is a function and cannot be assigned to", s)
            return
        if not assignable(declared, value_t):
            self.error(f"cannot put {value_t} into '{s.name}', which is {declared}",
                       s.value, conversion_hint(value_t, declared))

    def s_read(self, s):
        declared = self.scope.lookup(s.name)
        if declared is None:
            self.report_undeclared(s.name, s)
            return
        if isinstance(declared, FunType):
            self.error(f"'{s.name}' is a function and cannot be read from", s)
            return

    def s_block(self, s):
        previous = self.scope
        self.scope = TypeEnv(self.scope)
        try:
            for stmt in s.statements:
                self.check_stmt(stmt)
        finally:
            self.scope = previous

    def s_if(self, s):
        cond_t = self.check_expr(s.cond)
        if not assignable("bool", cond_t):
            self.error(f"the condition must be bool, got {cond_t}", s.cond)
        self.check_stmt(s.then_block)
        if s.else_block is not None:
            self.check_stmt(s.else_block)

    def s_while(self, s):
        cond_t = self.check_expr(s.cond)
        if not assignable("bool", cond_t):
            self.error(f"the condition must be bool, got {cond_t}", s.cond)
        self.check_stmt(s.body)

    def s_return(self, s):
        if self.current_fn is None:
            self.error("return outside a function", s)
            if s.value is not None:
                self.check_expr(s.value)
            return
        name, ret = self.current_fn
        if s.value is None:
            self.error(f"{name} must return {ret}", s)
            return
        t = self.check_expr(s.value)
        if not assignable(ret, t):
            self.error(f"{name} must return {ret}, got {t}", s.value,
                       conversion_hint(t, ret))

    def s_fun_decl(self, s):
        if self.scope.has_local(s.name):
            self.error(f"'{s.name}' is already declared in this scope", s)
        self.scope.define(s.name, FunType(s.name, [p.type_name for p in s.params], s.return_type))
        outer_scope, outer_fn = self.scope, self.current_fn
        self.scope = TypeEnv(outer_scope)
        self.current_fn = (s.name, s.return_type)
        for p in s.params:
            self.scope.define(p.name, p.type_name)
        try:
            for stmt in s.body.statements:
                self.check_stmt(stmt)
        finally:
            self.scope, self.current_fn = outer_scope, outer_fn

    # ---- expressions: YOUR TURN ------------------------------------------

    def e_unary(self, e):
        t = self.check_expr(e.operand)
        if t == ERR:
            return ERR
        if e.op == "-":
            if not is_num(t):
                self.error(f"cannot negate {t}", e)
                return ERR
            return t
        if e.op == "not":
            if not assignable("bool", t):
                self.error(f"the operand of 'not' must be bool, got {t}", e.operand)
                return ERR
            return "bool"
        raise NotImplementedError

    def e_binary(self, e):
        lt = self.check_expr(e.left)
        rt = self.check_expr(e.right)
        if e.op in ("and", "or"):
            if not assignable("bool", lt):
                self.error(f"the left side of '{e.op}' must be bool, got {lt}", e.left)
            if not assignable("bool", rt):
                self.error(f"the right side of '{e.op}' must be bool, got {rt}", e.right)
            return "bool"
        if lt == ERR or rt == ERR:
            if e.op in ("==", "!=", "<", "<=", ">", ">="):
                return "bool"
            else:
                return ERR
        if e.op in ("==", "!="):
            if (is_num(lt) and is_num(rt)) or lt == rt:
                return "bool"
            else:
                self.error(f"cannot compare {lt} with {rt}", e)
                return "bool"
        if e.op in ("<", "<=", ">", ">="):
            if (is_num(lt) and is_num(rt)) or (lt == "string" and rt == "string"):
                return "bool"
            else:
                self.error(f"cannot compare {lt} with {rt}", e)
                return "bool"
        if e.op == "+":
            if lt == "string" and rt == "string":
                return "string"
            if is_num(lt) and is_num(rt):
                return "int" if lt == "int" and rt == "int" else "float"
            self.error(f"cannot add {lt} to {rt}", e,
                       "convert with toInt(...) or toString(...)")
            return ERR
        if e.op in ("-", "*", "/", "%"):
            if is_num(lt) and is_num(rt):
                return "int" if lt == "int" and rt == "int" else "float"
            self.error(f"cannot use '{e.op}' on {lt} and {rt}", e)
            return ERR
        raise NotImplementedError

    def e_call(self, e):
        callee = self.scope.lookup(e.name)
        arg_types = [self.check_expr(a) for a in e.args]
        if callee is None:
            self.report_undeclared(e.name, e)
            return ERR
        if not isinstance(callee, FunType):
            self.error(f"{e.name} is not a function", e)
            return ERR
        if len(e.args) != len(callee.params):
            n = len(callee.params)
            self.error(f"{e.name} expects {n} argument{'s' if n != 1 else ''}, "
                       f"got {len(e.args)}", e)
            return callee.ret
        for i, (arg, expected, actual) in enumerate(
                zip(e.args, callee.params, arg_types), start=1):
            if not assignable(expected, actual):
                self.error(f"argument {i} of {e.name} must be {expected}, got {actual}",
                           arg, conversion_hint(actual, expected))
        return callee.ret
