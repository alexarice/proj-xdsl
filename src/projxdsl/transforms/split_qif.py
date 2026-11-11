"""
Split qif statements into simpler forms.

This pass provides two patterns:

1. SplitQifElsePattern: Splits a qif with an else region into two separate qifs,
   where the second has a negated condition.

2. SplitQifNoElsePattern: Splits a qif with multiple quantum ops (no else) into
   a sequence of single-operation qifs.

Both patterns only apply when the qif regions contain only quantum operations
(phase or nested qif).
"""

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Block, Region
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint

from projxdsl.dialects.proj import NotOp, PhaseOp, QifOp


def has_only_quantum_ops(region: Region) -> bool:
    """Check if a single-block region contains only quantum operations."""
    block = region.blocks.first
    assert block is not None
    for op in block.ops:
        if not isinstance(op, PhaseOp | QifOp):
            return False
    return True


class SplitQifElsePattern(RewritePattern):
    """Split a qif with an else region into two separate qifs."""

    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: QifOp, rewriter: PatternRewriter, /):
        if op.false_region is None:
            return

        if not has_only_quantum_ops(op.true_region):
            return
        if not has_only_quantum_ops(op.false_region):
            return

        insert_point = InsertPoint.before(op)

        true_block = op.true_region.blocks.first
        false_block = op.false_region.blocks.first
        assert true_block is not None
        assert false_block is not None

        op.true_region.detach_block(true_block)
        op.false_region.detach_block(false_block)

        first_qif = QifOp(op.condition, Region([true_block]))
        rewriter.insert(first_qif, insert_point)

        not_op = NotOp(op.condition)
        rewriter.insert(not_op, insert_point)

        second_qif = QifOp(not_op.result, Region([false_block]))
        rewriter.insert(second_qif, insert_point)

        rewriter.erase(op, safe_erase=False)


class SplitQifNoElsePattern(RewritePattern):
    """Split a qif with multiple quantum ops into a sequence of single-op qifs."""

    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: QifOp, rewriter: PatternRewriter, /):
        if op.false_region is not None:
            return

        if not has_only_quantum_ops(op.true_region):
            return

        block = op.true_region.blocks.first
        assert block is not None

        if len(block.ops) <= 1:
            return

        insert_point = InsertPoint.before(op)

        while len(block.ops) > 1:
            op_to_split = block.ops.first
            assert op_to_split is not None

            op_to_split.detach()

            new_block = Block([op_to_split])
            new_qif = QifOp(op.condition, Region([new_block]))
            rewriter.insert(new_qif, insert_point)


class SplitQifPass(ModulePass):
    """Split qif statements into simpler forms."""

    name = "split-qif"

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            SplitQifElsePattern(),
            apply_recursively=True,
        ).rewrite_module(op)

        PatternRewriteWalker(
            SplitQifNoElsePattern(),
            apply_recursively=True,
        ).rewrite_module(op)
