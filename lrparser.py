"""OnlyGod bottom-up parser: an SLR(1) table-driven shift-reduce parser.

The recursive descent parser (parser.py) starts from the top rule and works
DOWN into the input. This one works the other way round: it reads tokens
left to right, PUSHES them on a stack (shift), and whenever the top of the
stack matches the right-hand side of a grammar rule it REPLACES those
symbols by the rule's left-hand side (reduce), building the AST node on the
way. When only the start symbol is left, the program is parsed.

Which action to take is decided by a TABLE. The table is not written by
hand: it is GENERATED from the grammar, which is what you build here.

    grammar ----> nullable / FIRST / FOLLOW ----> states (closure, goto)
                                                      |
              tokens ----> driver loop <---- action + goto tables

A symbol is a string. In `productions` a symbol is a NONTERMINAL when it
appears on the left of some rule, otherwise it is a TERMINAL. For OnlyGod
the terminals are token type names such as "PLUS" or "IDENT", and the end
of the input is the terminal "EOF".

An ITEM is a pair (production index, dot position): (3, 1) means "I am
in production 3 and have already seen 1 symbol of its right-hand side".
A STATE is a frozenset of items.
"""
from lexer import T
from parser import ParseError
from ast_nodes import (
    Literal, Variable, Unary, Binary, Call, Param,
    VarDecl, Assign, Print, Read, Block, If, While, Return,
    ExprStmt, FunDecl, Program,
)


# =========================================================================
# PART 1: the grammar (given). Compare it with the BNF in your report.
# Each rule has an ACTION: a function that receives the list of the values
# of the right-hand side symbols and returns the value of the left-hand side.
# For a token the value is the Token, for a nonterminal it is an AST node
# (or a list of them). Rule of thumb: a node starts where its FIRST symbol
# starts, so most actions copy c[0].line, c[0].col.
# =========================================================================

def _binary(c):
    return Binary(c[1].lexeme, c[0], c[2], c[0].line, c[0].col)


def _unary(c):
    return Unary(c[0].lexeme, c[1], c[0].line, c[0].col)


def _expr_stmt(c):
    return ExprStmt(c[0], c[0].line, c[0].col)


