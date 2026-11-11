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


class ScalarMultCombinePattern(RewritePattern):
    """
    Combine nested scalar multiplications: a * (b * angle) = (a * b) * angle.

    If the combined scalar is 1.0, the outer operation is replaced with the
    inner angle's operand.
    If the combined scalar is 0.0, the outer operation is replaced with
    angle.zero.
    """

    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: ScalarMultOp, rewriter: PatternRewriter, /):
        # Check if the angle operand is itself a scalar_mult
        inner_op = op.angle.owner
        if not isinstance(inner_op, ScalarMultOp):
            return

        # Get the scalars
        outer_scalar = op.scalar.value.data
        inner_scalar = inner_op.scalar.value.data

        # Compute the product
        combined_scalar = outer_scalar * inner_scalar

        # Otherwise, create new scalar_mult with combined scalar and inner angle
        new_op = ScalarMultOp(combined_scalar, inner_op.angle)
        rewriter.replace(op, new_op)
