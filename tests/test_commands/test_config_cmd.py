"""Tests for kanibako.commands.config_cmd."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from unittest.mock import patch

from kanibako.config import ClodboxConfig, load_config, write_global_config, write_project_config


class TestConfigGet:
    def test_get_image(self, config_file, tmp_home, credentials_dir, capsys):
        from kanibako.commands.config_cmd import run

        # Create project settings path so resolve_project finds it
        config = load_config(config_file)
        from kanibako.paths import load_std_paths, resolve_project
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)

        args = argparse.Namespace(
            key="image", value=None, show=False, clear=False, project=project_dir
        )
        rc = run(args)
        assert rc == 0
        captured = capsys.readouterr()
        assert "ghcr.io/doctorjei/kanibako-base:latest" in captured.out


class TestConfigSet:
    def test_set_image(self, config_file, tmp_home, credentials_dir, capsys):
        from kanibako.commands.config_cmd import run

        config = load_config(config_file)
        from kanibako.paths import load_std_paths, resolve_project
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)

        args = argparse.Namespace(
            key="image", value="new-image:v1", show=False, clear=False,
            project=project_dir,
        )
        rc = run(args)
        assert rc == 0

        # Verify the project.toml was written
        project_toml = proj.settings_path / "project.toml"
        assert project_toml.exists()
        loaded = load_config(project_toml)
        assert loaded.container_image == "new-image:v1"


class TestConfigUnknownKey:
    def test_unknown_key(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.config_cmd import run

        config = load_config(config_file)
        from kanibako.paths import load_std_paths, resolve_project
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        resolve_project(std, config, project_dir=project_dir, initialize=True)

        args = argparse.Namespace(
            key="nonexistent", value=None, show=False, clear=False,
            project=project_dir,
        )
        rc = run(args)
        assert rc == 1


class TestConfigShow:
    def test_show_all(self, config_file, tmp_home, credentials_dir, capsys):
        from kanibako.commands.config_cmd import run

        config = load_config(config_file)
        from kanibako.paths import load_std_paths, resolve_project
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        resolve_project(std, config, project_dir=project_dir, initialize=True)

        args = argparse.Namespace(
            key=None, value=None, show=True, clear=False, project=project_dir
        )
        rc = run(args)
        assert rc == 0
        captured = capsys.readouterr()
        assert "container_image" in captured.out
        assert "paths_dot_path" in captured.out

    def test_show_marks_project_overrides(self, config_file, tmp_home, credentials_dir, capsys):
        from kanibako.commands.config_cmd import run

        config = load_config(config_file)
        from kanibako.paths import load_std_paths, resolve_project
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)

        # Write a project override
        project_toml = proj.settings_path / "project.toml"
        write_project_config(project_toml, "custom:v1")

        args = argparse.Namespace(
            key=None, value=None, show=True, clear=False, project=project_dir
        )
        rc = run(args)
        assert rc == 0
        captured = capsys.readouterr()
        assert "(project)" in captured.out
        assert "custom:v1" in captured.out


class TestConfigClear:
    def test_clear_removes_project_toml(self, config_file, tmp_home, credentials_dir, capsys):
        from kanibako.commands.config_cmd import run

        config = load_config(config_file)
        from kanibako.paths import load_std_paths, resolve_project
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)

        # Write a project override first
        project_toml = proj.settings_path / "project.toml"
        write_project_config(project_toml, "custom:v1")
        assert project_toml.exists()

        with patch("kanibako.commands.config_cmd.confirm_prompt"):
            args = argparse.Namespace(
                key=None, value=None, show=False, clear=True, project=project_dir
            )
            rc = run(args)
        assert rc == 0
        assert not project_toml.exists()
        captured = capsys.readouterr()
        assert "Cleared" in captured.out

    def test_clear_no_project_config(self, config_file, tmp_home, credentials_dir, capsys):
        from kanibako.commands.config_cmd import run

        config = load_config(config_file)
        from kanibako.paths import load_std_paths, resolve_project
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        resolve_project(std, config, project_dir=project_dir, initialize=True)

        args = argparse.Namespace(
            key=None, value=None, show=False, clear=True, project=project_dir
        )
        rc = run(args)
        assert rc == 0
        captured = capsys.readouterr()
        assert "No project config" in captured.out


class TestConfigNoArgs:
    def test_no_key_or_flag_prints_help(self, config_file, tmp_home, credentials_dir, capsys):
        from kanibako.cli import build_parser

        # Parse through the real parser so _config_parser is set
        parser = build_parser()
        args = parser.parse_args(["config"])

        from kanibako.commands.config_cmd import run

        config = load_config(config_file)
        from kanibako.paths import load_std_paths, resolve_project
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        resolve_project(std, config, project_dir=project_dir, initialize=True)

        args.project = project_dir
        rc = run(args)
        assert rc == 0
        captured = capsys.readouterr()
        assert "--show" in captured.out
        assert "--clear" in captured.out
