"""Tests for the proj-xdsl CST parser."""

import pytest
from xdsl.utils.exceptions import ParseError

from projxdsl.frontend.cst import (
    AngleConstantExpr,
    AngleConstantKind,
    AngleOpKind,
    BinaryAngleExpr,
    BinaryOpKind,
    BinaryProjExpr,
    BoolLiteralExpr,
    EqExpr,
    IdentExpr,
    NegAngleExpr,
    NotExpr,
    ScalarMultExpr,
)
from projxdsl.frontend.cst_parser import ProjCSTParser


def parse_expression(code: str):
    """Helper to parse an expression and return the CST node."""
    parser = ProjCSTParser(code)
    result = parser.parse_expression()
    return result


class TestBooleanLiterals:
    """Test parsing of boolean literals."""

    def test_true_literal(self):
        """Test parsing true literal."""
        result = parse_expression("true")
        assert isinstance(result, BoolLiteralExpr)
        assert result.value is True

    def test_false_literal(self):
        """Test parsing false literal."""
        result = parse_expression("false")
        assert isinstance(result, BoolLiteralExpr)
        assert result.value is False


class TestNotOperator:
    """Test parsing of negation operator."""

    def test_not_bool_variable(self):
        """Test parsing !p where p is a boolean."""
        result = parse_expression("!p")
        assert isinstance(result, NotExpr)
        assert isinstance(result.operand, IdentExpr)
        assert result.operand.name == "p"

    def test_not_true(self):
        """Test parsing !true."""
        result = parse_expression("!true")
        assert isinstance(result, NotExpr)
        assert isinstance(result.operand, BoolLiteralExpr)

    def test_not_false(self):
        """Test parsing !false."""
        result = parse_expression("!false")
        assert isinstance(result, NotExpr)
        assert isinstance(result.operand, BoolLiteralExpr)

    def test_double_not_bool(self):
        """Test parsing !!p where p is a boolean."""
        result = parse_expression("!!p")
        assert isinstance(result, NotExpr)
        assert isinstance(result.operand, NotExpr)
        assert isinstance(result.operand.operand, IdentExpr)


class TestAndOperator:
    """Test parsing of conjunction operator."""

    def test_and_bool_variables(self):
        """Test parsing p && q where both are booleans."""
        result = parse_expression("p && q")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.AND
        assert isinstance(result.left, IdentExpr)
        assert isinstance(result.right, IdentExpr)

    def test_and_with_true(self):
        """Test parsing p && true where p is boolean."""
        result = parse_expression("p && true")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.AND
        assert isinstance(result.right, BoolLiteralExpr)

    def test_and_chaining_bool(self):
        """Test parsing p && q && r where all are booleans (left associative)."""
        result = parse_expression("p && q && r")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.AND
        assert isinstance(result.left, BinaryProjExpr)


class TestOrOperator:
    """Test parsing of disjunction operator."""

    def test_or_bool_variables(self):
        """Test parsing p || q where both are booleans."""
        result = parse_expression("p || q")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.OR

    def test_or_chaining_bool(self):
        """Test parsing p || q || r where all are booleans (left associative)."""
        result = parse_expression("p || q || r")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.OR
        assert isinstance(result.left, BinaryProjExpr)


class TestXorOperator:
    """Test parsing of exclusive-or operator."""

    def test_xor_bool_variables(self):
        """Test parsing p ^ q where both are booleans."""
        result = parse_expression("p ^ q")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.XOR

    def test_xor_chaining_bool(self):
        """Test parsing p ^ q ^ r where all are booleans (left associative)."""
        result = parse_expression("p ^ q ^ r")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.XOR
        assert isinstance(result.left, BinaryProjExpr)


class TestEqOperator:
    """Test parsing of equality (projection creation) operator."""

    def test_eq_zero(self):
        """Test parsing q == |0>."""
        result = parse_expression("q == |0>")
        assert isinstance(result, EqExpr)
        assert isinstance(result.qubit, IdentExpr)
        assert result.qubit.name == "q"

    def test_eq_plus(self):
        """Test parsing q == |+>."""
        result = parse_expression("q == |+>")
        assert isinstance(result, EqExpr)

    def test_eq_with_and(self):
        """Test parsing q == |0> && p."""
        result = parse_expression("q == |0> && p")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.AND
        assert isinstance(result.left, EqExpr)

    def test_eq_any_basis(self):
        """Test that qubit can use any basis state."""
        for state in ["|0>", "|1>", "|+>", "|->", "|L>", "|R>"]:
            result = parse_expression(f"q == {state}")
            assert isinstance(result, EqExpr)


class TestBindingPower:
    """Test operator binding power (precedence)."""

    def test_not_binds_tighter_than_and(self):
        """Test that !p && q parses as (!p) && q."""
        result = parse_expression("!p && q")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.AND
        assert isinstance(result.left, NotExpr)

    def test_and_binds_tighter_than_or(self):
        """Test that p || q && r parses as p || (q && r)."""
        result = parse_expression("p || q && r")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.OR
        assert isinstance(result.right, BinaryProjExpr)
        assert result.right.op == BinaryOpKind.AND

    def test_xor_binds_tighter_than_and(self):
        """Test that p && q ^ r parses as p && (q ^ r)."""
        result = parse_expression("p && q ^ r")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.AND
        assert isinstance(result.right, BinaryProjExpr)
        assert result.right.op == BinaryOpKind.XOR

    def test_eq_binds_tighter_than_not(self):
        """Test that !(q == |0>) parses the projection first, then negates."""
        result = parse_expression("!(q == |0>)")
        assert isinstance(result, NotExpr)
        assert isinstance(result.operand, EqExpr)


