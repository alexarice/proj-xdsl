"""Tests for the proj-xdsl typechecker."""

import pytest
from xdsl.builder import Builder
from xdsl.dialects.arith import AndIOp, ConstantOp, OrIOp, XOrIOp
from xdsl.dialects.builtin import IntegerAttr, i1
from xdsl.dialects.test import TestOp as XDSLTestOp
from xdsl.ir import Block, Operation, SSAValue
from xdsl.rewriter import InsertPoint
from xdsl.utils.scoped_dict import ScopedDict

from projxdsl.dialects.angle import AddOp, AngleType, PiOp, ScalarMultOp, ZeroOp
from projxdsl.dialects.proj import (
    AllocOp,
    AndOp,
    EqOp,
    FromBoolOp,
    IfOp,
    MeasureOp,
    NotOp,
    OrOp,
    PhaseOp,
    ProjectionType,
    QubitType,
    XorOp,
)
from projxdsl.frontend.parser import ProjParser
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


def make_proj_var() -> SSAValue:
    """Create a projection SSA value for testing."""
    return XDSLTestOp(result_types=[ProjectionType()]).results[0]


def typecheck_expression(
    code: str,
    variables: dict[str, SSAValue] | None = None,
    func_kind: FuncKind = FuncKind.MIXED,
) -> SSAValue:
    """Helper to parse and typecheck an expression, returning the SSA value."""
    if variables is None:
        variables = {}

    # Parse to CST
    parser = ProjParser(code)
    expr = parser.parse_expression()

    # Typecheck
    block = Block()
    builder = Builder(InsertPoint.at_end(block))
    ctx = TypingContext(
        func_kind=func_kind,
        variables=ScopedDict[str, SSAValue](local_scope=variables),
        borrows=ScopedDict[SSAValue, ProjectionBorrows](local_scope={}),
    )
    typechecker = TypeChecker()
    result = typechecker.infer_expression(expr, ctx, builder)
    assert result is not None, "typecheck_expression returned None in test"
    return result


