"""Extended tests for kanibako.config: legacy .rc parsing, TOML flattening, project config."""

from __future__ import annotations

from pathlib import Path

import pytest

from kanibako.config import (
    KanibakoConfig,
    _flatten_toml,
    load_config,
    load_merged_config,
    write_global_config,
    write_project_config,
)


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