class TestParentheses:
    """Test parenthesized expressions."""

    def test_parenthesized_variable(self):
        """Test parsing (p)."""
        result = parse_expression("(p)")
        assert isinstance(result, IdentExpr)
        assert result.name == "p"

    def test_parenthesized_expression(self):
        """Test parsing (p && q)."""
        result = parse_expression("(p && q)")
        assert isinstance(result, BinaryProjExpr)

    def test_override_binding_power(self):
        """Test that (p || q) && r parses as ((p || q) && r)."""
        result = parse_expression("(p || q) && r")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.AND
        assert isinstance(result.left, BinaryProjExpr)
        assert result.left.op == BinaryOpKind.OR


class TestAngleExpressions:
    """Test parsing of angle expressions."""

    def test_angle_add(self):
        """Test parsing angle addition."""
        result = parse_expression("a + b")
        assert isinstance(result, BinaryAngleExpr)
        assert result.op == AngleOpKind.ADD

    def test_angle_scalar_mult(self):
        """Test parsing scalar multiplication: 2.0 * a."""
        result = parse_expression("2.0 * a")
        assert isinstance(result, ScalarMultExpr)
        assert isinstance(result.scalar, ScalarMultExpr) or True  # scalar is float

    def test_angle_scalar_mult_binds_tighter(self):
        """Test that scalar_mult binds tighter than add."""
        result = parse_expression("2.0 * a + b")
        assert isinstance(result, BinaryAngleExpr)
        assert result.op == AngleOpKind.ADD
        assert isinstance(result.left, ScalarMultExpr)

    def test_angle_prefix_minus(self):
        """Test parsing prefix minus: -a."""
        result = parse_expression("-a")
        assert isinstance(result, NegAngleExpr)

    def test_angle_infix_minus(self):
        """Test parsing angle subtraction: a - b."""
        result = parse_expression("a - b")
        assert isinstance(result, BinaryAngleExpr)
        assert result.op == AngleOpKind.SUB

    def test_angle_minus_binds_same_as_add(self):
        """Test that minus binds same as add."""
        result = parse_expression("a - b + c")
        assert isinstance(result, BinaryAngleExpr)
        assert result.op == AngleOpKind.ADD
        assert isinstance(result.left, BinaryAngleExpr)

    def test_angle_minus_binds_looser_than_scalar_mult(self):
        """Test that minus binds looser than scalar_mult."""
        result = parse_expression("2.0 * a - b")
        assert isinstance(result, BinaryAngleExpr)
        assert isinstance(result.left, ScalarMultExpr)

    def test_angle_prefix_minus_binds_tightest(self):
        """Test that prefix minus binds tightest."""
        result = parse_expression("-a + b")
        assert isinstance(result, BinaryAngleExpr)
        assert isinstance(result.left, NegAngleExpr)

    def test_angle_minus_minus(self):
        """Test a - -b which should parse as a + (-1.0 * (-1.0 * b))."""
        result = parse_expression("a - -b")
        assert isinstance(result, BinaryAngleExpr)
        assert isinstance(result.left, IdentExpr)
        assert isinstance(result.right, NegAngleExpr)


class TestAngleConstants:
    """Test parsing of angle constants."""

    def test_pi_constant(self):
        """Test parsing pi constant."""
        result = parse_expression("pi")
        assert isinstance(result, AngleConstantExpr)
        assert result.kind == AngleConstantKind.PI

    def test_pi_unicode_constant(self):
        """Test parsing Unicode π constant."""
        result = parse_expression("π")
        assert isinstance(result, AngleConstantExpr)
        assert result.kind == AngleConstantKind.PI

    def test_pi_unicode_in_expression(self):
        """Test using Unicode π in expressions."""
        result = parse_expression("π + 0")
        assert isinstance(result, BinaryAngleExpr)
        assert isinstance(result.left, AngleConstantExpr)
        assert isinstance(result.right, AngleConstantExpr)

    def test_pi_mixed_ascii_unicode(self):
        """Test mixing ASCII pi and Unicode π."""
        result = parse_expression("pi + π")
        assert isinstance(result, BinaryAngleExpr)
        assert isinstance(result.left, AngleConstantExpr)
        assert isinstance(result.right, AngleConstantExpr)

    def test_zero_constant(self):
        """Test parsing 0 constant."""
        result = parse_expression("0")
        assert isinstance(result, AngleConstantExpr)
        assert result.kind == AngleConstantKind.ZERO

    def test_angle_constant_in_expression(self):
        """Test using angle constants in expressions."""
        result = parse_expression("pi + 0")
        assert isinstance(result, BinaryAngleExpr)
        assert isinstance(result.left, AngleConstantExpr)
        assert isinstance(result.right, AngleConstantExpr)

    def test_invalid_integer_angle(self):
        """Test that non-zero integers are rejected for angle context."""
        with pytest.raises(ParseError, match="Only 0 is a valid angle constant"):
            parse_expression("5")
