"""Tests for kanibako.commands.env_cmd."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kanibako.cli import build_parser


class TestEnvParser:
    """CLI parser wiring tests."""

    def test_env_command(self):
        parser = build_parser()
        args = parser.parse_args(["env"])
        assert args.command == "env"

    def test_env_list(self):
        parser = build_parser()
        args = parser.parse_args(["env", "list"])
        assert args.command == "env"
        assert args.env_command == "list"

    def test_env_set(self):
        parser = build_parser()
        args = parser.parse_args(["env", "set", "EDITOR", "vim"])
        assert args.command == "env"
        assert args.env_command == "set"
        assert args.key == "EDITOR"
        assert args.value == "vim"
        assert args.is_global is False

    def test_env_set_global(self):
        parser = build_parser()
        args = parser.parse_args(["env", "set", "--global", "EDITOR", "vim"])
        assert args.is_global is True

    def test_env_get(self):
        parser = build_parser()
        args = parser.parse_args(["env", "get", "EDITOR"])
        assert args.env_command == "get"
        assert args.key == "EDITOR"

    def test_env_unset(self):
        parser = build_parser()
        args = parser.parse_args(["env", "unset", "EDITOR"])
        assert args.env_command == "unset"
        assert args.key == "EDITOR"
        assert args.is_global is False

    def test_env_unset_global(self):
        parser = build_parser()
        args = parser.parse_args(["env", "unset", "--global", "EDITOR"])
        assert args.is_global is True


class TestEnvCommands:
    """Functional tests for env subcommands."""

    @pytest.fixture
    def env_paths(self, tmp_path):
        """Set up mock env paths and patch _resolve_env_paths."""
        global_env = tmp_path / "config" / "kanibako" / "env"
        project_env = tmp_path / "project" / ".kanibako" / "env"
        global_env.parent.mkdir(parents=True, exist_ok=True)
        project_env.parent.mkdir(parents=True, exist_ok=True)
        return global_env, project_env

    def test_list_empty(self, env_paths, capsys):
        from kanibako.commands.env_cmd import run_list
        global_env, project_env = env_paths
        with patch("kanibako.commands.env_cmd._resolve_env_paths", return_value=(global_env, project_env)):
            rc = run_list(argparse.Namespace(project=None))
        assert rc == 0
        assert "No environment variables" in capsys.readouterr().out

    def test_list_merged(self, env_paths, capsys):
        from kanibako.commands.env_cmd import run_list
        global_env, project_env = env_paths
        global_env.write_text("GLOBAL=yes\nEDITOR=nano\n")
        project_env.write_text("EDITOR=vim\nPROJECT=1\n")
        with patch("kanibako.commands.env_cmd._resolve_env_paths", return_value=(global_env, project_env)):
            rc = run_list(argparse.Namespace(project=None))
        assert rc == 0
        out = capsys.readouterr().out
        assert "EDITOR=vim" in out
        assert "GLOBAL=yes" in out
        assert "PROJECT=1" in out

    def test_set_project(self, env_paths, capsys):
        from kanibako.commands.env_cmd import run_set
        global_env, project_env = env_paths
        with patch("kanibako.commands.env_cmd._resolve_env_paths", return_value=(global_env, project_env)):
            rc = run_set(argparse.Namespace(project=None, key="EDITOR", value="vim", is_global=False))
        assert rc == 0
        assert "Set EDITOR (project)" in capsys.readouterr().out
        from kanibako.shellenv import read_env_file
        assert read_env_file(project_env)["EDITOR"] == "vim"

    def test_set_global(self, env_paths, capsys):
        from kanibako.commands.env_cmd import run_set
        global_env, project_env = env_paths
        with patch("kanibako.commands.env_cmd._resolve_env_paths", return_value=(global_env, project_env)):
            rc = run_set(argparse.Namespace(project=None, key="EDITOR", value="vim", is_global=True))
        assert rc == 0
        assert "Set EDITOR (global)" in capsys.readouterr().out
        from kanibako.shellenv import read_env_file
        assert read_env_file(global_env)["EDITOR"] == "vim"

    def test_set_invalid_key(self, env_paths, capsys):
        from kanibako.commands.env_cmd import run_set
        global_env, project_env = env_paths
        with patch("kanibako.commands.env_cmd._resolve_env_paths", return_value=(global_env, project_env)):
            rc = run_set(argparse.Namespace(project=None, key="123BAD", value="val", is_global=False))
        assert rc == 1
        assert "Invalid" in capsys.readouterr().err

    def test_get_existing(self, env_paths, capsys):
        from kanibako.commands.env_cmd import run_get
        global_env, project_env = env_paths
        project_env.write_text("EDITOR=vim\n")
        with patch("kanibako.commands.env_cmd._resolve_env_paths", return_value=(global_env, project_env)):
            rc = run_get(argparse.Namespace(project=None, key="EDITOR"))
        assert rc == 0
        assert "vim" in capsys.readouterr().out

    def test_get_missing(self, env_paths, capsys):
        from kanibako.commands.env_cmd import run_get
        global_env, project_env = env_paths
        with patch("kanibako.commands.env_cmd._resolve_env_paths", return_value=(global_env, project_env)):
            rc = run_get(argparse.Namespace(project=None, key="MISSING"))
        assert rc == 1
        assert "not set" in capsys.readouterr().err

    def test_unset_existing(self, env_paths, capsys):
        from kanibako.commands.env_cmd import run_unset
        global_env, project_env = env_paths
        project_env.write_text("EDITOR=vim\n")
        with patch("kanibako.commands.env_cmd._resolve_env_paths", return_value=(global_env, project_env)):
            rc = run_unset(argparse.Namespace(project=None, key="EDITOR", is_global=False))
        assert rc == 0
        assert "Unset EDITOR (project)" in capsys.readouterr().out
        from kanibako.shellenv import read_env_file
        assert "EDITOR" not in read_env_file(project_env)

    def test_unset_missing(self, env_paths, capsys):
        from kanibako.commands.env_cmd import run_unset
        global_env, project_env = env_paths
        with patch("kanibako.commands.env_cmd._resolve_env_paths", return_value=(global_env, project_env)):
            rc = run_unset(argparse.Namespace(project=None, key="MISSING", is_global=False))
        assert rc == 1
        assert "not set" in capsys.readouterr().err

    def test_unset_global(self, env_paths, capsys):
        from kanibako.commands.env_cmd import run_unset
        global_env, project_env = env_paths
        global_env.write_text("EDITOR=vim\n")
        with patch("kanibako.commands.env_cmd._resolve_env_paths", return_value=(global_env, project_env)):
            rc = run_unset(argparse.Namespace(project=None, key="EDITOR", is_global=True))
        assert rc == 0
        assert "Unset EDITOR (global)" in capsys.readouterr().out

    def test_get_global_var_via_merge(self, env_paths, capsys):
        """get shows vars from global env when not overridden by project."""
        from kanibako.commands.env_cmd import run_get
        global_env, project_env = env_paths
        global_env.write_text("GLOBAL_KEY=hello\n")
        with patch("kanibako.commands.env_cmd._resolve_env_paths", return_value=(global_env, project_env)):
            rc = run_get(argparse.Namespace(project=None, key="GLOBAL_KEY"))
        assert rc == 0
        assert "hello" in capsys.readouterr().out
