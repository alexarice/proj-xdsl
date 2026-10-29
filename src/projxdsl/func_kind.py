"""Function kind enumeration for proj-xdsl."""

from enum import Enum
from typing import Self


class FuncKind(Enum):
    """
    Function kind enumeration.

    Represents the three function kinds in proj-xdsl:
    - PURE: Classical only, no quantum operations
    - UNITARY: Quantum operations allowed, but no measurement or allocation
    - MIXED: All operations allowed

    Hierarchy: PURE ⊆ UNITARY ⊆ MIXED
    """

    PURE = 1
    UNITARY = 2
    MIXED = 3

    def __le__(self, other: Self) -> bool:
        """Check if this kind is a subtype of (or equal to) another."""
        return self.value <= other.value

    def __ge__(self, other: Self) -> bool:
        """Check if this kind is a supertype of (or equal to) another."""
        return self.value >= other.value

    def __lt__(self, other: Self) -> bool:
        """Check if this kind is a strict subtype of (or equal to) another."""
        return self.value < other.value

    def __gt__(self, other: Self) -> bool:
        """Check if this kind is a strict supertype of (or equal to) another."""
        return self.value > other.value

    @property
    def display_name(self) -> str:
        """Get the lowercase display name for error messages."""
        return self.name.lower()
