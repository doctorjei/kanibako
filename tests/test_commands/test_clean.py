"""Tests for kanibako.commands.clean (purge subcommand)."""

from __future__ import annotations

import argparse
from unittest.mock import patch

import pytest

from kanibako.config import load_config
from kanibako.paths import load_std_paths, resolve_project


class TestClean:
    def test_force_removes_data(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.clean import run

        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)

        assert proj.settings_path.is_dir()

        args = argparse.Namespace(
            path=project_dir,
            all_projects=False,
            force=True,
        )
        rc = run(args)
        assert rc == 0
        assert not proj.settings_path.exists()

    def test_no_session_data(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.clean import run

        new_project = tmp_home / "empty_project"
        new_project.mkdir()

        args = argparse.Namespace(
            path=str(new_project),
            all_projects=False,
            force=True,
        )
        rc = run(args)
        assert rc == 0

    def test_no_path_no_all_returns_error(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.clean import run

        args = argparse.Namespace(
            path=None,
            all_projects=False,
            force=True,
        )
        rc = run(args)
        assert rc == 1

    def test_all_force_removes_all(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.clean import run

        config = load_config(config_file)
        std = load_std_paths(config)

        # Create two projects
        proj_a_dir = tmp_home / "proj_a"
        proj_a_dir.mkdir()
        proj_a = resolve_project(std, config, project_dir=str(proj_a_dir), initialize=True)

        proj_b_dir = tmp_home / "proj_b"
        proj_b_dir.mkdir()
        proj_b = resolve_project(std, config, project_dir=str(proj_b_dir), initialize=True)

        assert proj_a.settings_path.is_dir()
        assert proj_b.settings_path.is_dir()

        args = argparse.Namespace(
            path=None,
            all_projects=True,
            force=True,
        )
        rc = run(args)
        assert rc == 0
        assert not proj_a.settings_path.exists()
        assert not proj_b.settings_path.exists()

    def test_all_empty_returns_zero(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.clean import run

        args = argparse.Namespace(
            path=None,
            all_projects=True,
            force=True,
        )
        rc = run(args)
        assert rc == 0
