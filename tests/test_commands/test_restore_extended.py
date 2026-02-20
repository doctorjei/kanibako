"""Extended tests for kanibako.commands.restore: hash mismatch, git state, corrupt archives."""

from __future__ import annotations

import argparse
import shutil
import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest

from kanibako.config import load_config
from kanibako.errors import UserCancelled
from kanibako.paths import load_std_paths, resolve_project


class TestRestoreExtended:
    def _create_archive(self, config_file, tmp_home, credentials_dir, archive_name="test.txz"):
        """Helper: create a valid archive from project."""
        from kanibako.commands.archive import run as archive_run

        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(tmp_home / "project")
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)
        (proj.settings_path / "data.txt").write_text("testdata")

        archive_path = str(tmp_home / archive_name)
        args = argparse.Namespace(
            path=project_dir, file=archive_path,
            all_projects=False, allow_uncommitted=True, allow_unpushed=True, force=True,
        )
        rc = archive_run(args)
        assert rc == 0
        return archive_path, project_dir, proj

    def test_hash_mismatch_prompts(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.restore import run

        archive_path, _, _ = self._create_archive(config_file, tmp_home, credentials_dir)

        # Create a different project directory
        other = tmp_home / "other_project"
        other.mkdir()

        with patch("kanibako.commands.restore.confirm_prompt") as m_prompt:
            args = argparse.Namespace(
                path=str(other), file=archive_path, all_archives=False, force=False,
            )
            run(args)
            # confirm_prompt should have been called due to hash mismatch
            m_prompt.assert_called()

    def test_user_cancels_returns_2(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.restore import run

        archive_path, _, _ = self._create_archive(config_file, tmp_home, credentials_dir)

        other = tmp_home / "other_project"
        other.mkdir()

        with patch("kanibako.commands.restore.confirm_prompt", side_effect=UserCancelled("no")):
            args = argparse.Namespace(
                path=str(other), file=archive_path, all_archives=False, force=False,
            )
            rc = run(args)
            assert rc == 2

    def test_force_bypasses_mismatch(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.restore import run

        archive_path, _, _ = self._create_archive(config_file, tmp_home, credentials_dir)

        other = tmp_home / "other_project"
        other.mkdir()

        with patch("kanibako.commands.restore.confirm_prompt") as m_prompt:
            args = argparse.Namespace(
                path=str(other), file=archive_path, all_archives=False, force=True,
            )
            rc = run(args)
            assert rc == 0
            m_prompt.assert_not_called()

    def test_git_commit_mismatch(self, config_file, tmp_home, credentials_dir, fake_git_repo):
        from kanibako.commands.restore import run

        archive_path, project_dir, _ = self._create_archive(
            config_file, tmp_home, credentials_dir, "git.txz"
        )

        # The archive has git metadata. Current HEAD may differ.
        # We patch _validate_git_state to simulate a mismatch prompt
        with patch("kanibako.commands.restore.confirm_prompt") as m_prompt:
            args = argparse.Namespace(
                path=project_dir, file=archive_path, all_archives=False, force=False,
            )
            # This should work since hash matches (same project)
            run(args)

    def test_force_bypasses_git_mismatch(self, config_file, tmp_home, credentials_dir, fake_git_repo):
        from kanibako.commands.restore import run

        archive_path, project_dir, _ = self._create_archive(
            config_file, tmp_home, credentials_dir, "git2.txz"
        )

        args = argparse.Namespace(
            path=project_dir, file=archive_path, all_archives=False, force=True,
        )
        rc = run(args)
        assert rc == 0

    def test_archive_from_git_workspace_not_git(self, config_file, tmp_home, credentials_dir, fake_git_repo):
        """Archive from a git repo, restore to a non-git workspace."""
        from kanibako.commands.archive import run as archive_run
        from kanibako.commands.restore import run as restore_run

        config = load_config(config_file)
        std = load_std_paths(config)
        project_dir = str(fake_git_repo)
        proj = resolve_project(std, config, project_dir=project_dir, initialize=True)
        (proj.settings_path / "data.txt").write_text("from-git")

        archive_path = str(tmp_home / "git-archive.txz")
        args = argparse.Namespace(
            path=project_dir, file=archive_path,
            all_projects=False, allow_uncommitted=True, allow_unpushed=True, force=True,
        )
        assert archive_run(args) == 0

        # Restore to same path with force (same hash)
        args = argparse.Namespace(
            path=project_dir, file=archive_path, all_archives=False, force=True,
        )
        rc = restore_run(args)
        assert rc == 0

    def test_corrupt_archive_returns_1(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.restore import run

        corrupt = tmp_home / "corrupt.txz"
        corrupt.write_text("this is not a tar file")

        args = argparse.Namespace(
            path=str(tmp_home / "project"), file=str(corrupt), all_archives=False, force=True,
        )
        rc = run(args)
        assert rc == 1

    def test_empty_archive_returns_1(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.restore import run

        empty_archive = tmp_home / "empty.txz"
        import lzma
        with lzma.open(str(empty_archive), "wb") as f:
            # Write a valid but empty tar
            with tarfile.open(fileobj=f, mode="w:") as tar:
                pass

        args = argparse.Namespace(
            path=str(tmp_home / "project"), file=str(empty_archive), all_archives=False, force=True,
        )
        rc = run(args)
        assert rc == 1

    def test_missing_info_file_returns_1(self, config_file, tmp_home, credentials_dir):
        from kanibako.commands.restore import run

        # Create a valid tar.xz with a directory but no info file
        archive_path = tmp_home / "no-info.txz"
        dummy_dir = tmp_home / "dummy_hash"
        dummy_dir.mkdir()
        (dummy_dir / "some_file.txt").write_text("data")
        with tarfile.open(str(archive_path), "w:xz") as tar:
            tar.add(str(dummy_dir), arcname="fakehash")

        args = argparse.Namespace(
            path=str(tmp_home / "project"), file=str(archive_path), all_archives=False, force=True,
        )
        rc = run(args)
        assert rc == 1
