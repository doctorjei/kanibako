"""Tests for kanibako.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from kanibako.config import (
    KanibakoConfig,
    load_config,
    load_merged_config,
    migrate_rc,
    write_global_config,
    write_project_config,
)


class TestLoadConfig:
    def test_defaults(self, tmp_path):
        cfg = load_config(tmp_path / "nonexistent.toml")
        assert cfg.container_image == "ghcr.io/doctorjei/kanibako-base:latest"
        assert cfg.paths_dot_path == "dotclod"

    def test_round_trip(self, tmp_path):
        path = tmp_path / "test.toml"
        cfg = KanibakoConfig(container_image="custom:latest")
        write_global_config(path, cfg)
        loaded = load_config(path)
        assert loaded.container_image == "custom:latest"
        assert loaded.paths_relative_std_path == "kanibako"


class TestMergedConfig:
    def test_project_overrides_global(self, tmp_path):
        global_path = tmp_path / "global.toml"
        project_path = tmp_path / "project.toml"

        write_global_config(global_path)
        write_project_config(project_path, "my-image:v2")

        merged = load_merged_config(global_path, project_path)
        assert merged.container_image == "my-image:v2"

    def test_cli_overrides_all(self, tmp_path):
        global_path = tmp_path / "global.toml"
        project_path = tmp_path / "project.toml"

        write_global_config(global_path)
        write_project_config(project_path, "my-image:v2")

        merged = load_merged_config(
            global_path,
            project_path,
            cli_overrides={"container_image": "cli-image:v3"},
        )
        assert merged.container_image == "cli-image:v3"


class TestWriteProjectConfig:
    def test_creates_new(self, tmp_path):
        path = tmp_path / "project.toml"
        write_project_config(path, "new-image:latest")
        cfg = load_config(path)
        assert cfg.container_image == "new-image:latest"

    def test_updates_existing(self, tmp_path):
        path = tmp_path / "project.toml"
        write_project_config(path, "first:latest")
        write_project_config(path, "second:latest")
        cfg = load_config(path)
        assert cfg.container_image == "second:latest"


class TestMigrateRc:
    def test_migration(self, tmp_path):
        rc = tmp_path / "kanibako.rc"
        toml = tmp_path / "kanibako.toml"
        rc.write_text(
            '#!/usr/bin/env bash\n'
            'export CLODBOX_RELATIVE_STD_PATH="kanibako"\n'
            'export CLODBOX_INIT_CREDENTIALS_PATH="credentials"\n'
            'export CLODBOX_PROJECTS_PATH="projects"\n'
            'export CLODBOX_DOT_PATH="dotclod"\n'
            'export CLODBOX_CFG_FILE="dotclod.json"\n'
            'export CLODBOX_CONTAINER_IMAGE="ghcr.io/doctorjei/kanibako-base:latest"\n'
        )

        cfg = migrate_rc(rc, toml)
        assert cfg.container_image == "ghcr.io/doctorjei/kanibako-base:latest"
        assert cfg.paths_dot_path == "dotclod"
        assert toml.exists()
        assert rc.with_suffix(".rc.bak").exists()
        assert not rc.exists()