def typecheck_statement(
    code: str,
    variables: dict[str, SSAValue] | None = None,
    func_kind: FuncKind = FuncKind.MIXED,
) -> list[Operation]:
    """Helper to parse and typecheck a statement, returning the list of operations."""
    if variables is None:
        variables = {}

    # Parse to CST
    parser = ProjParser(code)
    stmt = parser.parse_statement()

    # Typecheck
    block = Block()
    builder = Builder(InsertPoint.at_end(block))
    ctx = TypingContext(
        func_kind=func_kind,
        variables=ScopedDict[str, SSAValue](local_scope=variables),
        borrows=ScopedDict[SSAValue, ProjectionBorrows](local_scope={}),
    )
    typechecker = TypeChecker()
    typechecker.infer_statement(stmt, ctx, builder)
    return list(block.ops)


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
        assert isinstance(result.owner.lhs.owner, XOrIOp)

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
        assert isinstance(result.owner.lhs.owner, AndIOp)

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
        assert isinstance(result.owner.lhs.owner, FromBoolOp)


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
        assert isinstance(result.owner.lhs.owner, OrIOp)

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
        assert isinstance(result.owner.lhs.owner, FromBoolOp)


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
        assert isinstance(result.owner.lhs.owner, XOrIOp)

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
        assert isinstance(result.owner.lhs.owner, FromBoolOp)


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
        and_op = result.owner.lhs
        assert isinstance(and_op.owner, AndOp)
        from_bool_op = and_op.owner.lhs.owner
        assert isinstance(from_bool_op, FromBoolOp)
        assert isinstance(from_bool_op.input.owner, XOrIOp)
        eq_op = and_op.owner.rhs
        assert isinstance(eq_op.owner, EqOp)
        r_from_bool = result.owner.rhs.owner
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
        assert isinstance(result.owner.lhs.owner, ScalarMultOp)

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
        assert isinstance(result.owner.rhs.owner, ScalarMultOp)
        assert result.type == AngleType()

    def test_angle_minus_binds_same_as_add(self):
        """Test that minus binds same as add."""
        a = make_angle_var()
        b = make_angle_var()
        c = make_angle_var()
        result = typecheck_expression("a - b + c", {"a": a, "b": b, "c": c})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.lhs.owner, AddOp)

    def test_angle_minus_binds_looser_than_scalar_mult(self):
        """Test that minus binds looser than scalar_mult."""
        a = make_angle_var()
        b = make_angle_var()
        result = typecheck_expression("2.0 * a - b", {"a": a, "b": b})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.lhs.owner, ScalarMultOp)

    def test_angle_prefix_minus_binds_tightest(self):
        """Test that prefix minus binds tightest."""
        a = make_angle_var()
        b = make_angle_var()
        result = typecheck_expression("-a + b", {"a": a, "b": b})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.lhs.owner, ScalarMultOp)

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
        assert result.owner.lhs is a
        assert isinstance(result.owner.rhs.owner, ScalarMultOp)
        inner_scalar_mult = result.owner.rhs.owner.angle
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
        assert isinstance(result.owner.lhs.owner, PiOp)
        assert isinstance(result.owner.rhs.owner, ZeroOp)

    def test_pi_mixed_ascii_unicode(self):
        """Test mixing ASCII pi and Unicode π."""
        result = typecheck_expression("pi + π", {})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.lhs.owner, PiOp)
        assert isinstance(result.owner.rhs.owner, PiOp)

    def test_zero_constant(self):
        """Test typechecking 0 constant."""
        result = typecheck_expression("0", {})
        assert isinstance(result.owner, ZeroOp)
        assert result.type == AngleType()

    def test_angle_constant_in_expression(self):
        """Test using angle constants in expressions."""
        result = typecheck_expression("pi + 0", {})
        assert isinstance(result.owner, AddOp)
        assert isinstance(result.owner.lhs.owner, PiOp)
        assert isinstance(result.owner.rhs.owner, ZeroOp)


class TestPhaseStatement:
    """Test typechecking of phase statements."""

    def test_phase_statement(self):
        """Test typechecking ph(theta) statement."""
        angle_var = make_angle_var()
        ops = typecheck_statement("ph(theta)", {"theta": angle_var}, FuncKind.UNITARY)
        assert len(ops) == 1
        assert isinstance(ops[0], PhaseOp)
        assert ops[0].angle is angle_var

    def test_phase_statement_with_pi(self):
        """Test typechecking ph(pi) statement."""
        ops = typecheck_statement("ph(pi)", func_kind=FuncKind.UNITARY)
        assert len(ops) == 2
        assert isinstance(ops[0], PiOp)
        assert isinstance(ops[1], PhaseOp)

    def test_phase_statement_with_zero(self):
        """Test typechecking ph(0) statement."""
        ops = typecheck_statement("ph(0)", func_kind=FuncKind.UNITARY)
        assert len(ops) == 2
        assert isinstance(ops[0], ZeroOp)
        assert isinstance(ops[1], PhaseOp)

    def test_phase_statement_type_error(self):
        """Test that ph with non-angle raises error."""
        p = make_bool_var()
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            typecheck_statement("ph(p)", {"p": p}, FuncKind.UNITARY)

    def test_phase_statement_invalid_context(self):
        """Test that ph in PURE context raises error."""
        with pytest.raises(TypeCheckError, match="Phase operation not allowed"):
            typecheck_statement("ph(pi)", func_kind=FuncKind.PURE)


