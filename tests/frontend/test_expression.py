"""Tests for the proj-xdsl expression parser."""

import pytest
from xdsl.builder import Builder
from xdsl.dialects.arith import AndIOp, ConstantOp, OrIOp, XOrIOp
from xdsl.dialects.builtin import IntegerAttr, NoneAttr, i1
from xdsl.dialects.test import TestOp as XDSLTestOp
from xdsl.ir import Block, SSAValue
from xdsl.rewriter import InsertPoint
from xdsl.utils.exceptions import ParseError

from projxdsl.dialects.angle import AddOp, AngleType, PiOp, ScalarMultOp, ZeroOp
from projxdsl.dialects.proj import (
    AndOp,
    BasisAttr,
    EqOp,
    FromBoolOp,
    NotOp,
    OrOp,
    ProjectionType,
    QubitType,
    XorOp,
)
from projxdsl.frontend.parser import ProjParser, TypeCheckError


def make_bool_var(value: int = 1) -> SSAValue:
    """Create a boolean SSA value for testing."""
    return ConstantOp(IntegerAttr(value, 1)).result


def make_qubit_var() -> SSAValue:
    """Create a qubit SSA value for testing."""
    return XDSLTestOp(result_types=[QubitType(NoneAttr())]).results[0]


def make_angle_var() -> SSAValue:
    """Create an angle SSA value for testing."""
    return XDSLTestOp(result_types=[AngleType()]).results[0]


def parse_expression(
    code: str, variables: dict[str, SSAValue] | None = None
) -> SSAValue:
    """Helper to parse an expression and return the SSA value."""
    if variables is None:
        variables = {}
    parser = ProjParser(code)
    block = Block()
    builder = Builder(InsertPoint.at_end(block))
    result = parser.parse_expression(variables, builder)
    parser.expect_eof()
    assert result is not None, "parse_expression returned None in test"
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
        assert result.type == i1

    def test_false_literal(self):
        """Test parsing false literal."""
        result = parse_expression("false")
        assert result.type == i1


