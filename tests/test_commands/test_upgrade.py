"""Tests for kanibako.commands.upgrade."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from kanibako.commands.upgrade import run, _get_repo_dir


class TestGetRepoDir:
    def test_finds_repo(self):
        # The actual kanibako repo should be found
        repo = _get_repo_dir()
        assert repo is not None
        assert (repo / ".git").is_dir()
        assert (repo / "src" / "kanibako").is_dir()


class TestUpgrade:
    def test_check_up_to_date(self, capsys):
        with (
            patch("kanibako.commands.upgrade._get_repo_dir") as m_repo,
            patch("kanibako.commands.upgrade._git") as m_git,
        ):
            m_repo.return_value = Path("/fake/repo")

            def git_side_effect(*args, cwd):
                result = MagicMock()
                result.returncode = 0
                if args[0] == "status":
                    result.stdout = ""
                elif args[0] == "rev-parse" and args[1] == "HEAD":
                    result.stdout = "abc123def456"
                elif args[0] == "fetch":
                    result.stdout = ""
                elif args[0] == "rev-parse" and "--abbrev-ref" in args:
                    result.stdout = "origin/main"
                elif args[0] == "rev-parse" and args[1] == "origin/main":
                    result.stdout = "abc123def456"  # Same as HEAD = up to date
                return result

            m_git.side_effect = git_side_effect

            args = argparse.Namespace(check=False)
            rc = run(args)
            assert rc == 0
            out = capsys.readouterr().out
            assert "up to date" in out

    def test_check_updates_available(self, capsys):
        with (
            patch("kanibako.commands.upgrade._get_repo_dir") as m_repo,
            patch("kanibako.commands.upgrade._git") as m_git,
        ):
            m_repo.return_value = Path("/fake/repo")

            def git_side_effect(*args, cwd):
                result = MagicMock()
                result.returncode = 0
                if args[0] == "status":
                    result.stdout = ""
                elif args[0] == "rev-parse" and args[1] == "HEAD":
                    result.stdout = "abc123def456"
                elif args[0] == "fetch":
                    result.stdout = ""
                elif args[0] == "rev-parse" and "--abbrev-ref" in args:
                    result.stdout = "origin/main"
                elif args[0] == "rev-parse" and args[1] == "origin/main":
                    result.stdout = "xyz789000000"  # Different = updates available
                elif args[0] == "rev-list":
                    result.stdout = "3"
                elif args[0] == "pull":
                    result.stdout = ""
                elif args[0] == "diff":
                    result.stdout = ""
                return result

            m_git.side_effect = git_side_effect

            args = argparse.Namespace(check=False)
            rc = run(args)
            assert rc == 0
            out = capsys.readouterr().out
            assert "3 commit(s) available" in out

    def test_check_only_no_pull(self, capsys):
        with (
            patch("kanibako.commands.upgrade._get_repo_dir") as m_repo,
            patch("kanibako.commands.upgrade._git") as m_git,
        ):
            m_repo.return_value = Path("/fake/repo")
            calls = []

            def git_side_effect(*args, cwd):
                calls.append(args[0])
                result = MagicMock()
                result.returncode = 0
                if args[0] == "status":
                    result.stdout = ""
                elif args[0] == "rev-parse" and args[1] == "HEAD":
                    result.stdout = "abc123def456"
                elif args[0] == "fetch":
                    result.stdout = ""
                elif args[0] == "rev-parse" and "--abbrev-ref" in args:
                    result.stdout = "origin/main"
                elif args[0] == "rev-parse" and args[1] == "origin/main":
                    result.stdout = "xyz789000000"
                elif args[0] == "rev-list":
                    result.stdout = "3"
                return result

            m_git.side_effect = git_side_effect

            args = argparse.Namespace(check=True)
            rc = run(args)
            assert rc == 0
            assert "pull" not in calls

    def test_no_repo_found(self, capsys):
        with patch("kanibako.commands.upgrade._get_repo_dir", return_value=None):
            args = argparse.Namespace(check=False)
            rc = run(args)
            assert rc == 1
            err = capsys.readouterr().err
            assert "Could not find" in err

    def test_uncommitted_changes_blocks_upgrade(self, capsys):
        with (
            patch("kanibako.commands.upgrade._get_repo_dir") as m_repo,
            patch("kanibako.commands.upgrade._git") as m_git,
        ):
            m_repo.return_value = Path("/fake/repo")

            def git_side_effect(*args, cwd):
                result = MagicMock()
                result.returncode = 0
                if args[0] == "status":
                    result.stdout = "M some_file.py"  # Uncommitted changes
                elif args[0] == "rev-parse" and args[1] == "HEAD":
                    result.stdout = "abc123def456"
                elif args[0] == "fetch":
                    result.stdout = ""
                elif args[0] == "rev-parse" and "--abbrev-ref" in args:
                    result.stdout = "origin/main"
                elif args[0] == "rev-parse" and args[1] == "origin/main":
                    result.stdout = "xyz789000000"
                elif args[0] == "rev-list":
                    result.stdout = "3"
                return result

            m_git.side_effect = git_side_effect

            args = argparse.Namespace(check=False)
            rc = run(args)
            assert rc == 1
            err = capsys.readouterr().err
            assert "uncommitted changes" in err