class TestQifStatement:
    """Test typechecking of qif statements."""

    def test_simple_qif_statement(self):
        """Test typechecking a simple qif statement with one phase."""
        proj_var = make_proj_var()

        ops = typecheck_statement("qif p { ph(pi) }", {"p": proj_var}, FuncKind.UNITARY)
        assert len(ops) == 1
        assert isinstance(ops[0], IfOp)
        assert ops[0].condition is proj_var

    def test_qif_else_statement(self):
        """Test typechecking qif statement with else clause."""
        proj_var = make_proj_var()

        ops = typecheck_statement(
            "qif p { ph(pi) } else { ph(0) }", {"p": proj_var}, FuncKind.UNITARY
        )
        assert len(ops) == 1
        assert isinstance(ops[0], IfOp)
        assert ops[0].condition is proj_var

        # Check that both true and false regions exist
        if_op = ops[0]
        assert if_op.false_region is not None

    def test_qif_else_empty_blocks(self):
        """Test typechecking qif statement with empty else clause."""
        proj_var = make_proj_var()

        ops = typecheck_statement(
            "qif p { } else { }", {"p": proj_var}, FuncKind.UNITARY
        )
        assert len(ops) == 1
        assert isinstance(ops[0], IfOp)

    def test_nested_qif_statement(self):
        """Test typechecking nested qif statements."""
        proj_var = make_proj_var()

        ops = typecheck_statement(
            "qif p { qif p { ph(pi) } }", {"p": proj_var}, FuncKind.UNITARY
        )
        assert len(ops) == 1
        assert isinstance(ops[0], IfOp)

    def test_qif_statement_type_error(self):
        """Test that qif with non-projection condition raises error."""
        # Booleans can be coerced to projections, so test with angle type
        a = make_angle_var()
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            typecheck_statement("qif a { ph(pi) }", {"a": a}, FuncKind.UNITARY)


class TestLetStatement:
    """Test typechecking of let statements."""

    def test_let_statement(self):
        """Test typechecking a simple let statement."""
        qubit_var = make_qubit_var()
        ops = typecheck_statement("let p = q == |0>", {"q": qubit_var})
        assert len(ops) == 1  # EqOp inserted

    def test_let_statement_with_type(self):
        """Test typechecking a let statement with type annotation."""
        qubit_var = make_qubit_var()
        ops = typecheck_statement("let p: proj = q == |0>", {"q": qubit_var})
        assert len(ops) == 1  # EqOp inserted

    def test_let_statement_scoping(self):
        """Test that let variables are scoped to their block."""
        qubit_var = make_qubit_var()
        proj_var = make_proj_var()

        # x should be available inside the qif block
        ops = typecheck_statement(
            "qif p { let x = q == |0>\nph(pi) }",
            {"q": qubit_var, "p": proj_var},
            FuncKind.UNITARY,
        )
        assert len(ops) == 1
        assert isinstance(ops[0], IfOp)

    def test_let_statement_shadowing_error(self):
        """Test that redefining a variable raises an error."""
        qubit_var = make_qubit_var()
        with pytest.raises(TypeCheckError, match="already defined"):
            typecheck_statement("let q = q == |0>", {"q": qubit_var})

    def test_let_statement_type_mismatch(self):
        """Test that a type mismatch raises an error."""
        qubit_var = make_qubit_var()
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            typecheck_statement("let p: qubit = q == |0>", {"q": qubit_var})

    def test_let_with_alloc(self):
        """Test typechecking let with alloc expression."""
        # Note: alloc requires MIXED func_kind
        # Parse and typecheck to verify the variable is added to scope
        parser = ProjParser("let q = alloc |0>")
        stmt = parser.parse_statement()

        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        ctx = TypingContext(
            func_kind=FuncKind.MIXED,
            variables=ScopedDict[str, SSAValue](local_scope={}),
            borrows=ScopedDict[SSAValue, ProjectionBorrows](local_scope={}),
        )
        typechecker = TypeChecker()
        typechecker.infer_statement(stmt, ctx, builder)

        ops = list(block.ops)
        assert len(ops) == 1  # AllocOp inserted
        assert isinstance(ops[0], AllocOp)

        # Verify the variable was added to scope with correct type
        assert "q" in ctx.variables
        assert ctx.variables["q"].type == QubitType()


