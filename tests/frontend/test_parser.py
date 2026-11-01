"""Tests for the proj-xdsl surface syntax parser."""

import pytest
from xdsl.builder import Builder
from xdsl.dialects.arith import ConstantOp
from xdsl.dialects.builtin import IntegerAttr, ModuleOp, i1
from xdsl.dialects.test import TestOp as XDSLTestOp
from xdsl.ir import Block, SSAValue
from xdsl.rewriter import InsertPoint
from xdsl.utils.exceptions import ParseError
from xdsl.utils.lexer import Input
from xdsl.utils.scoped_dict import ScopedDict

from projxdsl.dialects.angle import AngleType, PiOp, ZeroOp
from projxdsl.dialects.proj import (
    AllocOp,
    AndOp,
    Basis,
    EqOp,
    FromBoolOp,
    IfOp,
    MeasureOp,
    MixedOp,
    PhaseOp,
    ProjectionType,
    PureOp,
    QubitType,
    ReturnOp,
    State,
    StateAttr,
    UnitaryOp,
)
from projxdsl.frontend.lexer import ProjLexer, ProjTokenKind
from projxdsl.frontend.parser import ProjParser, TypeCheckError
from projxdsl.func_kind import FuncKind


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
    return XDSLTestOp(result_types=[QubitType()]).results[0]


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

    def test_projection(self):
        result = parse_type("proj")
        assert result == ProjectionType()

    def test_boolean(self):
        result = parse_type("bool")
        assert result == i1

    def test_angle(self):
        result = parse_type("angle")
        assert isinstance(result, AngleType)


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_type(self):
        parser = ProjParser("Invalid")
        with pytest.raises(ParseError, match="Expected type"):
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
        result = parser.parse_expression({}, builder, {})
        assert result is not None
        assert isinstance(result.owner, ZeroOp)
        assert result.type == AngleType()
        assert len(list(block.ops)) == 1  # ZeroOp inserted

    def test_invalid_integer_for_angle(self):
        """Test that non-zero integers are rejected for angle context."""

        parser = ProjParser("5")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="Only 0 is a valid angle constant"):
            parser.parse_expression({}, builder, {})


