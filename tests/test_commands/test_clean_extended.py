"""Extended tests for kanibako.commands.clean: decentralized mode support."""

from __future__ import annotations

import argparse

import pytest

from kanibako.config import load_config
from kanibako.paths import load_std_paths, resolve_project


class TestCleanExtended:
    def test_purge_decentralized_project(self, config_file, tmp_home):
        """Purge removes .kanibako/ for decentralized projects."""
        from kanibako.commands.clean import run

        project_dir = tmp_home / "project"
        kanibako_dir = project_dir / ".kanibako"
        kanibako_dir.mkdir()
        (kanibako_dir / "data.txt").write_text("session-data")

        args = argparse.Namespace(
            path=str(project_dir), all_projects=False, force=True,
        )
        rc = run(args)
        assert rc == 0
        assert not kanibako_dir.exists()

    def test_purge_all_skips_decentralized(self, config_file, tmp_home, credentials_dir, capsys):
        """--all only covers account-centric projects, not decentralized."""
        from kanibako.commands.clean import run

        config = load_config(config_file)
        std = load_std_paths(config)

        # Create an account-centric project
        ac_dir = tmp_home / "ac_project"
        ac_dir.mkdir()
        proj = resolve_project(std, config, project_dir=str(ac_dir), initialize=True)

        # Create a decentralized project
        dec_dir = tmp_home / "dec_project"
        dec_dir.mkdir()
        (dec_dir / ".kanibako").mkdir()
        (dec_dir / ".kanibako" / "data.txt").write_text("dec-data")

        args = argparse.Namespace(all_projects=True, force=True)
        rc = run(args)
        assert rc == 0

        # Account-centric settings should be gone
        assert not proj.settings_path.exists()
        # Decentralized .kanibako/ should still exist (not covered by --all)
        assert (dec_dir / ".kanibako" / "data.txt").exists()
