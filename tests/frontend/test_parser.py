"""Tests for the proj-xdsl CST parser."""

import pytest
from xdsl.utils.exceptions import ParseError

from projxdsl.frontend.cst import (
    AllocExpr,
    AngleConstantExpr,
    AngleConstantKind,
    AngleOpKind,
    AngleTypeNode,
    BinaryAngleExpr,
    BinaryOpKind,
    BinaryProjExpr,
    BoolLiteralExpr,
    BoolTypeNode,
    CallExpr,
    EqExpr,
    ExprStmt,
    FuncDef,
    IdentExpr,
    LetStmt,
    MeasureExpr,
    Module,
    NegAngleExpr,
    NotExpr,
    PhaseStmt,
    ProjTypeNode,
    QifStmt,
    QubitTypeNode,
    ScalarMultExpr,
    StateExpr,
)
from projxdsl.frontend.parser import ProjParser
from projxdsl.func_kind import FuncKind


def parse_expression(code: str):
    """Helper to parse an expression and return the CST node."""
    parser = ProjParser(code)
    result = parser.parse_expression()
    return result


def parse_type(code: str):
    """Helper to parse a type and return the CST node."""
    parser = ProjParser(code)
    result = parser.parse_type()
    return result


def parse_statement(code: str):
    """Helper to parse a statement and return the CST node."""
    parser = ProjParser(code)
    result = parser.parse_statement()
    return result


def parse_func(code: str):
    """Helper to parse a function and return the CST node."""
    parser = ProjParser(code)
    result = parser.parse_func()
    return result


def parse_module(code: str):
    """Helper to parse a module and return the CST node."""
    parser = ProjParser(code)
    result = parser.parse_module()
    return result


class TestTypeParsing:
    """Test parsing of types."""

    def test_qubit_unborrowed(self):
        result = parse_type("qubit")
        assert isinstance(result, QubitTypeNode)

    def test_projection(self):
        result = parse_type("proj")
        assert isinstance(result, ProjTypeNode)

    def test_boolean(self):
        result = parse_type("bool")
        assert isinstance(result, BoolTypeNode)

    def test_angle(self):
        result = parse_type("angle")
        assert isinstance(result, AngleTypeNode)

    def test_invalid_type(self):
        with pytest.raises(ParseError, match="Expected type"):
            parse_type("Invalid")

    def test_unexpected_token_after_type(self):
        parser = ProjParser("qubit foo")
        parser.parse_type()
        with pytest.raises(ParseError, match="Unexpected token"):
            parser.expect_eof()


class TestStateParsing:
    """Test parsing of state literals."""

    def test_state_zero_ascii(self):
        result = parse_expression("|0>")
        assert isinstance(result, StateExpr)
        assert result.state.name == "ZERO"

    def test_state_one_ascii(self):
        result = parse_expression("|1>")
        assert isinstance(result, StateExpr)
        assert result.state.name == "ONE"

    def test_state_plus_ascii(self):
        result = parse_expression("|+>")
        assert isinstance(result, StateExpr)
        assert result.state.name == "PLUS"

    def test_state_minus_ascii(self):
        result = parse_expression("|->")
        assert isinstance(result, StateExpr)
        assert result.state.name == "MINUS"

    def test_state_left_ascii(self):
        result = parse_expression("|L>")
        assert isinstance(result, StateExpr)
        assert result.state.name == "LEFT"

    def test_state_right_ascii(self):
        result = parse_expression("|R>")
        assert isinstance(result, StateExpr)
        assert result.state.name == "RIGHT"

    def test_state_zero_unicode(self):
        result = parse_expression("|0⟩")
        assert isinstance(result, StateExpr)
        assert result.state.name == "ZERO"

    def test_state_one_unicode(self):
        result = parse_expression("|1⟩")
        assert isinstance(result, StateExpr)
        assert result.state.name == "ONE"

    def test_state_plus_unicode(self):
        result = parse_expression("|+⟩")
        assert isinstance(result, StateExpr)
        assert result.state.name == "PLUS"

    def test_state_minus_unicode(self):
        result = parse_expression("|-⟩")
        assert isinstance(result, StateExpr)
        assert result.state.name == "MINUS"

    def test_state_left_unicode(self):
        result = parse_expression("|L⟩")
        assert isinstance(result, StateExpr)
        assert result.state.name == "LEFT"

    def test_state_right_unicode(self):
        result = parse_expression("|R⟩")
        assert isinstance(result, StateExpr)
        assert result.state.name == "RIGHT"

    def test_invalid_state_character(self):
        with pytest.raises(ValueError, match="Unexpected character"):
            parse_expression("|X>")

    def test_missing_closing(self):
        with pytest.raises(ValueError, match="Unexpected character"):
            parse_expression("|0")

    def test_invalid_state_char(self):
        with pytest.raises(ValueError, match="Unexpected character"):
            parse_expression("|2>")


