"""Tests for the State enumeration and basis operations."""

from projxdsl.dialects.proj import Basis, State


class TestStateBasis:
    """Test State.get_basis() method."""

    def test_zero_basis(self):
        """Test that |0> returns Z basis."""
        assert State.ZERO.get_basis() == Basis.Z

    def test_one_basis(self):
        """Test that |1> returns Z basis."""
        assert State.ONE.get_basis() == Basis.Z

    def test_plus_basis(self):
        """Test that |+> returns X basis."""
        assert State.PLUS.get_basis() == Basis.X

    def test_minus_basis(self):
        """Test that |-> returns X basis."""
        assert State.MINUS.get_basis() == Basis.X

    def test_left_basis(self):
        """Test that |L> returns Y basis."""
        assert State.LEFT.get_basis() == Basis.Y

    def test_right_basis(self):
        """Test that |R> returns Y basis."""
        assert State.RIGHT.get_basis() == Basis.Y

    def test_all_states_have_basis(self):
        """Test that all states return a valid basis."""
        for state in State:
            basis = state.get_basis()
            assert isinstance(basis, Basis)
            assert basis in [Basis.X, Basis.Y, Basis.Z]