GRAMMAR = [
    # augmented start rule: ALWAYS production 0. Reaching its end = accept.
    ("start", ("program",), lambda c: c[0]),

    ("program", ("stmts",), lambda c: Program(c[0])),
    ("stmts", (), lambda c: []),
    ("stmts", ("stmts", "decl"), lambda c: c[0] + [c[1]]),

    ("decl", ("var_decl",), lambda c: c[0]),
    ("decl", ("fun_decl",), lambda c: c[0]),
    ("decl", ("stmt",), lambda c: c[0]),

    ("var_decl", ("LET", "IDENT", "COLON", "type", "EQ", "expr", "SEMI"),
     lambda c: VarDecl(c[1].lexeme, c[3], c[5], c[0].line, c[0].col)),
    ("fun_decl", ("FUN", "IDENT", "LPAREN", "params", "RPAREN", "COLON", "type", "block"),
     lambda c: FunDecl(c[1].lexeme, c[3], c[6], c[7], c[0].line, c[0].col)),

    ("params", (), lambda c: []),
    ("params", ("param_list",), lambda c: c[0]),
    ("param_list", ("param",), lambda c: [c[0]]),
    ("param_list", ("param_list", "COMMA", "param"), lambda c: c[0] + [c[2]]),
    ("param", ("IDENT", "COLON", "type"),
     lambda c: Param(c[0].lexeme, c[2], c[0].line, c[0].col)),

    ("type", ("TYPE_INT",), lambda c: c[0].lexeme),
    ("type", ("TYPE_FLOAT",), lambda c: c[0].lexeme),
    ("type", ("TYPE_STRING",), lambda c: c[0].lexeme),
    ("type", ("TYPE_BOOL",), lambda c: c[0].lexeme),

    ("stmt", ("PRINT", "expr", "SEMI"), lambda c: Print(c[1], c[0].line, c[0].col)),
    ("stmt", ("READ", "IDENT", "SEMI"), lambda c: Read(c[1].lexeme, c[0].line, c[0].col)),
    ("stmt", ("IF", "LPAREN", "expr", "RPAREN", "block"),
     lambda c: If(c[2], c[4], None, c[0].line, c[0].col)),
    ("stmt", ("IF", "LPAREN", "expr", "RPAREN", "block", "ELSE", "block"),
     lambda c: If(c[2], c[4], c[6], c[0].line, c[0].col)),
    ("stmt", ("WHILE", "LPAREN", "expr", "RPAREN", "block"),
     lambda c: While(c[2], c[4], c[0].line, c[0].col)),
    ("stmt", ("RETURN", "SEMI"), lambda c: Return(None, c[0].line, c[0].col)),
    ("stmt", ("RETURN", "expr", "SEMI"), lambda c: Return(c[1], c[0].line, c[0].col)),
    ("stmt", ("block",), lambda c: c[0]),
    ("stmt", ("IDENT", "EQ", "expr", "SEMI"),
     lambda c: Assign(c[0].lexeme, c[2], c[0].line, c[0].col)),
    ("stmt", ("expr", "SEMI"), _expr_stmt),

    ("block", ("LBRACE", "stmts", "RBRACE"),
     lambda c: Block(c[1], c[0].line, c[0].col)),

    # expressions: one nonterminal per precedence level, lowest first.
    # "or" binds loosest, unary and calls bind tightest. Left recursion
    # (or -> or OR and) is what makes the operators LEFT associative, and
    # it is fine here: bottom-up parsers have no problem with left recursion.
    ("expr", ("or_e",), lambda c: c[0]),
    ("or_e", ("or_e", "OR", "and_e"), _binary),
    ("or_e", ("and_e",), lambda c: c[0]),
    ("and_e", ("and_e", "AND", "eq_e"), _binary),
    ("and_e", ("eq_e",), lambda c: c[0]),
    ("eq_e", ("eq_e", "EQEQ", "cmp_e"), _binary),
    ("eq_e", ("eq_e", "BANGEQ", "cmp_e"), _binary),
    ("eq_e", ("cmp_e",), lambda c: c[0]),
    ("cmp_e", ("cmp_e", "LT", "add_e"), _binary),
    ("cmp_e", ("cmp_e", "LE", "add_e"), _binary),
    ("cmp_e", ("cmp_e", "GT", "add_e"), _binary),
    ("cmp_e", ("cmp_e", "GE", "add_e"), _binary),
    ("cmp_e", ("add_e",), lambda c: c[0]),
    ("add_e", ("add_e", "PLUS", "mul_e"), _binary),
    ("add_e", ("add_e", "MINUS", "mul_e"), _binary),
    ("add_e", ("mul_e",), lambda c: c[0]),
    ("mul_e", ("mul_e", "STAR", "un_e"), _binary),
    ("mul_e", ("mul_e", "SLASH", "un_e"), _binary),
    ("mul_e", ("mul_e", "PERCENT", "un_e"), _binary),
    ("mul_e", ("un_e",), lambda c: c[0]),
    ("un_e", ("MINUS", "un_e"), _unary),
    ("un_e", ("NOT", "un_e"), _unary),
    ("un_e", ("call_e",), lambda c: c[0]),
    ("call_e", ("IDENT", "LPAREN", "args", "RPAREN"),
     lambda c: Call(c[0].lexeme, c[2], c[0].line, c[0].col)),
    ("call_e", ("primary",), lambda c: c[0]),
    ("primary", ("NUMBER",), lambda c: Literal(c[0].value, c[0].line, c[0].col)),
    ("primary", ("STRING",), lambda c: Literal(c[0].value, c[0].line, c[0].col)),
    ("primary", ("TRUE",), lambda c: Literal(True, c[0].line, c[0].col)),
    ("primary", ("FALSE",), lambda c: Literal(False, c[0].line, c[0].col)),
    ("primary", ("IDENT",), lambda c: Variable(c[0].lexeme, c[0].line, c[0].col)),
    ("primary", ("LPAREN", "expr", "RPAREN"), lambda c: c[1]),

    ("args", (), lambda c: []),
    ("args", ("arg_list",), lambda c: c[0]),
    ("arg_list", ("expr",), lambda c: [c[0]]),
    ("arg_list", ("arg_list", "COMMA", "expr"), lambda c: c[0] + [c[2]]),
]

PRODUCTIONS = [(lhs, rhs) for lhs, rhs, _ in GRAMMAR]
ACTIONS = [action for _, _, action in GRAMMAR]

# How a terminal is shown in an error message.
TERMINAL_TEXT = {
    "SEMI": "';'", "COLON": "':'", "COMMA": "','", "EQ": "'='",
    "LPAREN": "'('", "RPAREN": "')'", "LBRACE": "'{'", "RBRACE": "'}'",
    "IDENT": "a name", "NUMBER": "a number", "STRING": "a string",
    "TYPE_INT": "'int'", "TYPE_FLOAT": "'float'", "TYPE_STRING": "'string'",
    "TYPE_BOOL": "'bool'", "ELSE": "'else'", "EOF": "end of input",
}


