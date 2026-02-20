"""Tests for kanibako.commands.archive."""

from __future__ import annotations

import argparse
import tarfile
from pathlib import Path

import pytest

from kanibako.config import load_config, write_global_config
from kanibako.paths import load_std_paths, resolve_project


class TestArchive:
    def test_creates_archive(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.archive import run

        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)

        # Put some data in settings
        (proj.settings_path / "test_data.txt").write_text("hello")

        archive_path = str(tmp_home / "test.txz")
        args = argparse.Namespace(
            path=project_dir,
            file=archive_path,
            all_projects=False,
            allow_uncommitted=True,
            allow_unpushed=True,
            force=True,
        )
        rc = run(args)
        assert rc == 0
        assert Path(archive_path).exists()

        # Verify archive contents
        with tarfile.open(archive_path, "r:xz") as tar:
            names = tar.getnames()
            assert any("test_data.txt" in n for n in names)

    def test_no_session_data(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.archive import run

        # Create a project dir but don't initialize it
        new_project = tmp_home / "empty_project"
        new_project.mkdir()

        args = argparse.Namespace(
            path=str(new_project),
            file=None,
            all_projects=False,
            allow_uncommitted=True,
            allow_unpushed=True,
            force=True,
        )
        rc = run(args)
        assert rc == 1
