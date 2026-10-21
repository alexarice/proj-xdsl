from __future__ import annotations

from xdsl.ir import Dialect, ParametrizedAttribute, TypeAttribute
from xdsl.irdl import irdl_attr_definition


@irdl_attr_definition
class ProjectionType(ParametrizedAttribute, TypeAttribute):
    """
    Projection type (P).
    """

    name = "proj.projection"


@irdl_attr_definition
class QubitType(ParametrizedAttribute, TypeAttribute):
    """
    Q - Qubit type
    """

    name = "proj.qubit"


Proj = Dialect(
    "proj",
    [],
    [
        QubitType,
        ProjectionType,
    ],
)
