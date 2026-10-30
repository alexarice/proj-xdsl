"""
Liveness analysis for projection SSA values.

Computes live-before and live-after sets for each operation in a function,
tracking which projection values are live at each program point.
Handles IfOp regions with control flow merging.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from xdsl.ir import Block, Operation, SSAValue

from projxdsl.dialects.proj import FuncOpBase, IfOp, ProjectionType


@dataclass
class LivenessInfo:
    """
    Liveness information for a function.

    Maps each operation to the set of projection SSA values
    that are live immediately before and after that operation executes.
    """

    _live_before: dict[Operation, set[SSAValue]] = field(default_factory=dict)
    _live_after: dict[Operation, set[SSAValue]] = field(default_factory=dict)

    def is_live_before(self, op: Operation, value: SSAValue) -> bool:
        """Check if a value is live before an operation."""
        return value in self._live_before.get(op, set())

    def get_live_before(self, op: Operation) -> set[SSAValue]:
        """Get the set of values live before an operation."""
        return self._live_before.get(op, set())

    def is_live_after(self, op: Operation, value: SSAValue) -> bool:
        """Check if a value is live after an operation."""
        return value in self._live_after.get(op, set())

    def get_live_after(self, op: Operation) -> set[SSAValue]:
        """Get the set of values live after an operation."""
        return self._live_after.get(op, set())


def _is_projection(value: SSAValue) -> bool:
    """Check if an SSA value has projection type."""
    return isinstance(value.type, ProjectionType)


def _get_defined_projections(op: Operation) -> Iterable[SSAValue]:
    """Get projection values defined by an operation."""
    for result in op.results:
        if _is_projection(result):
            yield result


def _get_used_projections(op: Operation) -> Iterable[SSAValue]:
    """Get projection values used by an operation."""
    for operand in op.operands:
        if _is_projection(operand):
            yield operand


def compute_liveness(func_op: FuncOpBase) -> LivenessInfo:
    """
    Compute liveness information for projection values in a function.

    Uses backward dataflow analysis:
    - live_in[block] = uses_in_block ∪ (live_out[block] - defs_in_block)
    - live_out[block] = union of live_in[succ] for all successors

    Handles IfOp regions:
    - true_region and false_region are separate control flow paths
    - Both merge back after the IfOp

    For a structure like:
    ```
    before-if
    if_op
      true_region:
        true_stmts
        yield
      false_region:
        false_stmts
        yield
    after_if
    ```

    The liveness flows:
    - live_out[before-if] = live_in[true_region] ∪ live_in[false_region]
    - live_in[if_op] = live_out[true_region]
                     ∪ live_out[false_region]
                     ∪ live_in[after_if]

    Args:
        func_op: The function operation to analyse

    Returns:
        LivenessInfo with live-before and live-after sets for each operation
    """
    live_before: dict[Operation, set[SSAValue]] = {}
    live_after: dict[Operation, set[SSAValue]] = {}

    func_block = func_op.body.first_block

    assert func_block is not None

    def analyse_block(block: Block, live_out: set[SSAValue]) -> set[SSAValue]:
        """Analyze a block, handling IfOp regions. Returns live_in for the block."""
        next_live_before = live_out

        for op in reversed(block.ops):
            live_after[op] = next_live_before.copy()

            uses = set(_get_used_projections(op))
            defs = set(_get_defined_projections(op))
            live_before[op] = uses | (live_after[op] - defs)

            if isinstance(op, IfOp):
                # Condition projection remains live through both regions
                region_live_out = live_after[op] | {op.condition}
                if (true_block := op.true_region.first_block) is not None:
                    live_before[op] |= analyse_block(true_block, region_live_out)
                if (false_block := op.false_region.first_block) is not None:
                    live_before[op] |= analyse_block(false_block, region_live_out)

            next_live_before = live_before[op]

        return next_live_before

    analyse_block(func_block, set())

    return LivenessInfo(_live_before=live_before, _live_after=live_after)
