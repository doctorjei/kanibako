"""Tests for kanibako.commands.install (setup subcommand)."""

from __future__ import annotations

import argparse
import json
from unittest.mock import patch


from kanibako.config import KanibakoConfig, load_config, write_global_config


class TestInstall:
    def test_writes_config(self, tmp_home):
        from kanibako.commands.install import run

        config_file = tmp_home / "config" / "kanibako.toml"
        assert not config_file.exists()

        with patch("kanibako.commands.install.ContainerRuntime", side_effect=Exception("no runtime")):
            args = argparse.Namespace()
            rc = run(args)

        assert rc == 0
        assert config_file.exists()
        cfg = load_config(config_file)
        assert cfg.container_image == "ghcr.io/doctorjei/kanibako-base:latest"


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

    def test_existing_toml_not_overwritten(self, tmp_home):
        from kanibako.commands.install import run

        self._base_setup(tmp_home)
        config_file = tmp_home / "config" / "kanibako.toml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        custom_cfg = KanibakoConfig(container_image="custom:v1")
        write_global_config(config_file, custom_cfg)

        with patch("kanibako.commands.install.ContainerRuntime", side_effect=Exception("no")):
            rc = run(argparse.Namespace())
        assert rc == 0
        # Custom image should be preserved
        loaded = load_config(config_file)
        assert loaded.container_image == "custom:v1"

    def test_fresh_install_writes_defaults(self, tmp_home):
        from kanibako.commands.install import run

        self._base_setup(tmp_home)
        config_file = tmp_home / "config" / "kanibako.toml"
        assert not config_file.exists()

        with patch("kanibako.commands.install.ContainerRuntime", side_effect=Exception("no")):
            rc = run(argparse.Namespace())
        assert rc == 0
        assert config_file.exists()
        loaded = load_config(config_file)
        assert loaded.container_image == KanibakoConfig().container_image
