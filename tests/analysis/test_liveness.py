"""Tests for projection liveness analysis."""

from typing import cast

from xdsl.ir import Block, Operation

from projxdsl.analysis.liveness import LivenessAnalysis
from projxdsl.dialects.proj import FuncOpBase, IfOp, ProjectionType
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


class TestLivenessBasic:
    """Basic liveness analysis tests."""

    def test_single_projection(self):
        """Test liveness for a single projection."""
        func = parse_function("""
pure fn test(q: qubit) -> proj {
    let p = q == |0>;
    p
}
""")
        liveness = LivenessAnalysis.compute(func)

        eq_ops = get_ops_by_name(func, "proj.eq")
        return_ops = get_ops_by_name(func, "proj.return")
        assert len(eq_ops) == 1
        assert len(return_ops) == 1

        eq_op = eq_ops[0]
        return_op = return_ops[0]

        # Before eq: nothing live (p not yet defined)
        assert len(liveness.get_live_before(eq_op)) == 0

        # After eq: p is live
        live_after_eq = liveness.get_live_after(eq_op)
        assert len(live_after_eq) == 1
        assert isinstance(list(live_after_eq)[0].type, ProjectionType)

        # Before return: p is live (will be returned)
        assert len(liveness.get_live_before(return_op)) == 1

        # After return: nothing live
        assert len(liveness.get_live_after(return_op)) == 0

    def test_multiple_projections(self):
        """Test liveness with multiple projections."""
        func = parse_function("""
pure fn test(q1: qubit, q2: qubit) -> proj {
    let p1 = q1 == |0>;
    let p2 = q2 == |1>;
    p1 && p2
}
""")
        liveness = LivenessAnalysis.compute(func)

        eq_ops = get_ops_by_name(func, "proj.eq")
        and_ops = get_ops_by_name(func, "proj.and")

        # After first eq (eq_ops[0]), only p1 is live
        assert len(liveness.get_live_after(eq_ops[0])) == 1

        # Before second eq (eq_ops[1]), p1 is live
        assert len(liveness.get_live_before(eq_ops[1])) == 1

        # After second eq (eq_ops[1]), both p1 and p2 are live
        assert len(liveness.get_live_after(eq_ops[1])) == 2

        # After and, only result is live
        assert len(and_ops) == 1
        assert len(liveness.get_live_after(and_ops[0])) == 1

    def test_projection_released(self):
        """Test that projections are released when no longer used."""
        func = parse_function("""
pure fn test(q: qubit) -> proj {
    let p1 = q == |0>;
    let p2 = q == |1>;
    p2
}
""")
        liveness = LivenessAnalysis.compute(func)

        eq_ops = get_ops_by_name(func, "proj.eq")

        # After first eq (eq_ops[0]), nothing is live (p1 never used)
        assert len(liveness.get_live_after(eq_ops[0])) == 0

        # Before second eq (eq_ops[1]), nothing is live (p1 dead, p2 not yet defined)
        assert len(liveness.get_live_before(eq_ops[1])) == 0

        # After second eq (eq_ops[1]), p2 is live
        assert len(liveness.get_live_after(eq_ops[1])) == 1


class TestLivenessCompound:
    """Tests for compound projection operations."""

    def test_and_operation(self):
        """Test liveness through and operation."""
        func = parse_function("""
pure fn test(q1: qubit, q2: qubit) -> proj {
    let p1 = q1 == |0>;
    let p2 = q2 == |1>;
    p1 && p2
}
""")
        liveness = LivenessAnalysis.compute(func)

        and_ops = get_ops_by_name(func, "proj.and")
        assert len(and_ops) == 1

        # Before and: p1 and p2 are live
        assert len(liveness.get_live_before(and_ops[0])) == 2

        # After and: only result is live
        assert len(liveness.get_live_after(and_ops[0])) == 1

    def test_not_operation(self):
        """Test liveness through not operation."""
        func = parse_function("""
pure fn test(q: qubit) -> proj {
    let p = q == |0>;
    !p
}
""")
        liveness = LivenessAnalysis.compute(func)

        not_ops = get_ops_by_name(func, "proj.not")
        assert len(not_ops) == 1

        # Before not: p is live
        assert len(liveness.get_live_before(not_ops[0])) == 1

        # After not: result is live
        assert len(liveness.get_live_after(not_ops[0])) == 1


