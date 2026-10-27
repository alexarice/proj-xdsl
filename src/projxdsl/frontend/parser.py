"""Parser for proj-xdsl surface syntax."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NoReturn

from xdsl.builder import Builder
from xdsl.dialects.arith import AndIOp, ConstantOp, OrIOp, XOrIOp
from xdsl.dialects.builtin import IntegerAttr, ModuleOp, NoneAttr, i1
from xdsl.ir import BlockArgument, Region, SSAValue, TypeAttribute
from xdsl.parser.generic_parser import GenericParser, ParserState
from xdsl.utils.exceptions import ParseError
from xdsl.utils.lexer import Input

from projxdsl.dialects.angle import AddOp, AngleType, PiOp, ScalarMultOp, ZeroOp
from projxdsl.dialects.proj import (
    AllocOp,
    AndOp,
    Basis,
    BasisAttr,
    EqOp,
    FromBoolOp,
    IfOp,
    MeasureOp,
    MixedOp,
    NotOp,
    OrOp,
    PhaseOp,
    ProjectionType,
    PureOp,
    QubitType,
    ReturnOp,
    State,
    StateAttr,
    UnitaryOp,
    XorOp,
    YieldOp,
)
from projxdsl.frontend.func_kind import FuncKind
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
    _PREFIX_SCALAR_MULT_BP = 11  # Prefix operator (single binding power) - tightest
    _PREFIX_MEASURE_BP = 7
    _PREFIX_NOT_BP = 7
    _POSTFIX_EQ_BP = 9  # Postfix operator (single binding power)
    _INFIX_ADD_BP = (8, 9)  # (left_bp, right_bp) - tighter than not
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

    def parse_optional_float(self) -> float | None:
        """
        Parse a float literal, if present.
        """
        if self._current_token.kind == ProjTokenKind.FLOAT:
            token = self._consume_token()
            return token.kind.get_float_value(token.span)
        return None

    def parse_float(self) -> float:
        """
        Parse a float literal.
        """
        return self.expect(
            lambda: self.parse_optional_float(),
            "Expected float literal",
        )

    def parse_statement(
        self,
        variables: dict[str, SSAValue],
        builder: Builder,
        func_kind: FuncKind = FuncKind.MIXED,
    ) -> SSAValue | None:
        """
        Parse a statement and insert it into the block via builder.

        May mutate `variables` by adding new variable bindings (e.g., let statements).

        statement ::= "ph" "(" angle-expr ")"
                    | "if" expr block
                    | "let" ident (":" type)? "=" expr
                    | expr
        block ::= "{" statement* "}"
        angle-expr ::= expression that evaluates to an angle type

        Returns:
            SSAValue if the statement is an expression, None otherwise.
        """
        if self._parse_optional_token(ProjTokenKind.PHASE) is not None:
            if not func_kind.allows_operation("phase"):
                self.raise_error(
                    f"Phase operation not allowed in {func_kind.value} functions"
                )
            with self.in_parens():
                # Parse the angle expression
                angle = self.parse_expression(variables, builder, func_kind=func_kind)

                # Check that the expression has angle type
                if angle.type != AngleType():
                    self.raise_typing_error(
                        f"Expected angle expression for phase statement,"
                        f" got {angle.type}"
                    )

            builder.insert(PhaseOp(angle))
            return None
        elif self._parse_optional_token(ProjTokenKind.IF) is not None:
            if not func_kind.allows_operation("if"):
                self.raise_error(
                    f"If operation not allowed in {func_kind.value} functions"
                )
            self._parse_if_statement(variables, builder, func_kind=func_kind)
            return None
        elif self._parse_optional_token(ProjTokenKind.LET) is not None:
            self._parse_let_statement(variables, builder, func_kind=func_kind)
            return None
        else:
            # Parse as an expression statement (result is returned)
            return self.parse_expression(
                variables,
                builder,
                func_kind=func_kind,
                initial_error=(
                    f"Expected 'ph', 'if', 'let', or an expression for statement, "
                    f"got '{self._current_token.text}'"
                ),
            )

    def _parse_if_statement(
        self,
        variables: dict[str, SSAValue],
        builder: Builder,
        func_kind: FuncKind,
    ) -> IfOp:
        """
        Parse an if statement.

        if-stmt ::= "if" expr block
        block ::= "{" statement* "}"
        """
        # Parse the condition expression (inserted in parent block)
        condition = self.parse_expression(variables, builder, func_kind=func_kind)

        # Check that the condition is a projection
        if condition.type != ProjectionType():
            self.raise_typing_error(
                f"Expected projection type for 'if' condition, got {condition.type}"
            )

        # Parse the true block (with scoped variables)
        def parse_statements(inner_builder: Builder):
            # Create a copy of variables for scoping
            block_variables = dict(variables)
            self.parse_list(
                delimiter=self.Delimiter.BRACES,
                parse=lambda: self.parse_statement(
                    block_variables, inner_builder, func_kind
                ),
                separator=";",
                context_msg=" in statement block",
            )
            inner_builder.insert(YieldOp())
            return None

        true_region = Builder.region(parse_statements)

        # Parse the optional else block
        false_region = Region()
        if self._current_token.kind == ProjTokenKind.IF:
            # Check if it's actually 'else' by peeking ahead
            # For now, we don't support else, so this is a placeholder
            pass

        return builder.insert(IfOp(condition, true_region, false_region))

    def _parse_let_statement(
        self,
        variables: dict[str, SSAValue],
        builder: Builder,
        func_kind: FuncKind,
    ) -> None:
        """
        Parse a let statement and add the binding to variables.

        let-stmt ::= "let" ident (":" type)? "=" expr
        """
        # Parse the identifier
        ident_token = self._parse_token(
            ProjTokenKind.IDENTIFIER, "Expected identifier after 'let'"
        )
        var_name = ident_token.text

        # Parse optional type annotation
        if self.parse_optional_punctuation(":") is not None:
            # Parse the type (we'll validate it matches the expression type later)
            expected_type = self.parse_type()
        else:
            expected_type = None

        # Parse the equals sign
        self.parse_punctuation("=", "Expected '=' in let statement")

        # Parse the expression
        expr_value = self.parse_expression(variables, builder, func_kind=func_kind)

        # Validate type if annotation was provided
        if expected_type is not None and expr_value.type != expected_type:
            self.raise_typing_error(
                f"Type mismatch: expected {expected_type}, got {expr_value.type}"
            )

        # Add the binding to variables (mutates the dict)
        if var_name in variables:
            self.raise_error(f"Variable '{var_name}' is already defined")
        variables[var_name] = expr_value

    def parse_expression(
        self,
        variables: Mapping[str, SSAValue],
        builder: Builder,
        min_bp: int = 0,
        initial_error: str | None = None,
        func_kind: FuncKind = FuncKind.MIXED,
    ) -> SSAValue:
        """
        Parse a projection expression using Pratt parsing.

        Args:
            variables: Mapping from variable names to SSA values
            builder: Builder for inserting operations
            min_bp: Minimum binding power for Pratt parsing (default 0)
            initial_error: Error message if first token cannot start
                an expression (should mention the unexpected token)
            func_kind: Function kind for operation validation

        Returns:
            SSA value of the parsed expression

        Grammar:
            expr ::= primary postfix* infix*
            primary ::= identifier | "true" | "false" | "!" expr | "measure" expr
                    | "alloc" state | "(" expr ")"
            postfix ::= "==" state
            infix ::= "&&" expr | "||" expr | "^" expr
        """
        lhs = self._parse_prefix_and_primary(
            variables, builder, initial_error, func_kind
        )

        while True:
            if self._current_token.kind == ProjTokenKind.EQ:
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

                lhs = builder.insert(EqOp(lhs, state)).result

            elif self._current_token.kind == ProjTokenKind.AND:
                left_bp, right_bp = self._INFIX_AND_BP
                if min_bp > left_bp:
                    break
                self._consume_token()
                rhs = self.parse_expression(
                    variables, builder, right_bp, func_kind=func_kind
                )
                lhs = self._build_binary_predicate_op(
                    lhs, rhs, AndIOp, AndOp, "&&", builder
                )

            elif self._current_token.kind == ProjTokenKind.OR:
                left_bp, right_bp = self._INFIX_OR_BP
                if min_bp > left_bp:
                    break
                self._consume_token()
                rhs = self.parse_expression(
                    variables, builder, right_bp, func_kind=func_kind
                )
                lhs = self._build_binary_predicate_op(
                    lhs, rhs, OrIOp, OrOp, "||", builder
                )

            elif self._current_token.kind == ProjTokenKind.PLUS:
                left_bp, right_bp = self._INFIX_ADD_BP
                if min_bp > left_bp:
                    break
                self._consume_token()
                rhs = self.parse_expression(
                    variables, builder, right_bp, func_kind=func_kind
                )

                # Check that both operands are angles
                if lhs.type != AngleType():
                    self.raise_typing_error(
                        f"Expected angle for '+' left operand, got {lhs.type}"
                    )
                if rhs.type != AngleType():
                    self.raise_typing_error(
                        f"Expected angle for '+' right operand, got {rhs.type}"
                    )

                lhs = builder.insert(AddOp(lhs, rhs)).result

            elif self._current_token.kind == ProjTokenKind.XOR:
                left_bp, right_bp = self._INFIX_XOR_BP
                if min_bp > left_bp:
                    break
                self._consume_token()
                rhs = self.parse_expression(
                    variables, builder, right_bp, func_kind=func_kind
                )
                lhs = self._build_binary_predicate_op(
                    lhs, rhs, XOrIOp, XorOp, "^", builder
                )

            else:
                break

        return lhs

    def _build_binary_predicate_op(
        self,
        lhs: SSAValue,
        rhs: SSAValue,
        classical_op: type[AndIOp | OrIOp | XOrIOp],
        projection_op: type[AndOp | OrOp | XorOp],
        op_name: str,
        builder: Builder,
    ) -> SSAValue:
        """
        Build a binary operation with proper type checking.

        Args:
            lhs: Left-hand side operand
            rhs: Right-hand side operand
            classical_op: Classical operation class (arith.andi, arith.ori, arith.xori)
            projection_op: Projection operation class (proj.and, proj.or, proj.xor)
            op_name: Name of the operator for error messages
            builder: Builder for inserting operations

        Returns:
            SSA value of the result

        Raises:
            TypeCheckError: If operand types are incompatible
        """
        lhs_is_bool = lhs.type == i1
        rhs_is_bool = rhs.type == i1
        lhs_is_proj = lhs.type == ProjectionType()
        rhs_is_proj = rhs.type == ProjectionType()

        if lhs_is_bool and rhs_is_bool:
            # Both booleans: use classical operation
            return builder.insert(classical_op(lhs, rhs)).result
        elif lhs_is_proj and rhs_is_proj:
            # Both projections: use projection operation
            return builder.insert(projection_op(lhs, rhs)).result
        elif (lhs_is_bool and rhs_is_proj) or (lhs_is_proj and rhs_is_bool):
            # Mixed: convert boolean to projection, then use projection operation
            if lhs_is_bool:
                lhs = builder.insert(FromBoolOp(lhs)).result
            if rhs_is_bool:
                rhs = builder.insert(FromBoolOp(rhs)).result
            return builder.insert(projection_op(lhs, rhs)).result
        else:
            # Invalid types
            self.raise_typing_error(
                f"Invalid operand types for '{op_name}': expected boolean or "
                f"projection, got {lhs.type} and {rhs.type}"
            )

    def _parse_prefix_and_primary(
        self,
        variables: Mapping[str, SSAValue],
        builder: Builder,
        initial_error: str | None = None,
        func_kind: FuncKind = FuncKind.MIXED,
    ) -> SSAValue:
        """
        Parse prefix operators and primary expressions.

        Prefix operators: !, measure
        Primary expressions: identifier, true, false, alloc, parenthesized expression

        Args:
            variables: Mapping from variable names to SSA values
            builder: Builder for inserting operations
            initial_error: Error message if first token cannot start
                an expression (should mention the unexpected token)
            func_kind: Function kind for operation validation
        """
        if (token := self._parse_optional_token(ProjTokenKind.IDENTIFIER)) is not None:
            var_name = token.text

            if var_name not in variables:
                self.raise_error(f"Undefined variable: {var_name}")

            return variables[var_name]

        if self._parse_optional_token(ProjTokenKind.TRUE) is not None:
            return builder.insert(ConstantOp(IntegerAttr(1, 1))).result

        if self._parse_optional_token(ProjTokenKind.FALSE) is not None:
            return builder.insert(ConstantOp(IntegerAttr(0, 1))).result

        if self._parse_optional_token(ProjTokenKind.PI) is not None:
            return builder.insert(PiOp()).result

        if (integer := self._parse_optional_token(ProjTokenKind.INTEGER)) is not None:
            # Only 0 is valid as an angle constant
            value = integer.kind.get_integer_value(integer.span)
            if value != 0:
                self.raise_error(f"Only 0 is a valid angle constant, got {value}")
            return builder.insert(ZeroOp()).result

        if (scalar := self.parse_optional_float()) is not None:
            # Scalar multiplication: `2.0 * a` where `2.0 *` is a prefix operator
            self._parse_token(
                ProjTokenKind.STAR,
                "Expected '*' after float literal for scalar multiplication",
            )

            # Parse the angle expression with tight binding
            angle = self.parse_expression(
                variables, builder, self._PREFIX_SCALAR_MULT_BP, func_kind=func_kind
            )

            # Check that the operand is an angle
            if angle.type != AngleType():
                self.raise_typing_error(
                    f"Expected angle for '*' operand, got {angle.type}"
                )

            return builder.insert(ScalarMultOp(scalar, angle)).result

        if self._parse_optional_token(ProjTokenKind.BANG) is not None:
            operand = self.parse_expression(
                variables, builder, self._PREFIX_NOT_BP, func_kind=func_kind
            )

            if operand.type == ProjectionType():
                return builder.insert(NotOp(operand)).result
            elif operand.type == i1:
                const_one = builder.insert(ConstantOp(IntegerAttr(1, 1))).result
                return builder.insert(XOrIOp(operand, const_one)).result
            else:
                self.raise_typing_error(
                    f"Expected projection or boolean for '!' operator,"
                    f" got {operand.type}"
                )

        if self._parse_optional_token(ProjTokenKind.ALLOC) is not None:
            if not func_kind.allows_operation("alloc"):
                self.raise_error(
                    f"Alloc operation not allowed in {func_kind.value} functions"
                )
            state = self.parse_state()
            alloc_op = builder.insert(AllocOp(state))
            return alloc_op.result

        if self._parse_optional_token(ProjTokenKind.MEASURE) is not None:
            if not func_kind.allows_operation("measure"):
                self.raise_error(
                    f"Measure operation not allowed in {func_kind.value} functions"
                )
            operand = self.parse_expression(
                variables, builder, self._PREFIX_MEASURE_BP, func_kind=func_kind
            )
            if operand.type == ProjectionType():
                return builder.insert(MeasureOp(operand)).result
            elif operand.type == i1:
                proj = builder.insert(FromBoolOp(operand)).result
                return builder.insert(MeasureOp(proj)).result
            else:
                self.raise_typing_error(
                    f"Expected projection or boolean for 'measure' operator,"
                    f" got {operand.type}"
                )

        if self._parse_optional_token(ProjTokenKind.LPAREN) is not None:
            expr = self.parse_expression(variables, builder, 0, func_kind=func_kind)
            self.parse_punctuation(")", " to close parenthesized expression")
            return expr

        self.raise_error(
            initial_error
            or f"Unexpected token in expression: {self._current_token.text}"
        )

    def parse_func(self) -> PureOp | UnitaryOp | MixedOp:
        """
        Parse a function definition.

        func-def ::= <kind> "fn" ident "(" params ")" ("->" type)? "{" body "}"
        kind ::= "pure" | "unitary" | "mixed"
        params ::= param ("," param)*
        param ::= ident ":" type
        body ::= statement* expr?

        Returns:
            The parsed function operation (PureOp, UnitaryOp, or MixedOp)
        """
        # Parse function kind (required)
        if self._parse_optional_token(ProjTokenKind.PURE) is not None:
            func_kind = FuncKind.PURE
            func_op_class = PureOp
        elif self._parse_optional_token(ProjTokenKind.UNITARY) is not None:
            func_kind = FuncKind.UNITARY
            func_op_class = UnitaryOp
        elif self._parse_optional_token(ProjTokenKind.MIXED) is not None:
            func_kind = FuncKind.MIXED
            func_op_class = MixedOp
        else:
            self.raise_error("Expected function kind keyword (pure, unitary, or mixed)")

        # Parse "fn" keyword
        self._parse_token(ProjTokenKind.FN, "Expected 'fn' keyword after function kind")

        # Parse function name
        name_token = self._parse_token(
            ProjTokenKind.IDENTIFIER, "Expected function name"
        )
        func_name = name_token.text

        # Parse parameter list
        def parse_param() -> tuple[str, TypeAttribute]:
            # Parse parameter name
            param_name_token = self._parse_token(
                ProjTokenKind.IDENTIFIER, "Expected parameter name"
            )
            param_name = param_name_token.text

            # Parse colon
            self.parse_punctuation(":", " after parameter name")

            # Parse type
            param_type = self.parse_type()
            return (param_name, param_type)

        param_list = self.parse_list(
            delimiter=self.Delimiter.PAREN,
            parse=parse_param,
            separator=",",
            context_msg=" in parameter list",
        )
        param_names = [name for name, _ in param_list]
        input_types = [type for _, type in param_list]

        # Parse optional return type
        return_types: list[TypeAttribute] = []
        if self.parse_optional_punctuation("->") is not None:
            return_type = self.parse_type()
            return_types.append(return_type)

        # Parse function body
        @Builder.region(input_types)
        def parse_body(inner_builder: Builder, args: tuple[BlockArgument, ...]):
            # Create variables dict with parameters
            variables: dict[str, SSAValue] = {}
            for param_name, block_arg in zip(param_names, args, strict=True):
                variables[param_name] = block_arg

            # Parse statements using parse_list
            statements = self.parse_list(
                delimiter=self.Delimiter.BRACES,
                parse=lambda: self.parse_statement(variables, inner_builder, func_kind),
                separator=";",
                context_msg=" in function body",
            )

            # Handle return value
            if return_types:
                # Function has a return type, expect final expression
                if not statements or statements[-1] is None:
                    self.raise_error(
                        f"Expected expression of type {return_types[0]}"
                        " at end of function body"
                    )
                final_expr = statements[-1]
                if final_expr.type != return_types[0]:
                    self.raise_typing_error(
                        f"Expected return type {return_types[0]}, got {final_expr.type}"
                    )
                inner_builder.insert(ReturnOp(final_expr))
            else:
                # Void function, insert ReturnOp with no arguments
                inner_builder.insert(ReturnOp())

        body_region = parse_body

        # Create the function operation
        return func_op_class(
            sym_name=func_name,
            function_type=(input_types, return_types),
            body=body_region,
        )

    def parse_module(self) -> ModuleOp:
        """
        Parse a module containing function definitions.

        module ::= func-def*

        Returns:
            The parsed module operation containing all function definitions
        """
        # Parse all function definitions
        func_ops: list[PureOp | UnitaryOp | MixedOp] = []
        while self._current_token.kind != ProjTokenKind.EOF:
            func_op = self.parse_func()
            func_ops.append(func_op)

        # Create the module operation with all functions
        return ModuleOp(func_ops)
