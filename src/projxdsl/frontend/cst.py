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

from projxdsl.dialects.proj.attrs import State
from projxdsl.func_kind import FuncKind

# =============================================================================
# Base Classes
# =============================================================================


@dataclass(frozen=True)
class CSTNode(ABC):
    """Base class for all CST nodes."""

    span: Span

    node_name = "node"


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


# =============================================================================
# Expression Nodes
# =============================================================================


@dataclass(frozen=True)
class IdentExpr(ExprNode):
    """Identifier reference."""

    name: str

    node_name = "identifier"


@dataclass(frozen=True)
class BoolLiteralExpr(ExprNode):
    """Boolean literal: true or false."""

    value: bool

    node_name = "boolean literal"


@dataclass(frozen=True)
class IntLiteralExpr(ExprNode):
    """Integer literal: 0, 1, 2, etc."""

    value: int

    node_name = "integer literal"


@dataclass(frozen=True)
class StateExpr(ExprNode):
    """State literal: |0>, |1>, |+>, |->, |L>, |R>."""

    state: State

    node_name = "state literal"


@dataclass(frozen=True)
class FloatLiteralExpr(ExprNode):
    """Float literal: 2.0, -1.0, etc."""

    value: float

    node_name = "float literal"


@dataclass(frozen=True)
class PiExpr(ExprNode):
    """Pi constant for angles."""

    node_name = "pi constant"


@dataclass(frozen=True)
class NotExpr(ExprNode):
    """Negation: !expr."""

    operand: ExprNode

    node_name = "negation"


@dataclass(frozen=True)
class MeasureExpr(ExprNode):
    """Measurement: measure expr."""

    operand: ExprNode

    node_name = "measurement"


@dataclass(frozen=True)
class NegAngleExpr(ExprNode):
    """Angle negation: -angle."""

    operand: ExprNode

    node_name = "angle negation"


@dataclass(frozen=True)
class ScalarMultExpr(ExprNode):
    """Scalar multiplication: scalar * angle."""

    scalar: ExprNode
    angle: ExprNode

    node_name = "scalar multiplication"


@dataclass(frozen=True)
class BinaryProjExpr(ExprNode):
    """Binary operator on projections/booleans: &&, ||, ^."""

    op: BinaryOpKind
    left: ExprNode
    right: ExprNode

    node_name = "binary operator"


@dataclass(frozen=True)
class BinaryAngleExpr(ExprNode):
    """Binary operator on angles: +, -."""

    op: AngleOpKind
    left: ExprNode
    right: ExprNode

    node_name = "angle operator"


@dataclass(frozen=True)
class EqExpr(ExprNode):
    """Equality: qubit == state."""

    qubit: ExprNode
    state: ExprNode

    node_name = "equality"


@dataclass(frozen=True)
class CallExpr(ExprNode):
    """Function call: name(args)."""

    name: str
    args: tuple[ExprNode, ...]

    node_name = "function call"


@dataclass(frozen=True)
class AllocExpr(ExprNode):
    """Qubit allocation: alloc state."""

    state: ExprNode

    node_name = "allocation"


@dataclass(frozen=True)
class IfExpr(ExprNode):
    """Classical if expression: if cond { block } (else { block })?."""

    condition: ExprNode
    true_body: BlockNode
    false_body: BlockNode | None

    node_name = "if expression"


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
class QubitTypeNode(TypeNode):
    """Qubit type."""

    node_name = "qubit"


@dataclass(frozen=True)
class ProjTypeNode(TypeNode):
    """Projection type."""

    node_name = "proj"


@dataclass(frozen=True)
class BoolTypeNode(TypeNode):
    """Boolean type."""

    node_name = "bool"


@dataclass(frozen=True)
class AngleTypeNode(TypeNode):
    """Angle type."""

    node_name = "angle"
