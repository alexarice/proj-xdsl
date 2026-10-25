from __future__ import annotations

import re
from enum import Enum, auto
from typing import NoReturn

from xdsl.utils.lexer import Lexer, Position, Span, Token


class ProjTokenKind(Enum):
    """Token kinds for proj-xdsl surface syntax."""

    # Markers
    EOF = auto()

    # Type keywords (reserved, cannot be used as identifiers)
    QUBIT = auto()
    PROJECTION = auto()
    BOOL = auto()
    ANGLE = auto()

    # Punctuation
    LESS = auto()
    GREATER = auto()

    # Identifier (includes X, Y, Z which can be basis or identifiers)
    IDENTIFIER = auto()

    def is_punctuation(self) -> bool:
        """Check if this token kind is punctuation."""
        return self in (
            ProjTokenKind.LESS,
            ProjTokenKind.GREATER,
        )

    @staticmethod
    def get_punctuation_kind_from_spelling(spelling: str) -> ProjTokenKind:
        """Get the token kind for a punctuation spelling."""
        if spelling not in KIND_BY_PUNCTUATION_SPELLING:
            raise ValueError(f"Unknown punctuation: {spelling}")
        return KIND_BY_PUNCTUATION_SPELLING[spelling]


KIND_BY_PUNCTUATION_SPELLING = {
    "<": ProjTokenKind.LESS,
    ">": ProjTokenKind.GREATER,
}

TYPE_KEYWORD_MAP = {
    "qubit": ProjTokenKind.QUBIT,
    "proj": ProjTokenKind.PROJECTION,
    "bool": ProjTokenKind.BOOL,
    "angle": ProjTokenKind.ANGLE,
}

ProjToken = Token[ProjTokenKind]


class ProjLexer(Lexer[ProjTokenKind]):
    """Lexer for proj-xdsl surface syntax."""

    _whitespace_regex = re.compile(r"((//[^\n]*(\n)?)|(\s+))*", re.ASCII)
    _identifier_regex = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*", re.ASCII)

    def _is_in_bounds(self, size: Position = 1) -> bool:
        """Check if the current position is within the bounds of the input."""
        return self.pos + size - 1 < self.input.len

    def _get_chars(self, size: int = 1) -> str | None:
        """Get the character at the current location, or multiple characters ahead."""
        res = self.input.slice(self.pos, self.pos + size)
        self.pos += size
        return res

    def _peek_chars(self, size: int = 1) -> str | None:
        """Peek at the character at the current location."""
        return self.input.slice(self.pos, self.pos + size)

    def _consume_chars(self, size: int = 1) -> None:
        """Advance the lexer position in the input by the given amount."""
        self.pos += size

    def _consume_whitespace(self) -> None:
        """Skip whitespace and comments."""
        self._consume_regex(self._whitespace_regex)

    def _consume_regex(self, regex: re.Pattern[str]) -> re.Match[str] | None:
        """Advance lexer position to end of next match of given regex."""
        match = regex.match(self.input.content, self.pos)
        if match is None:
            return None
        self.pos = match.end()
        return match

    def _form_token(self, kind: ProjTokenKind, start_pos: Position) -> ProjToken:
        """Return a token with the given kind and start position."""
        return Token(kind, Span(start_pos, self.pos, self.input))

    def lex(self) -> ProjToken:
        """Lex a token from the input and return it."""
        self._consume_whitespace()

        if not self._is_in_bounds():
            return self._form_token(ProjTokenKind.EOF, self.pos)

        # Try punctuation first
        if punct := self._try_punctuation():
            return punct

        # Try type keywords (single character)
        if keyword := self._try_type_keyword():
            return keyword

        # Try identifier (includes X, Y, Z which can be basis or identifiers)
        if ident := self._try_identifier():
            return ident

        # Unknown character
        start_pos = self.pos
        self._consume_chars()
        self.raise_error(f"Unexpected character: {self.input.content[start_pos]}")

    def _try_punctuation(self) -> ProjToken | None:
        """Try to lex punctuation."""
        for spelling, kind in KIND_BY_PUNCTUATION_SPELLING.items():
            if self._peek_chars(len(spelling)) == spelling:
                start_pos = self.pos
                self._consume_chars(len(spelling))
                return self._form_token(kind, start_pos)
        return None

    def _try_type_keyword(self) -> ProjToken | None:
        """Try to lex type keywords (qubit, proj, bool, angle)."""
        for keyword, kind in TYPE_KEYWORD_MAP.items():
            if self._peek_chars(len(keyword)) == keyword:
                # Make sure it's not part of a larger identifier
                next_char: str | None = None
                if self._is_in_bounds(len(keyword) + 1):
                    peeked = self._peek_chars(len(keyword) + 1)
                    assert peeked is not None
                    next_char = peeked[-1]
                if next_char is None or not (next_char.isalnum() or next_char == "_"):
                    self._consume_chars(len(keyword))
                    return self._form_token(kind, self.pos - len(keyword))
        return None

    def _try_identifier(self) -> ProjToken | None:
        """Try to lex an identifier."""
        match = self._consume_regex(self._identifier_regex)
        if match is None:
            return None
        return self._form_token(ProjTokenKind.IDENTIFIER, match.start())

    def raise_error(self, msg: str, at_position: Position | None = None) -> NoReturn:
        """Raise a lexing error at the given position."""
        if at_position is None:
            at_position = self.pos
        span = Span(at_position, at_position + 1, self.input)
        raise ValueError(span.print_with_context(msg))
