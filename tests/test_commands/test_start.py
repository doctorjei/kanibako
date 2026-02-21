"""Tests for kanibako.commands.start."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestStartArgs:
    """Verify CLI args are correctly passed through to container."""

    def test_claude_mode_adds_skip_permissions(self):
        """Default (no entrypoint) should inject --dangerously-skip-permissions."""
        from kanibako.commands.start import _run_container
        from kanibako.paths import ProjectMode

        # We can't run a real container, but we can test the arg assembly
        # by mocking the runtime and checking what gets passed.
        with (
            patch("kanibako.commands.start.load_config"),
            patch("kanibako.commands.start.load_std_paths"),
            patch("kanibako.commands.start.resolve_any_project") as mock_resolve_any,
            patch("kanibako.commands.start.load_merged_config") as mock_merged,
            patch("kanibako.commands.start.ContainerRuntime") as MockRT,
            patch("kanibako.commands.start.refresh_host_to_central"),
            patch("kanibako.commands.start.refresh_central_to_project"),
            patch("kanibako.commands.start.writeback_project_to_central_and_host"),
            patch("kanibako.commands.start.fcntl"),
            patch("builtins.open", MagicMock()),
        ):
            proj = MagicMock()
            proj.is_new = False
            proj.mode = ProjectMode.account_centric
            proj.settings_path = MagicMock()
            proj.settings_path.__truediv__ = MagicMock(return_value=MagicMock())
            proj.dot_path.__truediv__ = MagicMock(return_value=MagicMock())
            mock_resolve_any.return_value = proj

            merged = MagicMock()
            merged.container_image = "test:latest"
            mock_merged.return_value = merged

            runtime = MagicMock()
            runtime.run.return_value = 0
            MockRT.return_value = runtime

            _run_container(
                project_dir=None,
                entrypoint=None,
                image_override=None,
                new_session=False,
                safe_mode=False,
                resume_mode=False,
                extra_args=[],
            )

            call_kwargs = runtime.run.call_args
            cli_args = call_kwargs.kwargs.get("cli_args", [])
            assert "--dangerously-skip-permissions" in cli_args
            assert "--continue" in cli_args

    def test_safe_mode_skips_permissions(self):
        from kanibako.commands.start import _run_container
        from kanibako.paths import ProjectMode

        with (
            patch("kanibako.commands.start.load_config"),
            patch("kanibako.commands.start.load_std_paths"),
            patch("kanibako.commands.start.resolve_any_project") as mock_resolve_any,
            patch("kanibako.commands.start.load_merged_config") as mock_merged,
            patch("kanibako.commands.start.ContainerRuntime") as MockRT,
            patch("kanibako.commands.start.refresh_host_to_central"),
            patch("kanibako.commands.start.refresh_central_to_project"),
            patch("kanibako.commands.start.writeback_project_to_central_and_host"),
            patch("kanibako.commands.start.fcntl"),
            patch("builtins.open", MagicMock()),
        ):
            proj = MagicMock()
            proj.is_new = True
            proj.mode = ProjectMode.account_centric
            proj.settings_path = MagicMock()
            proj.settings_path.__truediv__ = MagicMock(return_value=MagicMock())
            proj.dot_path.__truediv__ = MagicMock(return_value=MagicMock())
            mock_resolve_any.return_value = proj

            merged = MagicMock()
            merged.container_image = "test:latest"
            mock_merged.return_value = merged

            runtime = MagicMock()
            runtime.run.return_value = 0
            MockRT.return_value = runtime

            _run_container(
                project_dir=None,
                entrypoint=None,
                image_override=None,
                new_session=False,
                safe_mode=True,
                resume_mode=False,
                extra_args=[],
            )

            call_kwargs = runtime.run.call_args
            cli_args = call_kwargs.kwargs.get("cli_args") or []
            assert "--dangerously-skip-permissions" not in cli_args
