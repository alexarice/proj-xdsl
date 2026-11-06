"""Angle dialect for proj-xdsl."""

from __future__ import annotations

from xdsl.dialects.builtin import Float64Type, FloatAttr
from xdsl.ir import Dialect, ParametrizedAttribute, SSAValue, TypeAttribute
from xdsl.irdl import (
    IRDLOperation,
    irdl_attr_definition,
    irdl_op_definition,
    operand_def,
    prop_def,
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


@irdl_op_definition
class AddOp(IRDLOperation):
    """
    Angle addition operation.
    Adds two angles together.
    """

    name = "angle.add"

    lhs = operand_def(AngleType)
    rhs = operand_def(AngleType)
    result = result_def(AngleType)

    assembly_format = "$lhs `,` $rhs attr-dict"

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[AngleType()])


@irdl_op_definition
class ScalarMultOp(IRDLOperation):
    """
    Scalar multiplication operation.
    Multiplies an angle by a scalar float value.
    """

    name = "angle.scalar_mult"

    scalar = prop_def(FloatAttr.constr(Float64Type()))
    angle = operand_def(AngleType)
    result = result_def(AngleType)

    assembly_format = "$scalar `,` $angle attr-dict"

    def __init__(self, scalar: float | FloatAttr[Float64Type], angle: SSAValue):
        if isinstance(scalar, int | float):
            scalar = FloatAttr(scalar, Float64Type())
        super().__init__(
            operands=[angle],
            properties={"scalar": scalar},
            result_types=[AngleType()],
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