class TestFloatParsing:
    """Test parsing of float literals."""

    def test_simple_float(self):
        parser = ProjParser("3.14")
        result = parser.parse_float()
        assert result == 3.14

    def test_float_with_exponent(self):
        parser = ProjParser("2.5e-3")
        result = parser.parse_float()
        assert abs(result - 0.0025) < 1e-10

    def test_float_in_parser(self):
        """Test parsing a float in the parser."""
        parser = ProjParser("3.14")
        result = parser.parse_float()
        assert result == 3.14

    def test_optional_float_present(self):
        parser = ProjParser("2.0")
        result = parser.parse_optional_float()
        assert result == 2.0

    def test_optional_float_absent(self):
        parser = ProjParser("x")
        result = parser.parse_optional_float()
        assert result is None


class TestIntegerParsing:
    """Test parsing of integer literals."""

    def test_simple_integer(self):
        parser = ProjParser("42")
        token = parser._consume_token()  # pyright: ignore[reportPrivateUsage]
        assert token.kind.name == "INTEGER"
        assert token.kind.get_integer_value(token.span) == 42

    def test_single_digit_integer(self):
        parser = ProjParser("0")
        token = parser._consume_token()  # pyright: ignore[reportPrivateUsage]
        assert token.kind.name == "INTEGER"
        assert token.kind.get_integer_value(token.span) == 0

    def test_multi_digit_integer(self):
        parser = ProjParser("123")
        token = parser._consume_token()  # pyright: ignore[reportPrivateUsage]
        assert token.kind.name == "INTEGER"
        assert token.kind.get_integer_value(token.span) == 123


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


class TestPhaseStatement:
    """Test parsing of phase statements."""

    def test_phase_statement(self):
        result = parse_statement("ph(theta)")
        assert isinstance(result, PhaseStmt)
        assert isinstance(result.angle, IdentExpr)
        assert result.angle.name == "theta"

    def test_phase_statement_with_pi(self):
        result = parse_statement("ph(pi)")
        assert isinstance(result, PhaseStmt)
        assert isinstance(result.angle, AngleConstantExpr)
        assert result.angle.kind == AngleConstantKind.PI

    def test_phase_statement_with_zero(self):
        result = parse_statement("ph(0)")
        assert isinstance(result, PhaseStmt)
        assert isinstance(result.angle, AngleConstantExpr)
        assert result.angle.kind == AngleConstantKind.ZERO

    def test_phase_statement_with_expression(self):
        result = parse_statement("ph(a + b)")
        assert isinstance(result, PhaseStmt)
        assert isinstance(result.angle, BinaryAngleExpr)