class TestFuncParsing:
    """Test function typechecking."""

    def test_function_return_type_mismatch(self):
        """Test that return type mismatch raises error."""
        parser = ProjParser("pure fn foo() -> bool { 0 }")
        func_def = parser.parse_func()

        typechecker = TypeChecker()

        with pytest.raises(TypeCheckError, match="Type mismatch"):
            typechecker.check_func_def(func_def)

    def test_function_missing_return_expression(self):
        """Test that function with return type but no return expression raises error."""
        # Note: no semicolon, CST parser uses newlines
        parser = ProjParser("pure fn foo() -> bool { let x = true }")
        func_def = parser.parse_func()

        typechecker = TypeChecker()

        with pytest.raises(TypeCheckError, match="Expected statement with value"):
            typechecker.check_func_def(func_def)

    def test_module_function_signatures(self):
        """Test that function signatures are registered in the typechecker."""
        parser = ProjParser(
            "pure fn foo(a: bool, b: bool) -> bool { a }\n"
            "unitary fn bar(p: proj) -> proj { p }\n"
            "mixed fn baz() { }"
        )
        module = parser.parse_module()

        typechecker = TypeChecker()
        typechecker.check_module(module)

        # Check symbol table has all three functions
        assert len(typechecker.functions) == 3
        assert "foo" in typechecker.functions
        assert "bar" in typechecker.functions
        assert "baz" in typechecker.functions

        # Verify foo signature
        foo_sig = typechecker.functions["foo"]
        assert foo_sig.kind == FuncKind.PURE
        assert len(foo_sig.function_type.inputs.data) == 2

        # Verify bar signature
        bar_sig = typechecker.functions["bar"]
        assert bar_sig.kind == FuncKind.UNITARY
        assert len(bar_sig.function_type.inputs.data) == 1

        # Verify baz signature
        baz_sig = typechecker.functions["baz"]
        assert baz_sig.kind == FuncKind.MIXED
        assert len(baz_sig.function_type.inputs.data) == 0

    def test_module_clears_symbol_table(self):
        """Test that symbol table is cleared between module checks."""
        # First module
        parser1 = ProjParser("pure fn first() { }")
        module1 = parser1.parse_module()

        typechecker = TypeChecker()
        typechecker.check_module(module1)

        # First check should have 'first'
        assert "first" in typechecker.functions
        assert len(typechecker.functions) == 1

        # Second module - should clear old symbols
        parser2 = ProjParser("pure fn second() { }")
        module2 = parser2.parse_module()
        typechecker.check_module(module2)

        # Second check should only have 'second', not 'first'
        assert "second" in typechecker.functions
        assert "first" not in typechecker.functions
        assert len(typechecker.functions) == 1


