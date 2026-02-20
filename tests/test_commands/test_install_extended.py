"""Extended tests for clodbox.commands.install (setup): cron, migration, containers dir."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clodbox.config import ClodboxConfig, load_config, write_global_config


class TestInstallExtended:
    def _base_setup(self, tmp_home):
        """Set up home with host credentials."""
        home = tmp_home / "home"
        claude_dir = home / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        (claude_dir / ".credentials.json").write_text(
            json.dumps({"claudeAiOauth": {"token": "t"}})
        )
        (home / ".claude.json").write_text(
            json.dumps({"oauthAccount": "a", "installMethod": "cli"})
        )
        return home

    def test_cron_entry_added(self, tmp_home):
        from clodbox.commands.install import _install_cron

        with patch("clodbox.commands.install.subprocess.run") as m_run:
            # crontab -l returns empty
            m_run.return_value = MagicMock(returncode=0, stdout="")
            _install_cron()
            # Should call crontab -l then crontab -
            assert m_run.call_count == 2
            # Second call writes new crontab
            input_text = m_run.call_args_list[1].kwargs.get("input", "")
            assert "refresh-creds" in input_text

    def test_cron_dedup(self, tmp_home):
        from clodbox.commands.install import _install_cron

        existing = "0 */6 * * * /usr/bin/clodbox refresh-creds\nother job\n"
        with (
            patch("clodbox.commands.install.subprocess.run") as m_run,
            patch("clodbox.commands.install.shutil.which", return_value="/usr/bin/clodbox"),
        ):
            m_run.return_value = MagicMock(returncode=0, stdout=existing)
            _install_cron()
            input_text = m_run.call_args_list[1].kwargs.get("input", "")
            lines = [l for l in input_text.strip().splitlines() if "refresh-creds" in l]
            assert len(lines) == 1
            assert "other job" in input_text

    def test_crontab_unavailable(self, tmp_home):
        from clodbox.commands.install import _install_cron

        with patch(
            "clodbox.commands.install.subprocess.run",
            side_effect=FileNotFoundError("no crontab"),
        ):
            # Should not raise
            _install_cron()

    def test_existing_toml_not_overwritten(self, tmp_home):
        from clodbox.commands.install import run

        self._base_setup(tmp_home)
        config_file = tmp_home / "config" / "clodbox" / "clodbox.toml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        custom_cfg = ClodboxConfig(container_image="custom:v1")
        write_global_config(config_file, custom_cfg)

        with (
            patch("clodbox.commands.install.ContainerRuntime", side_effect=Exception("no")),
            patch("clodbox.commands.install._install_cron"),
        ):
            rc = run(argparse.Namespace())
        assert rc == 0
        # Custom image should be preserved
        loaded = load_config(config_file)
        assert loaded.container_image == "custom:v1"

    def test_legacy_rc_migrated(self, tmp_home):
        from clodbox.commands.install import run

        self._base_setup(tmp_home)
        config_dir = tmp_home / "config" / "clodbox"
        config_dir.mkdir(parents=True, exist_ok=True)
        rc_file = config_dir / "clodbox.rc"
        rc_file.write_text('CLODBOX_CONTAINER_IMAGE="migrated:v1"\n')

        with (
            patch("clodbox.commands.install.ContainerRuntime", side_effect=Exception("no")),
            patch("clodbox.commands.install._install_cron"),
        ):
            rc = run(argparse.Namespace())
        assert rc == 0
        toml_file = config_dir / "clodbox.toml"
        assert toml_file.exists()
        loaded = load_config(toml_file)
        assert loaded.container_image == "migrated:v1"
        assert (config_dir / "clodbox.rc.bak").exists()

    def test_fresh_install_writes_defaults(self, tmp_home):
        from clodbox.commands.install import run

        self._base_setup(tmp_home)
        config_file = tmp_home / "config" / "clodbox" / "clodbox.toml"
        assert not config_file.exists()

        with (
            patch("clodbox.commands.install.ContainerRuntime", side_effect=Exception("no")),
            patch("clodbox.commands.install._install_cron"),
        ):
            rc = run(argparse.Namespace())
        assert rc == 0
        assert config_file.exists()
        loaded = load_config(config_file)
        assert loaded.container_image == ClodboxConfig().container_image

