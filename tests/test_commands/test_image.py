"""Tests for clodbox.commands.image."""

from __future__ import annotations

import argparse

import pytest

from clodbox.config import load_config
from clodbox.paths import load_std_paths, resolve_project


class TestImage:
    def test_runs_without_error(self, config_file, tmp_home, credentials_dir, capsys):
        """Smoke test: image list runs without crashing."""
        from clodbox.commands.image import run_list

        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        resolve_project(std, config, project_dir=project_dir, initialize=True)

        args = argparse.Namespace(project=project_dir)
        rc = run_list(args)
        assert rc == 0

        captured = capsys.readouterr()
        assert "Current image:" in captured.out


class TestImageRebuild:
    def test_rebuild_one_success(self, tmp_home, config_file, credentials_dir, capsys):
        """Test rebuilding a single image."""
        from unittest.mock import MagicMock, patch
        from clodbox.commands.image import run_rebuild

        # Create containers dir with a Containerfile
        from clodbox.config import load_config
        from clodbox.paths import load_std_paths
        config = load_config(config_file)
        std = load_std_paths(config)
        containers_dir = std.data_path / "containers"
        containers_dir.mkdir(parents=True, exist_ok=True)
        (containers_dir / "Containerfile.base").write_text("FROM ubuntu\n")

        with patch("clodbox.commands.image.ContainerRuntime") as MockRT:
            runtime = MagicMock()
            runtime.guess_containerfile.return_value = "base"
            runtime.rebuild.return_value = 0
            MockRT.return_value = runtime

            args = argparse.Namespace(image="clodbox-base:latest", all_images=False)
            rc = run_rebuild(args)
            assert rc == 0
            runtime.rebuild.assert_called_once()

    def test_rebuild_unknown_image(self, tmp_home, config_file, credentials_dir, capsys):
        """Test error when image pattern is unknown."""
        from unittest.mock import MagicMock, patch
        from clodbox.commands.image import run_rebuild

        from clodbox.config import load_config
        from clodbox.paths import load_std_paths
        config = load_config(config_file)
        std = load_std_paths(config)
        containers_dir = std.data_path / "containers"
        containers_dir.mkdir(parents=True, exist_ok=True)

        with patch("clodbox.commands.image.ContainerRuntime") as MockRT:
            runtime = MagicMock()
            runtime.guess_containerfile.return_value = None
            MockRT.return_value = runtime

            args = argparse.Namespace(image="unknown:latest", all_images=False)
            rc = run_rebuild(args)
            assert rc == 1
            captured = capsys.readouterr()
            assert "cannot determine Containerfile" in captured.err

    def test_rebuild_all(self, tmp_home, config_file, credentials_dir, capsys):
        """Test rebuilding all local images."""
        from unittest.mock import MagicMock, patch
        from clodbox.commands.image import run_rebuild

        from clodbox.config import load_config
        from clodbox.paths import load_std_paths
        config = load_config(config_file)
        std = load_std_paths(config)
        containers_dir = std.data_path / "containers"
        containers_dir.mkdir(parents=True, exist_ok=True)
        (containers_dir / "Containerfile.base").write_text("FROM ubuntu\n")
        (containers_dir / "Containerfile.jvm").write_text("FROM ubuntu\n")

        with patch("clodbox.commands.image.ContainerRuntime") as MockRT:
            runtime = MagicMock()
            runtime.list_local_images.return_value = [
                ("ghcr.io/foo/clodbox-base:latest", "1GB"),
                ("ghcr.io/foo/clodbox-jvm:latest", "2GB"),
            ]
            runtime.guess_containerfile.side_effect = ["base", "jvm"]
            runtime.rebuild.return_value = 0
            MockRT.return_value = runtime

            args = argparse.Namespace(image=None, all_images=True)
            rc = run_rebuild(args)
            assert rc == 0
            assert runtime.rebuild.call_count == 2


class TestExtractGhcrOwner:
    def test_valid_ghcr_url(self):
        from clodbox.commands.image import _extract_ghcr_owner

        assert _extract_ghcr_owner("ghcr.io/doctorjei/clodbox-base:latest") == "doctorjei"

    def test_non_ghcr_url(self):
        from clodbox.commands.image import _extract_ghcr_owner

        assert _extract_ghcr_owner("docker.io/library/ubuntu:latest") is None
