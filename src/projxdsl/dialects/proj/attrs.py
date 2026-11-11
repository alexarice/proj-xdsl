"""Projection dialect attributes."""

from enum import auto

from xdsl.dialects.utils import EnumAttribute
from xdsl.irdl import irdl_attr_definition
from xdsl.parser import AttrParser
from xdsl.printer import Printer
from xdsl.utils.str_enum import StrEnum


class Basis(StrEnum):
    """Basis enum for qubit borrow annotations."""

    X = auto()
    Y = auto()
    Z = auto()


class State(StrEnum):
    """State enum for ket states."""

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
    """State attribute for ket states (|0>, |1>, |+>, |->, |L>, |R>)."""

    name = "proj.state"

    @classmethod
    def ZERO(cls) -> "StateAttr":
        return StateAttr(State.ZERO)

    @classmethod
    def ONE(cls) -> "StateAttr":
        return StateAttr(State.ONE)

    @classmethod
    def PLUS(cls) -> "StateAttr":
        return StateAttr(State.PLUS)

    @classmethod
    def MINUS(cls) -> "StateAttr":
        return StateAttr(State.MINUS)

    @classmethod
    def LEFT(cls) -> "StateAttr":
        return StateAttr(State.LEFT)

    @classmethod
    def RIGHT(cls) -> "StateAttr":
        return StateAttr(State.RIGHT)

    @classmethod
    def parse_parameter(cls, parser: AttrParser) -> State:
        with parser.in_angle_brackets():
            return super().parse_parameter(parser)

    def print_parameter(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            super().print_parameter(printer)


__all__ = [
    "Basis",
    "State",
    "StateAttr",
]
