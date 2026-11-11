"""Angle dialect canonicalization patterns."""

from xdsl.pattern_rewriter import (
    PatternRewriter,
    RewritePattern,
    op_type_rewrite_pattern,
)

from projxdsl.dialects.angle.ops import ScalarMultOp, ZeroOp


class ScalarMultZeroPattern(RewritePattern):
    """
    Canonicalize 0 * angle to 0.
    """

    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: ScalarMultOp, rewriter: PatternRewriter, /):
        # Check if scalar is 0.0
        if op.scalar.value.data != 0.0:
            return

        # Replace with angle.zero
        zero_op = ZeroOp()
        rewriter.replace(op, zero_op)
