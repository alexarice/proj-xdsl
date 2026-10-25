"""Parser for proj-xdsl surface syntax."""

from __future__ import annotations

from xdsl.dialects.builtin import NoneAttr, i1
from xdsl.ir import TypeAttribute
from xdsl.parser.generic_parser import GenericParser, ParserState

from projxdsl.dialects.proj import (
    AngleType,
    Basis,
    BasisAttr,
    ProjectionType,
    QubitType,
)
from projxdsl.frontend.lexer import ProjLexer, ProjToken, ProjTokenKind


class ProjParserState(ParserState[ProjTokenKind]):
    """Parser state for proj-xdsl surface syntax."""

    def __init__(self, lexer: ProjLexer):
        super().__init__(lexer)


class ProjParser(GenericParser[ProjTokenKind]):
    """
    Recursive descent parser for proj-xdsl surface syntax.
    Extends xDSL's GenericParser infrastructure.
    """

    def __init__(self, code: str, filename: str = "<input>"):
        from xdsl.utils.lexer import Input

        input = Input(code, filename)
        lexer = ProjLexer(input)
        super().__init__(ProjParserState(lexer))

    def parse_type(self) -> TypeAttribute:
        """
        Parse a type from surface syntax.

        type ::= qubit-type | proj-type | bool-type | angle-type
        qubit-type ::= "qubit" ( "<" basis ">" )?
        basis ::= "X" | "Y" | "Z" (uppercase only)
        proj-type ::= "proj"
        bool-type ::= "bool"
        angle-type ::= "angle"
        """
        if self._parse_optional_token(ProjTokenKind.QUBIT) is not None:
            # Parse qubit type: qubit or qubit<basis>
            if self.parse_optional_punctuation("<") is not None:
                basis = self._parse_basis()
                self.parse_punctuation(">", " to close qubit basis")
                return QubitType(BasisAttr(basis))
            return QubitType(NoneAttr())
        elif self._parse_optional_token(ProjTokenKind.PROJECTION) is not None:
            return ProjectionType()
        elif self._parse_optional_token(ProjTokenKind.BOOL) is not None:
            return i1
        elif self._parse_optional_token(ProjTokenKind.ANGLE) is not None:
            return AngleType()
        else:
            self.raise_error(
                "Expected type (qubit, projection, bool, or angle),"
                f" got {self._current_token.kind.name}",
            )

    def _parse_basis(self) -> Basis:
        """
        Parse basis: X, Y, or Z (uppercase only).
        Basis is lexed as an identifier, so we validate it here.
        """
        token = self._parse_optional_token(ProjTokenKind.IDENTIFIER)
        if token is None:
            self.raise_error(
                "Expected basis identifier (X, Y, or Z),"
                f" got {self._current_token.kind.name}",
            )

        if token.text == "X":
            return Basis.X
        elif token.text == "Y":
            return Basis.Y
        elif token.text == "Z":
            return Basis.Z
        else:
            self.raise_error(
                f"Invalid basis '{token.text}', expected X, Y, or Z (uppercase only)"
            )

    def parse_punctuation(self, punctuation: str, context_msg: str = "") -> ProjToken:
        """Parse expected punctuation."""
        return self.expect(
            lambda: self.parse_optional_punctuation(punctuation),
            f"Expected '{punctuation}'{context_msg}",
        )

    def parse_optional_punctuation(self, punctuation: str) -> ProjToken | None:
        """Try to parse punctuation, return None if not present."""
        kind = ProjTokenKind.get_punctuation_kind_from_spelling(punctuation)
        return self._parse_optional_token(kind)

    def expect_eof(self) -> None:
        """Expect end of file, raise error if there are remaining tokens."""
        if self._current_token.kind != ProjTokenKind.EOF:
            self.raise_error(
                f"Unexpected token after expression: {self._current_token.text}"
            )
