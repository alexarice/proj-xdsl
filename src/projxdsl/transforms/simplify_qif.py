"""
Simplify qif statements by splitting and hoisting classical operations.

This pass combines two simplification patterns:

1. Split qif/else into separate qifs with negated conditions
2. Split multi-op qifs into single-op qifs
3. Hoist classical operations out of qif regions

The patterns are applied iteratively to handle cases where splitting creates
new opportunities for hoisting (e.g., negated conditions from else-splitting).
"""

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Block, Operation, Region
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
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


def is_classical_op(op: Operation) -> bool:
    """Check if an operation is classical (not phase or qif)."""
    return not isinstance(op, PhaseOp | QifOp)


def can_hoist(op: Operation, region: Region) -> bool:
    """Check if an operation can be hoisted out of a qif region."""
    if not is_classical_op(op):
        return False

    for operand in op.operands:
        defining_op = operand.owner
        if isinstance(defining_op, Operation) and region.is_ancestor(defining_op):
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
    """Split a qif with multiple quantum ops into single-op qifs."""

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


class HoistClassicalPattern(RewritePattern):
    """Hoist classical operations out of qif regions."""

    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter, /):
        parent_block = op.parent
        if parent_block is None:
            return

        parent_region = parent_block.parent
        if parent_region is None:
            return

        qif_op = parent_region.parent
        if not isinstance(qif_op, QifOp):
            return

        if not can_hoist(op, parent_region):
            return

        op.detach()
        insert_point = InsertPoint.before(qif_op)
        rewriter.insert(op, insert_point)


class SimplifyQifPass(ModulePass):
    """Simplify qif statements by splitting and hoisting."""

    name = "simplify-qif"

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        # Apply all patterns iteratively until no more changes
        from xdsl.pattern_rewriter import PatternRewriteWalker

        # Keep applying until no changes are made
        changed = True
        while changed:
            changed = False

            walker = PatternRewriteWalker(
                SplitQifElsePattern(),
                apply_recursively=True,
            )
            if walker.rewrite_module(op):
                changed = True

            walker = PatternRewriteWalker(
                SplitQifNoElsePattern(),
                apply_recursively=True,
            )
            if walker.rewrite_module(op):
                changed = True

            walker = PatternRewriteWalker(
                HoistClassicalPattern(),
                apply_recursively=True,
            )
            if walker.rewrite_module(op):
                changed = True
