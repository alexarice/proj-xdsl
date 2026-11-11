"""
Function inlining pass for proj-xdsl.

Inlines proj.call operations by replacing them with the callee's body operations.
Preserves the single-block constraint of FuncOpBase by cloning operations
directly into the caller block with argument substitution.
"""

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint
from xdsl.traits import SymbolTable

from projxdsl.dialects.proj.ops import CallOp, FuncOpBase, ReturnOp


class FuncInlinePattern(RewritePattern):
    """Pattern that inlines a proj.call by replacing it with the callee's body."""

    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: CallOp, rewriter: PatternRewriter, /):
        callee = SymbolTable.lookup_symbol(op, op.callee)

        if not isinstance(callee, FuncOpBase):
            return

        # Clone the region to get a cloned block with properly mapped args/ops
        cloned_region = callee.body.clone()
        callee_block = cloned_region.blocks.first
        if callee_block is None:
            return

        return_op = callee_block.ops.last
        if return_op is None or not isinstance(return_op, ReturnOp):
            return

        # Inline the cloned block before the call, substituting arguments
        rewriter.inline_block(callee_block, InsertPoint.before(op), op.arguments)

        # The return op is now inlined; get its arguments (which are now mapped)
        inlined_return = op.prev_op
        if inlined_return is None or not isinstance(inlined_return, ReturnOp):
            return

        return_args = list(inlined_return.arguments)

        # Erase the inlined return op
        rewriter.erase(inlined_return, safe_erase=False)

        # Replace call with return arguments
        rewriter.replace(op, [], return_args)


class FuncInlinePass(ModulePass):
    """Function inlining pass for proj-xdsl."""

    name = "func-inline"

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            FuncInlinePattern(),
            apply_recursively=False,
        ).rewrite_module(op)
