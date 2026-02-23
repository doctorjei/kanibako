"""Tests for kanibako.commands.remove."""

from __future__ import annotations

import argparse
from unittest.mock import patch


from kanibako.config import write_global_config


class TestRemove:
    def test_removes_config(self, tmp_home):
        from kanibako.commands.remove import run

        config_file = tmp_home / "config" / "kanibako.toml"
        write_global_config(config_file)
        assert config_file.exists()

        with patch("kanibako.commands.remove.confirm_prompt"):
            args = argparse.Namespace()
            rc = run(args)

        assert rc == 0
        assert not config_file.exists()
