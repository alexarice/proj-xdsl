"""Projection dialect package."""

from xdsl.ir import Dialect

from projxdsl.dialects.proj.attrs import Basis, State, StateAttr
from projxdsl.dialects.proj.canonicalize import RemoveEmptyQifPattern
from projxdsl.dialects.proj.ops import (
    AllocOp,
    AndOp,
    CallOp,
    EqOp,
    FromBoolOp,
    FuncOpBase,
    MeasureOp,
    MixedOp,
    NotOp,
    OrOp,
    PhaseOp,
    PureOp,
    QifOp,
    ReturnOp,
    UnitaryOp,
    XorOp,
)
from projxdsl.dialects.proj.types import ProjectionType, QubitType

__all__ = [
    "Proj",
    # Operations
    "AllocOp",
    "NotOp",
    "AndOp",
    "OrOp",
    "XorOp",
    "FromBoolOp",
    "EqOp",
    "MeasureOp",
    "PhaseOp",
    "QifOp",
    "ReturnOp",
    "CallOp",
    "PureOp",
    "UnitaryOp",
    "MixedOp",
    "FuncOpBase",
    # Attributes
    "Basis",
    "State",
    "StateAttr",
    # Types
    "ProjectionType",
    "QubitType",
    # Canonicalization
    "RemoveEmptyQifPattern",
]

Proj = Dialect(
    "proj",
    [
        AllocOp,
        NotOp,
        AndOp,
        OrOp,
        XorOp,
        FromBoolOp,
        EqOp,
        MeasureOp,
        PhaseOp,
        QifOp,
        ReturnOp,
        CallOp,
        PureOp,
        UnitaryOp,
        MixedOp,
    ],
    [
        StateAttr,
        ProjectionType,
        QubitType,
    ],
)
