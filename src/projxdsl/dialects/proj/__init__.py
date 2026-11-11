"""Projection dialect package."""

# ruff: noqa: F401
# pyright: reportUnusedImport=false

from xdsl.ir import Dialect

from projxdsl.dialects.proj.attrs import Basis, State, StateAttr
from projxdsl.dialects.proj.canonicalize import (
    RemoveEmptyQifElsePattern,
    RemoveEmptyQifPattern,
)
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
