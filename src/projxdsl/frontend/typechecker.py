"""
Typechecker for proj-xdsl.

This module performs type checking on the CST produced by the CST parser,
emitting xDSL IR operations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import NamedTuple

from xdsl.builder import Builder
from xdsl.dialects.arith import AndIOp, ConstantOp, OrIOp, XOrIOp
from xdsl.dialects.builtin import FunctionType, IntegerAttr, ModuleOp, i1
from xdsl.ir import Attribute, BlockArgument, SSAValue, TypeAttribute
from xdsl.utils.exceptions import VerifyException
from xdsl.utils.lexer import Span
from xdsl.utils.scoped_dict import ScopedDict

from projxdsl.dialects.angle import AddOp, AngleType, PiOp, ScalarMultOp, ZeroOp
from projxdsl.dialects.proj import (
    AllocOp,
    AndOp,
    Basis,
    CallOp,
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
    StateAttr,
    UnitaryOp,
    XorOp,
)
from projxdsl.frontend.cst import (
    AllocExpr,
    AngleOpKind,
    AngleTypeNode,
    BinaryAngleExpr,
    BinaryOpKind,
    BinaryProjExpr,
    BlockNode,
    BoolLiteralExpr,
    BoolTypeNode,
    CallExpr,
    EqExpr,
    ExprNode,
    ExprStmt,
    FuncDef,
    IdentExpr,
    IntLiteralExpr,
    LetStmt,
    MeasureExpr,
    Module,
    NegAngleExpr,
    NotExpr,
    PhaseStmt,
    PiExpr,
    ProjTypeNode,
    QifStmt,
    QubitTypeNode,
    ScalarExpr,
    ScalarMultExpr,
    StateExpr,
    StmtNode,
    TypeNode,
)
from projxdsl.func_kind import FuncKind


class _UnknownBorrowSentinel:
    name = "unknown basis"


UNKNOWN = _UnknownBorrowSentinel()
"""Sentinel value indicating a qubit borrow is unknown."""

BorrowValue = Basis | _UnknownBorrowSentinel


class TypeCheckError(VerifyException):
    """Exception raised when type checking fails."""

    def __init__(self, span: Span, message: str):
        self.span = span
        super().__init__(span.print_with_context(message))


@dataclass(frozen=True)
class ProjectionBorrows:
    """
    Borrow information for a single projection.

    Maps each borrowed qubit to its basis, or UNKNOWN if borrow is unknown.
    """

    _borrows: dict[SSAValue, BorrowValue] = field(default_factory=dict)

    @property
    def borrows(self) -> Mapping[SSAValue, BorrowValue]:
        """Get the dict of qubit → basis/total borrows."""
        return self._borrows

    def merge(self, other: ProjectionBorrows) -> ProjectionBorrows:
        """
        Merge borrows from another projection, returning a new ProjectionBorrows.

        Does not check compatibility - that's done by the caller.
        UNKNOWN takes precedence over Basis.
        """
        merged = {**self._borrows, **other._borrows}
        return ProjectionBorrows(merged)

    def has_conflicting_borrow(self, other: ProjectionBorrows) -> SSAValue | None:
        """
        Check if this projection has a conflicting borrow with another.

        Conflicts occur when:
        - Same qubit borrowed in different bases (e.g., Z vs X)
        - Any qubit with UNKNOWN borrow (dynamically determined)

        Returns:
            The conflicting qubit SSAValue if found, None otherwise.
        """
        for qubit in self._borrows.keys() & other._borrows.keys():
            self_val = self._borrows[qubit]
            other_val = other._borrows[qubit]
            # UNKNOWN conflicts with everything (including itself)
            if self_val is UNKNOWN or other_val is UNKNOWN:
                return qubit
            # Different bases conflict
            if self_val != other_val:
                return qubit


@dataclass
class TypingContext:
    """
    Type-checking state threaded through type checking.

    Uses ScopedDict for variables and borrows to automatically
    handle lexical scoping.
    """

    func_kind: FuncKind
    variables: ScopedDict[str, SSAValue] = field(
        default_factory=ScopedDict[str, SSAValue]
    )
    borrows: ScopedDict[SSAValue, ProjectionBorrows] = field(
        default_factory=ScopedDict[SSAValue, ProjectionBorrows]
    )
    active_borrows: ProjectionBorrows = field(default_factory=ProjectionBorrows)

    def new_scope(
        self,
        func_kind: FuncKind,
        active_borrows: ProjectionBorrows,
    ) -> TypingContext:
        """
        Create a new typing context with fresh scopes.

        Args:
            func_kind: Function kind for the new scope (e.g., UNITARY for qif bodies)
            active_borrows: Borrows from outer qif conditions to enforce

        Returns:
            New TypingContext with child scopes for variables and borrows
        """
        return TypingContext(
            func_kind=func_kind,
            variables=ScopedDict(parent=self.variables),
            borrows=ScopedDict(parent=self.borrows),
            active_borrows=active_borrows,
        )


class FuncSignature(NamedTuple):
    """
    Function signature information for function call resolution.

    Stores the essential type information needed to validate function calls.
    """

    kind: FuncKind
    function_type: FunctionType


@dataclass
class TypeChecker:
    """
    Type checker for proj-xdsl CST.

    Walks the CST and emits xDSL IR operations, performing type checking
    and borrow analysis.
    """

    functions: dict[str, FuncSignature] = field(default_factory=dict)
    """Symbol table mapping function names to their signatures."""

    def check_type(self, node: TypeNode) -> TypeAttribute:
        """
        Convert a CST type node to an xDSL TypeAttribute.

        This is a pure conversion with no context needed.

        Args:
            node: CST type node

        Returns:
            Corresponding xDSL TypeAttribute

        Raises:
            TypeCheckError: If the type is unknown
        """
        match node:
            case QubitTypeNode():
                return QubitType()
            case ProjTypeNode():
                return ProjectionType()
            case BoolTypeNode():
                return i1
            case AngleTypeNode():
                return AngleType()
            case _:
                raise TypeCheckError(
                    node.span,
                    f"Unknown type node: {node.node_name}",
                )

    def check_state(self, node: ExprNode) -> StateAttr:
        """
        Check that an expression is a state literal and extract its StateAttr.

        This is a checking function - it verifies the expression matches the
        expected form (state literal) and extracts the semantic value.

        Args:
            node: CST expression node

        Returns:
            StateAttr from the state literal

        Raises:
            TypeCheckError: If the expression is not a state literal
        """
        match node:
            case StateExpr():
                return StateAttr(node.state)
            case _:
                raise TypeCheckError(
                    node.span,
                    f"Expected state literal, got {node.node_name}",
                )

    def infer_expression(
        self,
        node: ExprNode,
        ctx: TypingContext,
        builder: Builder,
    ) -> SSAValue | None:
        """
        Infer the type of an expression and return its SSA value.

        This is the "synthesis" direction of bidirectional typechecking.
        The expression determines its own type.

        Args:
            node: CST expression node
            ctx: Typing context with variables and borrows
            builder: Builder for inserting operations

        Returns:
            SSA value of the typed expression, or None for void expressions

        Raises:
            TypeCheckError: If type inference fails
        """
        match node:
            case BoolLiteralExpr():
                value = IntegerAttr(1 if node.value else 0, 1)
                return builder.insert(ConstantOp(value)).result

            case IntLiteralExpr():
                # Only 0 is valid as an angle; typechecker validates this
                if node.value != 0:
                    raise TypeCheckError(
                        node.span,
                        f"Integer literal {node.value} is not a valid angle; "
                        "only 0 is allowed",
                    )
                return builder.insert(ZeroOp()).result

            case PiExpr():
                return builder.insert(PiOp()).result

            case IdentExpr():
                if node.name not in ctx.variables:
                    raise TypeCheckError(
                        node.span,
                        f"Undefined variable: {node.name}",
                    )
                return ctx.variables[node.name]

            case EqExpr():
                qubit = self.check_expression(node.qubit, QubitType(), ctx, builder)
                state = self.check_state(node.state)
                result = builder.insert(EqOp(qubit, state)).result
                basis = state.data.get_basis()
                ctx.borrows[result] = ProjectionBorrows({qubit: basis})
                return result

            case NotExpr():
                operand = self.check_expression(
                    node.operand, ProjectionType(), ctx, builder, coerce=False
                )
                return self._make_not_expr(operand, builder, ctx)

            case BinaryProjExpr():
                left = self.check_expression(
                    node.left, ProjectionType(), ctx, builder, coerce=False
                )
                right = self.check_expression(
                    node.right, ProjectionType(), ctx, builder, coerce=False
                )

                return self._make_binary_proj(
                    left, right, node.op, builder, ctx, node.span
                )

            case NegAngleExpr():
                operand = self.check_expression(node.operand, AngleType(), ctx, builder)
                return builder.insert(ScalarMultOp(-1.0, operand)).result

            case ScalarMultExpr():
                if not isinstance(node.scalar, ScalarExpr):
                    raise TypeCheckError(
                        node.scalar.span,
                        f"Expected scalar literal, got {node.scalar.node_name}",
                    )
                scalar_val = node.scalar.value
                angle = self.check_expression(node.angle, AngleType(), ctx, builder)
                return builder.insert(ScalarMultOp(scalar_val, angle)).result

            case BinaryAngleExpr():
                left = self.check_expression(node.left, AngleType(), ctx, builder)
                right = self.check_expression(node.right, AngleType(), ctx, builder)

                match node.op:
                    case AngleOpKind.ADD:
                        return builder.insert(AddOp(left, right)).result
                    case AngleOpKind.SUB:
                        neg_right = builder.insert(ScalarMultOp(-1.0, right)).result
                        return builder.insert(AddOp(left, neg_right)).result

            case AllocExpr():
                if ctx.func_kind < FuncKind.MIXED:
                    raise TypeCheckError(
                        node.span,
                        f"Alloc operation not allowed in "
                        f"{ctx.func_kind.display_name} context",
                    )
                state = self.check_state(node.state)
                return builder.insert(AllocOp(state)).result

            case MeasureExpr():
                if ctx.func_kind < FuncKind.MIXED:
                    raise TypeCheckError(
                        node.span,
                        f"Measure operation not allowed in "
                        f"{ctx.func_kind.display_name} context",
                    )
                operand = self.check_expression(
                    node.operand, ProjectionType(), ctx, builder
                )
                return builder.insert(MeasureOp(operand)).result

            case CallExpr():
                if node.name not in self.functions:
                    raise TypeCheckError(
                        node.span,
                        f"Undefined function: {node.name}",
                    )
                func_sig = self.functions[node.name]

                if func_sig.kind > ctx.func_kind:
                    raise TypeCheckError(
                        node.span,
                        f"Cannot call {func_sig.kind.display_name} function from "
                        f"{ctx.func_kind.display_name} context",
                    )

                expected_arg_count = len(func_sig.function_type.inputs.data)
                if len(node.args) != expected_arg_count:
                    raise TypeCheckError(
                        node.span,
                        f"Function '{node.name}' expects "
                        f"{expected_arg_count} argument(s), got {len(node.args)}",
                    )

                arg_values: list[SSAValue] = []
                for i, (arg, expected_type) in enumerate(
                    zip(node.args, func_sig.function_type.inputs.data, strict=True)
                ):
                    arg_val = self.check_expression(
                        arg,
                        expected_type,
                        ctx,
                        builder,
                        context=f" in argument {i + 1} of function '{node.name}'",
                    )
                    arg_values.append(arg_val)

                # Borrow analysis for function call
                direct_qubits: set[SSAValue] = set()
                projection_borrows: list[ProjectionBorrows] = []

                for arg_val in arg_values:
                    if isinstance(arg_val.type, QubitType):
                        if arg_val in direct_qubits:
                            raise TypeCheckError(
                                node.span,
                                "Qubit is passed into function twice",
                            )
                        direct_qubits.add(arg_val)
                    elif isinstance(arg_val.type, ProjectionType):
                        arg_borrows = ctx.borrows.get(arg_val, ProjectionBorrows())
                        projection_borrows.append(arg_borrows)

                # Check projection borrows don't overlap with direct qubits
                for proj_borrows in projection_borrows:
                    for qubit in proj_borrows.borrows.keys():
                        if qubit in direct_qubits:
                            raise TypeCheckError(
                                node.span,
                                "Qubit is both directly passed and borrowed"
                                " in function call",
                            )

                # Check projections don't borrow from same qubits
                for i, borrows1 in enumerate(projection_borrows):
                    for borrows2 in projection_borrows[i + 1 :]:
                        conflict = borrows1.has_conflicting_borrow(borrows2)
                        if conflict is not None:
                            raise TypeCheckError(
                                node.span,
                                "Function call arguments have conflicting borrows",
                            )

                # Check arguments against active qif borrows
                for qubit in direct_qubits:
                    if qubit in ctx.active_borrows.borrows:
                        raise TypeCheckError(
                            node.span,
                            "Qubit argument conflicts with outer qif condition borrow",
                        )
                for arg_borrows in projection_borrows:
                    conflict = ctx.active_borrows.has_conflicting_borrow(arg_borrows)
                    if conflict is not None:
                        raise TypeCheckError(
                            node.span,
                            "Function call argument has conflicting borrow"
                            " with outer qif",
                        )

                result_types = func_sig.function_type.outputs.data
                call_op = builder.insert(CallOp(node.name, arg_values, result_types))

                # Handle borrows for return value
                if result_types and isinstance(result_types[0], ProjectionType):
                    result_borrows_dict: dict[SSAValue, BorrowValue] = {}
                    for proj_borrows in projection_borrows:
                        result_borrows_dict.update(proj_borrows.borrows)
                    for qubit in direct_qubits:
                        result_borrows_dict[qubit] = UNKNOWN
                    ctx.borrows[call_op.res[0]] = ProjectionBorrows(result_borrows_dict)

                if len(result_types) == 0:
                    return None
                elif len(result_types) == 1:
                    return call_op.res[0]
                else:
                    raise TypeCheckError(
                        node.span,
                        f"Function '{node.name}' returns multiple values,"
                        " not yet supported",
                    )

            case _:
                raise TypeCheckError(
                    node.span,
                    f"Cannot infer type for expression: {node.node_name}",
                )

    def check_expression(
        self,
        node: ExprNode,
        expected: Attribute,
        ctx: TypingContext,
        builder: Builder,
        coerce: bool = True,
        context: str = "expression",
    ) -> SSAValue:
        """
        Check that an expression has the expected type.

        This is the "checking" direction of bidirectional typechecking.
        Infers the type and coerces if necessary.

        Args:
            node: CST expression node
            expected: Expected type attribute
            ctx: Typing context with variables and borrows
            builder: Builder for inserting operations
            coerce: If True (default), insert coercion. If False, only validate
                    and return the original SSA value (useful for borrow analysis).
            context: Context string for error messages (default: "expression")

        Returns:
            SSA value (coerced if coerce=True, original otherwise)

        Raises:
            TypeCheckError: If the expression is void or doesn't match the expected type
        """
        # Special handling for binary proj expressions
        if isinstance(node, BinaryProjExpr):
            # Validate: expected type must be ≥ proj (i.e., proj ≤ expected)
            self.check_subtype(
                ProjectionType(), expected, node.span, f"'{node.op.value}' expression"
            )

            # Check operands without coercion
            left = self.check_expression(
                node.left, expected, ctx, builder, coerce=False, context=context
            )
            right = self.check_expression(
                node.right, expected, ctx, builder, coerce=False, context=context
            )

            result = self._make_binary_proj(
                left, right, node.op, builder, ctx, node.span
            )

        # Special handling for not expressions
        elif isinstance(node, NotExpr):
            # Validate: expected type must be ≥ proj (i.e., proj ≤ expected)
            self.check_subtype(ProjectionType(), expected, node.span, "not expression")

            # Check operand without coercion (for analysis)
            operand = self.check_expression(
                node.operand, expected, ctx, builder, coerce=False, context=context
            )

            result = self._make_not_expr(operand, builder, ctx)

        # Default: infer expression
        else:
            result = self.infer_expression(node, ctx, builder)
            if result is None:
                raise TypeCheckError(
                    node.span,
                    f"Expected value, got '()'{context}",
                )

        # Coerce result if needed
        self.check_subtype(result.type, expected, node.span, context)
        if coerce:
            return self.coerce_to(result, expected, builder)
        return result

    def infer_statement(
        self,
        node: StmtNode,
        ctx: TypingContext,
        builder: Builder,
    ) -> SSAValue | None:
        """
        Infer the type of a statement and return its SSA value (if any).

        Statements are typically void (let, ph, qif), but expression statements
        without semicolons return their value (used as block results).

        Args:
            node: CST statement node
            ctx: Typing context with variables and borrows
            builder: Builder for inserting operations

        Returns:
            SSA value if the statement produces one (expression without semicolon),
            None for void statements

        Raises:
            TypeCheckError: If type inference fails
        """
        match node:
            case LetStmt():
                if node.type_ann:
                    expected = self.check_type(node.type_ann)
                    value = self.check_expression(node.value, expected, ctx, builder)
                else:
                    value = self.infer_expression(node.value, ctx, builder)
                    if value is None:
                        raise TypeCheckError(
                            node.span, f"Cannot bind void to variable {node.name}"
                        )
                if node.name in ctx.variables.local_scope:
                    raise TypeCheckError(
                        node.span,
                        f"Variable '{node.name}' is already defined",
                    )
                value.name_hint = node.name
                ctx.variables[node.name] = value

            case PhaseStmt():
                if ctx.func_kind < FuncKind.UNITARY:
                    raise TypeCheckError(
                        node.span,
                        f"Phase operation not allowed in "
                        f"{ctx.func_kind.display_name} context",
                    )
                angle = self.check_expression(node.angle, AngleType(), ctx, builder)
                builder.insert(PhaseOp(angle))

            case QifStmt():
                if ctx.func_kind < FuncKind.UNITARY:
                    raise TypeCheckError(
                        node.span,
                        f"Qif operation not allowed in "
                        f"{ctx.func_kind.display_name} context",
                    )
                condition = self.check_expression(
                    node.condition, ProjectionType(), ctx, builder
                )
                condition_borrows = ctx.borrows.get(condition, ProjectionBorrows())
                conflict = ctx.active_borrows.has_conflicting_borrow(condition_borrows)
                if conflict is not None:
                    raise TypeCheckError(
                        node.condition.span,
                        "Qif condition borrows qubit already borrowed by outer qif",
                    )
                merged_borrows = ctx.active_borrows.merge(condition_borrows)

                @Builder.region
                def true_region(inner_builder: Builder):
                    self.infer_block(
                        node.true_body,
                        ctx.new_scope(FuncKind.UNITARY, merged_borrows),
                        inner_builder,
                    )

                false_region = None
                if node.false_body is not None:
                    false_body = node.false_body

                    @Builder.region
                    def _false_region(inner_builder: Builder):
                        self.infer_block(
                            false_body,
                            ctx.new_scope(FuncKind.UNITARY, merged_borrows),
                            inner_builder,
                        )

                    false_region = _false_region

                builder.insert(IfOp(condition, true_region, false_region))

            case ExprStmt():
                return self.infer_expression(node.expr, ctx, builder)

            case _:
                raise TypeCheckError(
                    node.span,
                    f"Unknown statement type: {node.node_name}",
                )

    def check_statement(
        self,
        node: StmtNode,
        ctx: TypingContext,
        builder: Builder,
        expected: Attribute,
    ) -> SSAValue:
        """
        Check a statement and return its value.

        This is the "checking" direction - errors if the statement is void.
        Used for expression statements in block-final position.

        Args:
            node: CST statement node
            ctx: Typing context with variables and borrows
            builder: Builder for inserting operations
            expected: Expected type

        Returns:
            SSA value of the statement

        Raises:
            TypeCheckError: If checking fails, statement is void, or type mismatch
        """
        if isinstance(node, ExprStmt):
            return self.check_expression(node.expr, expected, ctx, builder)

        result = self.infer_statement(node, ctx, builder)
        if result is None:
            raise TypeCheckError(
                node.span,
                "Expected statement with value, got void",
            )
        self.check_subtype(result.type, expected, node.span, "statement")
        return self.coerce_to(result, expected, builder)

    def infer_block(
        self,
        node: BlockNode,
        ctx: TypingContext,
        builder: Builder,
    ) -> SSAValue | None:
        """
        Infer the type of a block of statements.

        Intermediate statements can have values (discarded).
        The last statement determines the block's result.

        Args:
            node: CST block node
            ctx: Typing context with variables and borrows
            builder: Builder for inserting operations

        Returns:
            SSA value of the final expression (if any), None if block is void

        Raises:
            TypeCheckError: If type inference fails
        """
        if not node.statements:
            return None

        # Intermediate statements: infer and discard values
        for stmt in node.statements[:-1]:
            self.infer_statement(stmt, ctx, builder)

        # Last statement determines block result
        return self.infer_statement(node.statements[-1], ctx, builder)

    def check_block(
        self,
        node: BlockNode,
        ctx: TypingContext,
        builder: Builder,
        expected: Attribute,
    ) -> SSAValue:
        """
        Check a block of statements and return its value.

        Intermediate statements can have values (discarded).
        The last statement is checked against the expected type.

        Args:
            node: CST block node
            ctx: Typing context with variables and borrows
            builder: Builder for inserting operations
            expected: Expected type for the block result

        Returns:
            SSA value of the block result (possibly coerced)

        Raises:
            TypeCheckError: If checking fails, block is void, or type mismatch
        """
        if not node.statements:
            raise TypeCheckError(
                node.span,
                "Expected block with value, got void",
            )

        # Intermediate statements: infer and discard values
        for stmt in node.statements[:-1]:
            self.infer_statement(stmt, ctx, builder)

        # Check last statement against expected type
        return self.check_statement(node.statements[-1], ctx, builder, expected)

    def check_func_def(self, node: FuncDef) -> PureOp | UnitaryOp | MixedOp:
        """
        Check a function definition and return the corresponding function operation.

        Functions cannot be recursive, so the signature is registered after checking.

        Args:
            node: CST function definition node

        Returns:
            The checked function operation (PureOp, UnitaryOp, or MixedOp)

        Raises:
            TypeCheckError: If type checking fails
        """
        # Determine function kind and operation class
        match node.kind:
            case FuncKind.PURE:
                func_op_class = PureOp
            case FuncKind.UNITARY:
                func_op_class = UnitaryOp
            case FuncKind.MIXED:
                func_op_class = MixedOp

        # Parse parameter types
        input_types: list[TypeAttribute] = []
        param_names: list[str] = []
        for param in node.params:
            param_type = self.check_type(param.type_ann)
            input_types.append(param_type)
            param_names.append(param.name)

        # Parse optional return type
        return_types: list[TypeAttribute] = []
        if node.return_type is not None:
            return_types.append(self.check_type(node.return_type))

        # Create FunctionType
        func_type = FunctionType.from_lists(input_types, return_types)

        # Create typing context with parameters
        ctx = TypingContext(
            func_kind=node.kind,
            variables=ScopedDict[str, SSAValue](name=node.name),
            borrows=ScopedDict[SSAValue, ProjectionBorrows](name=node.name),
        )

        # Create function body region
        @Builder.region(input_types)
        def build_body(inner_builder: Builder, args: tuple[BlockArgument, ...]):
            for param_name, block_arg in zip(param_names, args, strict=True):
                block_arg.name_hint = param_name
                ctx.variables[param_name] = block_arg

            # Check function body using infer_block or check_block
            if return_types:
                # Function has return type - check block against expected type
                final_result = self.check_block(
                    node.body, ctx, inner_builder, return_types[0]
                )

                # Check that returned projection doesn't borrow locally allocated qubits
                if final_result.type == ProjectionType():
                    final_borrows = ctx.borrows.get(final_result, ProjectionBorrows())
                    for qubit, borrow_val in final_borrows.borrows.items():
                        if isinstance(qubit.owner, AllocOp):
                            raise TypeCheckError(
                                node.body.span,
                                "Locally allocated qubit is still borrowed at return: "
                                f"borrowed in {borrow_val.name}",
                            )

                inner_builder.insert(ReturnOp(final_result))
            else:
                # Void function - infer block (result discarded)
                self.infer_block(node.body, ctx, inner_builder)
                inner_builder.insert(ReturnOp())

        # Create the function operation
        func_op = func_op_class(
            sym_name=node.name,
            function_type=func_type,
            body=build_body,
        )

        # Register signature after checking (functions cannot be recursive)
        signature = FuncSignature(kind=node.kind, function_type=func_type)
        self.functions[node.name] = signature

        return func_op

    def check_module(self, node: Module) -> ModuleOp:
        """
        Check a module containing function definitions.

        Functions are checked in order. A function can only call functions
        that were defined earlier in the module (no recursion allowed).

        Args:
            node: CST module node

        Returns:
            The checked module operation containing all function definitions

        Raises:
            TypeCheckError: If type checking fails
        """
        # Clear function symbol table for fresh checking
        self.functions = {}

        # Check functions in order - each function is fully checked before
        # its signature is registered, so functions can only call earlier ones
        func_ops: list[PureOp | UnitaryOp | MixedOp] = []
        for func_def in node.functions:
            func_op = self.check_func_def(func_def)
            func_ops.append(func_op)

        # Create the module operation with all functions
        return ModuleOp(func_ops)

    def check_subtype(
        self, sub: Attribute, sup: Attribute, span: Span, context: str
    ) -> None:
        """
        Check that sub ≤ sup in the subtyping lattice, raising an error if not.

        Subtyping relation: bool (i1) ≤ proj

        Args:
            sub: The subtype to check
            sup: The supertype to check against
            span: Source span for error reporting
            context: Description of the context for error messages

        Raises:
            TypeCheckError: If sub is not a subtype of sup
        """
        # Reflexivity
        if sub == sup:
            return
        # bool (i1) ≤ proj
        if sub == i1 and isinstance(sup, ProjectionType):
            return
        raise TypeCheckError(span, f"Type mismatch: expected {sup}, got {sub}{context}")

    def _make_binary_proj(
        self,
        left: SSAValue,
        right: SSAValue,
        op: BinaryOpKind,
        builder: Builder,
        ctx: TypingContext,
        span: Span,
    ) -> SSAValue:
        """
        Create a binary projection/boolean operation.

        Performs borrow analysis for projections.

        Args:
            left: Left operand (must have same type as right)
            right: Right operand
            op: Binary operator kind
            builder: Builder for inserting operations
            ctx: Typing context for borrow analysis
            span: Source span for error reporting

        Returns:
            Result SSA value
        """
        if left.type == i1 and right.type == i1:
            match op:
                case BinaryOpKind.AND:
                    return builder.insert(AndIOp(left, right)).result
                case BinaryOpKind.OR:
                    return builder.insert(OrIOp(left, right)).result
                case BinaryOpKind.XOR:
                    return builder.insert(XOrIOp(left, right)).result

        left = self.coerce_to(left, ProjectionType(), builder)
        right = self.coerce_to(right, ProjectionType(), builder)
        match op:
            case BinaryOpKind.AND:
                result = builder.insert(AndOp(left, right)).result
            case BinaryOpKind.OR:
                result = builder.insert(OrOp(left, right)).result
            case BinaryOpKind.XOR:
                result = builder.insert(XorOp(left, right)).result

        # Borrow analysis for projections
        if isinstance(left.type, ProjectionType):
            left_borrows = ctx.borrows.get(left, ProjectionBorrows())
            right_borrows = ctx.borrows.get(right, ProjectionBorrows())
            conflict = left_borrows.has_conflicting_borrow(right_borrows)
            if conflict is not None:
                left_val = left_borrows.borrows.get(conflict, UNKNOWN)
                right_val = right_borrows.borrows.get(conflict, UNKNOWN)
                raise TypeCheckError(
                    span,
                    f"Cannot combine projections with conflicting borrows: "
                    f"qubit borrowed in {left_val.name} and {right_val.name}",
                )
            ctx.borrows[result] = left_borrows.merge(right_borrows)

        return result

    def _make_not_expr(
        self,
        operand: SSAValue,
        builder: Builder,
        ctx: TypingContext,
    ) -> SSAValue:
        """
        Create a negation operation.

        Propagates borrows for projections.

        Args:
            operand: Operand to negate
            builder: Builder for inserting operations
            ctx: Typing context for borrow propagation

        Returns:
            Result SSA value
        """
        if operand.type == i1:
            one = builder.insert(ConstantOp(IntegerAttr(1, 1))).result
            return builder.insert(XOrIOp(operand, one)).result

        result = builder.insert(NotOp(operand)).result
        operand_borrows = ctx.borrows.get(operand, ProjectionBorrows())
        ctx.borrows[result] = operand_borrows
        return result

    def coerce_to(
        self,
        value: SSAValue,
        expected: Attribute,
        builder: Builder,
    ) -> SSAValue:
        """
        Coerce a value to an expected type.

        Supported coercions:
        - bool (i1) → proj (via FromBoolOp)
        - T → T (identity, no coercion needed)

        Assumes the caller has already verified the subtype relation.

        Args:
            value: SSA value to coerce
            expected: Expected type (must be a supertype of value.type)
            builder: Builder for inserting operations

        Returns:
            SSA value (possibly wrapped in coercion)
        """
        # Equality check (no coercion needed)
        if value.type == expected:
            return value

        # bool → proj
        assert value.type == i1, f"Can only coerce from i1, got {value.type}"
        assert expected == ProjectionType(), f"Can only coerce to proj, got {expected}"
        return builder.insert(FromBoolOp(value)).result
