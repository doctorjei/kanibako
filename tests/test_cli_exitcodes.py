"""Tests for kanibako.cli main() exit codes and decentralized launch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from kanibako.errors import KanibakoError, UserCancelled
from kanibako.paths import ProjectMode


def _fake_xdg(*args, **kwargs):
    """Return a mock Path whose / chain ends with .exists() → True."""
    p = MagicMock(spec=Path)
    p.__truediv__ = lambda self, other: p
    p.exists.return_value = True
    return p


class TestMainExitCodes:
    def test_user_cancelled_exits_2(self):
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_parser,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.side_effect = UserCancelled("nope")
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 2

    def test_kanibako_error_exits_1(self):
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_parser,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.side_effect = KanibakoError("boom")
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 1

    def test_keyboard_interrupt_exits_130(self):
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_parser,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.side_effect = KeyboardInterrupt()
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 130

    def test_success_exits_0(self):
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_parser,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.return_value = 0
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 0

    def test_nonzero_propagation(self):
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_parser,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "start"
            args.func.return_value = 42
            mock_parser.return_value.parse_args.return_value = args
            main(["start"])
        assert exc_info.value.code == 42

    def test_no_command_defaults_to_start(self):
        """When no command given, main() prepends 'start' and parses once."""
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_bp,
            patch("kanibako.paths._xdg", side_effect=_fake_xdg),
            pytest.raises(SystemExit) as exc_info,
        ):
            parser = MagicMock()
            mock_bp.return_value = parser

            with_cmd = MagicMock()
            with_cmd.command = "start"
            with_cmd.func.return_value = 0
            parser.parse_args.return_value = with_cmd

            main([])
        assert exc_info.value.code == 0
        parser.parse_args.assert_called_once_with(["start"])


class TestConfigPreCheck:
    def test_missing_config_exits_1(self, tmp_path, monkeypatch):
        """Running a non-setup command without config file exits 1."""
        from kanibako.cli import main

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no_config"))
        with pytest.raises(SystemExit) as exc_info:
            main(["start"])
        assert exc_info.value.code == 1

    def test_setup_exempt_from_config_check(self):
        """'setup' command does not fail on missing config."""
        from kanibako.cli import main

        with (
            patch("kanibako.cli.build_parser") as mock_bp,
            pytest.raises(SystemExit) as exc_info,
        ):
            args = MagicMock()
            args.command = "setup"
            args.func.return_value = 0
            mock_bp.return_value.parse_args.return_value = args
            main(["setup"])
        assert exc_info.value.code == 0


class TestDecentralizedLaunch:
    """Tests for decentralized project detection and launch (Phase 8.3)."""

    def _make_decentralized_proj(self, project_path):
        """Build a MagicMock ProjectPaths for decentralized mode."""
        proj = MagicMock()
        proj.is_new = False
        proj.mode = ProjectMode.decentralized
        proj.project_path = project_path
        proj.project_hash = "abc123"
        proj.settings_path = project_path / ".kanibako"
        proj.dot_path = project_path / ".kanibako" / "dotclaude"
        proj.cfg_file = project_path / ".kanibako" / "claude.json"
        proj.shell_path = project_path / ".shell"
        proj.vault_ro_path = project_path / "vault" / "share-ro"
        proj.vault_rw_path = project_path / "vault" / "share-rw"
        return proj

    def test_start_detects_decentralized_project(self, start_mocks, tmp_path):
        """start from an init --local dir uses resolve_any_project which returns decentralized."""
        from kanibako.commands.start import _run_container

        project = tmp_path / "myproject"
        project.mkdir()
        (project / ".kanibako").mkdir()

        with start_mocks() as m:
            proj = self._make_decentralized_proj(project)
            m.resolve_any_project.return_value = proj

            rc = _run_container(
                project_dir=str(project), entrypoint=None, image_override=None,
                new_session=False, safe_mode=False, resume_mode=False,
                extra_args=[],
            )

        assert rc == 0
        m.resolve_any_project.assert_called_once()

    def test_start_decentralized_creates_lock(self, start_mocks, tmp_path):
        """.kanibako/.kanibako.lock is used during run."""
        from kanibako.commands.start import _run_container

        project = tmp_path / "myproject"
        project.mkdir()
        kanibako_dir = project / ".kanibako"
        kanibako_dir.mkdir()

        with start_mocks() as m:
            proj = self._make_decentralized_proj(project)
            m.resolve_any_project.return_value = proj

            rc = _run_container(
                project_dir=str(project), entrypoint=None, image_override=None,
                new_session=False, safe_mode=False, resume_mode=False,
                extra_args=[],
            )

        assert rc == 0
        # The lock file path derives from proj.settings_path / ".kanibako.lock"
        # which is project/.kanibako/.kanibako.lock
        m.fcntl.flock.assert_called()

    def test_start_decentralized_passes_correct_paths(self, start_mocks, tmp_path):
        """runtime.run() receives paths inside the project dir."""
        from kanibako.commands.start import _run_container

        project = tmp_path / "myproject"
        project.mkdir()
        (project / ".kanibako").mkdir()

        with start_mocks() as m:
            proj = self._make_decentralized_proj(project)
            m.resolve_any_project.return_value = proj

            _run_container(
                project_dir=str(project), entrypoint=None, image_override=None,
                new_session=False, safe_mode=False, resume_mode=False,
                extra_args=[],
            )

        call_kwargs = m.runtime.run.call_args.kwargs
        assert call_kwargs["settings_path"] == project / ".kanibako"
        assert call_kwargs["dot_path"] == project / ".kanibako" / "dotclaude"
        assert call_kwargs["shell_path"] == project / ".shell"
        assert call_kwargs["project_path"] == project

    def test_start_decentralized_credential_flow(self, start_mocks, tmp_path):
        """Credential refresh uses project's .kanibako/dotclaude/.credentials.json."""
        from kanibako.commands.start import _run_container

        project = tmp_path / "myproject"
        project.mkdir()
        (project / ".kanibako").mkdir()

        with start_mocks() as m:
            proj = self._make_decentralized_proj(project)
            m.resolve_any_project.return_value = proj

            _run_container(
                project_dir=str(project), entrypoint=None, image_override=None,
                new_session=False, safe_mode=False, resume_mode=False,
                extra_args=[],
            )

        # refresh_central_to_project called with project creds path
        c2p_args = m.refresh_central_to_project.call_args
        project_creds = c2p_args[0][1]
        assert project_creds == project / ".kanibako" / "dotclaude" / ".credentials.json"

        # writeback called with same project creds path
        wb_args = m.writeback.call_args
        assert wb_args[0][0] == project / ".kanibako" / "dotclaude" / ".credentials.json"

    def test_shell_works_with_decentralized(self, start_mocks, tmp_path):
        """shell auto-detects decentralized mode via resolve_any_project."""
        from kanibako.commands.start import run_shell

        import argparse
        args = argparse.Namespace(project=str(tmp_path), entrypoint=None)
        (tmp_path / ".kanibako").mkdir()

        with start_mocks() as m:
            proj = self._make_decentralized_proj(tmp_path)
            m.resolve_any_project.return_value = proj

            rc = run_shell(args)

        assert rc == 0
        m.resolve_any_project.assert_called_once()

    def test_resume_works_with_decentralized(self, start_mocks, tmp_path):
        """resume auto-detects decentralized mode via resolve_any_project."""
        from kanibako.commands.start import run_resume

        import argparse
        args = argparse.Namespace(project=str(tmp_path), safe=False)
        (tmp_path / ".kanibako").mkdir()

        with start_mocks() as m:
            proj = self._make_decentralized_proj(tmp_path)
            m.resolve_any_project.return_value = proj

            rc = run_resume(args)

        assert rc == 0
        m.resolve_any_project.assert_called_once()

    def test_start_account_centric_still_works(self, start_mocks, tmp_path):
        """Non-decentralized dir falls through to account-centric."""
        from kanibako.commands.start import _run_container

        project = tmp_path / "regular_project"
        project.mkdir()

        with start_mocks() as m:
            # Default start_mocks proj is account_centric
            rc = _run_container(
                project_dir=str(project), entrypoint=None, image_override=None,
                new_session=False, safe_mode=False, resume_mode=False,
                extra_args=[],
            )

        assert rc == 0
        m.resolve_any_project.assert_called_once()

    def test_start_decentralized_no_orphan_hint(self, start_mocks, tmp_path, capsys):
        """No orphan hint printed for decentralized projects."""
        from kanibako.commands.start import _run_container

        project = tmp_path / "myproject"
        project.mkdir()
        (project / ".kanibako").mkdir()

        with start_mocks() as m:
            proj = self._make_decentralized_proj(project)
            proj.is_new = True  # new project, but decentralized
            m.resolve_any_project.return_value = proj

            with patch("kanibako.paths.iter_projects") as m_iter:
                orphan_path = MagicMock()
                orphan_path.is_dir.return_value = False
                m_iter.return_value = [(MagicMock(), orphan_path)]
                _run_container(
                    project_dir=str(project), entrypoint=None, image_override=None,
                    new_session=False, safe_mode=False, resume_mode=False,
                    extra_args=[],
                )

        captured = capsys.readouterr()
        assert "orphaned" not in captured.err
