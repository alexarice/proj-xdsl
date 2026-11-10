"""
Simplify qif statements by pulling out classical operations.

This pass identifies classical operations within qif regions that don't depend
on values defined inside the qif, and moves them before the qif operation.

Only phase and qif are quantum operations and remain inside.
All other operations are considered classical and can be pulled out.
"""

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Operation, Region
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint

from projxdsl.dialects.proj import PhaseOp, QifOp


def can_pull_out(op: Operation, region: Region) -> bool:
    """
    Check if an operation can be pulled out of a qif region.

    An operation can be pulled out if:
    1. It is not a quantum operation (phase or qif)
    2. All its operands are defined outside the given region
    """
    # Quantum operations cannot be pulled out
    if isinstance(op, PhaseOp | QifOp):
        return False

    # Check if all operands are defined outside the region
    for operand in op.operands:
        # Get the operation that defines this operand
        defining_op = operand.owner
        if not isinstance(defining_op, Operation):
            # Block argument - defined outside
            continue

        # Check if the defining op is inside the same region
        if region.is_ancestor(defining_op):
            return False

    return True


class PullOutClassicalOpPattern(RewritePattern):
    """
    Pattern that pulls a single classical operation out of a qif region.

    Matches classical ops inside qif regions and moves them before the qif.
    Only matches if all operands are defined outside the qif.
    """

    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter, /):
        # Find the parent region
        parent_block = op.parent
        if parent_block is None:
            return

        parent_region = parent_block.parent
        if parent_region is None:
            return

        # Find the qif op that owns this region
        qif_op = parent_region.parent
        if not isinstance(qif_op, QifOp):
            return

        # Check if we can pull this op out
        if not can_pull_out(op, parent_region):
            return

        # Detach from current position
        op.detach()

        # Insert before the qif
        insert_point = InsertPoint.before(qif_op)
        rewriter.insert(op, insert_point)


class HoistFromQifPass(ModulePass):
    """Hoist classical operations out of qif regions."""

    name = "hoist-from-qif"

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            PullOutClassicalOpPattern(),
            apply_recursively=True,
        ).rewrite_module(op)
