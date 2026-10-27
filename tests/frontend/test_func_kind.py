"""Tests for FuncKind enumeration."""

from projxdsl.frontend.func_kind import FuncKind


class TestFuncKindAllowsOperation:
    """Test FuncKind.allows_operation method."""

    def test_pure_allows_nothing(self):
        """Pure functions don't allow phase, if, alloc, or measure."""
        assert not FuncKind.PURE.allows_operation("phase")
        assert not FuncKind.PURE.allows_operation("if")
        assert not FuncKind.PURE.allows_operation("alloc")
        assert not FuncKind.PURE.allows_operation("measure")

    def test_unitary_allows_phase_and_if(self):
        """Unitary functions allow phase and if, but not alloc or measure."""
        assert FuncKind.UNITARY.allows_operation("phase")
        assert FuncKind.UNITARY.allows_operation("if")
        assert not FuncKind.UNITARY.allows_operation("alloc")
        assert not FuncKind.UNITARY.allows_operation("measure")

    def test_mixed_allows_all(self):
        """Mixed functions allow all operations."""
        assert FuncKind.MIXED.allows_operation("phase")
        assert FuncKind.MIXED.allows_operation("if")
        assert FuncKind.MIXED.allows_operation("alloc")
        assert FuncKind.MIXED.allows_operation("measure")

    def test_unknown_operation(self):
        """Unknown operations should be allowed by default."""
        assert FuncKind.PURE.allows_operation("unknown")
        assert FuncKind.UNITARY.allows_operation("unknown")
        assert FuncKind.MIXED.allows_operation("unknown")

    def test_value_property(self):
        """Test that value property returns correct string."""
        assert FuncKind.PURE.value == "pure"
        assert FuncKind.UNITARY.value == "unitary"
        assert FuncKind.MIXED.value == "mixed"
