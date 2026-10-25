"""Tests for the proj-xdsl surface syntax lexer."""

import pytest
from xdsl.utils.lexer import Input

from projxdsl.frontend.lexer import ProjLexer, ProjTokenKind


def lex_all(code: str) -> list[tuple[ProjTokenKind, str]]:
    """Helper to lex all tokens from a string."""
    lexer = ProjLexer(Input(code, "<test>"))
    tokens: list[tuple[ProjTokenKind, str]] = []
    while True:
        token = lexer.lex()
        tokens.append((token.kind, token.text))
        if token.kind == ProjTokenKind.EOF:
            break
    return tokens


class TestTypeKeywords:
    """Test lexing of type keywords."""

    def test_qubit_type(self):
        tokens = lex_all("qubit")
        assert tokens == [(ProjTokenKind.QUBIT, "qubit"), (ProjTokenKind.EOF, "")]

    def test_projection_type(self):
        tokens = lex_all("proj")
        assert tokens == [(ProjTokenKind.PROJECTION, "proj"), (ProjTokenKind.EOF, "")]

    def test_bool_type(self):
        tokens = lex_all("bool")
        assert tokens == [(ProjTokenKind.BOOL, "bool"), (ProjTokenKind.EOF, "")]

    def test_angle_type(self):
        tokens = lex_all("angle")
        assert tokens == [(ProjTokenKind.ANGLE, "angle"), (ProjTokenKind.EOF, "")]

    def test_all_types(self):
        tokens = lex_all("qubit proj bool angle")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.PROJECTION, "proj"),
            (ProjTokenKind.BOOL, "bool"),
            (ProjTokenKind.ANGLE, "angle"),
            (ProjTokenKind.EOF, ""),
        ]


class TestBasisAsIdentifiers:
    """Test that X, Y, Z are lexed as identifiers (parser validates context)."""

    def test_x_is_identifier(self):
        tokens = lex_all("X")
        assert tokens == [(ProjTokenKind.IDENTIFIER, "X"), (ProjTokenKind.EOF, "")]

    def test_x_lower_is_identifier(self):
        tokens = lex_all("x")
        assert tokens == [(ProjTokenKind.IDENTIFIER, "x"), (ProjTokenKind.EOF, "")]

    def test_y_is_identifier(self):
        tokens = lex_all("Y")
        assert tokens == [(ProjTokenKind.IDENTIFIER, "Y"), (ProjTokenKind.EOF, "")]

    def test_y_lower_is_identifier(self):
        tokens = lex_all("y")
        assert tokens == [(ProjTokenKind.IDENTIFIER, "y"), (ProjTokenKind.EOF, "")]

    def test_z_is_identifier(self):
        tokens = lex_all("Z")
        assert tokens == [(ProjTokenKind.IDENTIFIER, "Z"), (ProjTokenKind.EOF, "")]

    def test_z_lower_is_identifier(self):
        tokens = lex_all("z")
        assert tokens == [(ProjTokenKind.IDENTIFIER, "z"), (ProjTokenKind.EOF, "")]

    def test_basis_in_qubit_type(self):
        """X, Y, Z in Q<X> are identifiers - parser validates basis."""
        tokens = lex_all("qubit<X>")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.LESS, "<"),
            (ProjTokenKind.IDENTIFIER, "X"),
            (ProjTokenKind.GREATER, ">"),
            (ProjTokenKind.EOF, ""),
        ]

    def test_x_as_function_name(self):
        """X can be used as a function name."""
        tokens = lex_all("X")
        assert tokens == [(ProjTokenKind.IDENTIFIER, "X"), (ProjTokenKind.EOF, "")]

    def test_xyz_as_function_names(self):
        """X, Y, Z can all be used as function names."""
        for char in ["X", "Y", "Z", "x", "y", "z"]:
            tokens = lex_all(char)
            assert tokens == [(ProjTokenKind.IDENTIFIER, char), (ProjTokenKind.EOF, "")]


class TestPunctuation:
    """Test lexing of punctuation."""

    def test_less(self):
        tokens = lex_all("<")
        assert tokens == [(ProjTokenKind.LESS, "<"), (ProjTokenKind.EOF, "")]

    def test_greater(self):
        tokens = lex_all(">")
        assert tokens == [(ProjTokenKind.GREATER, ">"), (ProjTokenKind.EOF, "")]

    def test_angle_brackets(self):
        tokens = lex_all("<>")
        assert tokens == [
            (ProjTokenKind.LESS, "<"),
            (ProjTokenKind.GREATER, ">"),
            (ProjTokenKind.EOF, ""),
        ]