class TestLivenessQifStatement:
    """Tests for liveness with qif statements."""

    def test_qif_statement(self):
        """Test liveness through qif statement."""
        func = parse_function("""
unitary fn test(q: qubit) {
    let p = q == |0>;
    qif p {
        ph(0);
    };
}
""")
        liveness = LivenessAnalysis.compute(func)

        qif_ops = get_ops_by_name(func, "proj.if")
        eq_ops = get_ops_by_name(func, "proj.eq")
        assert len(qif_ops) == 1
        assert len(eq_ops) == 1

        # Get operations inside qif region
        qif_op = cast(IfOp, qif_ops[0])
        true_block = qif_op.true_region.blocks[0]
        phase_ops = get_ops_in_block(true_block, "proj.phase")
        assert len(phase_ops) == 1

        # Before qif: p is live (used by the qif condition)
        assert len(liveness.get_live_before(qif_op)) == 1

        # After qif: p is dead (consumed by the qif)
        # Note: condition is live WITHIN the qif region, but not after
        assert len(liveness.get_live_after(qif_op)) == 0

        # Within qif region: p is live (condition persists through region)
        assert len(liveness.get_live_before(phase_ops[0])) == 1
        assert len(liveness.get_live_after(phase_ops[0])) == 1

        # After eq: p is live
        live_after_eq = liveness.get_live_after(eq_ops[0])
        assert len(live_after_eq) == 1
        assert isinstance(list(live_after_eq)[0].type, ProjectionType)

    def test_qif_statement_live_through(self):
        """Test that values live after qif are live in both regions."""
        func = parse_function("""
mixed fn test(q1: qubit, q2: qubit) -> proj {
    let p1 = q1 == |0>;
    let p2 = q2 == |1>;
    qif p2 {
        ph(0);
    };
    p1
}
""")
        liveness = LivenessAnalysis.compute(func)

        qif_ops = get_ops_by_name(func, "proj.if")
        eq_ops = get_ops_by_name(func, "proj.eq")
        return_ops = get_ops_by_name(func, "proj.return")
        assert len(qif_ops) == 1
        assert len(eq_ops) == 2
        assert len(return_ops) == 1

        # p1 is defined by eq_ops[0], p2 by eq_ops[1]
        p2_eq = eq_ops[1]
        qif_op = qif_ops[0]
        return_op = return_ops[0]

        # After p2 eq: both p1 and p2 are live
        assert len(liveness.get_live_after(p2_eq)) == 2

        # After qif: only p1 is live (p2 consumed by qif)
        assert len(liveness.get_live_after(qif_op)) == 1

        # Before qif: p1 is live (flows through), p2 is live (used by condition)
        assert len(liveness.get_live_before(qif_op)) == 2

        # Before return: p1 is live
        assert len(liveness.get_live_before(return_op)) == 1


class TestLivenessAnalysis:
    """Tests for LivenessAnalysis helper methods."""

    def test_is_live_before_and_after(self):
        """Test is_live_before and is_live_after methods."""
        func = parse_function("""
pure fn test(q: qubit) -> proj {
    let p = q == |0>;
    p
}
""")
        liveness = LivenessAnalysis.compute(func)

        eq_ops = get_ops_by_name(func, "proj.eq")
        assert len(eq_ops) == 1
        eq_op = eq_ops[0]

        # p should be live after eq
        live_projs = [
            v
            for v in liveness.get_live_after(eq_op)
            if isinstance(v.type, ProjectionType)
        ]
        assert len(live_projs) == 1
        assert liveness.is_live_after(eq_op, live_projs[0])

        # p should not be live before eq (not yet defined)
        assert len(liveness.get_live_before(eq_op)) == 0

    def test_get_live_before(self):
        """Test get_live_before method."""
        func = parse_function("""
pure fn test(q: qubit) -> proj {
    let p = q == |0>;
    p
}
""")
        liveness = LivenessAnalysis.compute(func)

        return_ops = get_ops_by_name(func, "proj.return")
        assert len(return_ops) == 1
        return_op = return_ops[0]

        # p should be live before return
        assert len(liveness.get_live_before(return_op)) == 1
