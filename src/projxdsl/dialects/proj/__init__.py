"""Projection dialect package."""

from xdsl.ir import Dialect

from .attrs import StateAttr
from .ops import (
    AllocOp,
    AndOp,
    CallOp,
    EqOp,
    FromBoolOp,
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
from .ops import FuncOpBase as FuncOpBase
from .types import ProjectionType, QubitType

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
