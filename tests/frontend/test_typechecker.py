"""Tests for the proj-xdsl typechecker."""

import pytest
from xdsl.builder import Builder
from xdsl.dialects.arith import AndIOp, ConstantOp, OrIOp, XOrIOp
from xdsl.dialects.builtin import IntegerAttr, i1
from xdsl.dialects.test import TestOp as XDSLTestOp
from xdsl.ir import Block, SSAValue
from xdsl.rewriter import InsertPoint
from xdsl.utils.scoped_dict import ScopedDict

from projxdsl.dialects.angle import AddOp, AngleType, PiOp, ScalarMultOp, ZeroOp
from projxdsl.dialects.proj import (
    AndOp,
    EqOp,
    FromBoolOp,
    NotOp,
    OrOp,
    ProjectionType,
    QubitType,
    XorOp,
)
from projxdsl.frontend.cst_parser import ProjCSTParser
from projxdsl.frontend.typechecker import (
    ProjectionBorrows,
    TypeChecker,
    TypeCheckError,
    TypingContext,
)
from projxdsl.func_kind import FuncKind


def make_bool_var(value: int = 1) -> SSAValue:
    """Create a boolean SSA value for testing."""
    return ConstantOp(IntegerAttr(value, 1)).result


def make_qubit_var() -> SSAValue:
    """Create a qubit SSA value for testing."""
    return XDSLTestOp(result_types=[QubitType()]).results[0]


def make_angle_var() -> SSAValue:
    """Create an angle SSA value for testing."""
    return XDSLTestOp(result_types=[AngleType()]).results[0]


def typecheck_expression(
    code: str, variables: dict[str, SSAValue] | None = None
) -> SSAValue:
    """Helper to parse and typecheck an expression, returning the SSA value."""
    if variables is None:
        variables = {}

    # Parse to CST
    cst_parser = ProjCSTParser(code)
    cst_expr = cst_parser.parse_expression()

    # Typecheck
    block = Block()
    builder = Builder(InsertPoint.at_end(block))
    ctx = TypingContext(
        func_kind=FuncKind.MIXED,
        variables=ScopedDict[str, SSAValue](local_scope=variables),
        borrows=ScopedDict[SSAValue, ProjectionBorrows](local_scope={}),
    )
    typechecker = TypeChecker()
    result = typechecker.infer_expression(cst_expr, ctx, builder)
    assert result is not None, "typecheck_expression returned None in test"
    return result


class TestVariableExpressions:
    """Test typechecking of variable references."""

    def test_simple_variable(self):
        """Test typechecking a simple variable reference."""
        var = make_bool_var()
        result = typecheck_expression("p", {"p": var})
        assert result is var

    def test_undefined_variable(self):
        """Test that undefined variables raise an error."""
        with pytest.raises(TypeCheckError, match="Undefined variable"):
            typecheck_expression("p")


class TestBooleanLiterals:
    """Test typechecking of boolean literals."""

    def test_true_literal(self):
        """Test typechecking true literal."""
        result = typecheck_expression("true")
        assert result.type == i1

    def test_false_literal(self):
        """Test typechecking false literal."""
        result = typecheck_expression("false")
        assert result.type == i1


class TestNotOperator:
    """Test typechecking of negation operator."""

    def test_not_bool_variable(self):
        """Test typechecking !p where p is a boolean."""
        var = make_bool_var()
        result = typecheck_expression("!p", {"p": var})
        assert isinstance(result.owner, XOrIOp)
        assert result.type == i1

    def test_not_true(self):
        """Test typechecking !true."""
        result = typecheck_expression("!true")
        assert isinstance(result.owner, XOrIOp)
        assert result.type == i1

    def test_not_false(self):
        """Test typechecking !false."""
        result = typecheck_expression("!false")
        assert isinstance(result.owner, XOrIOp)
        assert result.type == i1

    def test_double_not_bool(self):
        """Test typechecking !!p where p is a boolean."""
        var = make_bool_var()
        result = typecheck_expression("!!p", {"p": var})
        assert isinstance(result.owner, XOrIOp)
        assert isinstance(result.owner.operands[0].owner, XOrIOp)

    def test_not_projection(self):
        """Test typechecking !p where p is a projection."""
        var = make_qubit_var()
        result = typecheck_expression("!(q == |0>)", {"q": var})
        assert isinstance(result.owner, NotOp)
        assert result.type == ProjectionType()

    def test_not_invalid_type(self):
        """Test that ! with invalid type raises error."""
        var = make_angle_var()
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            typecheck_expression("!a", {"a": var})


