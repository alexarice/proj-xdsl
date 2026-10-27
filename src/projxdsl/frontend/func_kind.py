"""Function kind enumeration for proj-xdsl."""

from enum import Enum


class FuncKind(Enum):
    """
    Function kind enumeration.

    Represents the three function kinds in proj-xdsl:
    - PURE: Classical only, no quantum operations
    - UNITARY: Quantum operations allowed, but no measurement or allocation
    - MIXED: All operations allowed

    Hierarchy: PURE ⊆ UNITARY ⊆ MIXED
    """

    PURE = "pure"
    UNITARY = "unitary"
    MIXED = "mixed"

    def allows_operation(self, op_kind: str) -> bool:
        """
        Check if this function kind allows the given operation kind.

        Args:
            op_kind: Operation kind string. One of:
                - "phase": Phase gate (unitary or mixed only)
                - "if": Conditional (unitary or mixed only)
                - "alloc": Qubit allocation (mixed only)
                - "measure": Measurement (mixed only)

        Returns:
            True if the operation is allowed in this function kind.
        """
        if op_kind in ("phase", "if"):
            return self in (FuncKind.UNITARY, FuncKind.MIXED)
        elif op_kind in ("alloc", "measure"):
            return self == FuncKind.MIXED
        return True
