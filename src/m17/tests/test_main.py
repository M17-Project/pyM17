"""Tests for M17 __main__ module.

Tests the CLI entry point and help text display.
"""

import pytest


class TestMain:
    """Tests for __main__.py module."""

    def test_main_prints_help(self, capsys):
        """Test that main() prints help text."""
        from m17.__main__ import main

        main()
        captured = capsys.readouterr()

        # Check key help text elements
        assert "python -m m17" in captured.out
        assert "m17.address" in captured.out
        assert "Examples:" in captured.out

    def test_helptext_content(self):
        """Test that helptext contains expected content."""
        from m17.__main__ import helptext

        assert "python -m m17.address" in helptext
        assert "python -m m17.audio_test" in helptext
        assert "pip install m17[Codec2]" in helptext
        assert "m17ref_client" in helptext

    def test_main_callable(self):
        """Test that main is callable without errors."""
        from m17.__main__ import main

        # Should not raise
        try:
            main()
        except SystemExit:
            pass  # OK if it exits

    def test_module_runnable(self, capsys):
        """Test running as module produces output."""
        import runpy

        try:
            runpy.run_module("m17.__main__", run_name="__main__", alter_sys=True)
        except SystemExit:
            pass

        captured = capsys.readouterr()
        # Should have printed something
        assert len(captured.out) > 0 or len(captured.err) > 0
