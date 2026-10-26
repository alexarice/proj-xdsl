"""Parser for proj-xdsl surface syntax."""

from __future__ import annotations

from typing import NoReturn

from xdsl.dialects.arith import ConstantOp, XOrIOp
from xdsl.dialects.builtin import IntegerAttr, NoneAttr, i1
from xdsl.ir import SSAValue, TypeAttribute
from xdsl.parser.generic_parser import GenericParser, ParserState
from xdsl.utils.exceptions import ParseError
from xdsl.utils.lexer import Input

from projxdsl.dialects.proj import (
    AndOp,
    AngleType,
    Basis,
    BasisAttr,
    EqOp,
    FromBoolOp,
    NotOp,
    OrOp,
    ProjectionType,
    QubitType,
    State,
    StateAttr,
    XorOp,
)
from projxdsl.frontend.lexer import ProjLexer, ProjToken, ProjTokenKind


class TypeCheckError(ParseError):
    """Exception raised when type checking fails during parsing."""

    pass


class ProjParserState(ParserState[ProjTokenKind]):
    """Parser state for proj-xdsl surface syntax."""

    def __init__(self, lexer: ProjLexer):
        super().__init__(lexer)


class ProjParser(GenericParser[ProjTokenKind]):
    """
    Recursive descent parser for proj-xdsl surface syntax.
    Extends xDSL's GenericParser infrastructure.
    """

    def __init__(self, code: str, filename: str = "<input>"):
        input = Input(code, filename)
        lexer = ProjLexer(input)
        super().__init__(ProjParserState(lexer))

    # Binding powers for Pratt parsing
    # Higher number = tighter binding
    _PREFIX_NOT_BP = 7
    _POSTFIX_EQ_BP = 9  # Postfix operator (single binding power)
    _INFIX_XOR_BP = (5, 6)  # (left_bp, right_bp)
    _INFIX_AND_BP = (3, 4)
    _INFIX_OR_BP = (1, 2)

    def parse_type(self) -> TypeAttribute:
        """
        Parse a type from surface syntax.

        type ::= qubit-type | proj-type | bool-type | angle-type
        qubit-type ::= "qubit" ( "<" basis ">" )?
        basis ::= "X" | "Y" | "Z" (uppercase only)
        proj-type ::= "proj"
        bool-type ::= "bool"
        angle-type ::= "angle"
        """
        if self._parse_optional_token(ProjTokenKind.QUBIT) is not None:
            # Parse qubit type: qubit or qubit<basis>
            if self.parse_optional_punctuation("<") is not None:
                basis = self._parse_basis()
                self.parse_punctuation(">", " to close qubit basis")
                return QubitType(BasisAttr(basis))
            return QubitType(NoneAttr())
        elif self._parse_optional_token(ProjTokenKind.PROJECTION) is not None:
            return ProjectionType()
        elif self._parse_optional_token(ProjTokenKind.BOOL) is not None:
            return i1
        elif self._parse_optional_token(ProjTokenKind.ANGLE) is not None:
            return AngleType()
        else:
            self.raise_error(
                "Expected type (qubit, projection, bool, or angle),"
                f" got {self._current_token.kind.name}",
            )

    def _parse_basis(self) -> Basis:
        """
        Parse basis: X, Y, or Z (uppercase only).
        Basis is lexed as an identifier, so we validate it here.
        """
        token = self._parse_optional_token(ProjTokenKind.IDENTIFIER)
        if token is None:
            self.raise_error(
                "Expected basis identifier (X, Y, or Z),"
                f" got {self._current_token.kind.name}",
            )

        if token.text == "X":
            return Basis.X
        elif token.text == "Y":
            return Basis.Y
        elif token.text == "Z":
            return Basis.Z
        else:
            self.raise_error(
                f"Invalid basis '{token.text}', expected X, Y, or Z (uppercase only)"
            )

    def parse_punctuation(self, punctuation: str, context_msg: str = "") -> ProjToken:
        """Parse expected punctuation."""
        return self.expect(
            lambda: self.parse_optional_punctuation(punctuation),
            f"Expected '{punctuation}'{context_msg}",
        )

    def parse_optional_punctuation(self, punctuation: str) -> ProjToken | None:
        """Try to parse punctuation, return None if not present."""
        kind = ProjTokenKind.get_punctuation_kind_from_spelling(punctuation)
        return self._parse_optional_token(kind)

    def expect_eof(self) -> None:
        """Expect end of file, raise error if there are remaining tokens."""
        if self._current_token.kind != ProjTokenKind.EOF:
            self.raise_error(
                f"Unexpected token after expression: {self._current_token.text}"
            )

    def raise_typing_error(self, msg: str) -> NoReturn:
        """Raise a type checking error."""
        raise TypeCheckError(self._current_token.span, msg)

    def parse_state(self) -> StateAttr:
        """
        Parse a state literal.

        state ::= "|" state-char (">" | "⟩")
        state-char ::= "0" | "1" | "+" | "-" | "L" | "R"
        """
        token = self._parse_token(
            ProjTokenKind.STATE,
            "Expected state literal (|0>, |1>, |+>, |->, |L>, |R>)",
        )

        # Extract state character from token text (e.g., "|0>" -> "0")
        state_text = token.text
        if len(state_text) < 2 or state_text[0] != "|":
            self.raise_error(f"Invalid state literal: {state_text}")

        # Get the character between | and > or ⟩
        state_char = state_text[1]

        # Map character to State enum
        match state_char:
            case "0":
                state = State.ZERO
            case "1":
                state = State.ONE
            case "+":
                state = State.PLUS
            case "-":
                state = State.MINUS
            case "L":
                state = State.LEFT
            case "R":
                state = State.RIGHT
            case _:
                self.raise_error(
                    f"Invalid state character '{state_char}',"
                    " expected 0, 1, +, -, L, or R",
                )

        return StateAttr(state)

    def parse_expression(
        self, variables: dict[str, SSAValue], min_bp: int = 0
    ) -> SSAValue:
        """
        Parse a projection expression using Pratt parsing.

        Args:
            variables: Mapping from variable names to SSA values
            min_bp: Minimum binding power for Pratt parsing (default 0)

        Returns:
            SSA value of the parsed expression

        Grammar:
            expr ::= primary postfix* infix*
            primary ::= identifier | "true" | "false" | "!" expr | "(" expr ")"
            postfix ::= "==" state
            infix ::= "&&" expr | "||" expr | "^" expr
        """
        lhs = self._parse_prefix_and_primary(variables)

        while True:
            match self._current_token.kind:
                case ProjTokenKind.EQ:
                    if min_bp > self._POSTFIX_EQ_BP:
                        break
                    self._consume_token()
                    state = self.parse_state()

                    if not isinstance(lhs.type, QubitType):
                        self.raise_typing_error(
                            f"Expected qubit type for '==' operator, got {lhs.type}"
                        )

                    # Check basis compatibility
                    qubit_type = lhs.type
                    if not isinstance(qubit_type.borrow_type, NoneAttr):
                        # Qubit has a basis annotation, check state matches
                        basis = qubit_type.borrow_type.data
                        state_basis = state.data.get_basis()
                        if basis != state_basis:
                            self.raise_typing_error(
                                f"Qubit borrowed in {basis.name} basis cannot be "
                                f"projected in {state_basis.name} basis"
                            )

                    lhs = EqOp.build(
                        operands=[lhs],
                        properties={"state": state},
                        result_types=[ProjectionType()],
                    ).result

                case ProjTokenKind.AND:
                    left_bp, right_bp = self._INFIX_AND_BP
                    if min_bp > left_bp:
                        break
                    self._consume_token()
                    rhs = self.parse_expression(variables, right_bp)

                    lhs_proj = (
                        FromBoolOp.build(
                            operands=[lhs], result_types=[ProjectionType()]
                        ).result
                        if lhs.type == i1
                        else lhs
                    )
                    rhs_proj = (
                        FromBoolOp.build(
                            operands=[rhs], result_types=[ProjectionType()]
                        ).result
                        if rhs.type == i1
                        else rhs
                    )
                    lhs = AndOp.build(
                        operands=[lhs_proj, rhs_proj], result_types=[ProjectionType()]
                    ).result

                case ProjTokenKind.OR:
                    left_bp, right_bp = self._INFIX_OR_BP
                    if min_bp > left_bp:
                        break
                    self._consume_token()
                    rhs = self.parse_expression(variables, right_bp)

                    lhs_proj = (
                        FromBoolOp.build(
                            operands=[lhs], result_types=[ProjectionType()]
                        ).result
                        if lhs.type == i1
                        else lhs
                    )
                    rhs_proj = (
                        FromBoolOp.build(
                            operands=[rhs], result_types=[ProjectionType()]
                        ).result
                        if rhs.type == i1
                        else rhs
                    )
                    lhs = OrOp.build(
                        operands=[lhs_proj, rhs_proj], result_types=[ProjectionType()]
                    ).result

                case ProjTokenKind.XOR:
                    left_bp, right_bp = self._INFIX_XOR_BP
                    if min_bp > left_bp:
                        break
                    self._consume_token()
                    rhs = self.parse_expression(variables, right_bp)

                    lhs_proj = (
                        FromBoolOp.build(
                            operands=[lhs], result_types=[ProjectionType()]
                        ).result
                        if lhs.type == i1
                        else lhs
                    )
                    rhs_proj = (
                        FromBoolOp.build(
                            operands=[rhs], result_types=[ProjectionType()]
                        ).result
                        if rhs.type == i1
                        else rhs
                    )
                    lhs = XorOp.build(
                        operands=[lhs_proj, rhs_proj], result_types=[ProjectionType()]
                    ).result

                case _:
                    break

        return lhs

    def _parse_prefix_and_primary(self, variables: dict[str, SSAValue]) -> SSAValue:
        """
        Parse prefix operators and primary expressions.

        Prefix operators: !
        Primary expressions: identifier, true, false, parenthesized expression

        Args:
            variables: Mapping from variable names to SSA values
        """
        match self._current_token.kind:
            case ProjTokenKind.IDENTIFIER:
                var_name = self._current_token.text
                self._consume_token()

                if var_name not in variables:
                    self.raise_error(f"Undefined variable: {var_name}")

                return variables[var_name]

            case ProjTokenKind.TRUE:
                self._consume_token()
                bool_const = ConstantOp(IntegerAttr(1, 1))
                return bool_const.result

            case ProjTokenKind.FALSE:
                self._consume_token()
                bool_const = ConstantOp(IntegerAttr(0, 1))
                return bool_const.result

            case ProjTokenKind.BANG:
                self._consume_token()

                operand = self.parse_expression(variables, self._PREFIX_NOT_BP)

                if isinstance(operand.type, ProjectionType):
                    return NotOp.build(
                        operands=[operand], result_types=[ProjectionType()]
                    ).result
                elif operand.type == i1:
                    const_one = ConstantOp(IntegerAttr(1, 1))
                    return XOrIOp(operand, const_one.result).result
                else:
                    self.raise_typing_error(
                        f"Expected projection or boolean for '!' operator,"
                        f" got {operand.type}"
                    )

            case ProjTokenKind.LPAREN:
                self._consume_token()
                expr = self.parse_expression(variables, 0)
                self.parse_punctuation(")", " to close parenthesized expression")
                return expr

            case _:
                self.raise_error(
                    f"Unexpected token in expression: {self._current_token.text}"
                )
