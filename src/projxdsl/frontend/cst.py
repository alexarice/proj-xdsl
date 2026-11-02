"""
Concrete Syntax Tree (CST) definitions for proj-xdsl.

All CST nodes are immutable (frozen dataclasses) with source location tracking.
The CST captures the complete syntactic structure without type information.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from enum import Enum

from xdsl.utils.lexer import Span

from projxdsl.dialects.proj import State
from projxdsl.func_kind import FuncKind

# =============================================================================
# Base Classes
# =============================================================================


@dataclass(frozen=True)
class CSTNode(ABC):
    """Base class for all CST nodes."""

    span: Span


@dataclass(frozen=True)
class ExprNode(CSTNode, ABC):
    """Base class for all expression nodes."""

    pass


@dataclass(frozen=True)
class StmtNode(CSTNode, ABC):
    """Base class for all statement nodes."""

    pass


@dataclass(frozen=True)
class TypeNode(CSTNode, ABC):
    """Base class for all type nodes."""

    pass


# =============================================================================
# Enums
# =============================================================================


class BinaryOpKind(Enum):
    """Binary operators on projections/booleans."""

    AND = "&&"
    OR = "||"
    XOR = "^"


class AngleOpKind(Enum):
    """Binary operators on angles."""

    ADD = "+"
    SUB = "-"


class AngleConstantKind(Enum):
    """Angle constant kinds."""

    ZERO = "0"
    PI = "pi"


# =============================================================================
# Expression Nodes
# =============================================================================


@dataclass(frozen=True)
class IdentExpr(ExprNode):
    """Identifier reference."""

    name: str


@dataclass(frozen=True)
class BoolLiteralExpr(ExprNode):
    """Boolean literal: true or false."""

    value: bool


@dataclass(frozen=True)
class StateExpr(ExprNode):
    """State literal: |0>, |1>, |+>, |->, |L>, |R>."""

    state: State


@dataclass(frozen=True)
class ScalarExpr(ExprNode):
    """Scalar literal: 2.0, -1.0, etc."""

    value: float


@dataclass(frozen=True)
class AngleConstantExpr(ExprNode):
    """Angle constant: 0 or pi."""

    kind: AngleConstantKind


@dataclass(frozen=True)
class NotExpr(ExprNode):
    """Negation: !expr."""

    operand: ExprNode


@dataclass(frozen=True)
class MeasureExpr(ExprNode):
    """Measurement: measure expr."""

    operand: ExprNode


@dataclass(frozen=True)
class NegAngleExpr(ExprNode):
    """Angle negation: -angle."""

    operand: ExprNode


@dataclass(frozen=True)
class ScalarMultExpr(ExprNode):
    """Scalar multiplication: scalar * angle."""

    scalar: ExprNode
    angle: ExprNode


@dataclass(frozen=True)
class BinaryProjExpr(ExprNode):
    """Binary operator on projections/booleans: &&, ||, ^."""

    op: BinaryOpKind
    left: ExprNode
    right: ExprNode


@dataclass(frozen=True)
class BinaryAngleExpr(ExprNode):
    """Binary operator on angles: +, -."""

    op: AngleOpKind
    left: ExprNode
    right: ExprNode


@dataclass(frozen=True)
class EqExpr(ExprNode):
    """Equality: qubit == state."""

    qubit: ExprNode
    state: ExprNode


@dataclass(frozen=True)
class CallExpr(ExprNode):
    """Function call: name(args)."""

    name: str
    args: tuple[ExprNode, ...]


@dataclass(frozen=True)
class AllocExpr(ExprNode):
    """Qubit allocation: alloc state."""

    state: ExprNode


@dataclass(frozen=True)
class ParenExpr(ExprNode):
    """Parenthesized expression: (expr)."""

    inner: ExprNode


# =============================================================================
# Statement Nodes
# =============================================================================


@dataclass(frozen=True)
class LetStmt(StmtNode):
    """Let statement: let name: type? = expr;"""

    name: str
    type_ann: TypeNode | None
    value: ExprNode


@dataclass(frozen=True)
class PhaseStmt(StmtNode):
    """Phase statement: ph(angle);"""

    angle: ExprNode


@dataclass(frozen=True)
class QifStmt(StmtNode):
    """Quantum if: qif condition { true_body } else { false_body }."""

    condition: ExprNode
    true_body: BlockNode
    false_body: BlockNode | None


@dataclass(frozen=True)
class ExprStmt(StmtNode):
    """Expression statement: expr;"""

    expr: ExprNode


@dataclass(frozen=True)
class BlockNode(CSTNode):
    """Block of statements: { stmt* }."""

    statements: tuple[StmtNode, ...]


# =============================================================================
# Declaration Nodes
# =============================================================================


@dataclass(frozen=True)
class Param(CSTNode):
    """Function parameter: name: type."""

    name: str
    type_ann: TypeNode


@dataclass(frozen=True)
class FuncDef(CSTNode):
    """Function definition: kind fn name(params) -> type? { body }."""

    kind: FuncKind
    name: str
    params: tuple[Param, ...]
    return_type: TypeNode | None
    body: BlockNode


# =============================================================================
# Module Node
# =============================================================================


@dataclass(frozen=True)
class Module(CSTNode):
    """Module: sequence of function definitions."""

    functions: tuple[FuncDef, ...]


# =============================================================================
# Type Nodes
# =============================================================================


@dataclass(frozen=True)
class QubitType(TypeNode):
    """Qubit type."""

    pass


@dataclass(frozen=True)
class ProjType(TypeNode):
    """Projection type."""

    pass


@dataclass(frozen=True)
class BoolType(TypeNode):
    """Boolean type."""

    pass


@dataclass(frozen=True)
class AngleType(TypeNode):
    """Angle type."""

    pass
