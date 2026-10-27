"""Tests for the proj-xdsl surface syntax parser."""

import pytest
from xdsl.builder import Builder
from xdsl.dialects.arith import ConstantOp
from xdsl.dialects.builtin import IntegerAttr, NoneAttr, i1
from xdsl.dialects.test import TestOp as XDSLTestOp
from xdsl.ir import Block, SSAValue
from xdsl.rewriter import InsertPoint
from xdsl.utils.exceptions import ParseError
from xdsl.utils.lexer import Input

from projxdsl.dialects.angle import AngleType, PiOp, ZeroOp
from projxdsl.dialects.proj import (
    AllocOp,
    AndOp,
    Basis,
    BasisAttr,
    EqOp,
    FromBoolOp,
    IfOp,
    MeasureOp,
    PhaseOp,
    ProjectionType,
    QubitType,
    State,
    StateAttr,
    YieldOp,
)
from projxdsl.frontend.lexer import ProjLexer, ProjTokenKind
from projxdsl.frontend.parser import ProjParser, TypeCheckError


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


def make_qubit_var() -> SSAValue:
    """Create a qubit SSA value for testing using test.op."""
    return XDSLTestOp(result_types=[QubitType(NoneAttr())]).results[0]


def make_qubit_with_basis(basis: Basis) -> SSAValue:
    """Create a qubit SSA value with basis annotation for testing."""
    return XDSLTestOp(result_types=[QubitType(BasisAttr(basis))]).results[0]


def make_proj_var(qubit: SSAValue) -> SSAValue:
    """Create a projection SSA value for testing."""
    return XDSLTestOp(operands=[qubit], result_types=[ProjectionType()]).results[0]


def make_angle_var() -> SSAValue:
    """Create an angle SSA value for testing."""
    return XDSLTestOp(result_types=[AngleType()]).results[0]


class TestTypeParsing:
    """Test parsing of types."""

    def test_qubit_unborrowed(self):
        result = parse_type("qubit")
        assert isinstance(result, QubitType)
        assert isinstance(result.borrow_type, NoneAttr)

    def test_projection(self):
        result = parse_type("proj")
        assert result == ProjectionType()

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
        # Missing pipe causes parse error (0 is lexed as integer, but not a valid state)
        with pytest.raises(ParseError, match="Expected state literal"):
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


class TestFloatParsing:
    """Test float literal parsing."""

    def test_simple_float(self):
        """Test parsing a simple float literal."""

        input = Input("3.14", "<test>")
        lexer = ProjLexer(input)
        token = lexer.lex()

        assert token.kind == ProjTokenKind.FLOAT
        assert token.kind.get_float_value(token.span) == 3.14

    def test_float_with_exponent(self):
        """Test parsing a float with exponent."""

        input = Input("2.5e-3", "<test>")
        lexer = ProjLexer(input)
        token = lexer.lex()

        assert token.kind == ProjTokenKind.FLOAT
        assert abs(token.kind.get_float_value(token.span) - 0.0025) < 1e-10

    def test_float_in_parser(self):
        """Test parsing floats in the parser."""

        parser = ProjParser("3.14")
        result = parser.parse_float()
        assert result == 3.14

    def test_optional_float_present(self):
        """Test parse_optional_float when float is present."""

        parser = ProjParser("2.0")
        result = parser.parse_optional_float()
        assert result == 2.0

    def test_optional_float_absent(self):
        """Test parse_optional_float when float is not present."""

        parser = ProjParser("x")
        result = parser.parse_optional_float()
        assert result is None


class TestIntegerParsing:
    """Test integer literal parsing."""

    def test_simple_integer(self):
        """Test parsing a simple integer literal."""

        input = Input("42", "<test>")
        lexer = ProjLexer(input)
        token = lexer.lex()

        assert token.kind == ProjTokenKind.INTEGER
        assert token.kind.get_integer_value(token.span) == 42

    def test_single_digit_integer(self):
        """Test parsing a single digit integer."""

        input = Input("0", "<test>")
        lexer = ProjLexer(input)
        token = lexer.lex()

        assert token.kind == ProjTokenKind.INTEGER
        assert token.kind.get_integer_value(token.span) == 0

    def test_multi_digit_integer(self):
        """Test parsing a multi-digit integer."""

        input = Input("123", "<test>")
        lexer = ProjLexer(input)
        token = lexer.lex()

        assert token.kind == ProjTokenKind.INTEGER
        assert token.kind.get_integer_value(token.span) == 123

    def test_integer_in_parser(self):
        """Test parsing integers in the parser (only 0 is valid for angles)."""

        parser = ProjParser("0")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        result = parser.parse_expression({}, builder)
        assert isinstance(result.owner, ZeroOp)
        assert result.type == AngleType()
        assert len(list(block.ops)) == 1  # ZeroOp inserted

    def test_invalid_integer_for_angle(self):
        """Test that non-zero integers are rejected for angle context."""

        parser = ProjParser("5")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="Only 0 is a valid angle constant"):
            parser.parse_expression({}, builder)


