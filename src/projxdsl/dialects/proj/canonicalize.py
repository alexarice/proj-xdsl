"""Projection dialect canonicalization patterns."""

from xdsl.pattern_rewriter import (
    PatternRewriter,
    RewritePattern,
    op_type_rewrite_pattern,
)

from projxdsl.dialects.proj.ops import QifOp


class RemoveEmptyQifPattern(RewritePattern):
    """Remove qif operations with empty regions."""

    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: QifOp, rewriter: PatternRewriter, /):
        true_block = op.true_region.blocks.first
        if true_block is None or len(true_block.ops) > 0:
            return

        false_block = op.false_region.blocks.first
        if false_block is not None and len(false_block.ops) > 0:
            return

        rewriter.erase(op, safe_erase=False)
