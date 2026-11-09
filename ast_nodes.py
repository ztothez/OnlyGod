"""AST node definitions for OnlyGod. This file is given, nothing to fill in.

Every node remembers where it starts (line, col) so that later stages
(type checker, interpreter) can report errors with a location.
"""
from dataclasses import dataclass


# ---- expressions ---------------------------------------------------------

@dataclass
class Literal:
    value: object          # 5, 3.14, "hi", True, False
    line: int
    col: int


@dataclass
class Variable:
    name: str
    line: int
    col: int


@dataclass
class Unary:
    op: str                # "-" or "not"
    operand: object
    line: int
    col: int


@dataclass
class Binary:
    op: str                # "+", "-", "*", "/", "%", "<", "==", "and", "or", ...
    left: object
    right: object
    line: int
    col: int


@dataclass
class Call:
    name: str
    args: list
    line: int
    col: int


# ---- statements (used in the next step) ----------------------------------

@dataclass
class Param:
    name: str
    type_name: str         # "int", "float", "string", "bool"
    line: int
    col: int


@dataclass
class VarDecl:
    name: str
    type_name: str
    init: object
    line: int
    col: int


@dataclass
class Assign:
    name: str
    value: object
    line: int
    col: int


@dataclass
class Print:
    value: object
    line: int
    col: int


@dataclass
class Read:
    name: str
    line: int
    col: int


@dataclass
class Block:
    statements: list
    line: int
    col: int


@dataclass
class If:
    cond: object
    then_block: object
    else_block: object     # None when there is no else
    line: int
    col: int


@dataclass
class While:
    cond: object
    body: object
    line: int
    col: int


@dataclass
class Return:
    value: object          # None for a bare "return;"
    line: int
    col: int


@dataclass
class ExprStmt:
    expr: object
    line: int
    col: int


@dataclass
class FunDecl:
    name: str
    params: list
    return_type: str
    body: object
    line: int
    col: int


@dataclass
class Program:
    statements: list
