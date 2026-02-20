"""Tests for kanibako.commands.migrate_clodbox."""

from __future__ import annotations

import argparse

import pytest

from kanibako.commands.migrate_clodbox import run


@pytest.fixture
def old_clodbox_env(tmp_path, monkeypatch):
    """Set up a fake clodbox installation for migration tests."""
    config_home = tmp_path / "config"
    data_home = tmp_path / "data"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    # Old clodbox config
    old_config_dir = config_home / "clodbox"
    old_config_dir.mkdir(parents=True)
    (old_config_dir / "clodbox.toml").write_text(
        '[paths]\n'
        'relative_std_path = "clodbox"\n'
        'projects_path = "projects"\n'
        'dot_path = "dotclod"\n'
        'cfg_file = "dotclod.json"\n'
        '\n'
        '[container]\n'
        'image = "ghcr.io/doctorjei/clodbox-base:latest"\n'
    )

    # Old clodbox data with one project
    old_data = data_home / "clodbox"
    project_hash = "abc123def456"
    proj_dir = old_data / "projects" / project_hash
    dotclod = proj_dir / "dotclod"
    dotclod.mkdir(parents=True)
    (dotclod / ".credentials.json").write_text('{"key": "val"}')
    (proj_dir / "dotclod.json").write_text("{}")
    (proj_dir / "project-path.txt").write_text("/home/user/myproject\n")

    # Old credentials
    creds = old_data / "credentials" / "dotclod"
    creds.mkdir(parents=True)
    (creds / ".credentials.json").write_text('{"template": true}')

    return {
        "config_home": config_home,
        "data_home": data_home,
        "project_hash": project_hash,
    }


class TestMigrateFromClodbox:
    def test_no_old_installation(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        rc = run(argparse.Namespace())
        assert rc == 1

    def test_already_configured(self, old_clodbox_env):
        env = old_clodbox_env
        # Create new config so migration refuses
        new_config = env["config_home"] / "kanibako"
        new_config.mkdir(parents=True)
        (new_config / "kanibako.toml").write_text("[paths]\n")

        rc = run(argparse.Namespace())
        assert rc == 1

    def test_successful_migration(self, old_clodbox_env):
        env = old_clodbox_env

        rc = run(argparse.Namespace())
        assert rc == 0

        # New config created
        new_config = env["config_home"] / "kanibako" / "kanibako.toml"
        assert new_config.exists()

        # Project data migrated
        new_settings = env["data_home"] / "kanibako" / "settings" / env["project_hash"]
        assert new_settings.is_dir()

        # dotclod renamed to dotclaude
        assert (new_settings / "dotclaude").is_dir()
        assert not (new_settings / "dotclod").exists()

        # dotclod.json renamed to claude.json
        assert (new_settings / "claude.json").is_file()
        assert not (new_settings / "dotclod.json").exists()

        # Shell directory created with skeleton
        shell_dir = env["data_home"] / "kanibako" / "shell" / env["project_hash"]
        assert shell_dir.is_dir()
        assert (shell_dir / ".bashrc").exists()
        assert (shell_dir / ".profile").exists()

        # Credentials migrated
        new_creds = env["data_home"] / "kanibako" / "credentials"
        assert new_creds.is_dir()

        # Old dirs renamed to migrated markers
        assert (env["config_home"] / "clodbox.migrated-to-kanibako").is_dir()
        assert not (env["config_home"] / "clodbox").exists()

    def test_preserves_custom_image(self, old_clodbox_env):
        env = old_clodbox_env

        # Set a custom image in old config
        old_config = env["config_home"] / "clodbox" / "clodbox.toml"
        old_config.write_text(
            '[paths]\n'
            'relative_std_path = "clodbox"\n'
            '\n'
            '[container]\n'
            'image = "custom-image:v2"\n'
        )

        rc = run(argparse.Namespace())
        assert rc == 0

        new_config = env["config_home"] / "kanibako" / "kanibako.toml"
        content = new_config.read_text()
        assert "custom-image:v2" in content

    def test_broken_symlinks_in_project(self, old_clodbox_env):
        """copytree must handle broken symlinks (e.g. debug/latest)."""
        env = old_clodbox_env
        proj = (
            env["data_home"]
            / "clodbox"
            / "projects"
            / env["project_hash"]
            / "dotclod"
            / "debug"
        )
        proj.mkdir(parents=True, exist_ok=True)
        (proj / "latest").symlink_to("/nonexistent/target")

        rc = run(argparse.Namespace())
        assert rc == 0

        dest = (
            env["data_home"]
            / "kanibako"
            / "settings"
            / env["project_hash"]
            / "dotclaude"
            / "debug"
            / "latest"
        )
        assert dest.is_symlink()

    def test_breadcrumb_preserved(self, old_clodbox_env):
        env = old_clodbox_env

        rc = run(argparse.Namespace())
        assert rc == 0

        new_settings = env["data_home"] / "kanibako" / "settings" / env["project_hash"]
        breadcrumb = new_settings / "project-path.txt"
        assert breadcrumb.read_text().strip() == "/home/user/myproject"
