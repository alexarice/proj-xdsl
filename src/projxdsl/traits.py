"""Traits for proj-xdsl dialect."""

from xdsl.ir import Operation
from xdsl.traits import OpTrait


class AllowedInFuncKinds(OpTrait):
    """
    Trait that verifies an operation only appears in specific function kinds.

    This is the opposite of HasAncestor - it prevents operations from appearing
    in certain function kinds.
    """

    def __init__(self, allowed_kinds: tuple[str, ...]):
        """
        Initialize the trait with allowed function kinds.

        Args:
            allowed_kinds: Tuple of function kind names that allow this operation
                          (e.g., ("proj.unitary", "proj.mixed"))
        """
        self.allowed_kinds = allowed_kinds

    def verify(self, op: Operation) -> None:
        """Verify that the operation appears only in allowed function kinds."""
        from xdsl.utils.exceptions import VerifyException

        # Find the ancestor function operation
        func_op = op.parent_op()
        while func_op is not None and func_op.name not in (
            "proj.pure",
            "proj.unitary",
            "proj.mixed",
        ):
            func_op = func_op.parent_op()

        if func_op is None:
            # No function ancestor, allow the operation
            return

        # Get the function kind from the operation name
        func_kind = func_op.name

        if func_kind not in self.allowed_kinds:
            allowed_str = " or ".join(self.allowed_kinds)
            raise VerifyException(
                f"Operation '{op.name}' is not allowed in {func_kind} functions. "
                f"Allowed in: {allowed_str}"
            )