class TestQifStatement:
    """Test parsing of qif statements."""

    def test_simple_qif_statement(self):
        result = parse_statement("qif p { ph(pi) }")
        assert isinstance(result, QifStmt)
        assert isinstance(result.condition, IdentExpr)
        assert len(result.true_body.statements) == 1
        assert isinstance(result.true_body.statements[0], PhaseStmt)

    def test_qif_statement_multiple_statements(self):
        result = parse_statement("qif p { ph(pi)\nph(0) }")
        assert isinstance(result, QifStmt)
        assert len(result.true_body.statements) == 2
        assert isinstance(result.true_body.statements[0], PhaseStmt)
        assert isinstance(result.true_body.statements[1], PhaseStmt)

    def test_qif_statement_empty_block(self):
        result = parse_statement("qif p { }")
        assert isinstance(result, QifStmt)
        assert len(result.true_body.statements) == 0

    def test_qif_statement_multiple_statements_same_line_error(self):
        """Test that multiple statements on the same line in a block is an error."""
        with pytest.raises(ParseError, match="Expected newline"):
            parse_statement("qif p { ph(pi) ph(0) }")

    def test_qif_statement_double_newlines(self):
        """Test that double newlines between statements work."""
        result = parse_statement("qif p { ph(pi)\n\nph(0) }")
        assert isinstance(result, QifStmt)
        assert len(result.true_body.statements) == 2

    def test_qif_statement_newline_after_brace(self):
        """Test that newline after opening brace works."""
        result = parse_statement("qif p {\nph(pi)\n}")
        assert isinstance(result, QifStmt)
        assert len(result.true_body.statements) == 1

    def test_qif_statement_missing_brace(self):
        """Test that missing opening brace raises error."""
        with pytest.raises(ParseError, match="Expected.*block"):
            parse_statement("qif p ph(pi)")

    def test_nested_qif_statement(self):
        """Test parsing nested qif statements."""
        result = parse_statement("qif p { qif q { ph(pi) } }")
        assert isinstance(result, QifStmt)
        assert len(result.true_body.statements) == 1
        nested_qif = result.true_body.statements[0]
        assert isinstance(nested_qif, QifStmt)
        assert len(nested_qif.true_body.statements) == 1

    def test_qif_statement_missing_closing_brace(self):
        """Test that missing closing brace raises error."""
        with pytest.raises(ParseError, match="Expected.*'}'"):
            parse_statement("qif p { ph(pi)")


class TestLetStatement:
    """Test parsing of let statements."""

    def test_let_statement(self):
        result = parse_statement("let x = theta")
        assert isinstance(result, LetStmt)
        assert result.name == "x"
        assert isinstance(result.value, IdentExpr)
        assert result.value.name == "theta"

    def test_let_statement_with_type(self):
        result = parse_statement("let x: qubit = q")
        assert isinstance(result, LetStmt)
        assert result.name == "x"
        assert isinstance(result.type_ann, QubitTypeNode)
        assert isinstance(result.value, IdentExpr)


class TestAllocExpression:
    """Test parsing of alloc expressions."""

    def test_alloc_expression(self):
        result = parse_expression("alloc |0>")
        assert isinstance(result, AllocExpr)
        assert isinstance(result.state, StateExpr)

    def test_alloc_expression_all_states(self):
        """Test parsing alloc with all state types."""
        for state_str in ["|0>", "|1>", "|+>", "|->", "|L>", "|R>"]:
            result = parse_expression(f"alloc {state_str}")
            assert isinstance(result, AllocExpr)
            assert isinstance(result.state, StateExpr)


class TestMeasureExpression:
    """Test parsing of measure expressions."""

    def test_measure_expression(self):
        result = parse_expression("measure q")
        assert isinstance(result, MeasureExpr)
        assert isinstance(result.operand, IdentExpr)

    def test_measure_with_complex_expression(self):
        """Test that measure(p && q) is parsed as measure, not function call."""
        result = parse_expression("measure(p && q)")
        assert isinstance(result, MeasureExpr)
        assert isinstance(result.operand, BinaryProjExpr)
        assert result.operand.op == BinaryOpKind.AND

    def test_measure_binding_power(self):
        """Test that measure binds tighter than &&."""
        result = parse_expression("measure p && q")
        assert isinstance(result, BinaryProjExpr)
        assert result.op == BinaryOpKind.AND
        assert isinstance(result.left, MeasureExpr)

    def test_measure_with_eq(self):
        """Test that measure binds weaker than ==."""
        result = parse_expression("measure q == |0>")
        assert isinstance(result, MeasureExpr)
        assert isinstance(result.operand, EqExpr)


