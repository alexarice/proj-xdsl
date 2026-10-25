"""Tests for the proj-xdsl surface syntax parser."""

import pytest
from xdsl.dialects.builtin import NoneAttr, i1
from xdsl.utils.exceptions import ParseError

from projxdsl.dialects.proj import (
    AngleType,
    Basis,
    BasisAttr,
    ProjectionType,
    QubitType,
)
from projxdsl.frontend.parser import ProjParser


def parse_type(code: str):
    """Helper to parse a type and return the TypeAttribute."""
    parser = ProjParser(code)
    result = parser.parse_type()
    parser.expect_eof()
    return result


class TestTypeParsing:
    """Test parsing of types."""

    def test_qubit_unborrowed(self):
        result = parse_type("Q")
        assert isinstance(result, QubitType)
        assert isinstance(result.borrow_type, NoneAttr)

    def test_projection(self):
        result = parse_type("P")
        assert isinstance(result, ProjectionType)

    def test_boolean(self):
        result = parse_type("B")
        assert result == i1

    def test_angle(self):
        result = parse_type("A")
        assert isinstance(result, AngleType)


class TestQubitWithBasis:
    """Test parsing of qubit types with basis annotations (uppercase only)."""

    def test_qubit_x_upper(self):
        result = parse_type("Q<X>")
        assert isinstance(result, QubitType)
        assert isinstance(result.borrow_type, BasisAttr)
        assert result.borrow_type.data == Basis.X

    def test_qubit_y_upper(self):
        result = parse_type("Q<Y>")
        assert isinstance(result, QubitType)
        assert isinstance(result.borrow_type, BasisAttr)
        assert result.borrow_type.data == Basis.Y

    def test_qubit_z_upper(self):
        result = parse_type("Q<Z>")
        assert isinstance(result, QubitType)
        assert isinstance(result.borrow_type, BasisAttr)
        assert result.borrow_type.data == Basis.Z

    def test_qubit_x_lower_invalid(self):
        with pytest.raises(ParseError, match="uppercase only"):
            parse_type("Q<x>")

    def test_qubit_y_lower_invalid(self):
        with pytest.raises(ParseError, match="uppercase only"):
            parse_type("Q<y>")

    def test_qubit_z_lower_invalid(self):
        with pytest.raises(ParseError, match="uppercase only"):
            parse_type("Q<z>")


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_type(self):
        parser = ProjParser("Invalid")
        with pytest.raises(ParseError, match="Expected type"):
            parser.parse_type()

    def test_missing_basis(self):
        parser = ProjParser("Q<")
        with pytest.raises(ParseError, match="Expected basis"):
            parser.parse_type()

    def test_invalid_basis(self):
        parser = ProjParser("Q<Invalid>")
        with pytest.raises(ParseError, match="Invalid basis"):
            parser.parse_type()

    def test_missing_closing_bracket(self):
        parser = ProjParser("Q<X")
        with pytest.raises(ParseError, match="Expected '>'"):
            parser.parse_type()

    def test_unexpected_token_after_type(self):
        parser = ProjParser("Q foo")
        parser.parse_type()
        with pytest.raises(ParseError, match="Unexpected token"):
            parser.expect_eof()

    def test_parse_identifier_when_not_identifier(self):
        # Identifier parsing methods removed - identifiers are parsed directly
        # This test is kept for documentation purposes
        pass


class TestMixedCase:
    """Test that only uppercase basis is accepted."""

    def test_all_bases_uppercase(self):
        for basis_char, expected_basis in [
            ("X", Basis.X),
            ("Y", Basis.Y),
            ("Z", Basis.Z),
        ]:
            result = parse_type(f"Q<{basis_char}>")
            assert isinstance(result, QubitType)
            assert isinstance(result.borrow_type, BasisAttr)
            assert result.borrow_type.data == expected_basis

    def test_lowercase_basis_rejected(self):
        for basis_char in ["x", "y", "z"]:
            with pytest.raises(ParseError, match="uppercase only"):
                parse_type(f"Q<{basis_char}>")
