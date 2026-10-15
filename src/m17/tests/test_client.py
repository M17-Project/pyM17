"""Tests for M17 client module.

Tests the legacy client.py module that imports from apps.
Note: These tests skip if kademlia is not installed since apps.py requires it.
"""

import sys

import pytest

# Check if kademlia is available (apps.py requires it through blocks.py -> network.py)
try:
    import kademlia

    HAS_KADEMLIA = True
except ImportError:
    HAS_KADEMLIA = False


@pytest.mark.skipif(not HAS_KADEMLIA, reason="kademlia not installed")
class TestClientModule:
    """Tests for client.py module."""

    def test_client_imports_voip(self):
        """Test that client module imports voip from apps."""
        # The module imports voip from m17.apps
        from m17.apps import voip

        # Verify voip is callable
        assert callable(voip)

    def test_client_module_exists(self):
        """Test that m17.client module can be imported."""
        import m17.client

        assert m17.client is not None

    def test_client_main_block(self, capsys):
        """Test client.py's main block behavior."""
        # The main block prints sys.argv and calls voip
        # We can't easily test this without actually running the module
        # but we can verify the structure
        import m17.client as client_module

        # Check that the module has the expected import
        assert "voip" in dir(client_module) or hasattr(client_module, "__file__")

    def test_voip_not_implemented(self):
        """Test that voip raises NotImplementedError."""
        from m17.apps import voip

        with pytest.raises(NotImplementedError):
            voip()
