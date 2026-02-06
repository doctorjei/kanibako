"""Tests for clodbox.container."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from clodbox.container import ContainerRuntime, detect_claude_install
from clodbox.errors import ContainerError


class TestDetectClaudeInstall:
    def test_finds_claude_in_path(self, tmp_path):
        # Set up a fake claude installation
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        share_dir = tmp_path / "share" / "claude"
        share_dir.mkdir(parents=True)

        # Create a version file and symlink
        version_file = share_dir / "2.1.34"
        version_file.write_text("fake binary")
        claude_link = bin_dir / "claude"
        claude_link.symlink_to(version_file)

        with patch("shutil.which", return_value=str(claude_link)):
            result = detect_claude_install()
            assert result is not None
            assert result.binary == claude_link
            assert result.install_dir == share_dir

    def test_returns_none_when_not_found(self):
        with patch("shutil.which", return_value=None):
            result = detect_claude_install()
            assert result is None


class TestContainerRuntime:
    def test_detect_raises_when_nothing_found(self, monkeypatch):
        monkeypatch.delenv("CLODBOX_DOCKER_CMD", raising=False)
        with patch("shutil.which", return_value=None):
            with pytest.raises(ContainerError, match="No container runtime"):
                ContainerRuntime()

    def test_uses_env_override(self, monkeypatch):
        monkeypatch.setenv("CLODBOX_DOCKER_CMD", "/usr/bin/fake-docker")
        rt = ContainerRuntime()
        assert rt.cmd == "/usr/bin/fake-docker"

    def test_explicit_command(self):
        rt = ContainerRuntime(command="/usr/bin/podman")
        assert rt.cmd == "/usr/bin/podman"

    def test_guess_containerfile(self):
        assert ContainerRuntime._guess_containerfile("ghcr.io/x/clodbox-base:latest") == "base"
        assert ContainerRuntime._guess_containerfile("ghcr.io/x/clodbox-systems:v1") == "systems"
        assert ContainerRuntime._guess_containerfile("ghcr.io/x/clodbox-jvm:latest") == "jvm"
        assert ContainerRuntime._guess_containerfile("totally-unrelated:latest") is None
