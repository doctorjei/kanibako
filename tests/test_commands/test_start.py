"""Tests for kanibako.commands.start."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kanibako.commands.start import _run_container


class TestTargetWarnings:
    """Verify warnings when target detection fails."""

    def test_detect_returns_none_warns(self, start_mocks, capsys):
        """When detect() returns None, a warning should be printed."""
        with start_mocks() as m:
            m.target.detect.return_value = None
            _run_container(
                project_dir=None,
                entrypoint=None,
                image_override=None,
                new_session=False,
                safe_mode=False,
                resume_mode=False,
                extra_args=[],
            )

        captured = capsys.readouterr()
        assert "Warning:" in captured.err
        assert "binary not found" in captured.err

    def test_resolve_target_keyerror_warns(self, start_mocks, capsys):
        """When resolve_target() raises KeyError, a warning should be printed."""
        with start_mocks() as m:
            m.resolve_target.side_effect = KeyError("no target")
            _run_container(
                project_dir=None,
                entrypoint=None,
                image_override=None,
                new_session=False,
                safe_mode=False,
                resume_mode=False,
                extra_args=[],
            )

        captured = capsys.readouterr()
        assert "Warning:" in captured.err
        assert "No agent target found" in captured.err

    def test_detect_returns_none_still_launches(self, start_mocks):
        """Container should still launch even when detection fails."""
        with start_mocks() as m:
            m.target.detect.return_value = None
            rc = _run_container(
                project_dir=None,
                entrypoint=None,
                image_override=None,
                new_session=False,
                safe_mode=False,
                resume_mode=False,
                extra_args=[],
            )
            assert rc == 0
            m.runtime.run.assert_called_once()

    def test_keyerror_still_launches(self, start_mocks):
        """Container should still launch even when resolve_target fails."""
        with start_mocks() as m:
            m.resolve_target.side_effect = KeyError("no target")
            rc = _run_container(
                project_dir=None,
                entrypoint=None,
                image_override=None,
                new_session=False,
                safe_mode=False,
                resume_mode=False,
                extra_args=[],
            )
            assert rc == 0
            m.runtime.run.assert_called_once()

    def test_shell_mode_skips_target(self, start_mocks, capsys):
        """When entrypoint is set, target detection is skipped entirely."""
        with start_mocks() as m:
            m.resolve_target.side_effect = KeyError("should not be called")
            _run_container(
                project_dir=None,
                entrypoint="/bin/bash",
                image_override=None,
                new_session=False,
                safe_mode=False,
                resume_mode=False,
                extra_args=[],
            )

        captured = capsys.readouterr()
        assert "Warning:" not in captured.err


class TestCheckAuth:
    """Verify pre-launch auth check behavior."""

    def test_auth_failure_returns_1(self, start_mocks, capsys):
        """When check_auth() returns False, start returns 1."""
        with start_mocks() as m:
            m.target.check_auth.return_value = False
            rc = _run_container(
                project_dir=None,
                entrypoint=None,
                image_override=None,
                new_session=False,
                safe_mode=False,
                resume_mode=False,
                extra_args=[],
            )
            assert rc == 1
            m.runtime.run.assert_not_called()

        captured = capsys.readouterr()
        assert "Authentication failed" in captured.err

    def test_auth_success_proceeds(self, start_mocks):
        """When check_auth() returns True, container launches normally."""
        with start_mocks() as m:
            m.target.check_auth.return_value = True
            rc = _run_container(
                project_dir=None,
                entrypoint=None,
                image_override=None,
                new_session=False,
                safe_mode=False,
                resume_mode=False,
                extra_args=[],
            )
            assert rc == 0
            m.runtime.run.assert_called_once()

    def test_auth_skipped_without_install(self, start_mocks):
        """When detect() returns None, check_auth is not called."""
        with start_mocks() as m:
            m.target.detect.return_value = None
            rc = _run_container(
                project_dir=None,
                entrypoint=None,
                image_override=None,
                new_session=False,
                safe_mode=False,
                resume_mode=False,
                extra_args=[],
            )
            assert rc == 0
            m.target.check_auth.assert_not_called()

    def test_auth_skipped_in_shell_mode(self, start_mocks):
        """In shell mode (entrypoint set), check_auth is not called."""
        with start_mocks() as m:
            rc = _run_container(
                project_dir=None,
                entrypoint="/bin/bash",
                image_override=None,
                new_session=False,
                safe_mode=False,
                resume_mode=False,
                extra_args=[],
            )
            assert rc == 0
            m.target.check_auth.assert_not_called()


class TestStartArgs:
    """Verify CLI args are correctly passed through to container."""

    def test_claude_mode_adds_skip_permissions(self, start_mocks):
        """Default (no entrypoint) should inject --dangerously-skip-permissions."""
        with start_mocks() as m:
            _run_container(
                project_dir=None,
                entrypoint=None,
                image_override=None,
                new_session=False,
                safe_mode=False,
                resume_mode=False,
                extra_args=[],
            )

            call_kwargs = m.runtime.run.call_args
            cli_args = call_kwargs.kwargs.get("cli_args", [])
            assert "--dangerously-skip-permissions" in cli_args
            assert "--continue" in cli_args

    def test_safe_mode_skips_permissions(self, start_mocks):
        with start_mocks() as m:
            m.proj.is_new = True
            _run_container(
                project_dir=None,
                entrypoint=None,
                image_override=None,
                new_session=False,
                safe_mode=True,
                resume_mode=False,
                extra_args=[],
            )

            call_kwargs = m.runtime.run.call_args
            cli_args = call_kwargs.kwargs.get("cli_args") or []
            assert "--dangerously-skip-permissions" not in cli_args
