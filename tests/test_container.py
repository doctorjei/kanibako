"""Tests for kanibako.container."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from kanibako.container import ContainerRuntime, detect_claude_install
from kanibako.errors import ContainerError


class TestDetectClaudeInstall:
    def test_flat_layout(self, tmp_path):
        """Older layout: ~/.local/share/claude/2.1.34 (no versions/ subdir)."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        claude_dir = tmp_path / "share" / "claude"
        claude_dir.mkdir(parents=True)

        version_file = claude_dir / "2.1.34"
        version_file.write_text("fake binary")
        claude_link = bin_dir / "claude"
        claude_link.symlink_to(version_file)

        with patch("shutil.which", return_value=str(claude_link)):
            result = detect_claude_install()
            assert result is not None
            assert result.binary == claude_link
            assert result.install_dir == claude_dir

    def test_versions_layout(self, tmp_path):
        """Newer layout: ~/.local/share/claude/versions/2.1.34."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        claude_dir = tmp_path / "share" / "claude"
        versions_dir = claude_dir / "versions"
        versions_dir.mkdir(parents=True)

        version_file = versions_dir / "2.1.34"
        version_file.write_text("fake binary")
        claude_link = bin_dir / "claude"
        claude_link.symlink_to(version_file)

        with patch("shutil.which", return_value=str(claude_link)):
            result = detect_claude_install()
            assert result is not None
            assert result.binary == claude_link
            assert result.install_dir == claude_dir

    def test_deep_nesting_layout(self, tmp_path):
        """Future-proof: walks up any depth to find 'claude' directory."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        claude_dir = tmp_path / "share" / "claude"
        deep_dir = claude_dir / "versions" / "stable"
        deep_dir.mkdir(parents=True)

        version_file = deep_dir / "2.2.0"
        version_file.write_text("fake binary")
        claude_link = bin_dir / "claude"
        claude_link.symlink_to(version_file)

        with patch("shutil.which", return_value=str(claude_link)):
            result = detect_claude_install()
            assert result is not None
            assert result.binary == claude_link
            assert result.install_dir == claude_dir

    def test_fallback_when_no_claude_dir(self, tmp_path):
        """Falls back to resolved parent if 'claude' dir not in path."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        weird_dir = tmp_path / "opt" / "something"
        weird_dir.mkdir(parents=True)

        version_file = weird_dir / "claude-binary"
        version_file.write_text("fake binary")
        claude_link = bin_dir / "claude"
        claude_link.symlink_to(version_file)

        with patch("shutil.which", return_value=str(claude_link)):
            result = detect_claude_install()
            assert result is not None
            assert result.binary == claude_link
            assert result.install_dir == weird_dir

    def test_returns_none_when_not_found(self):
        with patch("shutil.which", return_value=None):
            result = detect_claude_install()
            assert result is None


class TestContainerRuntime:
    def test_detect_raises_when_nothing_found(self, monkeypatch):
        monkeypatch.delenv("KANIBAKO_DOCKER_CMD", raising=False)
        with patch("shutil.which", return_value=None):
            with pytest.raises(ContainerError, match="No container runtime"):
                ContainerRuntime()

    def test_uses_env_override(self, monkeypatch):
        monkeypatch.setenv("KANIBAKO_DOCKER_CMD", "/usr/bin/fake-docker")
        rt = ContainerRuntime()
        assert rt.cmd == "/usr/bin/fake-docker"

    def test_explicit_command(self):
        rt = ContainerRuntime(command="/usr/bin/podman")
        assert rt.cmd == "/usr/bin/podman"

    def test_guess_containerfile(self):
        assert ContainerRuntime._guess_containerfile("ghcr.io/x/kanibako-base:latest") == "base"
        assert ContainerRuntime._guess_containerfile("ghcr.io/x/kanibako-systems:v1") == "systems"
        assert ContainerRuntime._guess_containerfile("ghcr.io/x/kanibako-jvm:latest") == "jvm"
        assert ContainerRuntime._guess_containerfile("totally-unrelated:latest") is None


class TestGetLocalDigest:
    def test_success_podman_format(self):
        """Podman returns a list; extract digest from RepoDigests."""
        import json
        rt = ContainerRuntime(command="echo")
        inspect_output = json.dumps([{
            "RepoDigests": ["ghcr.io/x/kanibako-base@sha256:abc123"]
        }])
        from unittest.mock import MagicMock
        with patch("kanibako.container.subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=inspect_output)
            result = rt.get_local_digest("ghcr.io/x/kanibako-base:latest")
        assert result == "sha256:abc123"

    def test_failure_returns_none(self):
        rt = ContainerRuntime(command="echo")
        from unittest.mock import MagicMock
        with patch("kanibako.container.subprocess.run") as m:
            m.return_value = MagicMock(returncode=1, stdout="")
            result = rt.get_local_digest("nonexistent:latest")
        assert result is None

    def test_empty_repo_digests(self):
        """Locally-built images may have no RepoDigests."""
        import json
        rt = ContainerRuntime(command="echo")
        inspect_output = json.dumps([{"RepoDigests": []}])
        from unittest.mock import MagicMock
        with patch("kanibako.container.subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=inspect_output)
            result = rt.get_local_digest("local:latest")
        assert result is None

    def test_exception_returns_none(self):
        """Any unexpected exception returns None."""
        rt = ContainerRuntime(command="echo")
        with patch("kanibako.container.subprocess.run", side_effect=OSError("fail")):
            result = rt.get_local_digest("img:latest")
        assert result is None


class TestRunEnvFlags:
    """Test that run() emits -e flags from the env parameter."""

    def test_env_flags_emitted(self):
        from unittest.mock import MagicMock
        rt = ContainerRuntime(command="/usr/bin/podman")
        with patch("kanibako.container.subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            rt.run(
                "test:latest",
                shell_path=Path("/tmp/shell"),
                project_path=Path("/tmp/project"),
                vault_ro_path=Path("/tmp/vault-ro"),
                vault_rw_path=Path("/tmp/vault-rw"),
                vault_enabled=False,
                env={"EDITOR": "vim", "NODE_ENV": "development"},
            )
            cmd = m.call_args[0][0]
            # env flags should appear as -e KEY=VALUE pairs
            assert "-e" in cmd
            idx_editor = cmd.index("EDITOR=vim")
            assert cmd[idx_editor - 1] == "-e"
            idx_node = cmd.index("NODE_ENV=development")
            assert cmd[idx_node - 1] == "-e"

    def test_env_none_no_flags(self):
        from unittest.mock import MagicMock
        rt = ContainerRuntime(command="/usr/bin/podman")
        with patch("kanibako.container.subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            rt.run(
                "test:latest",
                shell_path=Path("/tmp/shell"),
                project_path=Path("/tmp/project"),
                vault_ro_path=Path("/tmp/vault-ro"),
                vault_rw_path=Path("/tmp/vault-rw"),
                vault_enabled=False,
                env=None,
            )
            cmd = m.call_args[0][0]
            assert "-e" not in cmd

    def test_env_empty_dict_no_flags(self):
        from unittest.mock import MagicMock
        rt = ContainerRuntime(command="/usr/bin/podman")
        with patch("kanibako.container.subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            rt.run(
                "test:latest",
                shell_path=Path("/tmp/shell"),
                project_path=Path("/tmp/project"),
                vault_ro_path=Path("/tmp/vault-ro"),
                vault_rw_path=Path("/tmp/vault-rw"),
                vault_enabled=False,
                env={},
            )
            cmd = m.call_args[0][0]
            assert "-e" not in cmd
