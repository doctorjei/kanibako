"""Tests for kanibako.commands.install (setup subcommand)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from kanibako.config import load_config


class TestInstall:
    def test_writes_config(self, tmp_home):
        from kanibako.commands.install import run

        config_file = tmp_home / "config" / "kanibako" / "kanibako.toml"
        assert not config_file.exists()

        # Mock host credential files and container runtime
        home = tmp_home / "home"
        claude_dir = home / ".claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / ".credentials.json").write_text(
            json.dumps({"claudeAiOauth": {"token": "t"}})
        )
        (home / ".claude.json").write_text(
            json.dumps({"oauthAccount": "a", "installMethod": "cli"})
        )

        with (
            patch("kanibako.commands.install.ContainerRuntime", side_effect=Exception("no runtime")),
            patch("kanibako.commands.install._install_cron"),
        ):
            args = argparse.Namespace()
            rc = run(args)

        assert rc == 0
        assert config_file.exists()
        cfg = load_config(config_file)
        assert cfg.container_image == "ghcr.io/doctorjei/kanibako-base:latest"
