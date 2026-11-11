"""Projection dialect canonicalization patterns."""

from xdsl.pattern_rewriter import (
    PatternRewriter,
    RewritePattern,
    op_type_rewrite_pattern,
)

from projxdsl.dialects.proj.ops import QifOp


class RemoveEmptyQifElsePattern(RewritePattern):
    """Remove empty else block from qif operations."""

    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: QifOp, rewriter: PatternRewriter, /):
        # Only match if false_region has a block
        false_block = op.false_region.blocks.first
        if false_block is None:
            return

        # Only remove if the false block is empty
        if len(false_block.ops) > 0:
            return

        # Detach the empty false block and notify listeners of the modification
        op.false_region.detach_block(false_block)
        rewriter.notify_op_modified(op)


class RemoveEmptyQifPattern(RewritePattern):
    """Remove qif operations with empty then branch and no else."""

    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: QifOp, rewriter: PatternRewriter, /):
        true_block = op.true_region.blocks.first
        if true_block is None or len(true_block.ops) > 0:
            return

        # Only remove if false_region has no blocks
        if op.false_region.blocks:
            return

        rewriter.erase(op, safe_erase=False)