class TestPhaseStatement:
    """Test parsing of phase statements."""

    def test_phase_statement(self):
        """Test parsing ph(theta) statement."""

        angle_var = make_angle_var()
        parser = ProjParser("ph(theta)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement({"theta": angle_var}, builder)
        ops = list(block.ops)
        assert len(ops) == 1  # PhaseOp inserted
        assert isinstance(ops[0], PhaseOp)
        assert ops[0].angle is angle_var

    def test_phase_statement_with_pi(self):
        """Test parsing ph(pi) statement."""

        parser = ProjParser("ph(pi)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement({}, builder)
        ops = list(block.ops)
        assert len(ops) == 2  # PiOp + PhaseOp inserted
        assert isinstance(ops[0], PiOp)
        assert isinstance(ops[1], PhaseOp)

    def test_phase_statement_with_zero(self):
        """Test parsing ph(0) statement."""

        parser = ProjParser("ph(0)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement({}, builder)
        ops = list(block.ops)
        assert len(ops) == 2  # ZeroOp + PhaseOp inserted
        assert isinstance(ops[0], ZeroOp)
        assert isinstance(ops[1], PhaseOp)

    def test_phase_statement_type_error(self):
        """Test that ph with non-angle raises error."""

        # Create a boolean variable
        p = ConstantOp(IntegerAttr(1, 1)).result
        parser = ProjParser("ph(p)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(TypeCheckError, match="Expected angle"):
            parser.parse_statement({"p": p}, builder)


class TestIfStatement:
    """Test parsing of if statements."""

    def test_simple_if_statement(self):
        """Test parsing a simple if statement with one phase."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement({"p": proj_var}, builder)
        # IfOp is inserted into the block
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)
        assert if_op.condition is proj_var
        assert len(if_op.true_region.blocks) == 1
        inner_block = if_op.true_region.blocks[0]
        inner_ops = list(inner_block.ops)
        assert len(inner_ops) == 3  # PiOp + PhaseOp + YieldOp
        assert isinstance(inner_ops[0], PiOp)
        assert isinstance(inner_ops[1], PhaseOp)
        assert isinstance(inner_ops[2], YieldOp)

    def test_if_statement_multiple_statements(self):
        """Test parsing if statement with multiple phase statements."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi); ph(0) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement({"p": proj_var}, builder)
        # IfOp is inserted into the block
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)
        inner_block = if_op.true_region.blocks[0]
        inner_ops = list(inner_block.ops)
        assert len(inner_ops) == 5  # PiOp + PhaseOp + ZeroOp + PhaseOp + YieldOp
        assert isinstance(inner_ops[0], PiOp)
        assert isinstance(inner_ops[1], PhaseOp)
        assert isinstance(inner_ops[2], ZeroOp)
        assert isinstance(inner_ops[3], PhaseOp)
        assert isinstance(inner_ops[4], YieldOp)

    def test_if_statement_with_semicolons(self):
        """Test parsing if statement with semicolons between statements."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi); ph(0) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement({"p": proj_var}, builder)
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)
        inner_block = if_op.true_region.blocks[0]
        inner_ops = list(inner_block.ops)
        assert len(inner_ops) == 5  # PiOp + PhaseOp + ZeroOp + PhaseOp + YieldOp

    def test_if_statement_without_semicolons(self):
        """Test that missing semicolon between statements raises error."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi) ph(0) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="'\\}' expected"):
            parser.parse_statement({"p": proj_var}, builder)

    def test_if_statement_empty_block(self):
        """Test parsing if statement with empty block."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement({"p": proj_var}, builder)
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)
        inner_block = if_op.true_region.blocks[0]
        inner_ops = list(inner_block.ops)
        assert len(inner_ops) == 1  # Just YieldOp
        assert isinstance(inner_ops[0], YieldOp)

    def test_if_statement_type_error(self):
        """Test that if with non-projection condition raises error."""

        # Create a boolean variable
        p = ConstantOp(IntegerAttr(1, 1)).result
        parser = ProjParser("if p { ph(pi) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(TypeCheckError, match="Expected projection"):
            parser.parse_statement({"p": p}, builder)

    def test_if_statement_missing_brace(self):
        """Test that missing opening brace raises error."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p ph(pi) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="'\\{' expected"):
            parser.parse_statement({"p": proj_var}, builder)

    def test_if_statement_missing_closing_brace(self):
        """Test that missing closing brace raises error."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="'\\}' expected"):
            parser.parse_statement({"p": proj_var}, builder)

    def test_nested_if_statement(self):
        """Test parsing nested if statements."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { if q { ph(pi) } }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement({"p": proj_var, "q": proj_var}, builder)
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)
        assert if_op.condition is proj_var
        true_block = if_op.true_region.blocks[0]
        inner_ops = list(true_block.ops)
        assert len(inner_ops) == 2  # Inner IfOp + YieldOp
        inner_if = inner_ops[0]
        assert isinstance(inner_if, IfOp)
        inner_block = inner_if.true_region.blocks[0]
        inner_inner_ops = list(inner_block.ops)
        assert len(inner_inner_ops) == 3  # PiOp + PhaseOp + YieldOp
        assert isinstance(inner_inner_ops[0], PiOp)
        assert isinstance(inner_inner_ops[1], PhaseOp)
        assert isinstance(inner_inner_ops[2], YieldOp)


class TestLetStatement:
    """Test parsing of let statements."""

    def test_let_statement(self):
        """Test parsing a simple let statement."""

        qubit_var = make_qubit_var()
        parser = ProjParser("let p = q == |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables = {"q": qubit_var}
        parser.parse_statement(variables, builder)
        parser.expect_eof()

        assert "p" in variables
        assert len(list(block.ops)) == 1  # EqOp inserted

    def test_let_statement_with_type(self):
        """Test parsing a let statement with type annotation."""

        qubit_var = make_qubit_var()
        parser = ProjParser("let p: proj = q == |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables = {"q": qubit_var}
        parser.parse_statement(variables, builder)
        parser.expect_eof()

        assert "p" in variables
        assert len(list(block.ops)) == 1  # EqOp inserted

    def test_let_statement_scoping(self):
        """Test that let variables are scoped to their block."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { let x = q == |0> }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables = {"q": qubit_var, "p": proj_var}
        parser.parse_statement(variables, builder)
        parser.expect_eof()

        # x should NOT be in outer scope
        assert "x" not in variables

        # x should be in the if block
        if_op = list(block.ops)[0]
        assert isinstance(if_op, IfOp)
        inner_block = if_op.true_region.blocks[0]
        inner_ops = list(inner_block.ops)
        assert len(inner_ops) == 2  # EqOp + YieldOp

    def test_let_statement_shadowing_error(self):
        """Test that redefining a variable raises an error."""

        qubit_var = make_qubit_var()
        parser = ProjParser("let q = q == |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables = {"q": qubit_var}
        with pytest.raises(ParseError, match="already defined"):
            parser.parse_statement(variables, builder)

    def test_let_statement_type_mismatch(self):
        """Test that a type mismatch raises an error."""

        qubit_var = make_qubit_var()
        parser = ProjParser("let p: qubit = q == |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables = {"q": qubit_var}
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            parser.parse_statement(variables, builder)


class TestAllocExpression:
    """Test parsing of alloc expressions."""

    def test_alloc_expression_zero(self):
        """Test parsing alloc |0> expression."""

        parser = ProjParser("alloc |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        result = parser.parse_expression({}, builder)
        parser.expect_eof()

        ops = list(block.ops)
        assert len(ops) == 1
        assert isinstance(ops[0], AllocOp)
        assert result.type == QubitType()

    def test_alloc_expression_all_states(self):
        """Test parsing alloc with all state types."""

        for state_str in ["|0>", "|1>", "|+>", "|->", "|L>", "|R>"]:
            parser = ProjParser(f"alloc {state_str}")
            block = Block()
            builder = Builder(InsertPoint.at_end(block))
            result = parser.parse_expression({}, builder)
            parser.expect_eof()

            ops = list(block.ops)
            assert len(ops) == 1
            assert isinstance(ops[0], AllocOp)
            assert result.type == QubitType()

    def test_alloc_in_let_statement(self):
        """Test parsing alloc in let statement."""

        parser = ProjParser("let q = alloc |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables: dict[str, SSAValue] = {}
        parser.parse_statement(variables, builder)
        parser.expect_eof()

        ops = list(block.ops)
        assert len(ops) == 1
        assert isinstance(ops[0], AllocOp)
        assert "q" in variables
        assert variables["q"].type == QubitType()


class TestMeasureExpression:
    """Test parsing of measure expressions."""

    def test_measure_expression(self):
        """Test parsing measure expression."""

        parser = ProjParser("measure p")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables: dict[str, SSAValue] = {
            "p": XDSLTestOp(result_types=[ProjectionType()]).results[0]
        }
        result = parser.parse_expression(variables, builder)
        parser.expect_eof()

        ops = list(block.ops)
        assert len(ops) == 1
        assert isinstance(ops[0], MeasureOp)
        assert result.type == i1

    def test_measure_binding_power(self):
        """Test that measure binds tighter than &&."""

        parser = ProjParser("measure p && q")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables: dict[str, SSAValue] = {
            "p": XDSLTestOp(result_types=[ProjectionType()]).results[0],
            "q": XDSLTestOp(result_types=[ProjectionType()]).results[0],
        }
        result = parser.parse_expression(variables, builder)
        parser.expect_eof()

        ops = list(block.ops)
        assert len(ops) == 3  # MeasureOp, FromBoolOp, AndOp
        assert isinstance(ops[0], MeasureOp)
        assert isinstance(ops[1], FromBoolOp)
        assert isinstance(ops[2], AndOp)
        assert result.type == ProjectionType()

    def test_measure_with_eq(self):
        """Test that measure binds weaker than ==."""

        from projxdsl.dialects.proj import QubitType

        parser = ProjParser("measure p == |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables: dict[str, SSAValue] = {
            "p": XDSLTestOp(result_types=[QubitType()]).results[0],
        }
        result = parser.parse_expression(variables, builder)
        parser.expect_eof()

        ops = list(block.ops)
        assert len(ops) == 2  # EqOp, MeasureOp
        assert isinstance(ops[0], EqOp)
        assert isinstance(ops[1], MeasureOp)
        assert result.type == i1

    def test_measure_bool(self):
        """Test that measuring a bool inserts FromBool."""

        parser = ProjParser("measure true")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        result = parser.parse_expression({}, builder)
        parser.expect_eof()

        ops = list(block.ops)
        assert len(ops) == 3  # ConstantOp, FromBoolOp, MeasureOp
        assert isinstance(ops[0], ConstantOp)
        assert isinstance(ops[1], FromBoolOp)
        assert isinstance(ops[2], MeasureOp)
        assert result.type == i1

    def test_measure_nested(self):
        """Test nested measure expressions."""

        from projxdsl.dialects.proj import ProjectionType

        parser = ProjParser("measure measure p")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables: dict[str, SSAValue] = {
            "p": XDSLTestOp(result_types=[ProjectionType()]).results[0]
        }
        result = parser.parse_expression(variables, builder)
        parser.expect_eof()

        ops = list(block.ops)
        assert len(ops) == 3  # MeasureOp, FromBoolOp, MeasureOp
        assert isinstance(ops[0], MeasureOp)
        assert isinstance(ops[1], FromBoolOp)
        assert isinstance(ops[2], MeasureOp)
        assert result.type == i1


class TestExpressionStatement:
    """Test parsing of bare expression statements."""

    def test_measure_statement(self):
        """Test using measure as a statement."""

        from projxdsl.dialects.proj import ProjectionType

        parser = ProjParser("measure p")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables: dict[str, SSAValue] = {
            "p": XDSLTestOp(result_types=[ProjectionType()]).results[0]
        }
        parser.parse_statement(variables, builder)
        parser.expect_eof()

        ops = list(block.ops)
        assert len(ops) == 1
        assert isinstance(ops[0], MeasureOp)

    def test_bool_expression_statement(self):
        """Test using a boolean expression as a statement."""

        parser = ProjParser("true")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement({}, builder)
        parser.expect_eof()

        ops = list(block.ops)
        assert len(ops) == 1
        assert isinstance(ops[0], ConstantOp)

    def test_invalid_statement_error(self):
        """Test error message for invalid statement tokens."""

        parser = ProjParser("}")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(
            ParseError,
            match="Expected 'ph', 'if', 'let', or an expression for statement, got '}'",
        ):
            parser.parse_statement({}, builder)
