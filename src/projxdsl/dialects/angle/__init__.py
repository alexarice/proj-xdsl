"""Angle dialect for proj-xdsl."""

from xdsl.ir import Dialect

from projxdsl.dialects.angle.ops import (
    AddOp,
    AngleType,
    PiOp,
    ScalarMultOp,
    ZeroOp,
)

Angle = Dialect(
    "angle",
    [
        ZeroOp,
        PiOp,
        AddOp,
        ScalarMultOp,
    ],
    [
        AngleType,
    ],
)
