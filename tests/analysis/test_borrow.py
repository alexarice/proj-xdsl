"""Tests for projection borrow analysis."""

from typing import cast

import pytest
from xdsl.ir import Block, Operation

from projxdsl.analysis.borrow import BorrowError, BorrowType, compute_borrows
from projxdsl.analysis.liveness import compute_liveness
from projxdsl.dialects.proj import EqOp, FuncOpBase, IfOp, PhaseOp
from projxdsl.frontend.parser import ProjParser


def parse_function(code: str) -> FuncOpBase:
    """Helper to parse a function from code string."""
    parser = ProjParser(code)
    return parser.parse_func()


def get_ops_by_name(func: FuncOpBase, name: str) -> list[Operation]:
    """Helper to get operations by name from a function."""
    block = func.body.blocks[0]
    return [op for op in block.ops if op.name == name]


def get_ops_in_block(block: Block, name: str) -> list[Operation]:
    """Helper to get operations by name in a block."""
    return [op for op in block.ops if op.name == name]


class TestBorrowBasic:
    """Basic borrow analysis tests."""

    def test_single_projection(self):
        """Test borrow for a single projection."""
        func = parse_function("""
pure fn test(q: qubit) -> proj {
    let p = q == |0>;
    p
}
""")
        liveness = compute_liveness(func)
        borrows = compute_borrows(func, liveness)

        eq_ops = get_ops_by_name(func, "proj.eq")
        assert len(eq_ops) == 1
        eq_op = cast(EqOp, eq_ops[0])

        # After eq: qubit is borrowed in Z basis by p
        state_after = borrows.get_state_after(eq_op)
        assert state_after.is_borrowed(eq_op.qubit)
        borrow_info = state_after.get(eq_op.qubit)
        assert borrow_info is not None
        assert borrow_info.borrow_type == BorrowType.Z
        assert eq_op.result in borrow_info.projections


class TestBorrowIfStatement:
    """Tests for borrow analysis with if statements."""

    def test_if_statement_borrow_persists(self):
        """Test that condition borrow persists through if regions."""
        func = parse_function("""
unitary fn test(q: qubit) {
    let p = q == |0>;
    if p {
        ph(0)
    }
}
""")
        liveness = compute_liveness(func)
        borrows = compute_borrows(func, liveness)

        if_ops = get_ops_by_name(func, "proj.if")
        eq_ops = get_ops_by_name(func, "proj.eq")
        assert len(if_ops) == 1
        assert len(eq_ops) == 1

        # After eq: qubit is borrowed in Z basis by p
        eq_op = cast(EqOp, eq_ops[0])
        state_after_eq = borrows.get_state_after(eq_op)
        assert state_after_eq.is_borrowed(eq_op.qubit)
        borrow_info = state_after_eq.get(eq_op.qubit)
        assert borrow_info is not None
        assert borrow_info.borrow_type == BorrowType.Z

        # Within if region: borrow should still be active
        if_op = cast(IfOp, if_ops[0])
        true_block = if_op.true_region.blocks[0]
        phase_ops = get_ops_in_block(true_block, "proj.phase")
        assert len(phase_ops) == 1
        phase_op = cast(PhaseOp, phase_ops[0])

        # Before phase: qubit should still be borrowed by p
        state_before_phase = borrows.get_state_before(phase_op)
        assert state_before_phase.is_borrowed(eq_op.qubit)
        borrow_info = state_before_phase.get(eq_op.qubit)
        assert borrow_info is not None
        assert eq_op.result in borrow_info.projections

    @pytest.mark.xfail(reason="if-else not yet supported in parser")
    def test_if_else_borrow_persists(self):
        """Test that condition borrow persists through both if and else regions."""
        func = parse_function("""
unitary fn test(q1: qubit, q2: qubit) {
    let p = q1 == |0>;
    if p {
        ph(0)
    } else {
        ph(0.5*pi)
    }
}
""")
        liveness = compute_liveness(func)
        borrows = compute_borrows(func, liveness)

        if_ops = get_ops_by_name(func, "proj.if")
        eq_ops = get_ops_by_name(func, "proj.eq")
        assert len(if_ops) == 1
        assert len(eq_ops) == 1

        if_op = cast(IfOp, if_ops[0])
        eq_op = cast(EqOp, eq_ops[0])

        # Check true region
        true_block = if_op.true_region.blocks[0]
        true_phase_ops = get_ops_in_block(true_block, "proj.phase")
        assert len(true_phase_ops) == 1

        state_before_true_phase = borrows.get_state_before(true_phase_ops[0])
        assert state_before_true_phase.is_borrowed(eq_op.qubit)

        # Check false region
        false_block = if_op.false_region.blocks[0]
        false_phase_ops = get_ops_in_block(false_block, "proj.phase")
        assert len(false_phase_ops) == 1

        state_before_false_phase = borrows.get_state_before(false_phase_ops[0])
        assert state_before_false_phase.is_borrowed(eq_op.qubit)

    def test_if_statement_conflicting_borrow(self):
        """Test that conflicting borrows in if region are detected."""
        func = parse_function("""
unitary fn test(q: qubit) {
    let p = q == |0>;
    if p {
        let p2 = q == |+>;
        ph(0)
    }
}
""")
        liveness = compute_liveness(func)

        # Should raise BorrowError due to conflicting basis borrows (Z vs X)
        with pytest.raises(BorrowError, match="Cannot borrow qubit in X basis"):
            compute_borrows(func, liveness)

    @pytest.mark.xfail(reason="if-else not yet supported in parser")
    def test_if_else_conflicting_borrows(self):
        """Test that conflicting borrows between if/else are detected."""
        # Note: This test would check cross-region borrow conflicts
        # For now, just mark as xfail since parser doesn't support else
        pytest.fail("Parser does not support if-else yet")


class TestBorrowReturn:
    """Tests for borrow analysis with return statements."""

    def test_return_with_borrowed_local_qubit(self):
        """Test that returning with a borrowed local qubit raises an error."""
        func = parse_function("""
mixed fn test() -> proj {
    let q = alloc |0>;
    let p = q == |0>;
    p
}
""")
        liveness = compute_liveness(func)

        # Should raise BorrowError because q is locally allocated and still borrowed
        with pytest.raises(BorrowError, match="Locally allocated qubit"):
            compute_borrows(func, liveness)

    def test_return_without_borrowed_local_qubit(self):
        """Test that returning without borrowed local qubits is fine."""
        func = parse_function("""
mixed fn test() {
    let q = alloc |0>;
    let p = q == |0>;
    if p {
        ph(0)
    }
}
""")
        liveness = compute_liveness(func)

        # This should not raise an error (p is consumed by if, q not borrowed at return)
        borrows = compute_borrows(func, liveness)
        assert borrows is not None

    def test_return_with_parameter_qubit(self):
        """Test that returning with borrowed parameter qubit is fine."""
        func = parse_function("""
pure fn test(q: qubit) -> proj {
    let p = q == |0>;
    p
}
""")
        liveness = compute_liveness(func)

        # This should not raise an error (q is a parameter, not locally allocated)
        borrows = compute_borrows(func, liveness)
        assert borrows is not None
