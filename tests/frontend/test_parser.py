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
    State,
    StateAttr,
)
from projxdsl.frontend.parser import ProjParser


def parse_type(code: str):
    """Helper to parse a type and return the TypeAttribute."""
    parser = ProjParser(code)
    result = parser.parse_type()
    parser.expect_eof()
    return result


def parse_state(code: str):
    """Helper to parse a state and return the StateAttr."""
    parser = ProjParser(code)
    result = parser.parse_state()
    parser.expect_eof()
    return result


class TestTypeParsing:
    """Test parsing of types."""

    def test_qubit_unborrowed(self):
        result = parse_type("qubit")
        assert isinstance(result, QubitType)
        assert isinstance(result.borrow_type, NoneAttr)

    def test_projection(self):
        result = parse_type("proj")
        assert isinstance(result, ProjectionType)

    def test_boolean(self):
        result = parse_type("bool")
        assert result == i1

    def test_angle(self):
        result = parse_type("angle")
        assert isinstance(result, AngleType)


class TestQubitWithBasis:
    """Test parsing of qubit types with basis annotations (uppercase only)."""

    def test_qubit_x_upper(self):
        result = parse_type("qubit<X>")
        assert isinstance(result, QubitType)
        assert isinstance(result.borrow_type, BasisAttr)
        assert result.borrow_type.data == Basis.X

    def test_qubit_y_upper(self):
        result = parse_type("qubit<Y>")
        assert isinstance(result, QubitType)
        assert isinstance(result.borrow_type, BasisAttr)
        assert result.borrow_type.data == Basis.Y

    def test_qubit_z_upper(self):
        result = parse_type("qubit<Z>")
        assert isinstance(result, QubitType)
        assert isinstance(result.borrow_type, BasisAttr)
        assert result.borrow_type.data == Basis.Z

    def test_qubit_x_lower_invalid(self):
        with pytest.raises(ParseError, match="uppercase only"):
            parse_type("qubit<x>")

    def test_qubit_y_lower_invalid(self):
        with pytest.raises(ParseError, match="uppercase only"):
            parse_type("qubit<y>")

    def test_qubit_z_lower_invalid(self):
        with pytest.raises(ParseError, match="uppercase only"):
            parse_type("qubit<z>")


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_type(self):
        parser = ProjParser("Invalid")
        with pytest.raises(ParseError, match="Expected type"):
            parser.parse_type()

    def test_missing_basis(self):
        parser = ProjParser("qubit<")
        with pytest.raises(ParseError, match="Expected basis"):
            parser.parse_type()

    def test_invalid_basis(self):
        parser = ProjParser("qubit<Invalid>")
        with pytest.raises(ParseError, match="Invalid basis"):
            parser.parse_type()

    def test_missing_closing_bracket(self):
        parser = ProjParser("qubit<X")
        with pytest.raises(ParseError, match="Expected '>'"):
            parser.parse_type()

    def test_unexpected_token_after_type(self):
        parser = ProjParser("qubit foo")
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
            result = parse_type(f"qubit<{basis_char}>")
            assert isinstance(result, QubitType)
            assert isinstance(result.borrow_type, BasisAttr)
            assert result.borrow_type.data == expected_basis

    def test_lowercase_basis_rejected(self):
        for basis_char in ["x", "y", "z"]:
            with pytest.raises(ParseError, match="uppercase only"):
                parse_type(f"qubit<{basis_char}>")


class TestStateParsing:
    """Test parsing of state literals."""

    def test_state_zero_ascii(self):
        result = parse_state("|0>")
        assert isinstance(result, StateAttr)
        assert result.data == State.ZERO

    def test_state_one_ascii(self):
        result = parse_state("|1>")
        assert isinstance(result, StateAttr)
        assert result.data == State.ONE

    def test_state_plus_ascii(self):
        result = parse_state("|+>")
        assert isinstance(result, StateAttr)
        assert result.data == State.PLUS

    def test_state_minus_ascii(self):
        result = parse_state("|->")
        assert isinstance(result, StateAttr)
        assert result.data == State.MINUS

    def test_state_left_ascii(self):
        result = parse_state("|L>")
        assert isinstance(result, StateAttr)
        assert result.data == State.LEFT

    def test_state_right_ascii(self):
        result = parse_state("|R>")
        assert isinstance(result, StateAttr)
        assert result.data == State.RIGHT

    def test_state_zero_unicode(self):
        result = parse_state("|0⟩")
        assert isinstance(result, StateAttr)
        assert result.data == State.ZERO

    def test_state_one_unicode(self):
        result = parse_state("|1⟩")
        assert isinstance(result, StateAttr)
        assert result.data == State.ONE

    def test_state_plus_unicode(self):
        result = parse_state("|+⟩")
        assert isinstance(result, StateAttr)
        assert result.data == State.PLUS

    def test_state_minus_unicode(self):
        result = parse_state("|-⟩")
        assert isinstance(result, StateAttr)
        assert result.data == State.MINUS

    def test_state_left_unicode(self):
        result = parse_state("|L⟩")
        assert isinstance(result, StateAttr)
        assert result.data == State.LEFT

    def test_state_right_unicode(self):
        result = parse_state("|R⟩")
        assert isinstance(result, StateAttr)
        assert result.data == State.RIGHT

    def test_invalid_state_character(self):
        # Invalid state characters are rejected at lexing time
        with pytest.raises(ValueError, match="Unexpected character: \\|"):
            parse_state("|X>")

    def test_missing_pipe(self):
        # Missing pipe causes lexer error on the digit
        with pytest.raises(ValueError, match="Unexpected character: 0"):
            parse_state("0>")

    def test_missing_closing(self):
        # Lexer will fail to recognize |0 as a state (no closing bracket)
        with pytest.raises(ValueError, match="Unexpected character: \\|"):
            parse_state("|0")

    def test_invalid_state_char(self):
        # Invalid state characters are rejected at lexing time
        with pytest.raises(ValueError, match="Unexpected character: \\|"):
            parse_state("|2>")


class TestStateBasis:
    """Test State.get_basis() method."""

    def test_zero_basis(self):
        """Test that |0> returns Z basis."""
        assert State.ZERO.get_basis() == Basis.Z

    def test_one_basis(self):
        """Test that |1> returns Z basis."""
        assert State.ONE.get_basis() == Basis.Z

    def test_plus_basis(self):
        """Test that |+> returns X basis."""
        assert State.PLUS.get_basis() == Basis.X

    def test_minus_basis(self):
        """Test that |-> returns X basis."""
        assert State.MINUS.get_basis() == Basis.X

    def test_left_basis(self):
        """Test that |L> returns Y basis."""
        assert State.LEFT.get_basis() == Basis.Y

    def test_right_basis(self):
        """Test that |R> returns Y basis."""
        assert State.RIGHT.get_basis() == Basis.Y

    def test_all_states_have_basis(self):
        """Test that all states return a valid basis."""
        for state in State:
            basis = state.get_basis()
            assert isinstance(basis, Basis)
            assert basis in [Basis.X, Basis.Y, Basis.Z]
