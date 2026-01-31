"""Tests for clodbox.cli main() exit codes."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from clodbox.errors import ClodboxError, UserCancelled


class TestMainExitCodes:
    def test_user_cancelled_exits_2(self):
        from clodbox.cli import main

        with (
            patch("clodbox.cli.build_parser") as mock_parser,
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.side_effect = UserCancelled("nope")
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 2

    def test_clodbox_error_exits_1(self):
        from clodbox.cli import main

        with (
            patch("clodbox.cli.build_parser") as mock_parser,
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.side_effect = ClodboxError("boom")
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 1

    def test_keyboard_interrupt_exits_130(self):
        from clodbox.cli import main

        with (
            patch("clodbox.cli.build_parser") as mock_parser,
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.side_effect = KeyboardInterrupt()
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 130

    def test_success_exits_0(self):
        from clodbox.cli import main

        with (
            patch("clodbox.cli.build_parser") as mock_parser,
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.return_value = 0
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 0

    def test_nonzero_propagation(self):
        from clodbox.cli import main

        with (
            patch("clodbox.cli.build_parser") as mock_parser,
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
        from clodbox.cli import main

        with (
            patch("clodbox.cli.build_parser") as mock_bp,
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
