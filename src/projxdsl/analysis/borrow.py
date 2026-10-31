"""
Borrow analysis for projection SSA values.

Computes borrow information for each qubit at each program point in a function,
tracking which projections are borrowing each qubit and in which basis.
Handles IfOp regions with control flow merging.
Requires liveness analysis as input.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum, auto

from xdsl.ir import Block, Operation, SSAValue, VerifyException

from projxdsl.analysis.liveness import LivenessAnalysis
from projxdsl.dialects.proj import (
    AllocOp,
    EqOp,
    FuncOpBase,
    IfOp,
    ProjectionType,
    QubitType,
)


class BorrowError(VerifyException):
    """Exception raised when borrow rules are violated."""

    pass


class BorrowType(Enum):
    """
    Borrow type for a qubit.

    X/Y/Z: qubit is borrowed in a specific basis (matches Basis enum)
    Total: control flow disagreement, no new borrows allowed
    """

    Total = auto()
    X = auto()
    Y = auto()
    Z = auto()


@dataclass
class Borrows:
    """
    Borrow information for a single qubit.

    Tracks the borrow type and which projections are currently borrowing it.
    Only exists when the qubit is actually borrowed.
    """

    borrow_type: BorrowType
    projections: set[SSAValue] = field(default_factory=set)

    def add(self, basis: BorrowType, *projs: SSAValue) -> None:
        """
        Add projections borrowing this qubit in the given basis.

        Raises BorrowError if the basis is incompatible with existing borrows.

        Basis compatibility rules:
        - Same basis: Compatible (multiple projections can borrow in same basis)
        - Different basis: Incompatible (raises BorrowError)
        - Total borrow: Incompatible (raises BorrowError)
        """
        if self.borrow_type == BorrowType.Total:
            raise BorrowError(
                f"Cannot borrow qubit in {basis.name} basis: qubit has total borrow"
            )
        if self.borrow_type != basis:
            raise BorrowError(
                f"Cannot borrow qubit in {basis.name} basis: "
                f"qubit already borrowed in {self.borrow_type.name} basis"
            )
        self.projections.update(projs)


@dataclass
class BorrowState:
    """
    Borrow state for all qubits at a program point.

    Wraps a dictionary mapping qubit SSA values to their borrow information.
    Provides convenient methods for querying and modifying borrow state.
    """

    _borrows: dict[SSAValue, Borrows] = field(default_factory=dict)

    def get(self, qubit: SSAValue) -> Borrows | None:
        """Get borrow information for a qubit (None if not borrowed)."""
        return self._borrows.get(qubit)

    def is_borrowed(self, qubit: SSAValue) -> bool:
        """Check if a qubit is currently borrowed."""
        return qubit in self._borrows

    def add(self, qubit: SSAValue, basis: BorrowType, *projs: SSAValue) -> None:
        """
        Add projections borrowing a qubit in the given basis.

        Creates a new Borrows object if the qubit is not yet borrowed,
        or delegates to Borrows.add() if it is.

        If no projections are provided, just marks the qubit as borrowed
        (useful for Total borrow where we want to prevent further use).
        """
        if qubit not in self._borrows:
            self._borrows[qubit] = Borrows(borrow_type=basis, projections=set(projs))
        else:
            if projs:
                self._borrows[qubit].add(basis, *projs)
            else:
                # Just update the borrow type (e.g., to Total)
                existing = self._borrows[qubit]
                if existing.borrow_type != basis:
                    self._borrows[qubit] = Borrows(
                        borrow_type=basis, projections=existing.projections
                    )

    def items(self) -> Iterable[tuple[SSAValue, Borrows]]:
        """Iterate over (qubit, borrows) pairs."""
        return self._borrows.items()


@dataclass
class BorrowAnalysis:
    """
    Borrow analysis results for a function.

    Maps each operation to the borrow state before and after that operation.
    """

    _before: dict[Operation, BorrowState] = field(default_factory=dict)
    _after: dict[Operation, BorrowState] = field(default_factory=dict)

    def get_state_before(self, op: Operation) -> BorrowState:
        """Get the borrow state before an operation."""
        return self._before.get(op, BorrowState())

    def get_state_after(self, op: Operation) -> BorrowState:
        """Get the borrow state after an operation."""
        return self._after.get(op, BorrowState())

    @staticmethod
    def compute(func_op: FuncOpBase, liveness: LivenessAnalysis) -> "BorrowAnalysis":
        """
        Compute borrow information for projection values in a function.

        Uses forward dataflow analysis with propagation rule:
        "If qubit q is borrowed by P before op, and P is live after op,
         then q is borrowed by P after op"

        Args:
            func_op: The function operation to analyse
            liveness: Pre-computed liveness information

        Returns:
            BorrowAnalysis with borrow state before and after each operation
        """
        before: dict[Operation, BorrowState] = {}
        after: dict[Operation, BorrowState] = {}

        func_block = func_op.body.first_block
        assert func_block is not None

        def analyse_block(block: Block, state_in: BorrowState) -> BorrowState:
            """Analyse a block, handling IfOp regions."""
            next_state_after = state_in

            for op in block.ops:
                # State before this op = state after previous op
                before_state = next_state_after

                # Apply propagation rule:
                # "If qubit q is borrowed by P before op, and P is live after op,
                #  then q is borrowed by P after op"
                live_after = liveness.get_live_after(op)
                after_state = BorrowState()
                for qubit, borrows_before in before_state.items():
                    filtered_projs = borrows_before.projections & live_after
                    if filtered_projs:
                        after_state.add(
                            qubit, borrows_before.borrow_type, *filtered_projs
                        )

                # EqOp creates a new borrow: the result projection borrows the qubit
                if isinstance(op, EqOp):
                    qubit = op.qubit
                    basis = BorrowType[op.state.data.get_basis().name]
                    after_state.add(qubit, basis, op.result)
                else:
                    # Generic rule for all other ops:
                    # If there are result projections, inherit borrows from input
                    # projections and totally borrow input qubits
                    result_projs = [
                        r for r in op.results if isinstance(r.type, ProjectionType)
                    ]

                    if result_projs:
                        # Collect all input projections
                        input_projs = {
                            o for o in op.operands if isinstance(o.type, ProjectionType)
                        }

                        # Inherit borrows from input projections
                        for qubit, borrows_before in before_state.items():
                            if input_projs & borrows_before.projections:
                                after_state.add(
                                    qubit, borrows_before.borrow_type, *result_projs
                                )

                        # Totally borrow any input qubits with the result projections
                        for qubit in op.operands:
                            if isinstance(qubit.type, QubitType):
                                after_state.add(qubit, BorrowType.Total, *result_projs)

                # Recurse into IfOp regions
                if isinstance(op, IfOp):
                    if (true_block := op.true_region.first_block) is not None:
                        analyse_block(true_block, before_state)
                    if (
                        op.false_region is not None
                        and (false_block := op.false_region.first_block) is not None
                    ):
                        analyse_block(false_block, before_state)

                before[op] = before_state
                after[op] = after_state
                next_state_after = after_state

            return next_state_after

        analyse_block(func_block, BorrowState())

        # Check borrow state at function terminator
        terminator = func_block.last_op
        if terminator is not None:
            state_before_return = before.get(terminator, BorrowState())
            for qubit, borrows in state_before_return.items():
                if isinstance(qubit.owner, AllocOp):
                    raise BorrowError(
                        f"Locally allocated qubit is still borrowed at return: "
                        f"borrowed by {[p.name_hint for p in borrows.projections]}"
                    )

        return BorrowAnalysis(_before=before, _after=after)
