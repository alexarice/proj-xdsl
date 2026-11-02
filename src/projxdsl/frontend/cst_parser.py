"""
CST Parser for proj-xdsl surface syntax.

This parser builds a Concrete Syntax Tree (CST) without type checking.
Type checking is performed in a separate pass over the CST.
"""

from __future__ import annotations

from dataclasses import dataclass

from xdsl.parser.generic_parser import GenericParser, ParserState
from xdsl.utils.lexer import Input, Span

from projxdsl.dialects.proj import State
from projxdsl.frontend.cst import (
    AllocExpr,
    AngleConstantExpr,
    AngleConstantKind,
    AngleOpKind,
    AngleType,
    BinaryAngleExpr,
    BinaryOpKind,
    BinaryProjExpr,
    BlockNode,
    BoolLiteralExpr,
    BoolType,
    CallExpr,
    EqExpr,
    ExprNode,
    ExprStmt,
    FuncDef,
    IdentExpr,
    LetStmt,
    MeasureExpr,
    Module,
    NegAngleExpr,
    NotExpr,
    Param,
    ParenExpr,
    PhaseStmt,
    ProjType,
    QifStmt,
    QubitType,
    ScalarExpr,
    ScalarMultExpr,
    StateExpr,
    StmtNode,
    TypeNode,
)
from projxdsl.frontend.lexer import ProjLexer, ProjToken, ProjTokenKind
from projxdsl.func_kind import FuncKind


