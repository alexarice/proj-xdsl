"""Angle dialect for proj-xdsl."""

from __future__ import annotations

from xdsl.ir import Dialect, ParametrizedAttribute, TypeAttribute
from xdsl.irdl import (
    IRDLOperation,
    irdl_attr_definition,
    irdl_op_definition,
    result_def,
)


@irdl_attr_definition
class AngleType(ParametrizedAttribute, TypeAttribute):
    """
    angle - Classical angle type for Phase gate parameters.
    """

    name = "angle.type"


@irdl_op_definition
class ZeroOp(IRDLOperation):
    """
    Zero angle constant operation.
    Returns an angle with value 0.
    """

    name = "angle.zero"

    result = result_def(AngleType)

    assembly_format = "attr-dict"

    def __init__(self):
        super().__init__(result_types=[AngleType()])


@irdl_op_definition
class PiOp(IRDLOperation):
    """
    Pi angle constant operation.
    Returns an angle with value π.
    """

    name = "angle.pi"

    result = result_def(AngleType)

    assembly_format = "attr-dict"

    def __init__(self):
        super().__init__(result_types=[AngleType()])


Angle = Dialect(
    "angle",
    [
        ZeroOp,
        PiOp,
    ],
    [
        AngleType,
    ],
)
