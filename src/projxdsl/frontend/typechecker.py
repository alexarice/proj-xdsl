"""
Typechecker for proj-xdsl.

This module performs type checking on the CST produced by the CST parser,
emitting xDSL IR operations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import NamedTuple, overload

from xdsl.builder import Builder
from xdsl.dialects.arith import AndIOp, ConstantOp, OrIOp, XOrIOp
from xdsl.dialects.builtin import FunctionType, IntegerAttr, ModuleOp, i1
from xdsl.dialects.scf import IfOp as ScfIfOp
from xdsl.dialects.scf import YieldOp as ScfYieldOp
from xdsl.ir import Attribute, BlockArgument, Region, SSAValue, TypeAttribute
from xdsl.rewriter import InsertPoint
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
    MeasureOp,
    MixedOp,
    NotOp,
    OrOp,
    PhaseOp,
    ProjectionType,
    PureOp,
    QifOp,
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
    FloatLiteralExpr,
    FuncDef,
    IdentExpr,
    IfExpr,
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
    ScalarMultExpr,
    StateExpr,
    StmtNode,
    TypeNode,
)
from projxdsl.func_kind import FuncKind


class _NonVoid:
    """
    Sentinel type for bounds checking.

    NonVoid indicates that an expression must have a non-void type,
    but the specific type is unconstrained.

    Lattice ordering: bool < proj < NonVoid < None
    where None represents no constraint (top).
    """

    pass


NON_VOID = _NonVoid()
"""Singleton instance of NonVoid sentinel."""

# Type alias for bounds in type checking
Bounds = Attribute | _NonVoid | None


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

    @overload
    def typecheck_expression(
        self,
        node: ExprNode,
        ctx: TypingContext,
        builder: Builder,
        bound: Attribute | _NonVoid,
    ) -> SSAValue: ...

    @overload
    def typecheck_expression(
        self,
        node: ExprNode,
        ctx: TypingContext,
        builder: Builder,
        bound: None = ...,
    ) -> SSAValue | None: ...

    def typecheck_expression(
        self,
        node: ExprNode,
        ctx: TypingContext,
        builder: Builder,
        bound: Bounds = None,
    ) -> SSAValue | None:
        """
        Typecheck an expression with optional bound constraint.

        Args:
            node: CST expression node
            ctx: Typing context with variables and borrows
            builder: Builder for inserting operations
            bound:
                - None: pure inference, no validation
                - NonVoid: must be non-void, type unconstrained
                - TypeAttribute: result.type ≤ bound

        Returns:
            SSA value at its natural type (never coerced),
            or None if void and bound is None.

        Raises:
            TypeCheckError: If typechecking fails or bound is violated.
        """
        result: SSAValue | None = None

        match node:
            case BoolLiteralExpr():
                value = IntegerAttr(1 if node.value else 0, 1)
                result = builder.insert(ConstantOp(value)).result

            case IntLiteralExpr():
                # Only 0 is valid as an angle; typechecker validates this
                if node.value != 0:
                    raise TypeCheckError(
                        node.span,
                        f"Integer literal {node.value} is not a valid angle; "
                        "only 0 is allowed",
                    )
                result = builder.insert(ZeroOp()).result

            case PiExpr():
                result = builder.insert(PiOp()).result

            case IdentExpr():
                if node.name not in ctx.variables:
                    raise TypeCheckError(
                        node.span,
                        f"Undefined variable: {node.name}",
                    )
                result = ctx.variables[node.name]

            case EqExpr():
                # Qubit must be qubit type, state must be state literal
                qubit = self.typecheck_expression(
                    node.qubit, ctx, builder, bound=QubitType()
                )
                state = self.check_state(node.state)
                result = builder.insert(EqOp(qubit, state)).result
                basis = state.data.get_basis()
                ctx.borrows[result] = ProjectionBorrows({qubit: basis})

            case NotExpr():
                # not produces bool/proj, so bound must be compatible
                operand_bound = self.glb(ProjectionType(), bound)
                if operand_bound is None:
                    raise TypeCheckError(
                        node.span,
                        f"not expression has type bool/proj,"
                        f" cannot satisfy bound {bound}",
                    )
                operand = self.typecheck_expression(
                    node.operand, ctx, builder, bound=operand_bound
                )
                result = self._make_not_expr(operand, builder)
                if result.type != i1:
                    operand_borrows = ctx.borrows.get(operand, ProjectionBorrows())
                    ctx.borrows[result] = operand_borrows

            case BinaryProjExpr():
                # &&, ||, ^ produce bool/proj, so bound must be compatible
                operand_bound = self.glb(ProjectionType(), bound)
                if operand_bound is None:
                    raise TypeCheckError(
                        node.span,
                        f"Binary operator expression has type bool/proj,"
                        f" cannot satisfy bound {bound}",
                    )

                left = self.typecheck_expression(
                    node.left, ctx, builder, bound=operand_bound
                )
                right = self.typecheck_expression(
                    node.right, ctx, builder, bound=operand_bound
                )

                result = self._make_binary_op(left, right, node.op, builder)

                # Borrow analysis for projections
                if isinstance(result.type, ProjectionType):
                    left_borrows = ctx.borrows.get(left, ProjectionBorrows())
                    right_borrows = ctx.borrows.get(right, ProjectionBorrows())
                    conflict = left_borrows.has_conflicting_borrow(right_borrows)
                    if conflict is not None:
                        left_val = left_borrows.borrows.get(conflict, UNKNOWN)
                        right_val = right_borrows.borrows.get(conflict, UNKNOWN)
                        raise TypeCheckError(
                            node.span,
                            f"Cannot combine projections with conflicting borrows: "
                            f"qubit borrowed in {left_val.name} and {right_val.name}",
                        )
                    ctx.borrows[result] = left_borrows.merge(right_borrows)

            case NegAngleExpr():
                operand = self.typecheck_expression(
                    node.operand, ctx, builder, bound=AngleType()
                )
                result = builder.insert(ScalarMultOp(-1.0, operand)).result

            case ScalarMultExpr():
                # Accept both float and integer literals as scalars
                match node.scalar:
                    case FloatLiteralExpr():
                        scalar_val = node.scalar.value
                    case IntLiteralExpr():
                        scalar_val = float(node.scalar.value)
                    case _:
                        raise TypeCheckError(
                            node.scalar.span,
                            "Expected float or integer literal,"
                            f" got {node.scalar.node_name}",
                        )
                angle = self.typecheck_expression(
                    node.angle, ctx, builder, bound=AngleType()
                )
                result = builder.insert(ScalarMultOp(scalar_val, angle)).result

            case BinaryAngleExpr():
                left = self.typecheck_expression(
                    node.left, ctx, builder, bound=AngleType()
                )
                right = self.typecheck_expression(
                    node.right, ctx, builder, bound=AngleType()
                )

                match node.op:
                    case AngleOpKind.ADD:
                        result = builder.insert(AddOp(left, right)).result
                    case AngleOpKind.SUB:
                        neg_right = builder.insert(ScalarMultOp(-1.0, right)).result
                        result = builder.insert(AddOp(left, neg_right)).result

            case AllocExpr():
                if ctx.func_kind < FuncKind.MIXED:
                    raise TypeCheckError(
                        node.span,
                        f"Alloc operation not allowed in "
                        f"{ctx.func_kind.display_name} context",
                    )
                state = self.check_state(node.state)
                result = builder.insert(AllocOp(state)).result

            case MeasureExpr():
                if ctx.func_kind < FuncKind.MIXED:
                    raise TypeCheckError(
                        node.span,
                        f"Measure operation not allowed in "
                        f"{ctx.func_kind.display_name} context",
                    )
                # Measure operand must be ≤ ProjectionType (bool or proj)
                operand = self.typecheck_expression(
                    node.operand, ctx, builder, bound=ProjectionType()
                )
                operand = self.coerce_to(operand, ProjectionType(), builder)
                result = builder.insert(MeasureOp(operand)).result

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
                    # Function parameter types are always TypeAttribute
                    arg_val = self.typecheck_expression(
                        arg,
                        ctx,
                        builder,
                        bound=expected_type,
                    )
                    # Coerce argument to expected type if needed
                    arg_val = self.coerce_to(arg_val, expected_type, builder)
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
                    result = None
                elif len(result_types) == 1:
                    result = call_op.res[0]
                else:
                    raise TypeCheckError(
                        node.span,
                        f"Function '{node.name}' returns multiple values,"
                        " not yet supported",
                    )

            case IfExpr():
                # Condition must be bool
                condition = self.typecheck_expression(
                    node.condition, ctx, builder, bound=i1
                )

                # Typecheck branches - they may have different types, we compute LUB
                true_result: SSAValue | None = None
                false_result: SSAValue | None = None

                @Builder.region
                def true_region(inner_builder: Builder):
                    nonlocal true_result
                    true_result = self.typecheck_block(
                        node.true_body, ctx, inner_builder, bound=bound
                    )

                false_region: Region | None = None
                if node.false_body is not None:
                    false_body = node.false_body

                    @Builder.region
                    def _false_region(inner_builder: Builder):
                        nonlocal false_result
                        false_result = self.typecheck_block(
                            false_body, ctx, inner_builder, bound=bound
                        )

                    false_region = _false_region

                # Compute LUB of branch types for the result
                if (
                    true_result is not None
                    and false_result is not None
                    and (result_type := self.lub(true_result.type, false_result.type))
                    is not None
                ):
                    # Coerce both to LUB and add yields
                    true_block = true_region.blocks.last
                    true_coerced = self.coerce_to(
                        true_result,
                        result_type,
                        Builder(InsertPoint.at_end(true_block)),
                    )
                    true_block.add_op(ScfYieldOp(true_coerced))

                    false_block = false_region.blocks.last
                    false_coerced = self.coerce_to(
                        false_result,
                        result_type,
                        Builder(InsertPoint.at_end(false_block)),
                    )
                    false_block.add_op(ScfYieldOp(false_coerced))

                    if_op = builder.insert(
                        ScfIfOp(condition, [result_type], true_region, false_region)
                    )
                    result = if_op.results[0]

                # Void case - add empty yields
                else:
                    true_block = true_region.blocks.last
                    if true_block is not None:
                        true_block.add_op(ScfYieldOp())

                    if false_region is not None:
                        false_block = false_region.blocks.last
                        if false_block is not None:
                            false_block.add_op(ScfYieldOp())

                    builder.insert(ScfIfOp(condition, [], true_region, false_region))
                    result = None

            case _:
                raise TypeCheckError(
                    node.span,
                    f"Cannot typecheck expression: {node.node_name}",
                )

        # Validate result against bound
        self.check_bound(result, bound, node.span)
        return result

    def typecheck_statement(
        self,
        node: StmtNode,
        ctx: TypingContext,
        builder: Builder,
        bound: Bounds = None,
    ) -> SSAValue | None:
        """
        Typecheck a statement with optional bound constraint.

        Statements are typically void (let, ph, qif), but expression statements
        without semicolons return their value (used as block results).

        Args:
            node: CST statement node
            ctx: Typing context with variables and borrows
            builder: Builder for inserting operations
            bound:
                - None: pure inference, no validation
                - NonVoid: must be non-void, type unconstrained
                - TypeAttribute: result.type ≤ bound

        Returns:
            SSA value if the statement produces one (expression without semicolon),
            None for void statements

        Raises:
            TypeCheckError: If typechecking fails or bound is violated
        """
        match node:
            case LetStmt():
                # Let bindings must have a value (non-void)
                if node.type_ann:
                    expected = self.check_type(node.type_ann)
                    value = self.coerce_to(
                        self.typecheck_expression(
                            node.value, ctx, builder, bound=expected
                        ),
                        expected,
                        builder,
                    )
                else:
                    value = self.typecheck_expression(
                        node.value, ctx, builder, bound=NON_VOID
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
                angle = self.typecheck_expression(
                    node.angle, ctx, builder, bound=AngleType()
                )
                builder.insert(PhaseOp(angle))

            case QifStmt():
                if ctx.func_kind < FuncKind.UNITARY:
                    raise TypeCheckError(
                        node.span,
                        f"Qif operation not allowed in "
                        f"{ctx.func_kind.display_name} context",
                    )
                condition = self.coerce_to(
                    self.typecheck_expression(
                        node.condition, ctx, builder, bound=ProjectionType()
                    ),
                    ProjectionType(),
                    builder,
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
                    self.typecheck_block(
                        node.true_body,
                        ctx.new_scope(FuncKind.UNITARY, merged_borrows),
                        inner_builder,
                        bound=None,
                    )

                false_region = None
                if node.false_body is not None:
                    false_body = node.false_body

                    @Builder.region
                    def _false_region(inner_builder: Builder):
                        self.typecheck_block(
                            false_body,
                            ctx.new_scope(FuncKind.UNITARY, merged_borrows),
                            inner_builder,
                            bound=None,
                        )

                    false_region = _false_region

                builder.insert(QifOp(condition, true_region, false_region))

            case ExprStmt():
                return self.typecheck_expression(node.expr, ctx, builder, bound=bound)

            case _:
                raise TypeCheckError(
                    node.span,
                    f"Unknown statement type: {node.node_name}",
                )

    def infer_statement(
        self,
        node: StmtNode,
        ctx: TypingContext,
        builder: Builder,
    ) -> SSAValue | None:
        """
        Infer the type of a statement (legacy wrapper).

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
        return self.typecheck_statement(node, ctx, builder, bound=None)

    def typecheck_block(
        self,
        node: BlockNode,
        ctx: TypingContext,
        builder: Builder,
        bound: Bounds = None,
    ) -> SSAValue | None:
        """
        Typecheck a block of statements with optional bound constraint.

        Intermediate statements can have values (discarded).
        The last statement determines the block's result.

        Args:
            node: CST block node
            ctx: Typing context with variables and borrows
            builder: Builder for inserting operations
            bound:
                - None: pure inference, no validation
                - NonVoid: must be non-void, type unconstrained
                - TypeAttribute: result.type ≤ bound

        Returns:
            SSA value of the final expression (if any), None if block is void

        Raises:
            TypeCheckError: If typechecking fails or bound is violated
        """
        if not node.statements:
            if bound is not None:
                if bound is NON_VOID:
                    raise TypeCheckError(
                        node.span,
                        "Expected block with value, got '()'",
                    )
            return None

        # Intermediate statements: typecheck and discard values
        for stmt in node.statements[:-1]:
            self.typecheck_statement(stmt, ctx, builder, bound=None)

        # Last statement determines block result
        return self.typecheck_statement(node.statements[-1], ctx, builder, bound=bound)

    def infer_block(
        self,
        node: BlockNode,
        ctx: TypingContext,
        builder: Builder,
    ) -> SSAValue | None:
        """
        Infer the type of a block of statements (legacy wrapper).

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
        return self.typecheck_block(node, ctx, builder, bound=None)

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

            # Check function body
            if return_types:
                # Function has return type - check block against return type
                final_result = self.typecheck_block(
                    node.body, ctx, inner_builder, bound=return_types[0]
                )
                if final_result is None:
                    raise TypeCheckError(
                        node.body.span,
                        "Function body must return a value",
                    )

                # Coerce result to return type if needed
                final_result = self.coerce_to(
                    final_result, return_types[0], inner_builder
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
                # Void function - typecheck block (result discarded)
                self.typecheck_block(node.body, ctx, inner_builder, bound=None)
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

    @staticmethod
    def _display_bound(bound: Bounds) -> str:
        if bound is NON_VOID:
            return "value"
        if bound == ProjectionType():
            return "proj"
        if bound == QubitType():
            return "qubit"
        if bound == i1:
            return "bool"

        return str(bound)

    def check_bound(
        self,
        result: SSAValue | None,
        bound: Bounds,
        span: Span,
    ) -> None:
        """
        Check that a result value satisfies a bound constraint, raising an error if not.

        Lattice ordering: bool < proj < NonVoid < None

        Args:
            result: The SSA value to check (or None for void)
            bound: The bound to check against
                - None: always satisfied (no constraint)
                - NonVoid: requires non-void result
                - TypeAttribute: result.type must be ≤ bound
            span: Source span for error reporting
            context: Optional context description for error messages

        Raises:
            TypeCheckError: If the result does not satisfy the bound
        """
        # None bound is top - always satisfied
        if bound is None:
            return

        # Void result can only satisfy None bound
        if result is None:
            raise TypeCheckError(
                span, f"Type mismatch: expected {self._display_bound(bound)}, got '()'"
            )

        # NonVoid - satisfied by all non-void types (all our types are non-void)
        if bound is NON_VOID:
            return

        # Concrete type bound - check subtyping
        # Reflexivity
        if result.type == bound:
            return
        # bool (i1) ≤ proj
        if result.type == i1 and isinstance(bound, ProjectionType):
            return
        raise TypeCheckError(
            span,
            f"Type mismatch: expected {self._display_bound(bound)}, "
            f"got {self._display_bound(result.type)}",
        )

    def _make_binary_op(
        self,
        left: SSAValue,
        right: SSAValue,
        op: BinaryOpKind,
        builder: Builder,
    ) -> SSAValue:
        """
        Create a binary boolean/projection operation.

        Handles type coercion: if one operand is bool and the other is proj,
        the bool is coerced to proj.

        Performs borrow analysis for projections.

        Args:
            left: Left operand (bool or proj)
            right: Right operand (bool or proj)
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

        return result

    def _make_not_expr(
        self,
        operand: SSAValue,
        builder: Builder,
    ) -> SSAValue:
        """
        Create a negation operation.

        Propagates borrows for projections.

        Args:
            operand: Operand to negate
            builder: Builder for inserting operations
            ctx: Typing context for borrow propagation
            bound: Optional bound to validate result against

        Returns:
            Result SSA value at its natural type (same as operand)
        """
        if operand.type == i1:
            one = builder.insert(ConstantOp(IntegerAttr(1, 1))).result
            result = builder.insert(XOrIOp(operand, one)).result
        else:
            result = builder.insert(NotOp(operand)).result

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

    def glb(
        self,
        a: Bounds,
        b: Bounds,
    ) -> Bounds:
        """
        Compute the Greatest Lower Bound of two bounds in the constraint lattice.

        Lattice ordering: bool < proj < NonVoid < None
        where None is top (no constraint).

        GLB represents the tightest constraint that satisfies both inputs.

        Returns:
            The GLB of the two bounds, or None if they are incompatible.
        """
        # None is top - GLB with top is the other operand
        if a is None:
            return b
        if b is None:
            return a

        # NonVoid is below None, above concrete types
        if a is NON_VOID:
            return b
        if b is NON_VOID:
            return a

        # Both are concrete types
        # Same type - GLB is the type itself
        if a == b:
            return a

        # bool (i1) ≤ proj, so GLB(bool, proj) = bool
        if a == i1 and isinstance(b, ProjectionType):
            return a
        if b == i1 and isinstance(a, ProjectionType):
            return b

        # Incomparable types (e.g., angle vs proj, bool vs angle)
        return None

    def lub(
        self,
        lhs: TypeAttribute,
        rhs: TypeAttribute,
    ) -> TypeAttribute | None:
        """
        Compute the Least Upper Bound of two types in the subtyping lattice.

        Type lattice:
        - bool (i1) ≤ proj
        - angle, qubit are incomparable with bool/proj

        Returns:
            The LUB of the two types, or None if they have no common upper bound.
        """
        # Same type - LUB is the type itself
        if lhs == rhs:
            return lhs

        # bool (i1) and proj - LUB is proj
        if lhs == i1 and isinstance(rhs, ProjectionType):
            return rhs
        if isinstance(lhs, ProjectionType) and rhs == i1:
            return lhs

        # Incomparable types (e.g., angle vs proj, bool vs angle)
        return None