class TestNotOperator:
    """Test parsing of negation operator."""

    def test_not_bool_variable(self):
        """Test parsing !p where p is a boolean."""
        var = make_bool_var()
        result = parse_expression("!p", {"p": var})
        assert isinstance(result.owner, XOrIOp)
        assert result.type == i1

    def test_not_true(self):
        """Test parsing !true."""
        result = parse_expression("!true")
        assert isinstance(result.owner, XOrIOp)
        assert result.type == i1

    def test_not_false(self):
        """Test parsing !false."""
        result = parse_expression("!false")
        assert isinstance(result.owner, XOrIOp)
        assert result.type == i1

    def test_double_not_bool(self):
        """Test parsing !!p where p is a boolean."""
        var = make_bool_var()
        result = parse_expression("!!p", {"p": var})
        assert isinstance(result.owner, XOrIOp)
        assert isinstance(result.owner.operands[0].owner, XOrIOp)

    def test_not_projection(self):
        """Test parsing !p where p is a projection."""
        var = make_qubit_var()
        # Create a projection: q == |0>
        parser = ProjParser("q == |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        proj = parser.parse_expression({"q": var}, builder)
        assert proj is not None
        assert proj.type == ProjectionType()
        assert len(list(block.ops)) == 1  # EqOp inserted

        # Now test !(q == |0>)
        result = parse_expression("!(q == |0>)", {"q": var})
        assert isinstance(result.owner, NotOp)
        assert result.type == ProjectionType()

    def test_not_invalid_type(self):
        """Test that ! raises TypeCheckError for invalid types."""
        # Create an i32 value (not a valid type for !)

        invalid_var = ConstantOp(IntegerAttr(0, 32)).result
        with pytest.raises(TypeCheckError, match="Expected projection or boolean"):
            parse_expression("!x", {"x": invalid_var})


class TestAndOperator:
    """Test parsing of conjunction operator."""

    def test_and_bool_variables(self):
        """Test parsing p && q where both are booleans."""
        p = make_bool_var()
        q = make_bool_var()
        result = parse_expression("p && q", {"p": p, "q": q})
        assert isinstance(result.owner, AndIOp)
        assert result.type == i1

    def test_and_with_true(self):
        """Test parsing p && true where p is boolean."""
        p = make_bool_var()
        result = parse_expression("p && true", {"p": p})
        assert isinstance(result.owner, AndIOp)
        assert result.type == i1

    def test_and_chaining_bool(self):
        """Test parsing p && q && r where all are booleans (left associative)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("p && q && r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, AndIOp)
        assert isinstance(result.owner.operands[0].owner, AndIOp)

    def test_and_projection_variables(self):
        """Test parsing p && q where both are projections."""
        q1 = make_qubit_var()
        q2 = make_qubit_var()
        # Create projections
        parser = ProjParser("q1 == |0> && q2 == |1>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        result = parser.parse_expression({"q1": q1, "q2": q2}, builder)
        assert result is not None
        assert isinstance(result.owner, AndOp)
        assert result.type == ProjectionType()
        assert len(list(block.ops)) == 3  # Two EqOps + AndOp

    def test_and_mixed_bool_projection(self):
        """Test parsing p && q where p is boolean and q is projection."""
        p = make_bool_var()
        q = make_qubit_var()
        # p && (q == |0>)
        result = parse_expression("p && (q == |0>)", {"p": p, "q": q})
        assert isinstance(result.owner, AndOp)
        assert result.type == ProjectionType()
        # First operand should be wrapped in FromBool
        from_bool = result.owner.operands[0].owner
        assert isinstance(from_bool, FromBoolOp)


class TestOrOperator:
    """Test parsing of disjunction operator."""

    def test_or_bool_variables(self):
        """Test parsing p || q where both are booleans."""
        p = make_bool_var()
        q = make_bool_var()
        result = parse_expression("p || q", {"p": p, "q": q})
        assert isinstance(result.owner, OrIOp)
        assert result.type == i1

    def test_or_chaining_bool(self):
        """Test parsing p || q || r where all are booleans (left associative)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("p || q || r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, OrIOp)
        assert isinstance(result.owner.operands[0].owner, OrIOp)

    def test_or_projection_variables(self):
        """Test parsing p || q where both are projections."""
        q1 = make_qubit_var()
        q2 = make_qubit_var()
        # Create projections
        parser = ProjParser("q1 == |0> || q2 == |1>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        result = parser.parse_expression({"q1": q1, "q2": q2}, builder)
        assert result is not None
        assert isinstance(result.owner, OrOp)
        assert result.type == ProjectionType()
        assert len(list(block.ops)) == 3  # Two EqOps + OrOp

    def test_or_mixed_bool_projection(self):
        """Test parsing p || q where p is boolean and q is projection."""
        p = make_bool_var()
        q = make_qubit_var()
        # p || (q == |0>)
        result = parse_expression("p || (q == |0>)", {"p": p, "q": q})
        assert isinstance(result.owner, OrOp)
        assert result.type == ProjectionType()
        # First operand should be wrapped in FromBool
        from_bool = result.owner.operands[0].owner
        assert isinstance(from_bool, FromBoolOp)


class TestXorOperator:
    """Test parsing of exclusive-or operator."""

    def test_xor_bool_variables(self):
        """Test parsing p ^ q where both are booleans."""
        p = make_bool_var()
        q = make_bool_var()
        result = parse_expression("p ^ q", {"p": p, "q": q})
        assert isinstance(result.owner, XOrIOp)
        assert result.type == i1

    def test_xor_chaining_bool(self):
        """Test parsing p ^ q ^ r where all are booleans (left associative)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("p ^ q ^ r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, XOrIOp)
        assert isinstance(result.owner.operands[0].owner, XOrIOp)

    def test_xor_projection_variables(self):
        """Test parsing p ^ q where both are projections."""
        q1 = make_qubit_var()
        q2 = make_qubit_var()
        # Create projections
        parser = ProjParser("q1 == |0> ^ q2 == |1>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        result = parser.parse_expression({"q1": q1, "q2": q2}, builder)
        assert result is not None
        assert isinstance(result.owner, XorOp)
        assert result.type == ProjectionType()
        assert len(list(block.ops)) == 3  # Two EqOps + XorOp

    def test_xor_mixed_bool_projection(self):
        """Test parsing p ^ q where p is boolean and q is projection."""
        p = make_bool_var()
        q = make_qubit_var()
        # p ^ (q == |0>)
        result = parse_expression("p ^ (q == |0>)", {"p": p, "q": q})
        assert isinstance(result.owner, XorOp)
        assert result.type == ProjectionType()
        # First operand should be wrapped in FromBool
        from_bool = result.owner.operands[0].owner
        assert isinstance(from_bool, FromBoolOp)


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
        assert result.type == ProjectionType()

    def test_eq_invalid_type(self):
        """Test that == raises TypeCheckError for non-qubit types."""
        # Create a boolean variable (not a qubit)
        bool_var = make_bool_var()
        with pytest.raises(TypeCheckError, match="Expected qubit type"):
            parse_expression("p == |0>", {"p": bool_var})

    def test_eq_basis_compatible(self):
        """Test that qubit<Z> can use Z basis states."""

        q_z = XDSLTestOp(result_types=[QubitType(BasisAttr.Z())]).results[0]
        # Should work with |0> (Z basis)
        result = parse_expression("q == |0>", {"q": q_z})
        assert isinstance(result.owner, EqOp)
        # Should work with |1> (Z basis)
        result = parse_expression("q == |1>", {"q": q_z})
        assert isinstance(result.owner, EqOp)

    def test_eq_basis_incompatible(self):
        """Test that qubit<Z> cannot use X or Y basis states."""

        q_z = XDSLTestOp(result_types=[QubitType(BasisAttr.Z())]).results[0]
        # Should fail with |+> (X basis)
        with pytest.raises(
            TypeCheckError, match="Z basis cannot be projected in X basis"
        ):
            parse_expression("q == |+>", {"q": q_z})
        # Should fail with |L> (Y basis)
        with pytest.raises(
            TypeCheckError, match="Z basis cannot be projected in Y basis"
        ):
            parse_expression("q == |L>", {"q": q_z})

    def test_eq_unborrowed_any_basis(self):
        """Test that unborrowed qubit can use any basis state."""
        q = make_qubit_var()  # Unborrowed qubit
        # Should work with all states
        for state in ["|0>", "|1>", "|+>", "|->", "|L>", "|R>"]:
            result = parse_expression(f"q == {state}", {"q": q})
            assert isinstance(result.owner, EqOp)

    def test_eq_x_basis_compatible(self):
        """Test that qubit<X> can use X basis states."""

        q_x = XDSLTestOp(result_types=[QubitType(BasisAttr.X())]).results[0]
        # Should work with |+> (X basis)
        result = parse_expression("q == |+>", {"q": q_x})
        assert isinstance(result.owner, EqOp)
        # Should work with |-> (X basis)
        result = parse_expression("q == |->", {"q": q_x})
        assert isinstance(result.owner, EqOp)

    def test_eq_x_basis_incompatible(self):
        """Test that qubit<X> cannot use Y or Z basis states."""

        q_x = XDSLTestOp(result_types=[QubitType(BasisAttr.X())]).results[0]
        # Should fail with |0> (Z basis)
        with pytest.raises(
            TypeCheckError, match="X basis cannot be projected in Z basis"
        ):
            parse_expression("q == |0>", {"q": q_x})
        # Should fail with |L> (Y basis)
        with pytest.raises(
            TypeCheckError, match="X basis cannot be projected in Y basis"
        ):
            parse_expression("q == |L>", {"q": q_x})

    def test_eq_y_basis_compatible(self):
        """Test that qubit<Y> can use Y basis states."""

        q_y = XDSLTestOp(result_types=[QubitType(BasisAttr.Y())]).results[0]
        # Should work with |L> (Y basis)
        result = parse_expression("q == |L>", {"q": q_y})
        assert isinstance(result.owner, EqOp)
        # Should work with |R> (Y basis)
        result = parse_expression("q == |R>", {"q": q_y})
        assert isinstance(result.owner, EqOp)

    def test_eq_y_basis_incompatible(self):
        """Test that qubit<Y> cannot use X or Z basis states."""

        q_y = XDSLTestOp(result_types=[QubitType(BasisAttr.Y())]).results[0]
        # Should fail with |0> (Z basis)
        with pytest.raises(
            TypeCheckError, match="Y basis cannot be projected in Z basis"
        ):
            parse_expression("q == |0>", {"q": q_y})
        # Should fail with |+> (X basis)
        with pytest.raises(
            TypeCheckError, match="Y basis cannot be projected in X basis"
        ):
            parse_expression("q == |+>", {"q": q_y})


class TestBindingPower:
    """Test operator binding power (precedence)."""

    def test_not_binds_tighter_than_and(self):
        """Test that !p && q parses as (!p) && q."""
        p = make_bool_var()
        q = make_bool_var()
        result = parse_expression("!p && q", {"p": p, "q": q})
        # Both operands are boolean, so we use classical AndIOp
        assert isinstance(result.owner, AndIOp)
        # !p on boolean uses XOrIOp (XOR with 1)
        xor_op = result.owner.operands[0].owner
        assert isinstance(xor_op, XOrIOp)

    def test_and_binds_tighter_than_or(self):
        """Test that p || q && r parses as p || (q && r)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("p || q && r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, OrIOp)
        assert isinstance(result.owner.operands[1].owner, AndIOp)

    def test_xor_binds_tighter_than_and(self):
        """Test that p && q ^ r parses as p && (q ^ r)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("p && q ^ r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, AndIOp)
        assert isinstance(result.owner.operands[1].owner, XOrIOp)

    def test_eq_binds_tighter_than_not(self):
        """Test that !(q == |0>) parses the projection first, then negates."""
        q = make_qubit_var()
        result = parse_expression("!(q == |0>)", {"q": q})
        assert isinstance(result.owner, NotOp)
        assert isinstance(result.owner.operands[0].owner, EqOp)
        assert result.type == ProjectionType()


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
        # Both operands are boolean, so we use classical AndIOp
        assert isinstance(result.owner, AndIOp)

    def test_override_binding_power(self):
        """Test that (p || q) && r parses as ((p || q) && r)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = parse_expression("(p || q) && r", {"p": p, "q": q, "r": r})
        # All operands are boolean, so we use classical ops
        assert isinstance(result.owner, AndIOp)
        assert isinstance(result.owner.operands[0].owner, OrIOp)


class TestComplexExpressions:
    """Test complex expressions combining multiple operators."""

    def test_complex_expression(self):
        """Test parsing a complex expression with mixed boolean and projection types."""
        p = make_bool_var()
        q = make_qubit_var()
        r = make_bool_var()
        result = parse_expression("!p && q == |0> || r", {"p": p, "q": q, "r": r})
        # Final result should be ProjectionType (mixed bool and proj)
        assert isinstance(result.owner, OrOp)
        assert result.type == ProjectionType()
        and_op = result.owner.operands[0]
        assert isinstance(and_op.owner, AndOp)
        # !p returns i1, which is then wrapped in FromBoolOp for the && operator
        from_bool_op = and_op.owner.operands[0].owner
        assert isinstance(from_bool_op, FromBoolOp)
        # The operand of FromBoolOp should be XOrIOp
        assert isinstance(from_bool_op.operands[0].owner, XOrIOp)
        eq_op = and_op.owner.operands[1]
        assert isinstance(eq_op.owner, EqOp)
        # r should also be wrapped in FromBoolOp
        r_from_bool = result.owner.operands[1].owner
        assert isinstance(r_from_bool, FromBoolOp)


class TestAngleExpressions:
    """Test parsing of angle expressions."""

    def test_angle_add(self):
        """Test parsing angle addition."""

        a = make_angle_var()
        b = make_angle_var()
        result = parse_expression("a + b", {"a": a, "b": b})
        assert isinstance(result.owner, AddOp)
        assert result.type == AngleType()

    def test_angle_scalar_mult(self):
        """Test parsing scalar multiplication: 2.0 * a."""

        a = make_angle_var()
        result = parse_expression("2.0 * a", {"a": a})
        assert isinstance(result.owner, ScalarMultOp)
        assert result.type == AngleType()

    def test_angle_scalar_mult_binds_tighter(self):
        """Test that scalar_mult binds tighter than add."""

        a = make_angle_var()
        b = make_angle_var()
        # 2.0 * a + b should parse as (2.0 * a) + b
        result = parse_expression("2.0 * a + b", {"a": a, "b": b})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[0].owner, ScalarMultOp)

    def test_angle_add_type_error(self):
        """Test that add with non-angle raises error."""

        p = make_bool_var()
        a = make_angle_var()
        with pytest.raises(TypeCheckError, match="Expected angle"):
            parse_expression("p + a", {"p": p, "a": a})

    def test_angle_scalar_mult_type_error(self):
        """Test that scalar_mult with non-angle raises error."""

        p = make_bool_var()
        with pytest.raises(TypeCheckError, match="Expected angle"):
            parse_expression("2.0 * p", {"p": p})


class TestAngleConstants:
    """Test parsing of angle constants."""

    def test_pi_constant(self):
        """Test parsing pi constant."""

        result = parse_expression("pi", {})
        assert isinstance(result.owner, PiOp)
        assert result.type == AngleType()

    def test_pi_unicode_constant(self):
        """Test parsing Unicode π constant."""

        result = parse_expression("π", {})
        assert isinstance(result.owner, PiOp)
        assert result.type == AngleType()

    def test_pi_unicode_in_expression(self):
        """Test using Unicode π in expressions."""

        result = parse_expression("π + 0", {})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[0].owner, PiOp)
        assert isinstance(result.owner.operands[1].owner, ZeroOp)

    def test_pi_mixed_ascii_unicode(self):
        """Test mixing ASCII pi and Unicode π."""

        result = parse_expression("pi + π", {})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[0].owner, PiOp)
        assert isinstance(result.owner.operands[1].owner, PiOp)

    def test_zero_constant(self):
        """Test parsing 0 constant."""

        result = parse_expression("0", {})
        assert isinstance(result.owner, ZeroOp)
        assert result.type == AngleType()

    def test_angle_constant_in_expression(self):
        """Test using angle constants in expressions."""

        # pi + 0
        result = parse_expression("pi + 0", {})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[0].owner, PiOp)
        assert isinstance(result.owner.operands[1].owner, ZeroOp)

    def test_invalid_integer_angle(self):
        """Test that non-zero integers are rejected."""

        with pytest.raises(ParseError, match="Only 0 is a valid angle constant"):
            parse_expression("1", {})
