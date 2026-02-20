"""Tests for kanibako.cli main() exit codes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from kanibako.errors import KanibakoError, UserCancelled


def _fake_xdg(*args, **kwargs):
    """Return a mock Path whose / chain ends with .exists() → True."""
    p = MagicMock(spec=Path)
    p.__truediv__ = lambda self, other: p
    p.exists.return_value = True
    return p


class TestMainExitCodes:
    def test_user_cancelled_exits_2(self):
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_parser,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.side_effect = UserCancelled("nope")
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 2

    def test_kanibako_error_exits_1(self):
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_parser,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.side_effect = KanibakoError("boom")
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 1

    def test_keyboard_interrupt_exits_130(self):
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_parser,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.side_effect = KeyboardInterrupt()
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 130

    def test_success_exits_0(self):
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_parser,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.return_value = 0
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 0

    def test_nonzero_propagation(self):
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_parser,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.return_value = 42
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 42

    def test_no_command_defaults_to_start(self):
        """When no command given, main() prepends 'start' and parses once."""
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_bp,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            parser = MagicMock()
            mock_bp.return_value = parser

            with_cmd = MagicMock()
            with_cmd.command = "start"
            with_cmd.func.return_value = 0
            parser.parse_args.return_value = with_cmd

            main([])
        assert exc_info.value.code == 0
        parser.parse_args.assert_called_once_with(["start"])


class TestConfigPreCheck:
    def test_missing_config_exits_1(self, tmp_path, monkeypatch):
        """Running a non-setup command without config file exits 1."""
        from kanibako.cli import main

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no_config"))
        with pytest.raises(SystemExit) as exc_info:
            main(["start"])
        assert exc_info.value.code == 1

    def test_setup_exempt_from_config_check(self):
        """'setup' command does not fail on missing config."""
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_bp,
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "setup"
            args.func.return_value = 0
            mock_bp.return_value.parse_args.return_value = args
            main(["setup"])
        assert exc_info.value.code == 0
