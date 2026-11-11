"""Projection dialect types."""

from xdsl.ir import ParametrizedAttribute, TypeAttribute
from xdsl.irdl import irdl_attr_definition


@irdl_attr_definition
class ProjectionType(ParametrizedAttribute, TypeAttribute):
    """Projection type (proj)."""

    name = "proj.projection"


@irdl_attr_definition
class QubitType(ParametrizedAttribute, TypeAttribute):
    """Qubit type."""

    name = "proj.qubit"


__all__ = [
    "ProjectionType",
    "QubitType",
]
