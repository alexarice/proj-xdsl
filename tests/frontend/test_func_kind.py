"""Tests for FuncKind enumeration."""

from projxdsl.func_kind import FuncKind


class TestFuncKindOrdering:
    """Test FuncKind ordering for operation validation."""

    def test_pure_is_lowest(self):
        """Pure is the lowest kind - phase and if require UNITARY."""
        assert FuncKind.PURE < FuncKind.UNITARY
        assert FuncKind.PURE < FuncKind.MIXED

    def test_unitary_allows_phase_and_if(self):
        """Unitary functions allow phase and if (UNITARY <= UNITARY)."""
        assert FuncKind.UNITARY <= FuncKind.UNITARY
        # But not alloc or measure (require MIXED)
        assert FuncKind.UNITARY < FuncKind.MIXED

    def test_mixed_is_highest(self):
        """Mixed functions allow all operations."""
        assert FuncKind.MIXED >= FuncKind.PURE
        assert FuncKind.MIXED >= FuncKind.UNITARY
        assert FuncKind.MIXED >= FuncKind.MIXED

    def test_values_are_ordered(self):
        """Test that values follow the hierarchy order."""
        assert FuncKind.PURE.value == 1
        assert FuncKind.UNITARY.value == 2
        assert FuncKind.MIXED.value == 3
        assert FuncKind.PURE.value < FuncKind.UNITARY.value < FuncKind.MIXED.value


class TestFuncKindHierarchy:
    """Test FuncKind.__le__ method for hierarchy checking."""

    def test_reflexive(self):
        """Each kind is a subtype of itself."""
        assert FuncKind.PURE <= FuncKind.PURE
        assert FuncKind.UNITARY <= FuncKind.UNITARY
        assert FuncKind.MIXED <= FuncKind.MIXED

    def test_pure_is_subtype_of_all(self):
        """PURE is a subtype of all function kinds."""
        assert FuncKind.PURE <= FuncKind.PURE
        assert FuncKind.PURE <= FuncKind.UNITARY
        assert FuncKind.PURE <= FuncKind.MIXED

    def test_unitary_is_subtype_of_mixed(self):
        """UNITARY is a subtype of MIXED."""
        assert FuncKind.UNITARY <= FuncKind.MIXED
        assert not (FuncKind.UNITARY <= FuncKind.PURE)

    def test_mixed_is_not_subtype_of_others(self):
        """MIXED is not a subtype of PURE or UNITARY."""
        assert not (FuncKind.MIXED <= FuncKind.PURE)
        assert not (FuncKind.MIXED <= FuncKind.UNITARY)

    def test_transitivity(self):
        """Hierarchy is transitive: if A <= B and B <= C, then A <= C."""
        assert FuncKind.PURE <= FuncKind.UNITARY
        assert FuncKind.UNITARY <= FuncKind.MIXED
        assert FuncKind.PURE <= FuncKind.MIXED
