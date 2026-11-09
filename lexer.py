"""OnlyGod lexer: turns source text into a list of tokens.

Your job: fill in every TODO. Run `python test_lexer.py` after each one.
"""
from dataclasses import dataclass
from enum import Enum, auto


class T(Enum):
    # literals
    NUMBER = auto(); STRING = auto(); IDENT = auto()
    # keywords
    LET = auto(); FUN = auto(); IF = auto(); ELSE = auto(); WHILE = auto()
    RETURN = auto(); PRINT = auto(); READ = auto()
    TRUE = auto(); FALSE = auto(); AND = auto(); OR = auto(); NOT = auto()
    TYPE_INT = auto(); TYPE_FLOAT = auto(); TYPE_STRING = auto(); TYPE_BOOL = auto()
    # operators
    PLUS = auto(); MINUS = auto(); STAR = auto(); SLASH = auto(); PERCENT = auto()
    EQ = auto(); EQEQ = auto(); BANGEQ = auto()
    LT = auto(); LE = auto(); GT = auto(); GE = auto()
    # punctuation
    LPAREN = auto(); RPAREN = auto(); LBRACE = auto(); RBRACE = auto()
    COMMA = auto(); COLON = auto(); SEMI = auto()
    EOF = auto()


@dataclass
class Token:
    type: T
    lexeme: str      # the exact source text, e.g. "let" or "3.14"
    value: object    # the Python value for literals (5, 3.14, "hi"), else None
    line: int
    col: int

SINGLE = {
    "(": T.LPAREN,
    ")": T.RPAREN,
    "{": T.LBRACE,
    "}": T.RBRACE,
    ",": T.COMMA,
    ":": T.COLON,
    ";": T.SEMI,
    "+": T.PLUS,
    "-": T.MINUS,
    "*": T.STAR,
    "/": T.SLASH,
    "%": T.PERCENT
}

KEYWORDS = {
    "let": T.LET,
    "fun": T.FUN,
    "if": T.IF,
    "else": T.ELSE,
    "while": T.WHILE,
    "return": T.RETURN,
    "print": T.PRINT,
    "read": T.READ,
    "true": T.TRUE,
    "false": T.FALSE,
    "and": T.AND,
    "or": T.OR,
    "not": T.NOT,
    "int": T.TYPE_INT,
    "float": T.TYPE_FLOAT,
    "string": T.TYPE_STRING,
    "bool": T.TYPE_BOOL,
}


class LexError(Exception):
    def __init__(self, msg, line, col):
        super().__init__(f"line {line}, col {col}: {msg}")
        self.line = line
        self.col = col


class Lexer:
    def __init__(self, source: str):
        self.src = source
        self.pos = 0     # index of the next character to read
        self.line = 1
        self.col = 1

    # ---- helpers -------------------------------------------------------

    def at_end(self) -> bool:
        return self.pos >= len(self.src)
        

    def peek(self) -> str:
        if self.at_end():
            return "\0"
        return self.src[self.pos]
        

    def advance(self) -> str:
        if self.at_end():
            raise LexError("Unexpected end of input", self.line, self.col)
        char = self.src[self.pos]
        self.pos += 1
        if char == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return char
        

    def match(self, expected: str) -> bool:
        if self.at_end():
            return False
        if self.src[self.pos] == expected:
            self.advance()
            return True
        return False
        

    # ---- main loop -----------------------------------------------------

    def tokenize(self) -> list:
        tokens = []
        while not self.at_end():
            char = self.peek()
            if char.isspace():
                self.advance()
                continue
            elif char == '#':
                while not self.at_end() and self.peek() != '\n':
                    self.advance()
                continue
            else:
                token = self.scan_token()
                tokens.append(token)
        tokens.append(Token(T.EOF, "", None, self.line, self.col))
        return tokens

    def make(self, ttype, start_pos, line, col, value=None):
        return Token(ttype, self.src[start_pos:self.pos], value, line, col)

    def scan_token(self) -> Token:
        start_pos, line, col = self.pos, self.line, self.col
        char = self.peek()
        if char in SINGLE:
            self.advance()
            return self.make(SINGLE[char], start_pos, line, col)
        elif char == '=':
            self.advance()
            if self.match('='):
                return self.make(T.EQEQ, start_pos, line, col)
            else:
                return self.make(T.EQ, start_pos, line, col)
        elif char == '!':
            self.advance()
            if self.match('='):
                return self.make(T.BANGEQ, start_pos, line, col)
            raise LexError("unexpected '!', use 'not' for negation or '!=' for not equal", line, col)
        elif char == '<':
            self.advance()
            if self.match('='):
                return self.make(T.LE, start_pos, line, col)
            return self.make(T.LT, start_pos, line, col)
        elif char == '>':
            self.advance()
            if self.match('='):
                return self.make(T.GE, start_pos, line, col)
            return self.make(T.GT, start_pos, line, col)
        elif char == '"':
            self.advance()                       # consume the opening quote
            while not self.at_end() and self.peek() != '"':
                self.advance()
            if self.at_end():
                raise LexError("unterminated string, add a closing \" at the end", line, col)
            self.advance()                       # consume the closing quote
            text = self.src[start_pos + 1 : self.pos - 1]
            return self.make(T.STRING, start_pos, line, col, text)
        elif char.isdigit():
            value = ""
            while not self.at_end() and (self.peek().isdigit() or (self.peek() == '.' and not '.' in value)):
                value += self.advance()
            if '.' in value:
                return self.make(T.NUMBER, start_pos, line, col, float(value))
            else:
                return self.make(T.NUMBER, start_pos, line, col, int(value))
        elif char.isalpha() or char == '_':
            value = ""
            while not self.at_end() and (self.peek().isalnum() or self.peek() == '_'):
                value += self.advance()
            return self.make(KEYWORDS.get(value, T.IDENT), start_pos, line, col)
        #                 then look the text up in KEYWORDS
        #   f) anything else -> LexError with a helpful message
        raise LexError("Unexpected character", line, col)