class TestAndOperator:
    """Test typechecking of conjunction operator."""

    def test_and_bool_variables(self):
        """Test typechecking p && q where both are booleans."""
        p = make_bool_var()
        q = make_bool_var()
        result = typecheck_expression("p && q", {"p": p, "q": q})
        assert isinstance(result.owner, AndIOp)
        assert result.type == i1

    def test_and_with_true(self):
        """Test typechecking p && true where p is boolean."""
        p = make_bool_var()
        result = typecheck_expression("p && true", {"p": p})
        assert isinstance(result.owner, AndIOp)
        assert result.type == i1

    def test_and_chaining_bool(self):
        """Test typechecking p && q && r where all are booleans (left associative)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = typecheck_expression("p && q && r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, AndIOp)
        assert isinstance(result.owner.operands[0].owner, AndIOp)

    def test_and_projection_variables(self):
        """Test typechecking p && q where both are projections."""
        q1 = make_qubit_var()
        q2 = make_qubit_var()
        result = typecheck_expression("q1 == |0> && q2 == |1>", {"q1": q1, "q2": q2})
        assert isinstance(result.owner, AndOp)
        assert result.type == ProjectionType()

    def test_and_mixed_bool_projection(self):
        """Test typechecking p && q where p is bool and q is projection."""
        p = make_bool_var()
        q1 = make_qubit_var()
        result = typecheck_expression("p && (q1 == |0>)", {"p": p, "q1": q1})
        assert isinstance(result.owner, AndOp)
        assert result.type == ProjectionType()
        # First operand should be wrapped in FromBool
        from_bool = result.owner.operands[0].owner
        assert isinstance(from_bool, FromBoolOp)


class TestOrOperator:
    """Test typechecking of disjunction operator."""

    def test_or_bool_variables(self):
        """Test typechecking p || q where both are booleans."""
        p = make_bool_var()
        q = make_bool_var()
        result = typecheck_expression("p || q", {"p": p, "q": q})
        assert isinstance(result.owner, OrIOp)
        assert result.type == i1

    def test_or_chaining_bool(self):
        """Test typechecking p || q || r where all are booleans (left associative)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = typecheck_expression("p || q || r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, OrIOp)
        assert isinstance(result.owner.operands[0].owner, OrIOp)

    def test_or_projection_variables(self):
        """Test typechecking p || q where both are projections."""
        q1 = make_qubit_var()
        q2 = make_qubit_var()
        result = typecheck_expression("q1 == |0> || q2 == |1>", {"q1": q1, "q2": q2})
        assert isinstance(result.owner, OrOp)
        assert result.type == ProjectionType()

    def test_or_mixed_bool_projection(self):
        """Test typechecking p || q where p is boolean and q is projection."""
        p = make_bool_var()
        q = make_qubit_var()
        result = typecheck_expression("p || (q == |0>)", {"p": p, "q": q})
        assert isinstance(result.owner, OrOp)
        assert result.type == ProjectionType()
        # First operand should be wrapped in FromBool
        from_bool = result.owner.operands[0].owner
        assert isinstance(from_bool, FromBoolOp)


class TestXorOperator:
    """Test typechecking of exclusive-or operator."""

    def test_xor_bool_variables(self):
        """Test typechecking p ^ q where both are booleans."""
        p = make_bool_var()
        q = make_bool_var()
        result = typecheck_expression("p ^ q", {"p": p, "q": q})
        assert isinstance(result.owner, XOrIOp)
        assert result.type == i1

    def test_xor_chaining_bool(self):
        """Test typechecking p ^ q ^ r where all are booleans (left associative)."""
        p = make_bool_var()
        q = make_bool_var()
        r = make_bool_var()
        result = typecheck_expression("p ^ q ^ r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, XOrIOp)
        assert isinstance(result.owner.operands[0].owner, XOrIOp)

    def test_xor_projection_variables(self):
        """Test typechecking p ^ q where both are projections."""
        q1 = make_qubit_var()
        q2 = make_qubit_var()
        result = typecheck_expression("q1 == |0> ^ q2 == |1>", {"q1": q1, "q2": q2})
        assert isinstance(result.owner, XorOp)
        assert result.type == ProjectionType()

    def test_xor_mixed_bool_projection(self):
        """Test typechecking p ^ q where p is boolean and q is projection."""
        p = make_bool_var()
        q = make_qubit_var()
        result = typecheck_expression("p ^ (q == |0>)", {"p": p, "q": q})
        assert isinstance(result.owner, XorOp)
        assert result.type == ProjectionType()
        # First operand should be wrapped in FromBool
        from_bool = result.owner.operands[0].owner
        assert isinstance(from_bool, FromBoolOp)


class TestEqOperator:
    """Test typechecking of equality operator."""

    def test_eq_zero(self):
        """Test typechecking q == |0>."""
        q = make_qubit_var()
        result = typecheck_expression("q == |0>", {"q": q})
        assert isinstance(result.owner, EqOp)
        assert result.type == ProjectionType()

    def test_eq_plus(self):
        """Test typechecking q == |+>."""
        q = make_qubit_var()
        result = typecheck_expression("q == |+>", {"q": q})
        assert isinstance(result.owner, EqOp)
        assert result.type == ProjectionType()

    def test_eq_with_and(self):
        """Test typechecking q1 == |0> && q2 == |1>."""
        q1 = make_qubit_var()
        q2 = make_qubit_var()
        result = typecheck_expression("q1 == |0> && q2 == |1>", {"q1": q1, "q2": q2})
        assert isinstance(result.owner, AndOp)
        assert result.type == ProjectionType()

    def test_eq_invalid_type(self):
        """Test that == with non-qubit raises error."""
        p = make_bool_var()
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            typecheck_expression("p == |0>", {"p": p})

    def test_eq_any_basis(self):
        """Test eq with all basis states."""
        q = make_qubit_var()
        for state in ["|0>", "|1>", "|+>", "|->", "|L>", "|R>"]:
            result = typecheck_expression(f"q == {state}", {"q": q})
            assert isinstance(result.owner, EqOp)
            assert result.type == ProjectionType()


class TestComplexExpressions:
    """Test complex expressions combining multiple operators."""

    def test_complex_expression(self):
        """Test typechecking a complex expression with mixed boolean and
        projection types."""
        p = make_bool_var()
        q = make_qubit_var()
        r = make_bool_var()
        result = typecheck_expression("!p && q == |0> || r", {"p": p, "q": q, "r": r})
        assert isinstance(result.owner, OrOp)
        assert result.type == ProjectionType()
        and_op = result.owner.operands[0]
        assert isinstance(and_op.owner, AndOp)
        from_bool_op = and_op.owner.operands[0].owner
        assert isinstance(from_bool_op, FromBoolOp)
        assert isinstance(from_bool_op.operands[0].owner, XOrIOp)
        eq_op = and_op.owner.operands[1]
        assert isinstance(eq_op.owner, EqOp)
        r_from_bool = result.owner.operands[1].owner
        assert isinstance(r_from_bool, FromBoolOp)


class TestAngleExpressions:
    """Test typechecking of angle expressions."""

    def test_angle_add(self):
        """Test typechecking angle addition."""
        a = make_angle_var()
        b = make_angle_var()
        result = typecheck_expression("a + b", {"a": a, "b": b})
        assert isinstance(result.owner, AddOp)
        assert result.type == AngleType()

    def test_angle_scalar_mult(self):
        """Test typechecking scalar multiplication: 2.0 * a."""
        a = make_angle_var()
        result = typecheck_expression("2.0 * a", {"a": a})
        assert isinstance(result.owner, ScalarMultOp)
        assert result.type == AngleType()

    def test_angle_scalar_mult_binds_tighter(self):
        """Test that scalar_mult binds tighter than add."""
        a = make_angle_var()
        b = make_angle_var()
        result = typecheck_expression("2.0 * a + b", {"a": a, "b": b})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[0].owner, ScalarMultOp)

    def test_angle_add_type_error(self):
        """Test that add with non-angle raises error."""
        p = make_bool_var()
        a = make_angle_var()
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            typecheck_expression("p + a", {"p": p, "a": a})

    def test_angle_scalar_mult_type_error(self):
        """Test that scalar_mult with non-angle raises error."""
        p = make_bool_var()
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            typecheck_expression("2.0 * p", {"p": p})

    def test_angle_prefix_minus(self):
        """Test typechecking prefix minus: -a."""
        a = make_angle_var()
        result = typecheck_expression("-a", {"a": a})
        assert isinstance(result.owner, ScalarMultOp)
        assert result.type == AngleType()

    def test_angle_infix_minus(self):
        """Test typechecking angle subtraction: a - b."""
        a = make_angle_var()
        b = make_angle_var()
        result = typecheck_expression("a - b", {"a": a, "b": b})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[1].owner, ScalarMultOp)
        assert result.type == AngleType()

    def test_angle_minus_binds_same_as_add(self):
        """Test that minus binds same as add."""
        a = make_angle_var()
        b = make_angle_var()
        c = make_angle_var()
        result = typecheck_expression("a - b + c", {"a": a, "b": b, "c": c})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[0].owner, AddOp)

    def test_angle_minus_binds_looser_than_scalar_mult(self):
        """Test that minus binds looser than scalar_mult."""
        a = make_angle_var()
        b = make_angle_var()
        result = typecheck_expression("2.0 * a - b", {"a": a, "b": b})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[0].owner, ScalarMultOp)

    def test_angle_prefix_minus_binds_tightest(self):
        """Test that prefix minus binds tightest."""
        a = make_angle_var()
        b = make_angle_var()
        result = typecheck_expression("-a + b", {"a": a, "b": b})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[0].owner, ScalarMultOp)

    def test_angle_prefix_minus_type_error(self):
        """Test that prefix minus with non-angle raises error."""
        p = make_bool_var()
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            typecheck_expression("-p", {"p": p})

    def test_angle_infix_minus_type_error(self):
        """Test that infix minus with non-angle raises error."""
        p = make_bool_var()
        a = make_angle_var()
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            typecheck_expression("p - a", {"p": p, "a": a})
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            typecheck_expression("a - p", {"p": p, "a": a})

    def test_angle_minus_minus(self):
        """Test a - -b which should parse as a + (-1.0 * (-1.0 * b))."""
        a = make_angle_var()
        b = make_angle_var()
        result = typecheck_expression("a - -b", {"a": a, "b": b})
        assert isinstance(result.owner, AddOp)
        assert result.owner.operands[0] is a
        assert isinstance(result.owner.operands[1].owner, ScalarMultOp)
        inner_scalar_mult = result.owner.operands[1].owner.operands[0]
        assert isinstance(inner_scalar_mult.owner, ScalarMultOp)