class TestQubitWithBasis:
    """Test lexing of qubit types with basis annotations."""

    def test_qubit_x_upper(self):
        tokens = lex_all("qubit<X>")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.LESS, "<"),
            (ProjTokenKind.IDENTIFIER, "X"),
            (ProjTokenKind.GREATER, ">"),
            (ProjTokenKind.EOF, ""),
        ]

    def test_qubit_y(self):
        tokens = lex_all("qubit<Y>")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.LESS, "<"),
            (ProjTokenKind.IDENTIFIER, "Y"),
            (ProjTokenKind.GREATER, ">"),
            (ProjTokenKind.EOF, ""),
        ]

    def test_qubit_z(self):
        tokens = lex_all("qubit<Z>")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.LESS, "<"),
            (ProjTokenKind.IDENTIFIER, "Z"),
            (ProjTokenKind.GREATER, ">"),
            (ProjTokenKind.EOF, ""),
        ]


class TestWhitespace:
    """Test whitespace handling."""

    def test_spaces(self):
        tokens = lex_all("qubit   proj")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.PROJECTION, "proj"),
            (ProjTokenKind.EOF, ""),
        ]

    def test_tabs(self):
        tokens = lex_all("qubit\t\tproj")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.PROJECTION, "proj"),
            (ProjTokenKind.EOF, ""),
        ]

    def test_newlines(self):
        tokens = lex_all("qubit\nproj")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.PROJECTION, "proj"),
            (ProjTokenKind.EOF, ""),
        ]

    def test_mixed_whitespace(self):
        tokens = lex_all("qubit \t\n proj")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.PROJECTION, "proj"),
            (ProjTokenKind.EOF, ""),
        ]


class TestComments:
    """Test comment handling."""

    def test_single_line_comment(self):
        tokens = lex_all("qubit // this is a comment\nproj")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.PROJECTION, "proj"),
            (ProjTokenKind.EOF, ""),
        ]

    def test_comment_at_end(self):
        tokens = lex_all("qubit // comment")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.EOF, ""),
        ]

    def test_multiple_comments(self):
        tokens = lex_all("qubit // comment1\nproj // comment2\nbool")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.PROJECTION, "proj"),
            (ProjTokenKind.BOOL, "bool"),
            (ProjTokenKind.EOF, ""),
        ]


class TestIdentifiers:
    """Test identifier lexing."""

    def test_simple_identifier(self):
        tokens = lex_all("foo")
        assert tokens == [(ProjTokenKind.IDENTIFIER, "foo"), (ProjTokenKind.EOF, "")]

    def test_identifier_with_underscore(self):
        tokens = lex_all("_foo")
        assert tokens == [(ProjTokenKind.IDENTIFIER, "_foo"), (ProjTokenKind.EOF, "")]

    def test_identifier_with_numbers(self):
        tokens = lex_all("foo123")
        assert tokens == [(ProjTokenKind.IDENTIFIER, "foo123"), (ProjTokenKind.EOF, "")]

    def test_identifier_mixed(self):
        tokens = lex_all("foo_bar_123")
        assert tokens == [
            (ProjTokenKind.IDENTIFIER, "foo_bar_123"),
            (ProjTokenKind.EOF, ""),
        ]


class TestTypeKeywordNotIdentifier:
    """Test that type keywords are not lexed as identifiers."""

    def test_q_not_identifier(self):
        tokens = lex_all("qubit")
        assert tokens[0][0] == ProjTokenKind.QUBIT
        assert tokens[0][0] != ProjTokenKind.IDENTIFIER

    def test_qx_is_q_then_x(self):
        """QX should be lexed as identifier, not Q then X."""
        tokens = lex_all("qubitX")
        assert tokens == [(ProjTokenKind.IDENTIFIER, "qubitX"), (ProjTokenKind.EOF, "")]

    def test_q_then_x_separate(self):
        """Q X should be lexed separately."""
        tokens = lex_all("qubit X")
        assert tokens == [
            (ProjTokenKind.QUBIT, "qubit"),
            (ProjTokenKind.IDENTIFIER, "X"),
            (ProjTokenKind.EOF, ""),
        ]


class TestErrors:
    """Test error handling."""

    def test_unknown_character(self):
        lexer = ProjLexer(Input("@", "<test>"))
        with pytest.raises(ValueError, match="Unexpected character: @"):
            lexer.lex()

    def test_multiple_unknown_characters(self):
        lexer = ProjLexer(Input("@#$", "<test>"))
        with pytest.raises(ValueError, match="Unexpected character: @"):
            lexer.lex()

    def test_unknown_in_middle(self):
        lexer = ProjLexer(Input("qubit @ proj", "<test>"))
        # Should successfully lex Q
        token1 = lexer.lex()
        assert token1.kind == ProjTokenKind.QUBIT
        # Should fail on @
        with pytest.raises(ValueError, match="Unexpected character: @"):
            lexer.lex()
