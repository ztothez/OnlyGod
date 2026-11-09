"""OnlyGod parser: turns a list of tokens into an AST.

Recursive descent: every grammar rule from the BNF becomes one method.
Precedence works because a rule calls the rule BELOW it (the one that
binds tighter). Lowest precedence is at the top, highest at the bottom:

    expression -> logic_or -> logic_and -> equality -> comparison
               -> term -> factor -> unary -> call -> primary

Step 1: expressions (done). Step 2: statements (TODOs at the bottom of the class).
"""
from lexer import T, Token
from ast_nodes import (
    Literal, Variable, Unary, Binary, Call,
    Param, VarDecl, Assign, Print, Read, Block, If, While, Return,
    ExprStmt, FunDecl, Program,
)


class ParseError(Exception):
    def __init__(self, msg, line, col):
        super().__init__(f"line {line}, col {col}: {msg}")
        self.line = line
        self.col = col


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ---- helpers (given) -----------------------------------------------

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def at_end(self) -> bool:
        return self.peek().type == T.EOF

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if not self.at_end():
            self.pos += 1
        return tok

    def check(self, *types) -> bool:
        return self.peek().type in types

    def match(self, *types):
        """If the current token is one of `types`, consume and return it.
        Otherwise return None and consume nothing."""
        if self.check(*types):
            return self.advance()
        return None

    def expect(self, ttype, msg) -> Token:
        if self.check(ttype):
            return self.advance()
        tok = self.peek()
        raise ParseError(msg, tok.line, tok.col)

    # ---- expressions ---------------------------------------------------

    def expression(self):
        return self.logic_or()

    def logic_or(self):
        left = self.logic_and()
        while True:
            op = self.match(T.OR)
            if op is None:
                break
            right = self.logic_and()
            left = Binary(op.lexeme, left, right, left.line, left.col)
        return left

    def logic_and(self):
        left = self.equality()
        while True:
            op = self.match(T.AND)
            if op is None:
                break
            right = self.equality()
            left = Binary(op.lexeme, left, right, left.line, left.col)
        return left

    def equality(self):
        left = self.comparison()
        while True:
            op = self.match(T.EQEQ, T.BANGEQ)
            if op is None:
                break
            right = self.comparison()
            left = Binary(op.lexeme, left, right, left.line, left.col)
        return left

    def comparison(self):
        left = self.term()
        while True:
            op = self.match(T.LT, T.LE, T.GT, T.GE)
            if op is None:
                break
            right = self.term()
            left = Binary(op.lexeme, left, right, left.line, left.col)
        return left

    def term(self):
        # WORKED EXAMPLE. Copy this shape for the other levels.
        # The while loop (not recursion) is what makes "a - b - c"
        # group as "(a - b) - c", i.e. left associative.
        left = self.factor()
        while True:
            op = self.match(T.PLUS, T.MINUS)
            if op is None:
                break
            right = self.factor()
            left = Binary(op.lexeme, left, right, left.line, left.col)
        return left

    def factor(self):
        left = self.unary()
        while True:
            op = self.match(T.STAR, T.SLASH, T.PERCENT)
            if op is None:
                break
            right = self.unary()
            left = Binary(op.lexeme, left, right, left.line, left.col)
        return left

    def unary(self):
        op = self.match(T.MINUS, T.NOT)
        if op:
            operand = self.unary()
            return Unary(op.lexeme, operand, op.line, op.col)
        return self.call()

    def call(self):
        expr = self.primary()
        if isinstance(expr, Variable) and self.match(T.LPAREN):
            args = []
            if not self.check(T.RPAREN):
                while True:
                    args.append(self.expression())
                    if not self.match(T.COMMA):
                        break
            self.expect(T.RPAREN, "expected ')' to close the '('")
            return Call(expr.name, args, expr.line, expr.col)
        return expr

    def primary(self):
        tok = self.peek()
        if tok.type == T.NUMBER or tok.type == T.STRING:
            self.advance()
            return Literal(tok.value, tok.line, tok.col)
        elif tok.type == T.TRUE:
            self.advance()
            return Literal(True, tok.line, tok.col)
        elif tok.type == T.FALSE:
            self.advance()
            return Literal(False, tok.line, tok.col)
        elif tok.type == T.IDENT:
            self.advance()
            return Variable(tok.lexeme, tok.line, tok.col)
        elif tok.type == T.LPAREN:
            self.advance()
            expr = self.expression()
            self.expect(T.RPAREN, "expected ')' to close the '('")
            return expr
        found = "end of input" if tok.type == T.EOF else repr(tok.lexeme)
        raise ParseError(f"expected an expression, found {found}", tok.line, tok.col)

    # ====================================================================
    # STEP 2: STATEMENTS
    #
    #   program     -> declaration* EOF
    #   declaration -> varDecl | funDecl | statement
    #   varDecl     -> "let" IDENT ":" type "=" expression ";"
    #   funDecl     -> "fun" IDENT "(" params? ")" ":" type block
    #   statement   -> printStmt | readStmt | ifStmt | whileStmt
    #                | returnStmt | block | assignStmt | exprStmt
    #   assignStmt  -> IDENT "=" expression ";"
    #   printStmt   -> "print" expression ";"
    #   readStmt    -> "read" IDENT ";"
    #   ifStmt      -> "if" "(" expression ")" block ( "else" block )?
    #   whileStmt   -> "while" "(" expression ")" block
    #   returnStmt  -> "return" expression? ";"
    #   block       -> "{" declaration* "}"
    #   exprStmt    -> expression ";"
    #
    # Same idea as expressions: one method per rule. The difference is that
    # statements are chosen by looking at the FIRST token (let, fun, print...).
    # ====================================================================

    def peek_next(self) -> Token:
        """The token AFTER the current one, without consuming anything.
        Needed to tell `x = 1;` (assignment) from `x + 1;` (expression)."""
        return self.tokens[min(self.pos + 1, len(self.tokens) - 1)]

    # ---- WORKED EXAMPLES (read these, then copy the shape) ---------------

    def parse(self):
        statements = []
        while not self.at_end():
            statements.append(self.declaration())
        return Program(statements)

    def print_statement(self):
        kw = self.advance()                          # the 'print' keyword
        value = self.expression()
        self.expect(T.SEMI, "expected ';' after the value to print")
        return Print(value, kw.line, kw.col)         # node starts at the keyword

    # ---- YOUR TURN -------------------------------------------------------

    def declaration(self):
        if self.check(T.LET):
            return self.var_decl()
        elif self.check(T.FUN):
            return self.fun_decl()
        else:
            return self.statement()

    def statement(self):
        if self.check(T.PRINT):
            return self.print_statement()
        elif self.check(T.READ):
            return self.read_statement()
        elif self.check(T.IF):
            return self.if_statement()
        elif self.check(T.WHILE):
            return self.while_statement()
        elif self.check(T.RETURN):
            return self.return_statement()
        elif self.check(T.LBRACE):
            return self.block()
        elif self.check(T.IDENT) and self.peek_next().type == T.EQ:
            return self.assign_statement()
        else:
            return self.expr_statement()

    def parse_type(self):
        if self.check(T.TYPE_INT, T.TYPE_FLOAT, T.TYPE_STRING, T.TYPE_BOOL):
            return self.advance().lexeme
        tok = self.peek()
        raise ParseError("expected a type (int, float, string or bool)", tok.line, tok.col)

    def var_decl(self):
        kw = self.advance()  # 'let'
        name = self.expect(T.IDENT, "expected a variable name after 'let'")
        self.expect(T.COLON, "expected ':' and a type after the variable name")
        type_name = self.parse_type()
        self.expect(T.EQ, "expected '=' and an initial value after the type")
        init = self.expression()
        self.expect(T.SEMI, "expected ';' after the variable declaration")
        return VarDecl(name.lexeme, type_name, init, kw.line, kw.col)   

    def assign_statement(self):
        name = self.advance()  # the IDENT
        self.expect(T.EQ, "expected '=' after the variable name")
        value = self.expression()
        self.expect(T.SEMI, "expected ';' after the assignment")
        return Assign(name.lexeme, value, name.line, name.col)

    def read_statement(self):
        kw = self.advance()  # 'read'
        name = self.expect(T.IDENT, "expected a variable name after 'read'")
        self.expect(T.SEMI, "expected ';' after the variable name")
        return Read(name.lexeme, kw.line, kw.col)

    def expr_statement(self):
        first_token = self.peek()
        expr = self.expression()
        self.expect(T.SEMI, "expected ';' after the expression")
        return ExprStmt(expr, first_token.line, first_token.col)

    def return_statement(self):
        kw = self.advance()  # 'return'
        if self.check(T.SEMI):
            self.advance()  # consume the SEMI
            return Return(None, kw.line, kw.col)
        value = self.expression()
        self.expect(T.SEMI, "expected ';' after the return value")
        return Return(value, kw.line, kw.col)

    def block(self):
        lb = self.expect(T.LBRACE, "expected '{' to start a block")
        statements = []
        while not self.check(T.RBRACE) and not self.at_end():
            statements.append(self.declaration())
        self.expect(T.RBRACE, f"expected '}}' to close the block opened at line {lb.line}, col {lb.col}")
        return Block(statements, lb.line, lb.col)

    def if_statement(self):
        kw = self.advance()  # 'if'
        self.expect(T.LPAREN, "expected '(' after 'if'")
        cond = self.expression()
        self.expect(T.RPAREN, "expected ')' after the condition")
        then_block = self.block()
        else_block = None
        if self.match(T.ELSE):
            else_block = self.block()
        return If(cond, then_block, else_block, kw.line, kw.col)

    def while_statement(self):
        kw = self.advance()  # 'while'
        self.expect(T.LPAREN, "expected '(' after 'while'")
        cond = self.expression()
        self.expect(T.RPAREN, "expected ')' after the condition")
        body = self.block()
        return While(cond, body, kw.line, kw.col)

    def fun_decl(self):
        kw = self.advance()  # 'fun'
        name = self.expect(T.IDENT, "expected a function name after 'fun'")
        self.expect(T.LPAREN, "expected '(' after the function name")
        params = []
        if not self.check(T.RPAREN):
            while True:
                param_name = self.expect(T.IDENT, "expected a parameter name")
                self.expect(T.COLON, "expected ':' and a type after the parameter name")
                param_type = self.parse_type()
                params.append(Param(param_name.lexeme, param_type, param_name.line, param_name.col))
                if not self.match(T.COMMA):
                    break
        self.expect(T.RPAREN, "expected ')' after the parameter list")
        self.expect(T.COLON, "expected ':' and a return type after the parameter list")
        return_type = self.parse_type()
        body = self.block()
        return FunDecl(name.lexeme, params, return_type, body, kw.line, kw.col)