# =========================================================================
# PART 2: table construction (YOUR TURN). Every function takes plain
# `productions` (a list of (lhs, rhs) pairs) so test_lrparser.py can try
# them on small textbook grammars before the real one.
# =========================================================================

def compute_nullable_first(productions):
    """Returns (nullable, first).
      nullable: the set of nonterminals that can derive the EMPTY string.
      first:    dict symbol -> set of terminals that can START a string
                derived from that symbol. For a terminal t, first[t] == {t}.
                (Include every symbol that appears anywhere in the grammar.)
    """
    nts = {lhs for lhs, _ in productions}
    nullable = set()
    # Every symbol in the grammar: terminal t -> {t}, nonterminal -> set()
    first = {lhs: set() for lhs in nts}
    for _, rhs in productions:
        for sym in rhs:
            first[sym] = set() if sym in nts else {sym}
    while True:
        changed = False
        for lhs, rhs in productions:
            # Check if lhs is nullable
            if all(sym in nullable for sym in rhs):
                if lhs not in nullable:
                    nullable.add(lhs)
                    changed = True
            # Update first set for lhs
            before = len(first[lhs])
            for sym in rhs:
                first[lhs].update(first[sym])
                if sym not in nullable:
                    break
            if len(first[lhs]) != before:
                changed = True
        if not changed:
            break
    return nullable, first


def compute_follow(productions, nullable, first):
    """Returns dict nonterminal -> set of terminals that can come right AFTER it.
    The start symbol (productions[0][0]) is followed by "EOF"."""
    nts = {lhs for lhs, _ in productions}
    follow = {nt: set() for nt in nts}
    follow[productions[0][0]].add("EOF")
    while True:
        changed = False
        for lhs, rhs in productions:
            for i, sym in enumerate(rhs):
                if sym in nts:
                    before = len(follow[sym])
                    # FIRST of the rest of the rhs, up to the first non-nullable symbol
                    for nxt in rhs[i + 1:]:
                        follow[sym].update(first[nxt])
                        if nxt not in nullable:
                            break
                    else:
                        # the whole rest is nullable (or empty): FOLLOW(lhs) too
                        follow[sym].update(follow[lhs])
                    if len(follow[sym]) != before:
                        changed = True
        if not changed:
            break
    return follow


def closure(items, productions):
    """All items implied by `items`. If an item has the dot right before a
    nonterminal N, then every production of N, with the dot at the start
    (index, 0), belongs to the state too. Repeat until nothing is added.
    Returns a frozenset of (production index, dot) pairs."""
    nts = {lhs for lhs, _ in productions}
    items_set = set(items)
    while True:
        new_items = set()
        for index, dot in items_set:
            lhs, rhs = productions[index]
            if dot < len(rhs):
                next_sym = rhs[dot]
                if next_sym in nts:  # Nonterminal
                    for i, (prod_lhs, prod_rhs) in enumerate(productions):
                        if prod_lhs == next_sym:
                            new_items.add((i, 0))
        if not new_items - items_set:
            break
        items_set.update(new_items)
    return frozenset(items_set)

    


def goto(items, symbol, productions):
    """The state reached from `items` after reading `symbol`: take every item
    whose dot is right before `symbol`, move the dot one step right, then
    take the closure. Returns a frozenset (empty if no item matches)."""
    next_items = set()
    for index, dot in items:
        lhs, rhs = productions[index]
        if dot < len(rhs) and rhs[dot] == symbol:
            next_items.add((index, dot + 1))
    return closure(next_items, productions)


