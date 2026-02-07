"""Tests for clodbox.commands.box (list, migrate, and duplicate subcommands)."""

from __future__ import annotations

import argparse

import pytest

from clodbox.config import load_config
from clodbox.paths import load_std_paths, resolve_project
from clodbox.utils import project_hash


class TestBoxList:
    def test_list_empty(self, config_file, tmp_home, credentials_dir, capsys):
        from clodbox.commands.box import run_list

        args = argparse.Namespace()
        rc = run_list(args)
        assert rc == 0
        assert "No known projects" in capsys.readouterr().out

    def test_list_shows_projects(self, config_file, tmp_home, credentials_dir, capsys):
        from clodbox.commands.box import run_list

        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        resolve_project(std, config, project_dir=project_dir, initialize=True)

        args = argparse.Namespace()
        rc = run_list(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "ok" in out
        assert str(tmp_home / "project") in out

    def test_list_shows_missing_status(self, config_file, tmp_home, credentials_dir, capsys):
        from clodbox.commands.box import run_list

        config = load_config(config_file)
        std = load_std_paths(config)

        # Create a project, then remove the directory.
        gone_dir = tmp_home / "gone_project"
        gone_dir.mkdir()
        resolve_project(std, config, project_dir=str(gone_dir), initialize=True)
        gone_dir.rmdir()

        args = argparse.Namespace()
        rc = run_list(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "missing" in out


class TestBoxMigrate:
    def test_migrate_success(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        # Initialize old project.
        old_dir = tmp_home / "old_project"
        old_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(old_dir), initialize=True)

        # Create a marker file to verify data is preserved.
        marker = proj.settings_path / "marker.txt"
        marker.write_text("hello")

        # Create new project directory.
        new_dir = tmp_home / "new_project"
        new_dir.mkdir()

        args = argparse.Namespace(
            old_path=str(old_dir),
            new_path=str(new_dir),
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 0

        # Old settings should be gone.
        assert not proj.settings_path.exists()

        # New settings should exist with preserved data.
        new_hash = project_hash(str(new_dir.resolve()))
        projects_base = std.data_path / config.paths_projects_path
        new_settings = projects_base / new_hash
        assert new_settings.is_dir()
        assert (new_settings / "marker.txt").read_text() == "hello"

        # Breadcrumb should be updated.
        assert (new_settings / "project-path.txt").read_text().strip() == str(new_dir.resolve())

    def test_migrate_same_path_error(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_migrate

        project_dir = tmp_home / "project"

        args = argparse.Namespace(
            old_path=str(project_dir),
            new_path=str(project_dir),
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 1

    def test_migrate_no_old_data_error(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_migrate

        old_dir = tmp_home / "nonexistent_old"
        new_dir = tmp_home / "project"  # exists (created by tmp_home)

        args = argparse.Namespace(
            old_path=str(old_dir),
            new_path=str(new_dir),
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 1

    def test_migrate_new_path_not_dir_error(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        old_dir = tmp_home / "old_proj"
        old_dir.mkdir()
        resolve_project(std, config, project_dir=str(old_dir), initialize=True)

        args = argparse.Namespace(
            old_path=str(old_dir),
            new_path=str(tmp_home / "does_not_exist"),
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 1

    def test_migrate_new_data_exists_error(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        # Initialize both projects.
        old_dir = tmp_home / "old_proj2"
        old_dir.mkdir()
        resolve_project(std, config, project_dir=str(old_dir), initialize=True)

        new_dir = tmp_home / "new_proj2"
        new_dir.mkdir()
        resolve_project(std, config, project_dir=str(new_dir), initialize=True)

        args = argparse.Namespace(
            old_path=str(old_dir),
            new_path=str(new_dir),
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 1

    def test_migrate_defaults_to_cwd(self, config_file, tmp_home, credentials_dir, monkeypatch):
        from clodbox.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        old_dir = tmp_home / "old_cwd_proj"
        old_dir.mkdir()
        resolve_project(std, config, project_dir=str(old_dir), initialize=True)

        # CWD is tmp_home/project (set by tmp_home fixture).
        cwd = tmp_home / "project"

        args = argparse.Namespace(
            old_path=str(old_dir),
            new_path=None,
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 0

        # Verify data landed under CWD's hash.
        new_hash = project_hash(str(cwd.resolve()))
        projects_base = std.data_path / config.paths_projects_path
        new_settings = projects_base / new_hash
        assert new_settings.is_dir()

    def test_migrate_warns_on_lock_file(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        old_dir = tmp_home / "locked_proj"
        old_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(old_dir), initialize=True)

        # Create a lock file.
        (proj.settings_path / ".clodbox.lock").touch()

        new_dir = tmp_home / "new_locked_proj"
        new_dir.mkdir()

        # With --force, should still succeed despite lock file.
        args = argparse.Namespace(
            old_path=str(old_dir),
            new_path=str(new_dir),
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 0


class TestBoxDuplicate:
    def _make_args(self, source, dest, bare=False, force=False):
        return argparse.Namespace(
            source_path=str(source), new_path=str(dest),
            bare=bare, force=force,
        )

    def test_duplicate_success(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        # Create source project with workspace content and metadata.
        src_dir = tmp_home / "src_project"
        src_dir.mkdir()
        (src_dir / "code.py").write_text("print('hello')")
        proj = resolve_project(std, config, project_dir=str(src_dir), initialize=True)
        (proj.settings_path / "marker.txt").write_text("session-data")

        dst_dir = tmp_home / "dst_project"

        rc = run_duplicate(self._make_args(src_dir, dst_dir, force=True))
        assert rc == 0

        # Workspace copied.
        assert (dst_dir / "code.py").read_text() == "print('hello')"

        # Metadata copied with updated breadcrumb.
        new_hash = project_hash(str(dst_dir.resolve()))
        projects_base = std.data_path / config.paths_projects_path
        new_settings = projects_base / new_hash
        assert (new_settings / "marker.txt").read_text() == "session-data"
        assert (new_settings / "project-path.txt").read_text().strip() == str(dst_dir.resolve())

        # Source is intact.
        assert (src_dir / "code.py").read_text() == "print('hello')"
        assert proj.settings_path.is_dir()

    def test_duplicate_bare(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "bare_src"
        src_dir.mkdir()
        resolve_project(std, config, project_dir=str(src_dir), initialize=True)

        dst_dir = tmp_home / "bare_dst"

        rc = run_duplicate(self._make_args(src_dir, dst_dir, bare=True, force=True))
        assert rc == 0

        # Workspace NOT created.
        assert not dst_dir.exists()

        # Metadata exists.
        new_hash = project_hash(str(dst_dir.resolve()))
        projects_base = std.data_path / config.paths_projects_path
        assert (projects_base / new_hash).is_dir()

    def test_duplicate_source_not_dir_error(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_duplicate

        rc = run_duplicate(self._make_args(
            tmp_home / "nonexistent", tmp_home / "dst", force=True,
        ))
        assert rc == 1

    def test_duplicate_source_no_metadata_error(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_duplicate

        src_dir = tmp_home / "no_meta"
        src_dir.mkdir()

        rc = run_duplicate(self._make_args(src_dir, tmp_home / "dst", force=True))
        assert rc == 1

    def test_duplicate_dst_exists_error(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "dup_src"
        src_dir.mkdir()
        resolve_project(std, config, project_dir=str(src_dir), initialize=True)

        dst_dir = tmp_home / "dup_dst"
        dst_dir.mkdir()

        # Without --force, should fail because dst exists.
        rc = run_duplicate(self._make_args(src_dir, dst_dir))
        assert rc == 1

    def test_duplicate_dst_metadata_exists_error(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "meta_src"
        src_dir.mkdir()
        resolve_project(std, config, project_dir=str(src_dir), initialize=True)

        dst_dir = tmp_home / "meta_dst"
        dst_dir.mkdir()
        resolve_project(std, config, project_dir=str(dst_dir), initialize=True)

        # Without --force, should fail because dst metadata exists.
        rc = run_duplicate(self._make_args(src_dir, dst_dir, bare=True))
        assert rc == 1

    def test_duplicate_lock_file_aborts_without_force(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "locked_src"
        src_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(src_dir), initialize=True)
        (proj.settings_path / ".clodbox.lock").touch()

        dst_dir = tmp_home / "locked_dst"

        rc = run_duplicate(self._make_args(src_dir, dst_dir))
        assert rc == 2

    def test_duplicate_lock_file_skipped_with_force(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "lockforce_src"
        src_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(src_dir), initialize=True)
        (proj.settings_path / ".clodbox.lock").touch()

        dst_dir = tmp_home / "lockforce_dst"

        rc = run_duplicate(self._make_args(src_dir, dst_dir, force=True))
        assert rc == 0

    def test_duplicate_excludes_lock_file(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "excl_src"
        src_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(src_dir), initialize=True)
        (proj.settings_path / ".clodbox.lock").touch()

        dst_dir = tmp_home / "excl_dst"

        rc = run_duplicate(self._make_args(src_dir, dst_dir, force=True))
        assert rc == 0

        new_hash = project_hash(str(dst_dir.resolve()))
        projects_base = std.data_path / config.paths_projects_path
        new_settings = projects_base / new_hash
        assert not (new_settings / ".clodbox.lock").exists()

    def test_duplicate_force_overwrites_metadata(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "fw_src"
        src_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(src_dir), initialize=True)
        (proj.settings_path / "fresh.txt").write_text("new")

        dst_dir = tmp_home / "fw_dst"
        dst_dir.mkdir()
        dst_proj = resolve_project(std, config, project_dir=str(dst_dir), initialize=True)
        (dst_proj.settings_path / "stale.txt").write_text("old")

        rc = run_duplicate(self._make_args(src_dir, dst_dir, bare=True, force=True))
        assert rc == 0

        new_hash = project_hash(str(dst_dir.resolve()))
        projects_base = std.data_path / config.paths_projects_path
        new_settings = projects_base / new_hash

        # Fresh data present, stale data gone.
        assert (new_settings / "fresh.txt").read_text() == "new"
        assert not (new_settings / "stale.txt").exists()

    def test_duplicate_force_overwrites_workspace(self, config_file, tmp_home, credentials_dir):
        from clodbox.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "ws_src"
        src_dir.mkdir()
        (src_dir / "new_file.txt").write_text("new")
        resolve_project(std, config, project_dir=str(src_dir), initialize=True)

        dst_dir = tmp_home / "ws_dst"
        dst_dir.mkdir()
        (dst_dir / "existing.txt").write_text("keep")

        rc = run_duplicate(self._make_args(src_dir, dst_dir, force=True))
        assert rc == 0

        # New file merged in.
        assert (dst_dir / "new_file.txt").read_text() == "new"
        # Existing file preserved (dirs_exist_ok merges).
        assert (dst_dir / "existing.txt").read_text() == "keep"