@dataclass
class ProjCSTParser(GenericParser[ProjTokenKind]):
    """
    Recursive descent parser for proj-xdsl surface syntax.

    Builds a CST without type checking. Type checking is done separately.
    """

    def __init__(self, code: str, filename: str = "<input>"):
        self._input = Input(code, filename)
        lexer = ProjLexer(self._input)
        lexer.emit_newlines = True  # CST parser enforces newline separation
        super().__init__(ParserState(lexer))

    # Binding powers for Pratt parsing
    # Higher number = tighter binding
    _PREFIX_ALLOC_BP = 12  # Prefix operator - tightest
    _PREFIX_MINUS_BP = 11  # Prefix negation operator
    _PREFIX_MEASURE_BP = 7
    _PREFIX_NOT_BP = 7
    _POSTFIX_EQ_BP = 9  # Postfix operator (single binding power)
    _INFIX_STAR_BP = (10, 11)  # (left_bp, right_bp) - scalar multiplication
    _INFIX_ADD_BP = (8, 9)  # (left_bp, right_bp) - tighter than not
    _INFIX_SUB_BP = (8, 9)  # (left_bp, right_bp) - same as add
    _INFIX_XOR_BP = (5, 6)  # (left_bp, right_bp)
    _INFIX_AND_BP = (3, 4)
    _INFIX_OR_BP = (1, 2)

    def parse_type(self) -> TypeNode:
        """
        Parse a type from surface syntax.

        type ::= qubit-type | proj-type | bool-type | angle-type
        qubit-type ::= "qubit"
        proj-type ::= "proj"
        bool-type ::= "bool"
        angle-type ::= "angle"
        """
        if self._parse_optional_token(ProjTokenKind.QUBIT) is not None:
            return QubitType(span=self._current_token.span)
        elif self._parse_optional_token(ProjTokenKind.PROJECTION) is not None:
            return ProjType(span=self._current_token.span)
        elif self._parse_optional_token(ProjTokenKind.BOOL) is not None:
            return BoolType(span=self._current_token.span)
        elif self._parse_optional_token(ProjTokenKind.ANGLE) is not None:
            return AngleType(span=self._current_token.span)
        else:
            self.raise_error(
                "Expected type (qubit, projection, bool, or angle),"
                f" got {self._current_token.kind.name}",
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

    def _skip_newlines(self) -> bool:
        """Skip consecutive NEWLINE tokens. Returns True if any were skipped."""
        skipped = False
        while self._parse_optional_token(ProjTokenKind.NEWLINE):
            skipped = True
        return skipped

    def parse_state(self) -> StateExpr:
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

        return StateExpr(span=token.span, state=state)

    def _parse_state_from_token(self, token: ProjToken) -> StateExpr:
        """Parse a state literal from an already-consumed STATE token."""
        state_text = token.text
        if len(state_text) < 2 or state_text[0] != "|":
            self.raise_error(f"Invalid state literal: {state_text}")

        state_char = state_text[1]

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

        return StateExpr(span=token.span, state=state)

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

    def parse_statement(self) -> StmtNode:
        """
        Parse a statement.

        statement ::= "ph" "(" angle-expr ")"
                    | "qif" expr block
                    | "let" ident (":" type)? "=" expr
                    | expr

        Statements are separated by newlines (enforced by parse_block).
        Semicolons are not part of the surface syntax.
        """
        start_pos = self.pos

        if self._parse_optional_token(ProjTokenKind.PHASE) is not None:
            with self.in_parens():
                angle = self.parse_expression()
            # _current_token is after ')', so use its start as end
            return PhaseStmt(
                span=Span(start_pos, self._current_token.span.start, self._input),
                angle=angle,
            )

        elif self._parse_optional_token(ProjTokenKind.QIF) is not None:
            return self._parse_qif_statement(start_pos)

        elif self._parse_optional_token(ProjTokenKind.LET) is not None:
            return self._parse_let_statement(start_pos)

        else:
            # Parse as an expression
            expr = self.parse_expression(
                initial_error=(
                    f"Expected 'ph', 'qif', 'let', or an expression for statement, "
                    f"got '{self._current_token.text}'"
                ),
            )
            return ExprStmt(span=expr.span, expr=expr)

    def _parse_qif_statement(self, start_pos: int) -> QifStmt:
        """
        Parse a qif (quantum if) statement.

        qif-stmt ::= "qif" expr block ("else" block)?
        """
        condition = self.parse_expression()
        true_body = self._parse_block()
        end_pos = true_body.span.end

        false_body = None
        if self._parse_optional_token(ProjTokenKind.ELSE) is not None:
            false_body = self._parse_block()
            end_pos = false_body.span.end

        return QifStmt(
            span=Span(start_pos, end_pos, self._input),
            condition=condition,
            true_body=true_body,
            false_body=false_body,
        )

    def _parse_let_statement(self, start_pos: int) -> LetStmt:
        """
        Parse a let statement.

        let-stmt ::= "let" ident (":" type)? "=" expr
        """
        ident_token = self._parse_token(
            ProjTokenKind.IDENTIFIER, "Expected identifier after 'let'"
        )
        var_name = ident_token.text

        # Parse optional type annotation
        type_ann = None
        if self.parse_optional_punctuation(":") is not None:
            type_ann = self.parse_type()

        # Parse the equals sign
        self.parse_punctuation("=", "Expected '=' in let statement")

        # Parse the expression
        value = self.parse_expression()

        # _current_token is after the expression, so use its start as end
        return LetStmt(
            span=Span(start_pos, self._current_token.span.start, self._input),
            name=var_name,
            type_ann=type_ann,
            value=value,
        )

    def _parse_block(self) -> BlockNode:
        """
        Parse a block of statements.

        block ::= "{" statement* "}"

        Statements must be separated by newlines.
        """
        start_pos = self.pos
        self.parse_punctuation("{", " at start of block")

        statements: list[StmtNode] = []

        # Skip optional newlines after opening brace
        self._skip_newlines()

        seen_newline = True

        while (brace_token := self.parse_optional_punctuation("}")) is None:
            if not seen_newline:
                self.raise_error("Expected newline or '}' in block")
            statements.append(self.parse_statement())
            seen_newline = self._skip_newlines()

        return BlockNode(
            span=Span(start_pos, brace_token.span.end, self._input),
            statements=tuple(statements),
        )

    def parse_expression(
        self,
        min_bp: int = 0,
        initial_error: str | None = None,
    ) -> ExprNode:
        """
        Parse an expression using Pratt parsing.

        Args:
            min_bp: Minimum binding power for Pratt parsing (default 0)
            initial_error: Error message if first token cannot start an expression

        Returns:
            CST expression node
        """
        lhs = self._parse_prefix_and_primary(initial_error)

        while True:
            if self._current_token.kind == ProjTokenKind.EQ:
                if min_bp > self._POSTFIX_EQ_BP:
                    break
                self._consume_token()
                state = self.parse_state()
                lhs = EqExpr(
                    span=Span(lhs.span.start, state.span.end, self._input),
                    qubit=lhs,
                    state=state,
                )

            elif self._current_token.kind == ProjTokenKind.AND:
                left_bp, right_bp = self._INFIX_AND_BP
                if min_bp > left_bp:
                    break
                self._consume_token()
                rhs = self.parse_expression(right_bp)
                lhs = BinaryProjExpr(
                    span=Span(lhs.span.start, rhs.span.end, self._input),
                    op=BinaryOpKind.AND,
                    left=lhs,
                    right=rhs,
                )

            elif self._current_token.kind == ProjTokenKind.OR:
                left_bp, right_bp = self._INFIX_OR_BP
                if min_bp > left_bp:
                    break
                self._consume_token()
                rhs = self.parse_expression(right_bp)
                lhs = BinaryProjExpr(
                    span=Span(lhs.span.start, rhs.span.end, self._input),
                    op=BinaryOpKind.OR,
                    left=lhs,
                    right=rhs,
                )

            elif self._current_token.kind == ProjTokenKind.STAR:
                left_bp, right_bp = self._INFIX_STAR_BP
                if min_bp > left_bp:
                    break
                self._consume_token()
                rhs = self.parse_expression(right_bp)
                lhs = ScalarMultExpr(
                    span=Span(lhs.span.start, rhs.span.end, self._input),
                    scalar=lhs,
                    angle=rhs,
                )

            elif self._current_token.kind == ProjTokenKind.PLUS:
                left_bp, right_bp = self._INFIX_ADD_BP
                if min_bp > left_bp:
                    break
                self._consume_token()
                rhs = self.parse_expression(right_bp)
                lhs = BinaryAngleExpr(
                    span=Span(lhs.span.start, rhs.span.end, self._input),
                    op=AngleOpKind.ADD,
                    left=lhs,
                    right=rhs,
                )

            elif self._current_token.kind == ProjTokenKind.MINUS:
                left_bp, right_bp = self._INFIX_SUB_BP
                if min_bp > left_bp:
                    break
                self._consume_token()
                rhs = self.parse_expression(right_bp)
                lhs = BinaryAngleExpr(
                    span=Span(lhs.span.start, rhs.span.end, self._input),
                    op=AngleOpKind.SUB,
                    left=lhs,
                    right=rhs,
                )

            elif self._current_token.kind == ProjTokenKind.XOR:
                left_bp, right_bp = self._INFIX_XOR_BP
                if min_bp > left_bp:
                    break
                self._consume_token()
                rhs = self.parse_expression(right_bp)
                lhs = BinaryProjExpr(
                    span=Span(lhs.span.start, rhs.span.end, self._input),
                    op=BinaryOpKind.XOR,
                    left=lhs,
                    right=rhs,
                )

            else:
                break

        return lhs

    def _parse_prefix_and_primary(
        self,
        initial_error: str | None = None,
    ) -> ExprNode:
        """
        Parse prefix operators and primary expressions.

        Args:
            initial_error: Error message if first token cannot start an expression

        Returns:
            CST expression node
        """
        start_pos = self.pos

        if (token := self._parse_optional_token(ProjTokenKind.IDENTIFIER)) is not None:
            var_name = token.text
            # Check if this is a function call by peeking at the next token
            if self._current_token.kind == ProjTokenKind.LPAREN:
                return self._parse_function_call(var_name, start_pos)
            else:
                return IdentExpr(span=token.span, name=var_name)

        if (token := self._parse_optional_token(ProjTokenKind.TRUE)) is not None:
            return BoolLiteralExpr(span=token.span, value=True)

        if (token := self._parse_optional_token(ProjTokenKind.FALSE)) is not None:
            return BoolLiteralExpr(span=token.span, value=False)

        if (token := self._parse_optional_token(ProjTokenKind.PI)) is not None:
            return AngleConstantExpr(span=token.span, kind=AngleConstantKind.PI)

        if (integer := self._parse_optional_token(ProjTokenKind.INTEGER)) is not None:
            # Only 0 is valid as an angle constant
            value = integer.kind.get_integer_value(integer.span)
            if value != 0:
                self.raise_error(f"Only 0 is a valid angle constant, got {value}")
            return AngleConstantExpr(span=integer.span, kind=AngleConstantKind.ZERO)

        if (float_token := self._parse_optional_token(ProjTokenKind.FLOAT)) is not None:
            # Scalar literal (used in scalar multiplication: `2.0 * angle`)
            return ScalarExpr(
                span=float_token.span,
                value=float_token.kind.get_float_value(float_token.span),
            )

        if (token := self._parse_optional_token(ProjTokenKind.STATE)) is not None:
            # State literal: |0>, |1>, etc.
            return self._parse_state_from_token(token)

        if self._parse_optional_token(ProjTokenKind.BANG) is not None:
            operand = self.parse_expression(self._PREFIX_NOT_BP)
            return NotExpr(
                span=Span(start_pos, operand.span.end, self._input),
                operand=operand,
            )

        # Prefix minus: `-angle`
        if self._parse_optional_token(ProjTokenKind.MINUS) is not None:
            operand = self.parse_expression(self._PREFIX_MINUS_BP)
            return NegAngleExpr(
                span=Span(start_pos, operand.span.end, self._input),
                operand=operand,
            )

        if self._parse_optional_token(ProjTokenKind.ALLOC) is not None:
            state = self.parse_expression(self._PREFIX_ALLOC_BP)
            return AllocExpr(
                span=Span(start_pos, state.span.end, self._input),
                state=state,
            )

        if self._parse_optional_token(ProjTokenKind.MEASURE) is not None:
            operand = self.parse_expression(self._PREFIX_MEASURE_BP)
            return MeasureExpr(
                span=Span(start_pos, operand.span.end, self._input),
                operand=operand,
            )

        if self._parse_optional_token(ProjTokenKind.LPAREN) is not None:
            paren_start = start_pos
            # Lexer automatically suppresses NEWLINEs inside parentheses
            expr = self.parse_expression(0)
            rparen = self.parse_punctuation(")", " to close parenthesized expression")
            return ParenExpr(
                span=Span(paren_start, rparen.span.end, self._input),
                inner=expr,
            )

        self.raise_error(
            initial_error
            or f"Unexpected token in expression: {self._current_token.text}"
        )

    def _parse_function_call(
        self,
        func_name: str,
        start_pos: int,
    ) -> CallExpr:
        """
        Parse a function call expression.

        Args:
            func_name: Name of the function being called
            start_pos: Start position of the function name

        Returns:
            CST call expression node
        """
        # Parse opening parenthesis and argument list
        args_list: list[ExprNode] = []
        self._consume_token(ProjTokenKind.LPAREN)

        if self._current_token.kind != ProjTokenKind.RPAREN:
            args_list.append(self.parse_expression())
            while self._parse_optional_token(ProjTokenKind.COMMA) is not None:
                args_list.append(self.parse_expression())

        end_pos = self.parse_punctuation(
            ")", " at end of function call arguments"
        ).span.end

        return CallExpr(
            span=Span(start_pos, end_pos, self._input),
            name=func_name,
            args=tuple(args_list),
        )

    def parse_func(self) -> FuncDef:
        """
        Parse a function definition.

        func-def ::= <kind> "fn" ident "(" params ")" ("->" type)? "{" body "}"
        kind ::= "pure" | "unitary" | "mixed"
        params ::= param ("," param)*
        param ::= ident ":" type
        body ::= statement* expr?

        Returns:
            The parsed function definition CST node
        """
        start_pos = self.pos

        # Parse function kind (required)
        if self._parse_optional_token(ProjTokenKind.PURE) is not None:
            func_kind = FuncKind.PURE
        elif self._parse_optional_token(ProjTokenKind.UNITARY) is not None:
            func_kind = FuncKind.UNITARY
        elif self._parse_optional_token(ProjTokenKind.MIXED) is not None:
            func_kind = FuncKind.MIXED
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
        def parse_param() -> Param:
            # Parse parameter name
            param_start = self.pos
            param_token = self._parse_token(
                ProjTokenKind.IDENTIFIER, "Expected parameter name"
            )
            param_name = param_token.text

            # Parse colon
            self.parse_punctuation(":", " after parameter name")

            # Parse type
            param_type = self.parse_type()
            return Param(
                span=Span(param_start, self._current_token.span.start, self._input),
                name=param_name,
                type_ann=param_type,
            )

        params: list[Param] = []
        self._consume_token()  # consume LPAREN
        if self._current_token.kind != ProjTokenKind.RPAREN:
            params.append(parse_param())
            while self._parse_optional_token(ProjTokenKind.COMMA) is not None:
                params.append(parse_param())
        self.parse_punctuation(")", " at end of parameter list")

        # Parse optional return type
        return_type: TypeNode | None = None
        if self.parse_optional_punctuation("->") is not None:
            return_type = self.parse_type()

        # Parse function body
        body = self._parse_block()

        return FuncDef(
            span=Span(start_pos, body.span.end, self._input),
            kind=func_kind,
            name=func_name,
            params=tuple(params),
            return_type=return_type,
            body=body,
        )

    def parse_module(self) -> Module:
        """
        Parse a module containing function definitions.

        module ::= func-def*

        Returns:
            The parsed module CST node containing all function definitions
        """
        func_defs: list[FuncDef] = []
        while self._current_token.kind != ProjTokenKind.EOF:
            func_def = self.parse_func()
            func_defs.append(func_def)

        return Module(
            span=self._current_token.span,
            functions=tuple(func_defs),
        )
