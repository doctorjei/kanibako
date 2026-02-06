"""Extended tests for clodbox.container: ensure_image chain, run args, list_local_images."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from clodbox.container import ContainerRuntime, ClaudeInstall
from clodbox.errors import ContainerError


# ---------------------------------------------------------------------------
# ensure_image chain
# ---------------------------------------------------------------------------

class TestEnsureImage:
    def test_exists_locally(self):
        rt = ContainerRuntime(command="echo")
        with patch.object(rt, "image_exists", return_value=True) as m:
            rt.ensure_image("test:latest", Path("/containers"))
            m.assert_called_once_with("test:latest")

    def test_pull_succeeds(self):
        rt = ContainerRuntime(command="echo")
        with (
            patch.object(rt, "image_exists", return_value=False),
            patch.object(rt, "pull", return_value=True) as m_pull,
        ):
            rt.ensure_image("test:latest", Path("/containers"))
            m_pull.assert_called_once_with("test:latest")

    def test_pull_fails_build_fallback(self, tmp_path):
        rt = ContainerRuntime(command="echo")
        containers_dir = tmp_path / "containers"
        containers_dir.mkdir()
        (containers_dir / "Containerfile.base").write_text("FROM ubuntu\n")

        with (
            patch.object(rt, "image_exists", return_value=False),
            patch.object(rt, "pull", return_value=False),
            patch.object(rt, "build") as m_build,
        ):
            rt.ensure_image("clodbox-base:latest", containers_dir)
            m_build.assert_called_once()

    def test_no_containerfile_raises(self, tmp_path):
        rt = ContainerRuntime(command="echo")
        with (
            patch.object(rt, "image_exists", return_value=False),
            patch.object(rt, "pull", return_value=False),
        ):
            with pytest.raises(ContainerError, match="cannot determine Containerfile"):
                rt.ensure_image("unknown-image:latest", tmp_path)

    def test_unknown_image_no_file_raises(self, tmp_path):
        rt = ContainerRuntime(command="echo")
        containers_dir = tmp_path / "containers"
        containers_dir.mkdir()
        # No matching Containerfile for clodbox-base
        with (
            patch.object(rt, "image_exists", return_value=False),
            patch.object(rt, "pull", return_value=False),
        ):
            with pytest.raises(ContainerError, match="no local Containerfile"):
                rt.ensure_image("clodbox-base:latest", containers_dir)

    def test_build_fails_raises(self, tmp_path):
        rt = ContainerRuntime(command="echo")
        containers_dir = tmp_path / "containers"
        containers_dir.mkdir()
        (containers_dir / "Containerfile.base").write_text("FROM ubuntu\n")

        with (
            patch.object(rt, "image_exists", return_value=False),
            patch.object(rt, "pull", return_value=False),
            patch.object(rt, "build", side_effect=ContainerError("build failed")),
        ):
            with pytest.raises(ContainerError, match="build failed"):
                rt.ensure_image("clodbox-base:latest", containers_dir)


# ---------------------------------------------------------------------------
# run() command assembly
# ---------------------------------------------------------------------------

class TestRunCommandAssembly:
    def _make_rt(self):
        return ContainerRuntime(command="/usr/bin/podman")

    def test_volume_mounts(self):
        rt = self._make_rt()
        with patch("clodbox.container.subprocess.run") as m_run:
            m_run.return_value = MagicMock(returncode=0)
            rt.run(
                "img:latest",
                project_path=Path("/proj"),
                dot_path=Path("/dot"),
                cfg_file=Path("/cfg.json"),
            )
            cmd = m_run.call_args[0][0]
            # Check volume mounts
            assert "-v" in cmd
            assert "/proj:/home/agent/workspace:Z,U" in cmd
            assert "/dot:/home/agent/.claude:Z,U" in cmd
            assert "/cfg.json:/home/agent/.claude.json:Z,U" in cmd

    def test_entrypoint_override(self):
        rt = self._make_rt()
        with patch("clodbox.container.subprocess.run") as m_run:
            m_run.return_value = MagicMock(returncode=0)
            rt.run(
                "img:latest",
                project_path=Path("/proj"),
                dot_path=Path("/dot"),
                cfg_file=Path("/cfg.json"),
                entrypoint="/bin/bash",
            )
            cmd = m_run.call_args[0][0]
            idx = cmd.index("--entrypoint")
            assert cmd[idx + 1] == "/bin/bash"

    def test_no_entrypoint(self):
        rt = self._make_rt()
        with patch("clodbox.container.subprocess.run") as m_run:
            m_run.return_value = MagicMock(returncode=0)
            rt.run(
                "img:latest",
                project_path=Path("/proj"),
                dot_path=Path("/dot"),
                cfg_file=Path("/cfg.json"),
            )
            cmd = m_run.call_args[0][0]
            assert "--entrypoint" not in cmd

    def test_cli_args_appended(self):
        rt = self._make_rt()
        with patch("clodbox.container.subprocess.run") as m_run:
            m_run.return_value = MagicMock(returncode=0)
            rt.run(
                "img:latest",
                project_path=Path("/proj"),
                dot_path=Path("/dot"),
                cfg_file=Path("/cfg.json"),
                cli_args=["--continue", "--verbose"],
            )
            cmd = m_run.call_args[0][0]
            assert cmd[-2:] == ["--continue", "--verbose"]

    def test_claude_install_mounts(self):
        rt = self._make_rt()
        claude = ClaudeInstall(
            binary=Path("/home/user/.local/bin/claude"),
            install_dir=Path("/home/user/.local/share/claude"),
        )
        with patch("clodbox.container.subprocess.run") as m_run:
            m_run.return_value = MagicMock(returncode=0)
            rt.run(
                "img:latest",
                project_path=Path("/proj"),
                dot_path=Path("/dot"),
                cfg_file=Path("/cfg.json"),
                claude_install=claude,
            )
            cmd = m_run.call_args[0][0]
            # Check claude mounts are present
            assert "/home/user/.local/share/claude:/home/agent/.local/share/claude:ro" in cmd
            assert "/home/user/.local/bin/claude:/home/agent/.local/bin/claude:ro" in cmd

    def test_no_claude_install(self):
        rt = self._make_rt()
        with patch("clodbox.container.subprocess.run") as m_run:
            m_run.return_value = MagicMock(returncode=0)
            rt.run(
                "img:latest",
                project_path=Path("/proj"),
                dot_path=Path("/dot"),
                cfg_file=Path("/cfg.json"),
                claude_install=None,
            )
            cmd = m_run.call_args[0][0]
            # No claude-specific mounts
            cmd_str = " ".join(cmd)
            assert ".local/share/claude" not in cmd_str

    def test_cli_args_none(self):
        rt = self._make_rt()
        with patch("clodbox.container.subprocess.run") as m_run:
            m_run.return_value = MagicMock(returncode=0)
            rt.run(
                "img:latest",
                project_path=Path("/proj"),
                dot_path=Path("/dot"),
                cfg_file=Path("/cfg.json"),
                cli_args=None,
            )
            cmd = m_run.call_args[0][0]
            # Last element should be the image name
            assert cmd[-1] == "img:latest"


# ---------------------------------------------------------------------------
# list_local_images
# ---------------------------------------------------------------------------

class TestListLocalImages:
    def test_filters_clodbox(self):
        rt = ContainerRuntime(command="echo")
        output = (
            "ghcr.io/owner/clodbox-base:latest\t500MB\n"
            "docker.io/library/ubuntu:latest\t100MB\n"
            "ghcr.io/owner/clodbox-jvm:latest\t800MB\n"
        )
        with patch("clodbox.container.subprocess.run") as m_run:
            m_run.return_value = MagicMock(returncode=0, stdout=output)
            images = rt.list_local_images()
            assert len(images) == 2
            assert images[0][0] == "ghcr.io/owner/clodbox-base:latest"
            assert images[1][0] == "ghcr.io/owner/clodbox-jvm:latest"

    def test_empty_output(self):
        rt = ContainerRuntime(command="echo")
        with patch("clodbox.container.subprocess.run") as m_run:
            m_run.return_value = MagicMock(returncode=0, stdout="")
            images = rt.list_local_images()
            assert images == []

    def test_tab_parsing(self):
        rt = ContainerRuntime(command="echo")
        output = "ghcr.io/x/clodbox:latest\t1.2GB\n"
        with patch("clodbox.container.subprocess.run") as m_run:
            m_run.return_value = MagicMock(returncode=0, stdout=output)
            images = rt.list_local_images()
            assert len(images) == 1
            assert images[0] == ("ghcr.io/x/clodbox:latest", "1.2GB")
