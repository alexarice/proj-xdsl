from __future__ import annotations

from enum import auto
from typing import ClassVar

from xdsl.dialects.builtin import IntegerType, NoneAttr
from xdsl.dialects.utils import EnumAttribute
from xdsl.ir import Dialect, ParametrizedAttribute, TypeAttribute
from xdsl.irdl import (
    IRDLOperation,
    VarConstraint,
    irdl_attr_definition,
    irdl_op_definition,
    irdl_to_attr_constraint,
    operand_def,
    result_def,
)
from xdsl.parser import AttrParser
from xdsl.printer import Printer
from xdsl.utils.str_enum import StrEnum


class Basis(StrEnum):
    """
    Basis enum for qubit borrow annotations.
    """

    X = auto()
    Y = auto()
    Z = auto()


@irdl_attr_definition
class BasisAttr(EnumAttribute[Basis]):
    """
    Basis attribute (B ∈ {X, Y, Z}).
    """

    name = "proj.basis"

    @classmethod
    def X(cls) -> BasisAttr:
        return BasisAttr(Basis.X)

    @classmethod
    def Y(cls) -> BasisAttr:
        return BasisAttr(Basis.Y)

    @classmethod
    def Z(cls) -> BasisAttr:
        return BasisAttr(Basis.Z)

    @classmethod
    def parse_parameter(cls, parser: AttrParser) -> Basis:
        with parser.in_angle_brackets():
            return super().parse_parameter(parser)

    def print_parameter(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            super().print_parameter(printer)


class State(StrEnum):
    """
    State enum for ket states.
    """

    ZERO = auto()
    ONE = auto()
    PLUS = auto()
    MINUS = auto()
    LEFT = auto()
    RIGHT = auto()


@irdl_attr_definition
class StateAttr(EnumAttribute[State]):
    """
    State attribute for ket states (|0>, |1>, |+>, |->, |L>, |R>).
    """

    name = "proj.state"

    @classmethod
    def ZERO(cls) -> StateAttr:
        return StateAttr(State.ZERO)

    @classmethod
    def ONE(cls) -> StateAttr:
        return StateAttr(State.ONE)

    @classmethod
    def PLUS(cls) -> StateAttr:
        return StateAttr(State.PLUS)

    @classmethod
    def MINUS(cls) -> StateAttr:
        return StateAttr(State.MINUS)

    @classmethod
    def LEFT(cls) -> StateAttr:
        return StateAttr(State.LEFT)

    @classmethod
    def RIGHT(cls) -> StateAttr:
        return StateAttr(State.RIGHT)

    @classmethod
    def parse_parameter(cls, parser: AttrParser) -> State:
        with parser.in_angle_brackets():
            return super().parse_parameter(parser)

    def print_parameter(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            super().print_parameter(printer)


@irdl_attr_definition
class ProjectionType(ParametrizedAttribute, TypeAttribute):
    """
    Projection type (P).
    """

    name = "proj.projection"


@irdl_attr_definition
class QubitType(ParametrizedAttribute, TypeAttribute):
    """
    Q - Qubit type with optional basis borrow annotation.
    """

    name = "proj.qubit"

    borrow_type: BasisAttr | NoneAttr

    def print_parameters(self, printer: Printer) -> None:
        if isinstance(self.borrow_type, BasisAttr):
            self.borrow_type.print_parameter(printer)

    @classmethod
    def parse_parameters(cls, parser: AttrParser) -> tuple[BasisAttr | NoneAttr]:
        if parser.parse_optional_characters("<") is None:
            return (NoneAttr(),)
        basis = parser.parse_str_enum(Basis)
        parser.parse_characters(">", " to close proj.qubit parameters")
        return (BasisAttr(basis),)

    def __init__(self, borrow_type: BasisAttr | NoneAttr = NoneAttr()):
        super().__init__(borrow_type)


ProjectionOrBool = ProjectionType | IntegerType[1]
ProjectionOrBoolConstr = irdl_to_attr_constraint(ProjectionOrBool)


@irdl_op_definition
class NotOp(IRDLOperation):
    """
    Negation operation for projections or booleans.
    Takes a projection (P) or boolean (i1) and returns the same type.
    """

    name = "proj.not"

    T: ClassVar = VarConstraint("T", ProjectionOrBoolConstr)

    input = operand_def(T)
    result = result_def(T)

    assembly_format = "$input attr-dict `:` type($input)"


@irdl_op_definition
class AndOp(IRDLOperation):
    """
    Conjunction operation for projections or booleans.
    Takes two operands of the same type (P or i1) and returns the same type.
    """

    name = "proj.and"

    T: ClassVar = VarConstraint("T", ProjectionOrBoolConstr)

    lhs = operand_def(T)
    rhs = operand_def(T)
    result = result_def(T)

    assembly_format = "$lhs `,` $rhs attr-dict `:` type($result)"


Proj = Dialect(
    "proj",
    [
        NotOp,
        AndOp,
    ],
    [
        BasisAttr,
        StateAttr,
        QubitType,
        ProjectionType,
    ],
)