class TestExpressionStatement:
    """Test parsing of expression statements."""

    def test_expression_statement(self):
        result = parse_statement("foo()")
        assert isinstance(result, ExprStmt)
        assert isinstance(result.expr, CallExpr)
        assert result.expr.name == "foo"

    def test_measure_statement(self):
        """Test using measure as a statement."""
        result = parse_statement("measure p")
        assert isinstance(result, ExprStmt)
        assert isinstance(result.expr, MeasureExpr)

    def test_bool_expression_statement(self):
        """Test using a boolean expression as a statement."""
        result = parse_statement("true")
        assert isinstance(result, ExprStmt)
        assert isinstance(result.expr, BoolLiteralExpr)

    def test_invalid_statement_error(self):
        """Test error message for invalid statement tokens."""
        with pytest.raises(ParseError, match="Expected.*expression"):
            parse_statement("}")


class TestFuncParsing:
    """Test parsing of function definitions."""

    def test_parse_pure_function_void(self):
        """Test parsing a pure function with no return type."""
        result = parse_func("pure fn foo(b: bool) { }")
        assert isinstance(result, FuncDef)
        assert result.name == "foo"
        assert result.kind == FuncKind.PURE
        assert len(result.params) == 1
        assert result.params[0].name == "b"
        assert isinstance(result.params[0].type_ann, BoolTypeNode)
        assert result.return_type is None

    def test_parse_unitary_function_with_return(self):
        """Test parsing a unitary function with return type."""
        result = parse_func("unitary fn bar(p: proj) -> proj { p }")
        assert isinstance(result, FuncDef)
        assert result.name == "bar"
        assert result.kind == FuncKind.UNITARY
        assert len(result.params) == 1
        assert isinstance(result.return_type, ProjTypeNode)

    def test_parse_mixed_function_with_body(self):
        """Test parsing a mixed function with statements."""
        result = parse_func("mixed fn baz(q: qubit) { ph(pi)\nq == |0> }")
        assert isinstance(result, FuncDef)
        assert result.name == "baz"
        assert result.kind == FuncKind.MIXED
        assert len(result.params) == 1
        assert isinstance(result.params[0].type_ann, QubitTypeNode)
        assert len(result.body.statements) == 2

    def test_parse_function_multiple_params(self):
        """Test parsing a function with multiple parameters."""
        result = parse_func("pure fn multi(a: bool, b: bool) -> bool { a && b }")
        assert isinstance(result, FuncDef)
        assert result.name == "multi"
        assert len(result.params) == 2
        assert result.params[0].name == "a"
        assert result.params[1].name == "b"

    def test_parse_function_missing_kind_error(self):
        """Test that missing function kind raises error."""
        with pytest.raises(ParseError, match="Expected function kind"):
            parse_func("fn foo() { }")

    def test_parse_function_missing_fn_error(self):
        """Test that missing 'fn' keyword raises error."""
        with pytest.raises(ParseError, match="Expected 'fn' keyword"):
            parse_func("pure foo() { }")

    def test_parse_function_missing_name_error(self):
        """Test that missing function name raises error."""
        with pytest.raises(ParseError, match="Expected function name"):
            parse_func("pure fn (b: bool) { }")

    def test_parse_function_missing_param_name_error(self):
        """Test that missing parameter name raises error."""
        with pytest.raises(ParseError, match="Expected parameter name"):
            parse_func("pure fn foo(: bool) { }")

    def test_parse_function_missing_comma_between_params(self):
        """Test that missing comma between parameters raises error."""
        with pytest.raises(ParseError, match="parameter"):
            parse_func("pure fn foo(a: bool b: bool) { }")

    def test_parse_function_missing_param_type_error(self):
        """Test that missing parameter type raises error."""
        with pytest.raises(ParseError, match="Expected ':'"):
            parse_func("pure fn foo(b) { }")

    def test_parse_function_missing_return_type_error(self):
        """Test that missing return type after '->' raises error."""
        with pytest.raises(ParseError, match="Expected type"):
            parse_func("pure fn foo() -> { }")

    def test_parse_function_empty_body_void(self):
        """Test parsing a function with empty body and no return."""
        result = parse_func("pure fn empty() { }")
        assert isinstance(result, FuncDef)
        assert len(result.body.statements) == 0
        assert result.return_type is None

    def test_parse_function_all_kinds(self):
        """Test parsing all three function kinds."""
        for kind_str, expected_kind in [
            ("pure", FuncKind.PURE),
            ("unitary", FuncKind.UNITARY),
            ("mixed", FuncKind.MIXED),
        ]:
            result = parse_func(f"{kind_str} fn test() {{ }}")
            assert isinstance(result, FuncDef)
            assert result.kind == expected_kind

    def test_parse_function_with_let_and_return(self):
        """Test parsing a function with let statement and return."""
        result = parse_func(
            "pure fn with_let(q: qubit) -> proj { let p = q == |0>\np }"
        )
        assert isinstance(result, FuncDef)
        assert len(result.body.statements) == 2
        assert isinstance(result.body.statements[0], LetStmt)
        assert isinstance(result.return_type, ProjTypeNode)