class TestAngleConstants:
    """Test typechecking of angle constants."""

    def test_pi_constant(self):
        """Test typechecking pi constant."""
        result = typecheck_expression("pi", {})
        assert isinstance(result.owner, PiOp)
        assert result.type == AngleType()

    def test_pi_unicode_constant(self):
        """Test typechecking Unicode π constant."""
        result = typecheck_expression("π", {})
        assert isinstance(result.owner, PiOp)
        assert result.type == AngleType()

    def test_pi_unicode_in_expression(self):
        """Test using Unicode π in expressions."""
        result = typecheck_expression("π + 0", {})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[0].owner, PiOp)
        assert isinstance(result.owner.operands[1].owner, ZeroOp)

    def test_pi_mixed_ascii_unicode(self):
        """Test mixing ASCII pi and Unicode π."""
        result = typecheck_expression("pi + π", {})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[0].owner, PiOp)
        assert isinstance(result.owner.operands[1].owner, PiOp)

    def test_zero_constant(self):
        """Test typechecking 0 constant."""
        result = typecheck_expression("0", {})
        assert isinstance(result.owner, ZeroOp)
        assert result.type == AngleType()

    def test_angle_constant_in_expression(self):
        """Test using angle constants in expressions."""
        result = typecheck_expression("pi + 0", {})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.operands[0].owner, PiOp)
        assert isinstance(result.owner.operands[1].owner, ZeroOp)