def build_tables(productions):
    """Build the SLR(1) tables. Returns (action, goto_table):
        action[state][terminal]       -> ("shift", next_state)
                                         ("reduce", production_index)
                                         ("accept",)
        goto_table[state][nonterminal] -> next_state
    State 0 is closure({(0, 0)}). Raise ValueError("... conflict ...") if two
    different actions land in the same table cell (the grammar is not SLR(1)).
    """
    nullable, first = compute_nullable_first(productions)
    follow = compute_follow(productions, nullable, first)
    nts = {lhs for lhs, _ in productions}
    all_symbols = {s for _, rhs in productions for s in rhs}
    start_state = closure({(0, 0)}, productions)
    states = {start_state: 0}
    pending = [start_state]
    state_count = 1
    while pending:
        current = pending.pop(0)
        for symbol in all_symbols:
            next_state = goto(current, symbol, productions)
            if next_state:
                if next_state not in states:
                    states[next_state] = state_count
                    pending.append(next_state)
                    state_count += 1
    action = {}
    goto_table = {}
    for state, state_num in states.items():
        action[state_num] = {}
        goto_table[state_num] = {}
        for index, dot in state:
            lhs, rhs = productions[index]
            if dot < len(rhs):
                next_sym = rhs[dot]
                next_state = goto(state, next_sym, productions)
                if next_state:
                    target_state_num = states[next_state]
                    if next_sym not in nts:  # Terminal
                        new_act = ("shift", target_state_num)
                        old_act = action[state_num].get(next_sym)
                        if old_act is not None and old_act != new_act:
                            raise ValueError(f"conflict in action table for state {state_num} and terminal {next_sym}: {old_act} vs {new_act}")
                        action[state_num][next_sym] = new_act
                    else:  # Nonterminal
                        old = goto_table[state_num].get(next_sym)
                        if old is not None and old != target_state_num:
                            raise ValueError(f"conflict in goto table for state {state_num} and nonterminal {next_sym}")
                        goto_table[state_num][next_sym] = target_state_num
            else:  # Completed item
                if index == 0:  # Accept
                    old_act = action[state_num].get("EOF")
                    if old_act is not None and old_act != ("accept",):
                        raise ValueError(f"conflict in action table for state {state_num} and terminal EOF: {old_act} vs ('accept',)")
                    action[state_num]["EOF"] = ("accept",)
                else:  # Reduce
                    for t in follow[lhs]:
                        new_act = ("reduce", index)
                        old_act = action[state_num].get(t)
                        if old_act is not None and old_act != new_act:
                            raise ValueError(f"conflict in action table for state {state_num} and terminal {t}: {old_act} vs {new_act}")
                        action[state_num][t] = new_act
    return ([action[i] for i in range(len(action))],
            [goto_table[i] for i in range(len(goto_table))])


# =========================================================================
# PART 3: the parser (the driver loop is YOUR TURN)
# =========================================================================

_tables = None


def get_tables():
    """Build the tables once, the first time they are needed."""
    global _tables
    if _tables is None:
        _tables = build_tables(PRODUCTIONS)
    return _tables


class LRParser:
    """Same interface as Parser: LRParser(tokens).parse() returns a Program."""

    def __init__(self, tokens):
        self.tokens = tokens

    def syntax_error(self, action_row, tok):
        """(given) Turn 'no action for this token' into a ParseError."""
        found = "end of input" if tok.type == T.EOF else f"'{tok.lexeme}'"
        expected = sorted(TERMINAL_TEXT.get(t, t.lower()) for t in action_row)
        msg = f"unexpected {found}"
        if 1 <= len(expected) <= 6:
            msg += ", expected " + " or ".join(expected)
        return ParseError(msg, tok.line, tok.col)

    def parse(self):
        """The shift-reduce loop.

        stack: a list of (state, value) pairs, starting as [(0, None)].
        pos:   index of the next token.

        Repeat:
          1. tok = the current token; state = the state on top of the stack
          2. act = action[state].get(tok.type.name)
          3. act is None            -> raise self.syntax_error(action[state], tok)
             act[0] == "shift"      -> push (act[1], tok) and move to the next token
             act[0] == "reduce"     -> p = act[1]; n = len(PRODUCTIONS[p][1]).
                                       Pop n entries; their values, in order, are the
                                       `children`. value = ACTIONS[p](children).
                                       Then look at the NEW top state and push
                                       (goto_table[top_state][lhs], value).
                                       (Reducing does NOT consume a token.)
             act[0] == "accept"     -> return the value on top of the stack (the Program)
        """
        action, goto_table = get_tables()
        toks = self.tokens
        stack = [(0, None)]
        pos = 0
        while True:
            state = stack[-1][0]
            tok = toks[pos]
            act = action[state].get(tok.type.name)
            if act is None:
                raise self.syntax_error(action[state], tok)
            if act[0] == "shift":
                stack.append((act[1], tok))
                pos += 1
            elif act[0] == "reduce":
                p = act[1]
                n = len(PRODUCTIONS[p][1])
                children = [stack.pop()[1] for _ in range(n)][::-1]
                value = ACTIONS[p](children)
                new_state = stack[-1][0]
                lhs = PRODUCTIONS[p][0]
                stack.append((goto_table[new_state][lhs], value))
            elif act[0] == "accept":
                return stack[-1][1]
            else:
                raise ValueError(f"Unknown action {act[0]} in state {state}")