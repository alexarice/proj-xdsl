"""Angle dialect for proj-xdsl."""

from __future__ import annotations

from xdsl.ir import Dialect, ParametrizedAttribute, TypeAttribute
from xdsl.irdl import irdl_attr_definition


@irdl_attr_definition
class AngleType(ParametrizedAttribute, TypeAttribute):
    """
    angle - Classical angle type for Phase gate parameters.
    """

    name = "angle.type"


Angle = Dialect(
    "angle",
    [],
    [
        AngleType,
    ],
)
