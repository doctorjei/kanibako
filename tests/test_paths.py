"""Tests for kanibako.paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from kanibako.config import KanibakoConfig, load_config
from kanibako.errors import ConfigError, ProjectError
from kanibako.paths import (
    ProjectMode,
    detect_project_mode,
    load_std_paths,
    resolve_any_project,
    resolve_project,
)
from kanibako.utils import project_hash


class TestLoadStdPaths:
    def test_creates_directories(self, config_file, tmp_home):
        config = load_config(config_file)
        std = load_std_paths(config)

        assert std.data_path.is_dir()
        assert std.state_path.is_dir()
        assert std.cache_path.is_dir()

    def test_uses_xdg_dirs(self, config_file, tmp_home):
        config = load_config(config_file)
        std = load_std_paths(config)

        assert str(std.data_home) == str(tmp_home / "data")
        assert str(std.config_home) == str(tmp_home / "config")

    def test_missing_config_raises(self, tmp_home):
        with pytest.raises(ConfigError, match="missing"):
            load_std_paths()


class TestResolveProject:
    def test_computes_hash(self, config_file, tmp_home):
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=False)

        expected = project_hash(str(Path(project_dir).resolve()))
        assert proj.project_hash == expected

    def test_initialize_creates_dirs(self, config_file, tmp_home, credentials_dir):
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)

        assert proj.settings_path.is_dir()
        assert proj.dot_path.is_dir()
        assert proj.is_new

    def test_nonexistent_path_raises(self, config_file, tmp_home):
        config = load_config(config_file)
        std = load_std_paths(config)
        with pytest.raises(ProjectError, match="does not exist"):
            resolve_project(
                std, config, project_dir="/nonexistent/path", initialize=False
            )

    def test_not_initialize_skips_creation(self, config_file, tmp_home):
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=False)

        assert not proj.settings_path.exists()
        assert not proj.is_new

    def test_mode_is_account_centric(self, config_file, tmp_home, credentials_dir):
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)

        assert proj.mode is ProjectMode.account_centric


class TestDetectProjectMode:
    def test_account_centric_when_settings_exist(self, config_file, tmp_home, credentials_dir):
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = tmp_home / "project"
        # Initialize to create settings/{hash}/
        resolve_project(std, config, project_dir=str(project_dir), initialize=True)

        mode = detect_project_mode(project_dir.resolve(), std, config)
        assert mode is ProjectMode.account_centric

    def test_decentralized_when_dot_kanibako_dir_exists(self, config_file, tmp_home):
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = tmp_home / "project"
        (project_dir / ".kanibako").mkdir()

        mode = detect_project_mode(project_dir.resolve(), std, config)
        assert mode is ProjectMode.decentralized

    def test_default_account_centric_for_new_project(self, config_file, tmp_home):
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = tmp_home / "project"
        # No settings dir, no .kanibako dir → default
        mode = detect_project_mode(project_dir.resolve(), std, config)
        assert mode is ProjectMode.account_centric

    def test_account_centric_takes_priority_over_decentralized(
        self, config_file, tmp_home, credentials_dir
    ):
        """When both settings/{hash}/ and .kanibako exist, account-centric wins."""
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = tmp_home / "project"
        resolve_project(std, config, project_dir=str(project_dir), initialize=True)
        (project_dir / ".kanibako").mkdir(exist_ok=True)

        mode = detect_project_mode(project_dir.resolve(), std, config)
        assert mode is ProjectMode.account_centric

    def test_dot_kanibako_file_not_dir_is_not_decentralized(self, config_file, tmp_home):
        """A .kanibako *file* (not directory) should not trigger decentralized mode."""
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = tmp_home / "project"
        (project_dir / ".kanibako").write_text("not a directory")

        mode = detect_project_mode(project_dir.resolve(), std, config)
        assert mode is ProjectMode.account_centric

    def test_workset_when_inside_workspaces_dir(self, config_file, tmp_home):
        """Project inside a registered workset's workspaces/ → workset mode."""
        config = load_config(config_file)
        std = load_std_paths(config)

        from kanibako.workset import create_workset
        ws_root = tmp_home / "worksets" / "my-set"
        create_workset("my-set", ws_root, std)

        # Create a project dir inside the workset's workspaces/
        proj_dir = ws_root.resolve() / "workspaces" / "my-proj"
        proj_dir.mkdir(parents=True)

        mode = detect_project_mode(proj_dir, std, config)
        assert mode is ProjectMode.workset

    def test_workset_takes_priority_over_all(self, config_file, tmp_home, credentials_dir):
        """Workset detection (step 1) beats account-centric (step 2)."""
        config = load_config(config_file)
        std = load_std_paths(config)

        from kanibako.workset import create_workset
        ws_root = tmp_home / "worksets" / "my-set"
        create_workset("my-set", ws_root, std)

        proj_dir = ws_root.resolve() / "workspaces" / "my-proj"
        proj_dir.mkdir(parents=True)
        # Also create account-centric settings for the same path
        resolve_project(std, config, project_dir=str(proj_dir), initialize=True)

        mode = detect_project_mode(proj_dir, std, config)
        assert mode is ProjectMode.workset


class TestResolveAnyProject:
    def test_resolve_any_project_account_centric(self, config_file, tmp_home, credentials_dir):
        """Falls through to resolve_project for normal dirs."""
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_any_project(std, config, project_dir=project_dir, initialize=True)

        assert proj.mode is ProjectMode.account_centric
        assert proj.settings_path.is_dir()

    def test_resolve_any_project_decentralized(self, config_file, tmp_home):
        """Dispatches to resolve_decentralized_project when .kanibako/ exists."""
        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = tmp_home / "project"
        (project_dir / ".kanibako").mkdir()

        proj = resolve_any_project(std, config, project_dir=str(project_dir), initialize=False)

        assert proj.mode is ProjectMode.decentralized
        assert proj.settings_path == project_dir.resolve() / ".kanibako"

    def test_resolve_any_project_default_cwd(self, config_file, tmp_home, credentials_dir):
        """Uses cwd when project_dir is None."""
        config = load_config(config_file)
        std = load_std_paths(config)

        proj = resolve_any_project(std, config, initialize=True)

        # cwd is tmp_home/project (set by tmp_home fixture)
        assert proj.project_path == (tmp_home / "project").resolve()
        assert proj.mode is ProjectMode.account_centric
