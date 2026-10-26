"""Tests for the proj-xdsl expression parser."""

import pytest
from xdsl.dialects.arith import ConstantOp
from xdsl.dialects.builtin import IntegerAttr
from xdsl.ir import SSAValue
from xdsl.utils.exceptions import ParseError

from projxdsl.dialects.proj import (
    AndOp,
    EqOp,
    FromBoolOp,
    NotOp,
    OrOp,
    XorOp,
)
from projxdsl.frontend.parser import ProjParser


def make_bool_var(value: int = 1) -> SSAValue:
    """Create a boolean SSA value for testing."""
    return ConstantOp(IntegerAttr(value, 1)).result


def make_qubit_var() -> SSAValue:
    """Create a qubit SSA value for testing."""
    return ConstantOp(IntegerAttr(0, 1)).result  # Placeholder


def parse_expression(code: str, variables: dict[str, SSAValue] | None = None):
    """Helper to parse an expression and return the SSA value."""
    if variables is None:
        variables = {}
    parser = ProjParser(code)
    result = parser.parse_expression(variables)
    parser.expect_eof()
    return result


class TestVariableExpressions:
    """Test parsing of variable references."""

    def test_simple_variable(self):
        """Test parsing a simple variable reference."""
        var = make_bool_var()
        result = parse_expression("p", {"p": var})
        assert result is var

    def test_undefined_variable(self):
        """Test that undefined variables raise an error."""
        with pytest.raises(ParseError, match="Undefined variable"):
            parse_expression("p")


class TestBooleanLiterals:
    """Test parsing of boolean literals."""

    def test_true_literal(self):
        """Test parsing true literal."""
        result = parse_expression("true")
        assert isinstance(result.owner, FromBoolOp)

    def test_false_literal(self):
        """Test parsing false literal."""
        result = parse_expression("false")
        assert isinstance(result.owner, FromBoolOp)


class TestNotOperator:
    """Test parsing of negation operator."""

    def test_not_variable(self):
        """Test parsing !p."""
        var = make_bool_var()
        result = parse_expression("!p", {"p": var})
        assert isinstance(result.owner, NotOp)

    def test_not_true(self):
        """Test parsing !true."""
        result = parse_expression("!true")
        assert isinstance(result.owner, NotOp)

    def test_double_not(self):
        """Test parsing !!p."""
        var = make_bool_var()
        result = parse_expression("!!p", {"p": var})
        assert isinstance(result.owner, NotOp)
        assert isinstance(result.owner.operands[0].owner, NotOp)


class TestAndOperator:
    """Test parsing of conjunction operator."""

    def test_and_variables(self):
        """Test parsing p && q."""
        p = make_bool_var()
        q = make_bool_var()
        result = parse_expression("p && q", {"p": p, "q": q})
        assert isinstance(result.owner, AndOp)

    def test_and_with_true(self):
        """Test parsing p && true."""
        p = make_bool_var()
        result = parse_expression("p && true", {"p": p})
        assert isinstance(result.owner, AndOp)

    def test_and_chaining(self):
        """Test parsing p && q && r (left associative)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("p && q && r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, AndOp)
        assert isinstance(result.owner.operands[0].owner, AndOp)


class TestOrOperator:
    """Test parsing of disjunction operator."""

    def test_or_variables(self):
        """Test parsing p || q."""
        p = make_bool_var()
        q = make_bool_var()
        result = parse_expression("p || q", {"p": p, "q": q})
        assert isinstance(result.owner, OrOp)

    def test_or_chaining(self):
        """Test parsing p || q || r (left associative)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("p || q || r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, OrOp)
        assert isinstance(result.owner.operands[0].owner, OrOp)


class TestXorOperator:
    """Test parsing of exclusive-or operator."""

    def test_xor_variables(self):
        """Test parsing p ^ q."""
        p = make_bool_var()
        q = make_bool_var()
        result = parse_expression("p ^ q", {"p": p, "q": q})
        assert isinstance(result.owner, XorOp)

    def test_xor_chaining(self):
        """Test parsing p ^ q ^ r (left associative)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("p ^ q ^ r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, XorOp)
        assert isinstance(result.owner.operands[0].owner, XorOp)


class TestEqOperator:
    """Test parsing of equality (projection creation) operator."""

    def test_eq_zero(self):
        """Test parsing q == |0>."""
        q = make_qubit_var()
        result = parse_expression("q == |0>", {"q": q})
        assert isinstance(result.owner, EqOp)

    def test_eq_plus(self):
        """Test parsing q == |+>."""
        q = make_qubit_var()
        result = parse_expression("q == |+>", {"q": q})
        assert isinstance(result.owner, EqOp)

    def test_eq_with_and(self):
        """Test parsing q == |0> && p."""
        q = make_qubit_var()
        p = make_bool_var()
        result = parse_expression("q == |0> && p", {"q": q, "p": p})
        assert isinstance(result.owner, AndOp)


class TestBindingPower:
    """Test operator binding power (precedence)."""

    def test_not_binds_tighter_than_and(self):
        """Test that !p && q parses as (!p) && q."""
        p = make_bool_var()
        q = make_bool_var()
        result = parse_expression("!p && q", {"p": p, "q": q})
        assert isinstance(result.owner, AndOp)
        assert isinstance(result.owner.operands[0].owner, NotOp)

    def test_and_binds_tighter_than_or(self):
        """Test that p || q && r parses as p || (q && r)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("p || q && r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, OrOp)
        assert isinstance(result.owner.operands[1].owner, AndOp)

    def test_xor_binds_tighter_than_and(self):
        """Test that p && q ^ r parses as p && (q ^ r)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("p && q ^ r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, AndOp)
        assert isinstance(result.owner.operands[1].owner, XorOp)

    def test_eq_binds_tighter_than_not(self):
        """Test that !q == |0> parses as !(q == |0>)."""
        q = make_qubit_var()
        result = parse_expression("!q == |0>", {"q": q})
        assert isinstance(result.owner, NotOp)
        assert isinstance(result.owner.operands[0].owner, EqOp)


class TestParentheses:
    """Test parenthesized expressions."""

    def test_parenthesized_variable(self):
        """Test parsing (p)."""
        p = make_bool_var()
        result = parse_expression("(p)", {"p": p})
        assert result is p

    def test_parenthesized_expression(self):
        """Test parsing (p && q)."""
        p = make_bool_var()
        q = make_bool_var()
        result = parse_expression("(p && q)", {"p": p, "q": q})
        assert isinstance(result.owner, AndOp)

    def test_override_binding_power(self):
        """Test that (p || q) && r parses as ((p || q) && r)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("(p || q) && r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, AndOp)
        assert isinstance(result.owner.operands[0].owner, OrOp)


class TestComplexExpressions:
    """Test complex expressions combining multiple operators."""

    def test_complex_expression(self):
        """Test parsing a complex expression."""
        p = make_bool_var()
        q = make_qubit_var()
        r = make_bool_var()
        result = parse_expression("!p && q == |0> || r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, OrOp)
        and_op = result.owner.operands[0]
        assert isinstance(and_op.owner, AndOp)
        not_op = and_op.owner.operands[0]
        assert isinstance(not_op.owner, NotOp)
        eq_op = and_op.owner.operands[1]
        assert isinstance(eq_op.owner, EqOp)
