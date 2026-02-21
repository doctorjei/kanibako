"""Tests for AiderTarget."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from kanibako.targets.base import AgentInstall
from kanibako_target_aider import AiderTarget


class TestProperties:
    def test_name(self):
        assert AiderTarget().name == "aider"

    def test_display_name(self):
        assert AiderTarget().display_name == "Aider"


class TestDetect:
    def test_found(self, tmp_path):
        binary = tmp_path / "aider"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)

        with patch("shutil.which", return_value=str(binary)):
            result = AiderTarget().detect()

        assert result is not None
        assert isinstance(result, AgentInstall)
        assert result.name == "aider"
        assert result.binary == binary

    def test_not_found(self):
        with patch("shutil.which", return_value=None):
            assert AiderTarget().detect() is None


class TestBinaryMounts:
    def test_empty(self):
        install = AgentInstall(
            name="aider",
            binary=Path("/usr/bin/aider"),
            install_dir=Path("/usr/bin"),
        )
        assert AiderTarget().binary_mounts(install) == []


class TestInitHome:
    def test_noop(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        AiderTarget().init_home(home)
        # No agent-specific files created
        assert list(home.iterdir()) == []


class TestCredentials:
    def test_refresh_noop(self, tmp_path):
        AiderTarget().refresh_credentials(tmp_path)

    def test_writeback_noop(self, tmp_path):
        AiderTarget().writeback_credentials(tmp_path)


class TestBuildCliArgs:
    def _build(self, **overrides):
        defaults = dict(
            safe_mode=False, resume_mode=False,
            new_session=False, is_new_project=False,
            extra_args=[],
        )
        defaults.update(overrides)
        return AiderTarget().build_cli_args(**defaults)

    def test_default_auto_approve(self):
        args = self._build()
        assert "--yes" in args

    def test_safe_mode_no_auto_approve(self):
        args = self._build(safe_mode=True)
        assert "--yes" not in args

    def test_extra_args_passed_through(self):
        args = self._build(extra_args=["--model", "gpt-4"])
        assert "--model" in args
        assert "gpt-4" in args
