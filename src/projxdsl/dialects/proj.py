from __future__ import annotations

from enum import auto

from xdsl.dialects.builtin import NoneAttr, i1
from xdsl.dialects.utils import EnumAttribute
from xdsl.ir import Dialect, ParametrizedAttribute, SSAValue, TypeAttribute
from xdsl.irdl import (
    IRDLOperation,
    irdl_attr_definition,
    irdl_op_definition,
    irdl_to_attr_constraint,
    operand_def,
    prop_def,
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
    Basis attribute (basis ∈ {X, Y, Z}).
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

    def get_basis(self) -> Basis:
        """Get the measurement basis for this state."""
        match self:
            case State.ZERO | State.ONE:
                return Basis.Z
            case State.PLUS | State.MINUS:
                return Basis.X
            case State.LEFT | State.RIGHT:
                return Basis.Y


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
    Projection type (proj).
    """

    name = "proj.projection"


@irdl_attr_definition
class AngleType(ParametrizedAttribute, TypeAttribute):
    """
    angle - Classical angle type for Phase gate parameters.
    """

    name = "proj.angle"


@irdl_attr_definition
class QubitType(ParametrizedAttribute, TypeAttribute):
    """
    qubit - Qubit type with optional basis borrow annotation.
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


ProjectionConstr = irdl_to_attr_constraint(ProjectionType)


@irdl_op_definition
class NotOp(IRDLOperation):
    """
    Negation operation for projections.
    Takes a projection (proj) and returns a projection.
    """

    name = "proj.not"

    input = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$input attr-dict"

    def __init__(self, input: SSAValue):
        super().__init__(operands=[input], result_types=[ProjectionType()])


@irdl_op_definition
class AndOp(IRDLOperation):
    """
    Conjunction operation for projections.
    Takes two projections and returns a projection.
    """

    name = "proj.and"

    lhs = operand_def(ProjectionType)
    rhs = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$lhs `,` $rhs attr-dict"

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[ProjectionType()])


@irdl_op_definition
class OrOp(IRDLOperation):
    """
    Disjunction operation for projections.
    Takes two projections and returns a projection.
    """

    name = "proj.or"

    lhs = operand_def(ProjectionType)
    rhs = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$lhs `,` $rhs attr-dict"

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[ProjectionType()])


@irdl_op_definition
class XorOp(IRDLOperation):
    """
    Exclusive-or operation for projections.
    Takes two projections and returns a projection.
    """

    name = "proj.xor"

    lhs = operand_def(ProjectionType)
    rhs = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$lhs `,` $rhs attr-dict"

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[ProjectionType()])


@irdl_op_definition
class FromBoolOp(IRDLOperation):
    """
    Cast operation from boolean to projection.
    Takes a boolean (i1) and returns a projection.
    """

    name = "proj.from_bool"

    input = operand_def(i1)
    result = result_def(ProjectionType)

    assembly_format = "$input attr-dict"

    def __init__(self, input: SSAValue):
        super().__init__(operands=[input], result_types=[ProjectionType()])


@irdl_op_definition
class EqOp(IRDLOperation):
    """
    Projection creation operation.
    Creates a projection by comparing a qubit to a ket state.
    The state determines the basis (ZERO/ONE=Z, PLUS/MINUS=X, LEFT/RIGHT=Y).
    """

    name = "proj.eq"

    qubit = operand_def(QubitType)
    state = prop_def(StateAttr)
    result = result_def(ProjectionType)

    assembly_format = "$qubit `,` $state attr-dict `:` type($qubit)"

    def __init__(self, qubit: SSAValue, state: StateAttr):
        super().__init__(
            operands=[qubit],
            properties={"state": state},
            result_types=[ProjectionType()],
        )


Proj = Dialect(
    "proj",
    [
        NotOp,
        AndOp,
        OrOp,
        XorOp,
        FromBoolOp,
        EqOp,
    ],
    [
        BasisAttr,
        StateAttr,
        QubitType,
        ProjectionType,
        AngleType,
    ],
)