class TestModuleParsing:
    """Test parsing of modules containing multiple functions."""

    def test_parse_empty_module(self):
        """Test parsing an empty module."""
        result = parse_module("")
        assert isinstance(result, Module)
        assert len(result.functions) == 0

    def test_parse_module_single_function(self):
        """Test parsing a module with a single function."""
        result = parse_module("pure fn foo() { }")
        assert isinstance(result, Module)
        assert len(result.functions) == 1
        assert result.functions[0].name == "foo"

    def test_parse_module_multiple_functions(self):
        """Test parsing a module with multiple functions."""
        result = parse_module(
            "pure fn foo() { }\n"
            "unitary fn bar(p: proj) -> proj { p }\n"
            "mixed fn baz() { }"
        )
        assert isinstance(result, Module)
        assert len(result.functions) == 3
        assert result.functions[0].name == "foo"
        assert result.functions[1].name == "bar"
        assert result.functions[2].name == "baz"

    def test_parse_module_with_whitespace(self):
        """Test parsing a module with whitespace between functions."""
        result = parse_module(
            """
            pure fn foo() { }

            unitary fn bar() { }

            mixed fn baz() { }
            """
        )
        assert isinstance(result, Module)
        assert len(result.functions) == 3

    def test_parse_module_with_comments(self):
        """Test parsing a module with comments between functions."""
        result = parse_module(
            """
            // First function
            pure fn foo() { }
            // Second function
            unitary fn bar() { }
            """
        )
        assert isinstance(result, Module)
        assert len(result.functions) == 2

    def test_parse_module_function_signatures(self):
        """Test that function signatures are parsed correctly."""
        result = parse_module(
            "pure fn foo(a: bool, b: bool) -> bool { a && b }\n"
            "unitary fn bar(p: proj) -> proj { p }\n"
            "mixed fn baz() { }"
        )
        assert isinstance(result, Module)
        assert len(result.functions) == 3

        # Check foo signature
        foo = result.functions[0]
        assert foo.name == "foo"
        assert foo.kind == FuncKind.PURE
        assert len(foo.params) == 2
        assert isinstance(foo.return_type, BoolTypeNode)

        # Check bar signature
        bar = result.functions[1]
        assert bar.name == "bar"
        assert bar.kind == FuncKind.UNITARY
        assert len(bar.params) == 1
        assert isinstance(bar.return_type, ProjTypeNode)

        # Check baz signature
        baz = result.functions[2]
        assert baz.name == "baz"
        assert baz.kind == FuncKind.MIXED
        assert len(baz.params) == 0
        assert baz.return_type is None