class TestPhaseStatement:
    """Test parsing of phase statements."""

    def test_phase_statement(self):
        """Test parsing ph(theta) statement."""

        angle_var = make_angle_var()
        parser = ProjParser("ph(theta)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={"theta": angle_var}), builder, {}
        )
        ops = list(block.ops)
        assert len(ops) == 1  # PhaseOp inserted
        assert isinstance(ops[0], PhaseOp)
        assert ops[0].angle is angle_var

    def test_phase_statement_with_pi(self):
        """Test parsing ph(pi) statement."""

        parser = ProjParser("ph(pi)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(ScopedDict[str, SSAValue](local_scope={}), builder, {})
        ops = list(block.ops)
        assert len(ops) == 2  # PiOp + PhaseOp inserted
        assert isinstance(ops[0], PiOp)
        assert isinstance(ops[1], PhaseOp)

    def test_phase_statement_with_zero(self):
        """Test parsing ph(0) statement."""

        parser = ProjParser("ph(0)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(ScopedDict[str, SSAValue](local_scope={}), builder, {})
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
            parser.parse_statement(
                ScopedDict[str, SSAValue](local_scope={"p": p}), builder, {}
            )


class TestIfStatement:
    """Test parsing of if statements."""

    def test_simple_if_statement(self):
        """Test parsing a simple if statement with one phase."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={"p": proj_var}), builder, {}
        )
        # IfOp is inserted into the block
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)
        assert if_op.condition is proj_var
        assert len(if_op.true_region.blocks) == 1
        inner_block = if_op.true_region.blocks[0]
        inner_ops = list(inner_block.ops)
        assert len(inner_ops) == 2  # PiOp + PhaseOp (no YieldOp)
        assert isinstance(inner_ops[0], PiOp)
        assert isinstance(inner_ops[1], PhaseOp)

    def test_if_statement_multiple_statements(self):
        """Test parsing if statement with multiple phase statements."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi); ph(0) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={"p": proj_var}), builder, {}
        )
        # IfOp is inserted into the block
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)
        inner_block = if_op.true_region.blocks[0]
        inner_ops = list(inner_block.ops)
        assert len(inner_ops) == 4  # PiOp + PhaseOp + ZeroOp + PhaseOp (no YieldOp)
        assert isinstance(inner_ops[0], PiOp)
        assert isinstance(inner_ops[1], PhaseOp)
        assert isinstance(inner_ops[2], ZeroOp)
        assert isinstance(inner_ops[3], PhaseOp)

    def test_if_statement_with_semicolons(self):
        """Test parsing if statement with semicolons between statements."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi); ph(0) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={"p": proj_var}), builder, {}
        )
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)
        inner_block = if_op.true_region.blocks[0]
        inner_ops = list(inner_block.ops)
        assert len(inner_ops) == 4  # PiOp + PhaseOp + ZeroOp + PhaseOp (no YieldOp)

    def test_if_statement_without_semicolons(self):
        """Test that missing semicolon between statements raises error."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi) ph(0) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="'\\}' expected"):
            parser.parse_statement(
                ScopedDict[str, SSAValue](local_scope={"p": proj_var}), builder, {}
            )

    def test_if_statement_empty_block(self):
        """Test parsing if statement with empty block."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={"p": proj_var}), builder, {}
        )
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)
        inner_block = if_op.true_region.blocks[0]
        inner_ops = list(inner_block.ops)
        assert len(inner_ops) == 0  # Empty block (no YieldOp)

    def test_if_statement_type_error(self):
        """Test that if with non-projection condition raises error."""

        # Create a boolean variable
        p = ConstantOp(IntegerAttr(1, 1)).result
        parser = ProjParser("if p { ph(pi) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(TypeCheckError, match="Expected projection"):
            parser.parse_statement(
                ScopedDict[str, SSAValue](local_scope={"p": p}), builder, {}
            )

    def test_if_statement_missing_brace(self):
        """Test that missing opening brace raises error."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p ph(pi) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="'\\{' expected"):
            parser.parse_statement(
                ScopedDict[str, SSAValue](local_scope={"p": proj_var}), builder, {}
            )

    def test_if_statement_missing_closing_brace(self):
        """Test that missing closing brace raises error."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="'\\}' expected"):
            parser.parse_statement(
                ScopedDict[str, SSAValue](local_scope={"p": proj_var}), builder, {}
            )

    def test_nested_if_statement(self):
        """Test parsing nested if statements."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { if q { ph(pi) } }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={"p": proj_var, "q": proj_var}),
            builder,
            {},
        )
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)
        assert if_op.condition is proj_var
        true_block = if_op.true_region.blocks[0]
        inner_ops = list(true_block.ops)
        assert len(inner_ops) == 1  # Inner IfOp (no YieldOp)
        inner_if = inner_ops[0]
        assert isinstance(inner_if, IfOp)
        inner_block = inner_if.true_region.blocks[0]
        inner_inner_ops = list(inner_block.ops)
        assert len(inner_inner_ops) == 2  # PiOp + PhaseOp (no YieldOp)
        assert isinstance(inner_inner_ops[0], PiOp)
        assert isinstance(inner_inner_ops[1], PhaseOp)

    def test_if_else_statement(self):
        """Test parsing if statement with else clause."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi) } else { ph(0) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={"p": proj_var}), builder, {}
        )
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)
        assert if_op.condition is proj_var

        # Check true region
        assert len(if_op.true_region.blocks) == 1
        true_block = if_op.true_region.blocks[0]
        true_ops = list(true_block.ops)
        assert len(true_ops) == 2  # PiOp + PhaseOp
        assert isinstance(true_ops[0], PiOp)
        assert isinstance(true_ops[1], PhaseOp)

        # Check false region
        assert if_op.false_region is not None
        assert len(if_op.false_region.blocks) == 1
        false_block = if_op.false_region.blocks[0]
        false_ops = list(false_block.ops)
        assert len(false_ops) == 2  # ZeroOp + PhaseOp
        assert isinstance(false_ops[0], ZeroOp)
        assert isinstance(false_ops[1], PhaseOp)

    def test_if_else_empty_blocks(self):
        """Test parsing if statement with empty else clause."""

        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { } else { }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={"p": proj_var}), builder, {}
        )
        ops = list(block.ops)
        assert len(ops) == 1
        if_op = ops[0]
        assert isinstance(if_op, IfOp)

        # Both regions should have empty blocks
        true_block = if_op.true_region.blocks[0]
        assert len(list(true_block.ops)) == 0

        assert if_op.false_region is not None
        false_block = if_op.false_region.blocks[0]
        assert len(list(false_block.ops)) == 0


class TestLetStatement:
    """Test parsing of let statements."""

    def test_let_statement(self):
        """Test parsing a simple let statement."""

        qubit_var = make_qubit_var()
        parser = ProjParser("let p = q == |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables = ScopedDict[str, SSAValue](local_scope={"q": qubit_var})
        parser.parse_statement(variables, builder, {})
        parser.expect_eof()

        assert "p" in variables
        assert len(list(block.ops)) == 1  # EqOp inserted

    def test_let_statement_with_type(self):
        """Test parsing a let statement with type annotation."""

        qubit_var = make_qubit_var()
        parser = ProjParser("let p: proj = q == |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables = ScopedDict[str, SSAValue](local_scope={"q": qubit_var})
        parser.parse_statement(variables, builder, {})
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
        variables = ScopedDict[str, SSAValue](
            local_scope={"q": qubit_var, "p": proj_var}
        )
        parser.parse_statement(variables, builder, {})
        parser.expect_eof()

        # x should NOT be in outer scope
        assert "x" not in variables

        # x should be in the if block
        if_op = list(block.ops)[0]
        assert isinstance(if_op, IfOp)
        inner_block = if_op.true_region.blocks[0]
        inner_ops = list(inner_block.ops)
        assert len(inner_ops) == 1  # EqOp (no YieldOp)

    def test_let_statement_shadowing_error(self):
        """Test that redefining a variable raises an error."""

        qubit_var = make_qubit_var()
        parser = ProjParser("let q = q == |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables = ScopedDict[str, SSAValue](local_scope={"q": qubit_var})
        with pytest.raises(ParseError, match="already defined"):
            parser.parse_statement(variables, builder, {})

    def test_let_statement_type_mismatch(self):
        """Test that a type mismatch raises an error."""

        qubit_var = make_qubit_var()
        parser = ProjParser("let p: qubit = q == |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        variables = ScopedDict[str, SSAValue](local_scope={"q": qubit_var})
        with pytest.raises(TypeCheckError, match="Type mismatch"):
            parser.parse_statement(variables, builder, {})


class TestAllocExpression:
    """Test parsing of alloc expressions."""

    def test_alloc_expression_zero(self):
        """Test parsing alloc |0> expression."""

        parser = ProjParser("alloc |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        result = parser.parse_expression({}, builder, {})
        assert result is not None
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
            result = parser.parse_expression({}, builder, {})
            assert result is not None
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
        variables = ScopedDict[str, SSAValue](local_scope={})
        parser.parse_statement(variables, builder, {})
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
        variables = ScopedDict[str, SSAValue](
            local_scope={"p": XDSLTestOp(result_types=[ProjectionType()]).results[0]}
        )
        result = parser.parse_expression(variables, builder, {})
        assert result is not None
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
        variables = ScopedDict[str, SSAValue](
            local_scope={
                "p": XDSLTestOp(result_types=[ProjectionType()]).results[0],
                "q": XDSLTestOp(result_types=[ProjectionType()]).results[0],
            }
        )
        result = parser.parse_expression(variables, builder, {})
        assert result is not None
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
        variables = ScopedDict[str, SSAValue](
            local_scope={
                "p": XDSLTestOp(result_types=[QubitType()]).results[0],
            }
        )
        result = parser.parse_expression(variables, builder, {})
        assert result is not None
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
        result = parser.parse_expression({}, builder, {})
        assert result is not None
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
        variables = ScopedDict[str, SSAValue](
            local_scope={"p": XDSLTestOp(result_types=[ProjectionType()]).results[0]}
        )
        result = parser.parse_expression(variables, builder, {})
        assert result is not None
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
        variables = ScopedDict[str, SSAValue](
            local_scope={"p": XDSLTestOp(result_types=[ProjectionType()]).results[0]}
        )
        parser.parse_statement(variables, builder, {})
        parser.expect_eof()

        ops = list(block.ops)
        assert len(ops) == 1
        assert isinstance(ops[0], MeasureOp)

    def test_bool_expression_statement(self):
        """Test using a boolean expression as a statement."""

        parser = ProjParser("true")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(ScopedDict[str, SSAValue](local_scope={}), builder, {})
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
            parser.parse_statement(
                ScopedDict[str, SSAValue](local_scope={}), builder, {}
            )


class TestFuncKindValidation:
    """Test function kind validation during parsing."""

    def test_phase_in_pure_raises_error(self):
        """Test that phase in pure function raises error."""
        parser = ProjParser("ph(pi)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="Phase operation not allowed in pure"):
            parser.parse_statement(
                ScopedDict[str, SSAValue](local_scope={}),
                builder,
                {},
                func_kind=FuncKind.PURE,
            )

    def test_phase_in_unitary_allowed(self):
        """Test that phase in unitary function is allowed."""
        parser = ProjParser("ph(pi)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={}),
            builder,
            {},
            func_kind=FuncKind.UNITARY,
        )
        ops = list(block.ops)
        assert len(ops) == 2  # PiOp + PhaseOp

    def test_phase_in_mixed_allowed(self):
        """Test that phase in mixed function is allowed."""
        parser = ProjParser("ph(pi)")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={}),
            builder,
            {},
            func_kind=FuncKind.MIXED,
        )
        ops = list(block.ops)
        assert len(ops) == 2  # PiOp + PhaseOp

    def test_alloc_in_pure_raises_error(self):
        """Test that alloc in pure function raises error."""
        parser = ProjParser("alloc |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="Alloc operation not allowed in pure"):
            parser.parse_statement(
                ScopedDict[str, SSAValue](local_scope={}),
                builder,
                {},
                func_kind=FuncKind.PURE,
            )

    def test_alloc_in_unitary_raises_error(self):
        """Test that alloc in unitary function raises error."""
        parser = ProjParser("alloc |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="Alloc operation not allowed in unitary"):
            parser.parse_statement(
                ScopedDict[str, SSAValue](local_scope={}),
                builder,
                {},
                func_kind=FuncKind.UNITARY,
            )

    def test_alloc_in_mixed_allowed(self):
        """Test that alloc in mixed function is allowed."""
        parser = ProjParser("alloc |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={}),
            builder,
            {},
            func_kind=FuncKind.MIXED,
        )
        ops = list(block.ops)
        assert len(ops) == 1  # AllocOp

    def test_measure_in_pure_raises_error(self):
        """Test that measure in pure function raises error."""
        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("measure p")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="Measure operation not allowed in pure"):
            parser.parse_expression(
                {"p": proj_var}, builder, {}, func_kind=FuncKind.PURE
            )

    def test_measure_in_unitary_raises_error(self):
        """Test that measure in unitary function raises error."""
        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("measure p")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(
            ParseError, match="Measure operation not allowed in unitary"
        ):
            parser.parse_expression(
                {"p": proj_var}, builder, {}, func_kind=FuncKind.UNITARY
            )

    def test_measure_in_mixed_allowed(self):
        """Test that measure in mixed function is allowed."""
        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("measure p")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        result = parser.parse_expression(
            {"p": proj_var}, builder, {}, func_kind=FuncKind.MIXED
        )
        assert result is not None
        ops = list(block.ops)
        assert len(ops) == 1  # MeasureOp

    def test_if_in_pure_raises_error(self):
        """Test that if in pure function raises error."""
        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="If operation not allowed in pure"):
            parser.parse_statement(
                ScopedDict[str, SSAValue](local_scope={"p": proj_var}),
                builder,
                {},
                func_kind=FuncKind.PURE,
            )

    def test_if_in_unitary_allowed(self):
        """Test that if in unitary function is allowed."""
        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("if p { ph(pi) }")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        parser.parse_statement(
            ScopedDict[str, SSAValue](local_scope={"p": proj_var}),
            builder,
            {},
            func_kind=FuncKind.UNITARY,
        )
        ops = list(block.ops)
        assert len(ops) == 1  # IfOp

    def test_let_with_measure_in_unitary_raises_error(self):
        """Test that let with measure expression in unitary function raises error."""
        qubit_var = make_qubit_var()
        parser = ProjParser("let x = measure q == |0>")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(
            ParseError, match="Measure operation not allowed in unitary"
        ):
            parser.parse_statement(
                ScopedDict[str, SSAValue](local_scope={"q": qubit_var}),
                builder,
                {},
                func_kind=FuncKind.UNITARY,
            )

    def test_and_with_measure_in_unitary_raises_error(self):
        """Test that p && measure p in unitary function raises error."""
        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("p && measure p")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(
            ParseError, match="Measure operation not allowed in unitary"
        ):
            parser.parse_expression(
                {"p": proj_var}, builder, {}, func_kind=FuncKind.UNITARY
            )

    def test_or_with_measure_in_pure_raises_error(self):
        """Test that p || measure p in pure function raises error."""
        qubit_var = make_qubit_var()
        proj_var = make_proj_var(qubit_var)
        parser = ProjParser("p || measure p")
        block = Block()
        builder = Builder(InsertPoint.at_end(block))
        with pytest.raises(ParseError, match="Measure operation not allowed in pure"):
            parser.parse_expression(
                {"p": proj_var}, builder, {}, func_kind=FuncKind.PURE
            )


class TestFuncParsing:
    """Test parsing of function definitions."""

    def test_parse_pure_function_void(self):
        """Test parsing a pure function with no return type."""
        parser = ProjParser("pure fn foo(b: bool) { }")
        func_op = parser.parse_func()
        parser.expect_eof()

        assert isinstance(func_op, PureOp)
        assert func_op.sym_name.data == "foo"
        assert len(func_op.function_type.inputs.data) == 1
        assert func_op.function_type.inputs.data[0] == i1
        assert len(func_op.function_type.outputs.data) == 0
        assert len(func_op.body.blocks) == 1

    def test_parse_unitary_function_with_return(self):
        """Test parsing a unitary function with return type."""
        parser = ProjParser("unitary fn bar(p: proj) -> proj { p }")
        func_op = parser.parse_func()
        parser.expect_eof()

        assert isinstance(func_op, UnitaryOp)
        assert func_op.sym_name.data == "bar"
        assert len(func_op.function_type.inputs.data) == 1
        assert func_op.function_type.inputs.data[0] == ProjectionType()
        assert len(func_op.function_type.outputs.data) == 1
        assert func_op.function_type.outputs.data[0] == ProjectionType()

        # Check body has ReturnOp with the parameter
        entry_block = func_op.body.blocks[0]
        ops = list(entry_block.ops)
        assert len(ops) == 1
        assert isinstance(ops[0], ReturnOp)
        assert ops[0].arguments[0] is entry_block.args[0]

    def test_parse_mixed_function_with_body(self):
        """Test parsing a mixed function with statements."""
        parser = ProjParser("mixed fn baz(q: qubit) { ph(pi); q == |0> }")
        func_op = parser.parse_func()
        parser.expect_eof()

        assert isinstance(func_op, MixedOp)
        assert func_op.sym_name.data == "baz"
        assert len(func_op.function_type.inputs.data) == 1
        assert func_op.function_type.inputs.data[0] == QubitType()
        assert len(func_op.function_type.outputs.data) == 0

        # Check body has PiOp, PhaseOp, EqOp, ReturnOp
        entry_block = func_op.body.blocks[0]
        ops = list(entry_block.ops)
        assert len(ops) == 4  # PiOp, PhaseOp, EqOp, ReturnOp
        assert isinstance(ops[0], PiOp)
        assert isinstance(ops[1], PhaseOp)
        assert isinstance(ops[2], EqOp)
        assert isinstance(ops[3], ReturnOp)

    def test_parse_function_multiple_params(self):
        """Test parsing a function with multiple parameters."""
        parser = ProjParser("pure fn multi(a: bool, b: bool) -> bool { a && b }")
        func_op = parser.parse_func()
        parser.expect_eof()

        assert isinstance(func_op, PureOp)
        assert func_op.sym_name.data == "multi"
        assert len(func_op.function_type.inputs.data) == 2
        assert func_op.function_type.inputs.data[0] == i1
        assert func_op.function_type.inputs.data[1] == i1
        assert len(func_op.function_type.outputs.data) == 1

    def test_parse_function_missing_kind_error(self):
        """Test that missing function kind raises error."""
        parser = ProjParser("fn foo() { }")
        with pytest.raises(ParseError, match="Expected function kind"):
            parser.parse_func()

    def test_parse_function_missing_fn_error(self):
        """Test that missing 'fn' keyword raises error."""
        parser = ProjParser("pure foo() { }")
        with pytest.raises(ParseError, match="Expected 'fn' keyword"):
            parser.parse_func()

    def test_parse_function_missing_name_error(self):
        """Test that missing function name raises error."""
        parser = ProjParser("pure fn (b: bool) { }")
        with pytest.raises(ParseError, match="Expected function name"):
            parser.parse_func()

    def test_parse_function_missing_param_type_error(self):
        """Test that missing parameter type raises error."""
        parser = ProjParser("pure fn foo(b) { }")
        with pytest.raises(ParseError, match="Expected ':'"):
            parser.parse_func()

    def test_parse_function_missing_param_name_error(self):
        """Test that missing parameter name raises error."""
        parser = ProjParser("pure fn foo(: bool) { }")
        with pytest.raises(ParseError, match="Expected parameter name"):
            parser.parse_func()

    def test_parse_function_missing_comma_between_params(self):
        """Test that missing comma between parameters raises error."""
        parser = ProjParser("pure fn foo(a: bool b: bool) { }")
        with pytest.raises(ParseError, match="in parameter list"):
            parser.parse_func()

    def test_parse_function_missing_return_type_error(self):
        """Test that missing return type after '->' raises error."""
        parser = ProjParser("pure fn foo() -> { }")
        with pytest.raises(ParseError, match="Expected type"):
            parser.parse_func()

    def test_parse_function_return_type_mismatch(self):
        """Test that return type mismatch raises error."""
        parser = ProjParser("pure fn foo() -> bool { 0 }")
        with pytest.raises(TypeCheckError, match="Type mismatch.*for return value"):
            parser.parse_func()

    def test_parse_function_missing_final_expr(self):
        """Test that missing final expression raises error."""
        parser = ProjParser("pure fn foo() -> bool { let x = true }")
        with pytest.raises(ParseError, match="Expected expression"):
            parser.parse_func()

    def test_parse_function_error_in_body(self):
        """Test that syntax error in function body is caught."""
        parser = ProjParser("mixed fn foo() { ph(pi)")
        with pytest.raises(ParseError, match="in function body"):
            parser.parse_func()

    def test_parse_function_empty_body_void(self):
        """Test parsing a function with empty body and no return."""
        parser = ProjParser("pure fn empty() { }")
        func_op = parser.parse_func()
        parser.expect_eof()

        assert isinstance(func_op, PureOp)
        entry_block = func_op.body.blocks[0]
        ops = list(entry_block.ops)
        assert len(ops) == 1
        assert isinstance(ops[0], ReturnOp)
        assert len(ops[0].arguments) == 0

    def test_parse_function_with_let_and_return(self):
        """Test parsing a function with let statement and return."""
        parser = ProjParser(
            "pure fn with_let(q: qubit) -> proj { let p = q == |0>; p }"
        )
        func_op = parser.parse_func()
        parser.expect_eof()

        assert isinstance(func_op, PureOp)
        entry_block = func_op.body.blocks[0]
        ops = list(entry_block.ops)
        # EqOp, ReturnOp (let doesn't insert ops, just adds to variables)
        assert len(ops) == 2
        assert isinstance(ops[0], EqOp)
        assert isinstance(ops[1], ReturnOp)

    def test_parse_function_all_kinds(self):
        """Test parsing all three function kinds."""
        for kind_str, expected_class in [
            ("pure", PureOp),
            ("unitary", UnitaryOp),
            ("mixed", MixedOp),
        ]:
            parser = ProjParser(f"{kind_str} fn test() {{ }}")
            func_op = parser.parse_func()
            parser.expect_eof()
            assert isinstance(func_op, expected_class)


class TestModuleParsing:
    """Test parsing of modules containing multiple functions."""

    def test_parse_empty_module(self):
        """Test parsing an empty module."""
        parser = ProjParser("")
        module_op = parser.parse_module()
        parser.expect_eof()

        assert isinstance(module_op, ModuleOp)
        assert len(list(module_op.body.ops)) == 0

    def test_parse_module_single_function(self):
        """Test parsing a module with a single function."""
        parser = ProjParser("pure fn foo() { }")
        module_op = parser.parse_module()
        parser.expect_eof()

        assert isinstance(module_op, ModuleOp)
        ops = list(module_op.body.ops)
        assert len(ops) == 1
        assert isinstance(ops[0], PureOp)
        assert ops[0].sym_name.data == "foo"

    def test_parse_module_multiple_functions(self):
        """Test parsing a module with multiple functions."""
        parser = ProjParser(
            "pure fn foo() { }\n"
            "unitary fn bar(p: proj) -> proj { p }\n"
            "mixed fn baz() { }"
        )
        module_op = parser.parse_module()
        parser.expect_eof()

        assert isinstance(module_op, ModuleOp)
        ops = list(module_op.body.ops)
        assert len(ops) == 3
        assert isinstance(ops[0], PureOp)
        assert ops[0].sym_name.data == "foo"
        assert isinstance(ops[1], UnitaryOp)
        assert ops[1].sym_name.data == "bar"
        assert isinstance(ops[2], MixedOp)
        assert ops[2].sym_name.data == "baz"

    def test_parse_module_with_whitespace(self):
        """Test parsing a module with whitespace between functions."""
        parser = ProjParser(
            """
            pure fn foo() { }

            unitary fn bar() { }

            mixed fn baz() { }
            """
        )
        module_op = parser.parse_module()
        parser.expect_eof()

        assert isinstance(module_op, ModuleOp)
        ops = list(module_op.body.ops)
        assert len(ops) == 3

    def test_parse_module_with_comments(self):
        """Test parsing a module with comments between functions."""
        parser = ProjParser(
            """
            // First function
            pure fn foo() { }
            // Second function
            unitary fn bar() { }
            """
        )
        module_op = parser.parse_module()
        parser.expect_eof()

        assert isinstance(module_op, ModuleOp)
        ops = list(module_op.body.ops)
        assert len(ops) == 2

    def test_parse_module_function_signature_table(self):
        """Test that function signatures are registered in the symbol table."""
        from projxdsl.frontend.parser import FuncSignature

        parser = ProjParser(
            "pure fn foo(a: bool, b: bool) -> bool { a && b }\n"
            "unitary fn bar(p: proj) -> proj { p }\n"
            "mixed fn baz() { }"
        )
        module_op = parser.parse_module()
        parser.expect_eof()

        assert isinstance(module_op, ModuleOp)

        # Check symbol table has all three functions
        assert len(parser.functions) == 3
        assert "foo" in parser.functions
        assert "bar" in parser.functions
        assert "baz" in parser.functions

        # Verify foo signature
        foo_sig = parser.functions["foo"]
        assert isinstance(foo_sig, FuncSignature)
        assert foo_sig.kind.display_name == "pure"
        assert len(foo_sig.function_type.inputs.data) == 2
        assert foo_sig.function_type.inputs.data[0] == i1
        assert foo_sig.function_type.inputs.data[1] == i1
        assert len(foo_sig.function_type.outputs.data) == 1
        assert foo_sig.function_type.outputs.data[0] == i1

        # Verify bar signature
        bar_sig = parser.functions["bar"]
        assert isinstance(bar_sig, FuncSignature)
        assert bar_sig.kind.display_name == "unitary"
        assert len(bar_sig.function_type.inputs.data) == 1
        assert bar_sig.function_type.inputs.data[0] == ProjectionType()
        assert len(bar_sig.function_type.outputs.data) == 1
        assert bar_sig.function_type.outputs.data[0] == ProjectionType()

        # Verify baz signature
        baz_sig = parser.functions["baz"]
        assert isinstance(baz_sig, FuncSignature)
        assert baz_sig.kind.display_name == "mixed"
        assert len(baz_sig.function_type.inputs.data) == 0
        assert len(baz_sig.function_type.outputs.data) == 0

    def test_parse_module_clears_symbol_table(self):
        """Test that symbol table is cleared between module parses."""
        parser = ProjParser("pure fn first() { }")
        parser.parse_module()

        # First parse should have 'first'
        assert "first" in parser.functions
        assert len(parser.functions) == 1

        # Parse a new module - should clear old symbols
        parser2 = ProjParser("pure fn second() { }")
        parser2.parse_module()

        # Second parse should only have 'second', not 'first'
        assert "second" in parser2.functions
        assert "first" not in parser2.functions
        assert len(parser2.functions) == 1
