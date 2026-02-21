"""Tests for kanibako.commands.box (list, migrate, duplicate, and convert subcommands)."""

from __future__ import annotations

import argparse
import shutil

import pytest

from kanibako.config import load_config
from kanibako.paths import load_std_paths, resolve_decentralized_project, resolve_project
from kanibako.utils import project_hash


class TestBoxList:
    def test_list_empty(self, config_file, tmp_home, credentials_dir, capsys):
        from kanibako.commands.box import run_list

        args = argparse.Namespace()
        rc = run_list(args)
        assert rc == 0
        assert "No known projects" in capsys.readouterr().out

    def test_list_shows_projects(self, config_file, tmp_home, credentials_dir, capsys):
        from kanibako.commands.box import run_list

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
        from kanibako.commands.box import run_list

        config = load_config(config_file)
        std = load_std_paths(config)

        # Create a project, then remove the directory.
        gone_dir = tmp_home / "gone_project"
        gone_dir.mkdir()
        resolve_project(std, config, project_dir=str(gone_dir), initialize=True)
        shutil.rmtree(gone_dir)

        args = argparse.Namespace()
        rc = run_list(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "missing" in out


class TestBoxMigrate:
    def test_migrate_success(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

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
            to_mode=None,
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
        from kanibako.commands.box import run_migrate

        project_dir = tmp_home / "project"

        args = argparse.Namespace(
            old_path=str(project_dir),
            new_path=str(project_dir),
            to_mode=None,
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 1

    def test_migrate_no_old_data_error(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        old_dir = tmp_home / "nonexistent_old"
        new_dir = tmp_home / "project"  # exists (created by tmp_home)

        args = argparse.Namespace(
            old_path=str(old_dir),
            new_path=str(new_dir),
            to_mode=None,
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 1

    def test_migrate_new_path_not_dir_error(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        old_dir = tmp_home / "old_proj"
        old_dir.mkdir()
        resolve_project(std, config, project_dir=str(old_dir), initialize=True)

        args = argparse.Namespace(
            old_path=str(old_dir),
            new_path=str(tmp_home / "does_not_exist"),
            to_mode=None,
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 1

    def test_migrate_new_data_exists_error(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

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
            to_mode=None,
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 1

    def test_migrate_defaults_to_cwd(self, config_file, tmp_home, credentials_dir, monkeypatch):
        from kanibako.commands.box import run_migrate

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
            to_mode=None,
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
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        old_dir = tmp_home / "locked_proj"
        old_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(old_dir), initialize=True)

        # Create a lock file.
        (proj.settings_path / ".kanibako.lock").touch()

        new_dir = tmp_home / "new_locked_proj"
        new_dir.mkdir()

        # With --force, should still succeed despite lock file.
        args = argparse.Namespace(
            old_path=str(old_dir),
            new_path=str(new_dir),
            to_mode=None,
            force=True,
        )
        rc = run_migrate(args)
        assert rc == 0


class TestBoxDuplicate:
    def _make_args(self, source, dest, bare=False, force=False):
        return argparse.Namespace(
            source_path=str(source), new_path=str(dest),
            bare=bare, force=force, to_mode=None,
        )

    def test_duplicate_success(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

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
        from kanibako.commands.box import run_duplicate

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
        from kanibako.commands.box import run_duplicate

        rc = run_duplicate(self._make_args(
            tmp_home / "nonexistent", tmp_home / "dst", force=True,
        ))
        assert rc == 1

    def test_duplicate_source_no_metadata_error(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

        src_dir = tmp_home / "no_meta"
        src_dir.mkdir()

        rc = run_duplicate(self._make_args(src_dir, tmp_home / "dst", force=True))
        assert rc == 1

    def test_duplicate_dst_exists_error(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

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
        from kanibako.commands.box import run_duplicate

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
        from kanibako.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "locked_src"
        src_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(src_dir), initialize=True)
        (proj.settings_path / ".kanibako.lock").touch()

        dst_dir = tmp_home / "locked_dst"

        rc = run_duplicate(self._make_args(src_dir, dst_dir))
        assert rc == 2

    def test_duplicate_lock_file_skipped_with_force(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "lockforce_src"
        src_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(src_dir), initialize=True)
        (proj.settings_path / ".kanibako.lock").touch()

        dst_dir = tmp_home / "lockforce_dst"

        rc = run_duplicate(self._make_args(src_dir, dst_dir, force=True))
        assert rc == 0

    def test_duplicate_excludes_lock_file(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "excl_src"
        src_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(src_dir), initialize=True)
        (proj.settings_path / ".kanibako.lock").touch()

        dst_dir = tmp_home / "excl_dst"

        rc = run_duplicate(self._make_args(src_dir, dst_dir, force=True))
        assert rc == 0

        new_hash = project_hash(str(dst_dir.resolve()))
        projects_base = std.data_path / config.paths_projects_path
        new_settings = projects_base / new_hash
        assert not (new_settings / ".kanibako.lock").exists()

    def test_duplicate_force_overwrites_metadata(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

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
        from kanibako.commands.box import run_duplicate

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


class TestBoxInfo:
    def test_info_account_centric(self, config_file, tmp_home, credentials_dir, capsys):
        from kanibako.commands.box import run_info

        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        resolve_project(std, config, project_dir=project_dir, initialize=True)

        args = argparse.Namespace(path=project_dir)
        rc = run_info(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "account_centric" in out
        assert str(tmp_home / "project") in out

    def test_info_decentralized(self, config_file, tmp_home, capsys):
        from kanibako.commands.box import run_info

        project_dir = tmp_home / "project"
        (project_dir / ".kanibako").mkdir()

        args = argparse.Namespace(path=str(project_dir))
        rc = run_info(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "decentralized" in out

    def test_info_no_data(self, config_file, tmp_home, capsys):
        from kanibako.commands.box import run_info

        args = argparse.Namespace(path=str(tmp_home / "project"))
        rc = run_info(args)
        assert rc == 1
        err = capsys.readouterr().err
        assert "No project data found" in err

    def test_info_lock_status(self, config_file, tmp_home, credentials_dir, capsys):
        from kanibako.commands.box import run_info

        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)
        (proj.settings_path / ".kanibako.lock").touch()

        args = argparse.Namespace(path=project_dir)
        rc = run_info(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "ACTIVE" in out


class TestBoxMigrateShell:
    """Test that same-mode migrate also moves shell/{hash}/."""

    def test_migrate_moves_shell_data(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        old_dir = tmp_home / "shell_old"
        old_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(old_dir), initialize=True)

        # Add a marker in the shell directory.
        (proj.shell_path / "shell_marker.txt").write_text("shell-data")

        new_dir = tmp_home / "shell_new"
        new_dir.mkdir()

        args = argparse.Namespace(
            old_path=str(old_dir), new_path=str(new_dir),
            to_mode=None, force=True,
        )
        rc = run_migrate(args)
        assert rc == 0

        # Old shell should be gone.
        assert not proj.shell_path.exists()

        # New shell should exist with marker.
        new_hash = project_hash(str(new_dir.resolve()))
        new_shell = std.data_path / "shell" / new_hash
        assert new_shell.is_dir()
        assert (new_shell / "shell_marker.txt").read_text() == "shell-data"


class TestBoxConvert:
    """Tests for cross-mode conversion (kanibako box migrate --to)."""

    def _convert_args(self, project_path=None, to_mode="decentralized", force=True):
        return argparse.Namespace(
            old_path=str(project_path) if project_path else None,
            new_path=None,
            to_mode=to_mode,
            force=force,
        )

    def test_convert_ac_to_decentralized(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_ac"
        project_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(project_dir), initialize=True)
        (proj.settings_path / "marker.txt").write_text("settings-data")
        (proj.shell_path / "custom.sh").write_text("echo hello")

        args = self._convert_args(project_dir, "decentralized")
        rc = run_migrate(args)
        assert rc == 0

        # Decentralized layout should exist.
        assert (project_dir / ".kanibako").is_dir()
        assert (project_dir / ".shell").is_dir()
        assert (project_dir / ".kanibako" / "marker.txt").read_text() == "settings-data"
        assert (project_dir / ".shell" / "custom.sh").read_text() == "echo hello"

        # Old AC data should be gone.
        assert not proj.settings_path.exists()
        assert not proj.shell_path.exists()

    def test_convert_decentralized_to_ac(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_dec"
        project_dir.mkdir()
        proj = resolve_decentralized_project(
            std, config, project_dir=str(project_dir), initialize=True,
        )
        (proj.settings_path / "marker.txt").write_text("dec-settings")
        (proj.shell_path / "custom.sh").write_text("echo dec")

        args = self._convert_args(project_dir, "account-centric")
        rc = run_migrate(args)
        assert rc == 0

        # AC layout should exist.
        phash = project_hash(str(project_dir.resolve()))
        projects_base = std.data_path / config.paths_projects_path
        ac_settings = projects_base / phash
        ac_shell = std.data_path / "shell" / phash

        assert ac_settings.is_dir()
        assert (ac_settings / "marker.txt").read_text() == "dec-settings"
        assert ac_shell.is_dir()
        assert (ac_shell / "custom.sh").read_text() == "echo dec"

        # Old decentralized data should be gone.
        assert not (project_dir / ".kanibako").exists()
        assert not (project_dir / ".shell").exists()

    def test_convert_same_mode_error(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_same"
        project_dir.mkdir()
        resolve_project(std, config, project_dir=str(project_dir), initialize=True)

        args = self._convert_args(project_dir, "account-centric")
        rc = run_migrate(args)
        assert rc == 1

    def test_convert_to_workset_not_implemented(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        project_dir = tmp_home / "conv_ws"
        project_dir.mkdir()

        args = self._convert_args(project_dir, "workset")
        rc = run_migrate(args)
        assert rc == 1

    def test_convert_from_workset_not_implemented(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        # Create a fake workset registration so detect_project_mode returns workset.
        project_dir = tmp_home / "ws_proj"
        project_dir.mkdir()

        # Register a workset that covers this project.
        ws_root = tmp_home / "ws_root"
        ws_workspaces = ws_root / "workspaces"
        ws_workspaces.mkdir(parents=True)
        # Make project_dir inside workspaces.
        ws_project = ws_workspaces / "myproj"
        ws_project.mkdir()

        worksets_toml = std.data_path / "worksets.toml"
        worksets_toml.write_text(f'[worksets]\nmyws = "{ws_root}"\n')

        args = self._convert_args(ws_project, "decentralized")
        rc = run_migrate(args)
        assert rc == 1

    def test_convert_preserves_dot_path_contents(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_creds"
        project_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(project_dir), initialize=True)

        # The dot_path (dotclaude) should have credentials from initialization.
        creds_file = proj.dot_path / ".credentials.json"
        assert creds_file.exists()
        original_creds = creds_file.read_text()

        args = self._convert_args(project_dir, "decentralized")
        rc = run_migrate(args)
        assert rc == 0

        # Credentials should survive in new location.
        new_creds = project_dir / ".kanibako" / config.paths_dot_path / ".credentials.json"
        assert new_creds.exists()
        assert new_creds.read_text() == original_creds

    def test_convert_preserves_shell_contents(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_shell"
        project_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(project_dir), initialize=True)
        (proj.shell_path / "custom_tool").write_text("#!/bin/bash\necho tool")

        args = self._convert_args(project_dir, "decentralized")
        rc = run_migrate(args)
        assert rc == 0

        assert (project_dir / ".shell" / "custom_tool").read_text() == "#!/bin/bash\necho tool"

    def test_convert_removes_breadcrumb_for_decentralized(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_bc"
        project_dir.mkdir()
        resolve_project(std, config, project_dir=str(project_dir), initialize=True)

        args = self._convert_args(project_dir, "decentralized")
        rc = run_migrate(args)
        assert rc == 0

        # Decentralized should NOT have a breadcrumb.
        assert not (project_dir / ".kanibako" / "project-path.txt").exists()

    def test_convert_writes_breadcrumb_for_ac(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_bc_ac"
        project_dir.mkdir()
        resolve_decentralized_project(
            std, config, project_dir=str(project_dir), initialize=True,
        )

        args = self._convert_args(project_dir, "account-centric")
        rc = run_migrate(args)
        assert rc == 0

        phash = project_hash(str(project_dir.resolve()))
        projects_base = std.data_path / config.paths_projects_path
        breadcrumb = projects_base / phash / "project-path.txt"
        assert breadcrumb.exists()
        assert breadcrumb.read_text().strip() == str(project_dir.resolve())

    def test_convert_excludes_lock_file(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_lock_excl"
        project_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(project_dir), initialize=True)
        (proj.settings_path / ".kanibako.lock").touch()

        args = self._convert_args(project_dir, "decentralized", force=True)
        rc = run_migrate(args)
        assert rc == 0

        # Lock file should NOT be copied to the new location.
        assert not (project_dir / ".kanibako" / ".kanibako.lock").exists()

    def test_convert_warns_on_lock_file(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_lock_warn"
        project_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(project_dir), initialize=True)
        (proj.settings_path / ".kanibako.lock").touch()

        # Without --force, should abort on lock file.
        args = self._convert_args(project_dir, "decentralized", force=False)
        rc = run_migrate(args)
        assert rc == 2

    def test_convert_force_skips_confirmation(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_force"
        project_dir.mkdir()
        resolve_project(std, config, project_dir=str(project_dir), initialize=True)

        # With --force, should succeed without prompting.
        args = self._convert_args(project_dir, "decentralized", force=True)
        rc = run_migrate(args)
        assert rc == 0
        assert (project_dir / ".kanibako").is_dir()

    def test_convert_creates_vault_gitignore(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_vault"
        project_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(project_dir), initialize=True)

        # vault/ should already exist from AC init. Remove the gitignore to test creation.
        vault_gitignore = project_dir / "vault" / ".gitignore"
        if vault_gitignore.exists():
            vault_gitignore.unlink()

        args = self._convert_args(project_dir, "decentralized")
        rc = run_migrate(args)
        assert rc == 0

        assert vault_gitignore.exists()
        assert "share-rw/" in vault_gitignore.read_text()

    def test_convert_writes_root_gitignore(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        project_dir = tmp_home / "conv_gi"
        project_dir.mkdir()
        resolve_project(std, config, project_dir=str(project_dir), initialize=True)

        args = self._convert_args(project_dir, "decentralized")
        rc = run_migrate(args)
        assert rc == 0

        gitignore = project_dir / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert ".kanibako/" in content
        assert ".shell/" in content

    def test_convert_defaults_to_cwd(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_migrate

        config = load_config(config_file)
        std = load_std_paths(config)

        # CWD is tmp_home/project (set by tmp_home fixture).
        project_dir = tmp_home / "project"
        resolve_project(std, config, project_dir=str(project_dir), initialize=True)

        # No project path argument → should use cwd.
        args = argparse.Namespace(
            old_path=None, new_path=None,
            to_mode="decentralized", force=True,
        )
        rc = run_migrate(args)
        assert rc == 0

        assert (project_dir / ".kanibako").is_dir()


class TestBoxDuplicateCrossMode:
    """Tests for cross-mode duplication (kanibako box duplicate --to)."""

    def _make_args(self, source, dest, to_mode, bare=False, force=True):
        return argparse.Namespace(
            source_path=str(source), new_path=str(dest),
            to_mode=to_mode, bare=bare, force=force,
        )

    def test_duplicate_ac_to_decentralized(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "dup_ac_src"
        src_dir.mkdir()
        (src_dir / "code.py").write_text("print('hello')")
        proj = resolve_project(std, config, project_dir=str(src_dir), initialize=True)
        (proj.settings_path / "marker.txt").write_text("ac-data")

        dst_dir = tmp_home / "dup_ac_dst"

        args = self._make_args(src_dir, dst_dir, "decentralized")
        rc = run_duplicate(args)
        assert rc == 0

        # Destination should have decentralized layout.
        assert (dst_dir / ".kanibako").is_dir()
        assert (dst_dir / ".kanibako" / "marker.txt").read_text() == "ac-data"
        assert (dst_dir / "code.py").read_text() == "print('hello')"
        # No breadcrumb in decentralized.
        assert not (dst_dir / ".kanibako" / "project-path.txt").exists()

    def test_duplicate_decentralized_to_ac(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "dup_dec_src"
        src_dir.mkdir()
        (src_dir / "code.py").write_text("print('dec')")
        proj = resolve_decentralized_project(
            std, config, project_dir=str(src_dir), initialize=True,
        )
        (proj.settings_path / "marker.txt").write_text("dec-data")

        dst_dir = tmp_home / "dup_dec_dst"

        args = self._make_args(src_dir, dst_dir, "account-centric")
        rc = run_duplicate(args)
        assert rc == 0

        # Destination should have AC layout.
        phash = project_hash(str(dst_dir.resolve()))
        projects_base = std.data_path / config.paths_projects_path
        ac_settings = projects_base / phash
        assert ac_settings.is_dir()
        assert (ac_settings / "marker.txt").read_text() == "dec-data"
        assert (ac_settings / "project-path.txt").read_text().strip() == str(dst_dir.resolve())
        assert (dst_dir / "code.py").read_text() == "print('dec')"

    def test_duplicate_cross_mode_bare(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "dup_bare_src"
        src_dir.mkdir()
        (src_dir / "code.py").write_text("print('bare')")
        resolve_project(std, config, project_dir=str(src_dir), initialize=True)

        dst_dir = tmp_home / "dup_bare_dst"

        args = self._make_args(src_dir, dst_dir, "decentralized", bare=True)
        rc = run_duplicate(args)
        assert rc == 0

        # Metadata exists but workspace content not copied.
        assert (dst_dir / ".kanibako").is_dir()
        assert not (dst_dir / "code.py").exists()

    def test_duplicate_cross_mode_preserves_source(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "dup_preserve_src"
        src_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(src_dir), initialize=True)
        (proj.settings_path / "marker.txt").write_text("original")

        dst_dir = tmp_home / "dup_preserve_dst"

        args = self._make_args(src_dir, dst_dir, "decentralized")
        rc = run_duplicate(args)
        assert rc == 0

        # Source should be unchanged.
        assert proj.settings_path.is_dir()
        assert (proj.settings_path / "marker.txt").read_text() == "original"

    def test_duplicate_cross_mode_excludes_lock(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "dup_lock_src"
        src_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(src_dir), initialize=True)
        (proj.settings_path / ".kanibako.lock").touch()

        dst_dir = tmp_home / "dup_lock_dst"

        args = self._make_args(src_dir, dst_dir, "decentralized", force=True)
        rc = run_duplicate(args)
        assert rc == 0

        assert not (dst_dir / ".kanibako" / ".kanibako.lock").exists()

    def test_duplicate_cross_mode_to_workset_error(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.box import run_duplicate

        config = load_config(config_file)
        std = load_std_paths(config)

        src_dir = tmp_home / "dup_ws_src"
        src_dir.mkdir()
        resolve_project(std, config, project_dir=str(src_dir), initialize=True)

        dst_dir = tmp_home / "dup_ws_dst"

        args = self._make_args(src_dir, dst_dir, "workset")
        rc = run_duplicate(args)
        assert rc == 1