class TestFuncKindValidation:
    """Test function kind validation during typechecking."""

    def test_phase_in_pure_raises_error(self):
        """Test that phase in pure function raises error."""
        with pytest.raises(TypeCheckError, match="Phase operation not allowed"):
            typecheck_statement("ph(pi)", func_kind=FuncKind.PURE)

    def test_phase_in_unitary_allowed(self):
        """Test that phase in unitary function is allowed."""
        ops = typecheck_statement("ph(pi)", func_kind=FuncKind.UNITARY)
        assert len(ops) == 2  # PiOp + PhaseOp

    def test_phase_in_mixed_allowed(self):
        """Test that phase in mixed function is allowed."""
        ops = typecheck_statement("ph(pi)", func_kind=FuncKind.MIXED)
        assert len(ops) == 2  # PiOp + PhaseOp

    def test_alloc_in_pure_raises_error(self):
        """Test that alloc in pure function raises error."""
        with pytest.raises(TypeCheckError, match="Alloc operation not allowed"):
            typecheck_expression("alloc |0>", func_kind=FuncKind.PURE)

    def test_alloc_in_unitary_raises_error(self):
        """Test that alloc in unitary function raises error."""
        with pytest.raises(TypeCheckError, match="Alloc operation not allowed"):
            typecheck_expression("alloc |0>", func_kind=FuncKind.UNITARY)

    def test_alloc_in_mixed_allowed(self):
        """Test that alloc in mixed function is allowed."""
        ops = typecheck_statement("let q = alloc |0>", func_kind=FuncKind.MIXED)
        assert len(ops) == 1
        assert isinstance(ops[0], AllocOp)

    def test_measure_in_pure_raises_error(self):
        """Test that measure in pure function raises error."""
        proj_var = make_proj_var()
        with pytest.raises(TypeCheckError, match="Measure operation not allowed"):
            typecheck_expression("measure p", {"p": proj_var}, FuncKind.PURE)

    def test_measure_in_unitary_raises_error(self):
        """Test that measure in unitary function raises error."""
        proj_var = make_proj_var()
        with pytest.raises(TypeCheckError, match="Measure operation not allowed"):
            typecheck_expression("measure p", {"p": proj_var}, FuncKind.UNITARY)

    def test_measure_in_mixed_allowed(self):
        """Test that measure in mixed function is allowed."""
        proj_var = make_proj_var()
        result = typecheck_expression("measure p", {"p": proj_var}, FuncKind.MIXED)
        assert isinstance(result.owner, MeasureOp)

    def test_qif_in_pure_raises_error(self):
        """Test that qif in pure function raises error."""
        proj_var = make_proj_var()
        with pytest.raises(TypeCheckError, match="Qif operation not allowed"):
            typecheck_statement("qif p { ph(pi) }", {"p": proj_var}, FuncKind.PURE)

    def test_qif_in_unitary_allowed(self):
        """Test that qif in unitary function is allowed."""
        proj_var = make_proj_var()
        ops = typecheck_statement("qif p { ph(pi) }", {"p": proj_var}, FuncKind.UNITARY)
        assert len(ops) == 1

    def test_let_with_measure_in_unitary_raises_error(self):
        """Test that let with measure expression in unitary function raises error."""
        qubit_var = make_qubit_var()
        with pytest.raises(TypeCheckError, match="Measure operation not allowed"):
            typecheck_statement("let x = measure q", {"q": qubit_var}, FuncKind.UNITARY)

    def test_and_with_measure_in_unitary_raises_error(self):
        """Test that p && measure p in unitary function raises error."""
        proj_var = make_proj_var()
        with pytest.raises(TypeCheckError, match="Measure operation not allowed"):
            typecheck_expression("p && measure p", {"p": proj_var}, FuncKind.UNITARY)

    def test_or_with_measure_in_pure_raises_error(self):
        """Test that p || measure p in pure function raises error."""
        proj_var = make_proj_var()
        with pytest.raises(TypeCheckError, match="Measure operation not allowed"):
            typecheck_expression("p || measure p", {"p": proj_var}, FuncKind.PURE)


class TestMeasureExpression:
    """Test typechecking of measure expressions."""

    def test_measure_expression(self):
        proj_var = make_proj_var()
        result = typecheck_expression("measure p", {"p": proj_var})
        assert isinstance(result.owner, MeasureOp)
        assert result.type == i1

    def test_measure_bool(self):
        """Test that measuring a bool inserts FromBool."""
        result = typecheck_expression("measure true")
        assert isinstance(result.owner, MeasureOp)
        assert isinstance(result.owner.projection.owner, FromBoolOp)

    def test_measure_nested(self):
        """Test nested measure expressions."""
        proj_var = make_proj_var()
        result = typecheck_expression("measure measure p", {"p": proj_var})
        # Should have nested MeasureOps
        assert isinstance(result.owner, MeasureOp)
