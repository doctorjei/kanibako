"""Extended tests for kanibako.config: legacy .rc parsing, TOML flattening, project config."""

from __future__ import annotations

from pathlib import Path

import pytest

from kanibako.config import (
    ClodboxConfig,
    _flatten_toml,
    load_config,
    load_merged_config,
    migrate_rc,
    write_global_config,
    write_project_config,
)


# ---------------------------------------------------------------------------
# Legacy .rc parsing edge cases
# ---------------------------------------------------------------------------

class TestMigrateRcEdgeCases:
    def test_comments_ignored(self, tmp_path):
        rc = tmp_path / "kanibako.rc"
        toml = tmp_path / "kanibako.toml"
        rc.write_text("# This is a comment\nKANIBAKO_DOT_PATH=mypath\n")
        cfg = migrate_rc(rc, toml)
        assert cfg.paths_dot_path == "mypath"

    def test_bang_lines_ignored(self, tmp_path):
        rc = tmp_path / "kanibako.rc"
        toml = tmp_path / "kanibako.toml"
        rc.write_text("#!/bin/bash\nKANIBAKO_DOT_PATH=mypath\n")
        cfg = migrate_rc(rc, toml)
        assert cfg.paths_dot_path == "mypath"

    def test_export_prefix_stripped(self, tmp_path):
        rc = tmp_path / "kanibako.rc"
        toml = tmp_path / "kanibako.toml"
        rc.write_text('export KANIBAKO_CONTAINER_IMAGE="custom:v1"\n')
        cfg = migrate_rc(rc, toml)
        assert cfg.container_image == "custom:v1"

    def test_mixed_quoting(self, tmp_path):
        rc = tmp_path / "kanibako.rc"
        toml = tmp_path / "kanibako.toml"
        rc.write_text(
            'KANIBAKO_DOT_PATH="double"\n'
            "KANIBAKO_CFG_FILE='single'\n"
        )
        cfg = migrate_rc(rc, toml)
        assert cfg.paths_dot_path == "double"
        assert cfg.paths_cfg_file == "single"

    def test_empty_value(self, tmp_path):
        rc = tmp_path / "kanibako.rc"
        toml = tmp_path / "kanibako.toml"
        rc.write_text("KANIBAKO_DOT_PATH=\n")
        cfg = migrate_rc(rc, toml)
        assert cfg.paths_dot_path == ""

    def test_unknown_keys_ignored(self, tmp_path):
        rc = tmp_path / "kanibako.rc"
        toml = tmp_path / "kanibako.toml"
        rc.write_text("UNKNOWN_KEY=value\nKANIBAKO_DOT_PATH=ok\n")
        cfg = migrate_rc(rc, toml)
        assert cfg.paths_dot_path == "ok"
        assert not hasattr(cfg, "unknown_key")

    def test_no_equals_skipped(self, tmp_path):
        rc = tmp_path / "kanibako.rc"
        toml = tmp_path / "kanibako.toml"
        rc.write_text("this line has no equals sign\nKANIBAKO_DOT_PATH=ok\n")
        cfg = migrate_rc(rc, toml)
        assert cfg.paths_dot_path == "ok"

    def test_mixed_valid_invalid(self, tmp_path):
        rc = tmp_path / "kanibako.rc"
        toml = tmp_path / "kanibako.toml"
        rc.write_text(
            "# header\n"
            "KANIBAKO_DOT_PATH=dot1\n"
            "BAD_LINE\n"
            "export KANIBAKO_CFG_FILE=cfg1\n"
            "UNKNOWN=nope\n"
        )
        cfg = migrate_rc(rc, toml)
        assert cfg.paths_dot_path == "dot1"
        assert cfg.paths_cfg_file == "cfg1"
        # Backup created
        assert (tmp_path / "kanibako.rc.bak").exists()


# ---------------------------------------------------------------------------
# TOML flattening
# ---------------------------------------------------------------------------

class TestFlattenToml:
    def test_nested_dict(self):
        data = {"paths": {"dot_path": "x", "cfg_file": "y"}}
        flat = _flatten_toml(data)
        assert flat == {"paths_dot_path": "x", "paths_cfg_file": "y"}

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": "deep"}}}
        flat = _flatten_toml(data)
        assert flat == {"a_b_c": "deep"}

    def test_flat_input(self):
        data = {"key": "val"}
        flat = _flatten_toml(data)
        assert flat == {"key": "val"}


# ---------------------------------------------------------------------------
# Multiple project.toml updates
# ---------------------------------------------------------------------------

class TestWriteProjectConfig:
    def test_update_existing_image(self, tmp_path):
        p = tmp_path / "project.toml"
        write_project_config(p, "img:v1")
        assert 'image = "img:v1"' in p.read_text()
        write_project_config(p, "img:v2")
        text = p.read_text()
        assert 'image = "img:v2"' in text
        assert "img:v1" not in text

    def test_add_image_to_container_section(self, tmp_path):
        p = tmp_path / "project.toml"
        p.write_text("[container]\n# empty section\n")
        write_project_config(p, "new:img")
        text = p.read_text()
        assert 'image = "new:img"' in text

    def test_create_new_file(self, tmp_path):
        p = tmp_path / "sub" / "project.toml"
        write_project_config(p, "fresh:v1")
        assert p.exists()
        assert "[container]" in p.read_text()
        assert 'image = "fresh:v1"' in p.read_text()
