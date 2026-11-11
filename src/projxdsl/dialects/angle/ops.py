"""Angle dialect for proj-xdsl."""

from __future__ import annotations

from collections.abc import Sequence

from xdsl.dialects.builtin import Float64Type, FloatAttr
from xdsl.interfaces import HasCanonicalizationPatternsInterface, HasFolderInterface
from xdsl.ir import Attribute, ParametrizedAttribute, SSAValue, TypeAttribute
from xdsl.irdl import (
    IRDLOperation,
    irdl_attr_definition,
    irdl_op_definition,
    operand_def,
    prop_def,
    result_def,
    traits_def,
)
from xdsl.pattern_rewriter import RewritePattern
from xdsl.traits import Pure


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

    traits = traits_def(Pure())

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

    traits = traits_def(Pure())

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

    traits = traits_def(Pure())

    assembly_format = "$lhs `,` $rhs attr-dict"

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[AngleType()])


@irdl_op_definition
class ScalarMultOp(
    IRDLOperation, HasCanonicalizationPatternsInterface, HasFolderInterface
):
    """
    Scalar multiplication operation.
    Multiplies an angle by a scalar float value.
    """

    name = "angle.scalar_mult"

    scalar = prop_def(FloatAttr.constr(Float64Type()))
    angle = operand_def(AngleType)
    result = result_def(AngleType)

    assembly_format = "$scalar `,` $angle attr-dict"

    traits = traits_def(Pure())

    def __init__(self, scalar: float | FloatAttr[Float64Type], angle: SSAValue):
        if isinstance(scalar, int | float):
            scalar = FloatAttr(scalar, Float64Type())
        super().__init__(
            operands=[angle],
            properties={"scalar": scalar},
            result_types=[AngleType()],
        )

    def fold(self) -> Sequence[SSAValue | Attribute] | None:
        """
        Fold: 1.0 * angle = angle (returns the angle operand).

        Note: 0.0 * angle is handled by canonicalization (ScalarMultZeroPattern)
        since it requires creating a new angle.zero operation.
        """
        if self.scalar.value.data == 1.0:
            return (self.angle,)
        return None

    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from projxdsl.dialects.angle.canonicalize import (
            ScalarMultCombinePattern,
            ScalarMultZeroPattern,
        )

        return (
            ScalarMultZeroPattern(),
            ScalarMultCombinePattern(),
        )
