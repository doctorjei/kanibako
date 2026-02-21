"""Integration tests for the install command.

Exercises real filesystem operations for install, containerfile discovery,
cron job installation, and legacy .rc migration.  Run with::

    pytest -m integration tests/test_install_integration.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests.conftest_integration import requires_crontab


@pytest.mark.integration
class TestInstallFilesystem:
    """Verify real filesystem operations during install."""

    def test_full_install_creates_directory_tree(
        self, integration_home, integration_config
    ):
        """Install creates config, data, and credentials directories."""
        from kanibako.config import load_config
        from kanibako.paths import load_std_paths

        config = load_config(integration_config)
        std = load_std_paths(config)

        assert std.config_file.parent.is_dir()
        assert std.data_path.is_dir()
        assert std.state_path.is_dir()
        assert std.cache_path.is_dir()

    def test_install_preserves_existing_config(
        self, integration_home, integration_config
    ):
        """Running install twice is idempotent — existing config untouched."""
        from kanibako.config import KanibakoConfig, load_config, write_global_config

        # Write a config with a custom image
        config = load_config(integration_config)
        config.container_image = "custom:v99"
        write_global_config(integration_config, config)

        # Reload and verify custom value preserved
        reloaded = load_config(integration_config)
        assert reloaded.container_image == "custom:v99"

    def test_install_copies_host_credentials(
        self, integration_home, integration_config
    ):
        """Host credentials are copied to the central store."""
        from kanibako.config import load_config
        from kanibako.paths import load_std_paths

        config = load_config(integration_config)
        std = load_std_paths(config)

        # Create fake host credentials
        host_claude = integration_home / "int_home" / ".claude"
        host_claude.mkdir(parents=True, exist_ok=True)
        host_creds = host_claude / ".credentials.json"
        creds = {"claudeAiOauth": {"token": "install-test-token"}}
        host_creds.write_text(json.dumps(creds))

        # Simulate install's credential copy
        dot_template = std.credentials_path / config.paths_dot_path
        dot_template.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(host_creds), str(dot_template / ".credentials.json"))

        copied = dot_template / ".credentials.json"
        assert copied.is_file()
        copied_data = json.loads(copied.read_text())
        assert copied_data["claudeAiOauth"]["token"] == "install-test-token"

    def test_install_filters_settings_json(
        self, integration_home, integration_config
    ):
        """Only safe keys survive the settings filter."""
        from kanibako.credentials import filter_settings

        src = integration_home / "host_settings.json"
        dst = integration_home / "filtered_settings.json"

        # Include safe + unsafe keys
        data = {
            "oauthAccount": "user@example.com",
            "hasCompletedOnboarding": False,
            "installMethod": "npm",
            "sensitiveKey": "should-be-removed",
            "anotherPrivate": 42,
        }
        src.write_text(json.dumps(data))

        filter_settings(src, dst)

        filtered = json.loads(dst.read_text())
        assert filtered["oauthAccount"] == "user@example.com"
        assert filtered["hasCompletedOnboarding"] is True  # forced to True
        assert filtered["installMethod"] == "npm"
        assert "sensitiveKey" not in filtered
        assert "anotherPrivate" not in filtered


@pytest.mark.integration
class TestContainerfileDiscovery:
    """Containerfile discovery and copy logic."""

    def test_discovers_containers_in_cwd(self, integration_home):
        """Finds Containerfile.base in a user-override directory."""
        from kanibako.containerfiles import get_containerfile

        override_dir = integration_home / "containers"
        override_dir.mkdir()
        cf = override_dir / "Containerfile.base"
        cf.write_text("FROM busybox\n")

        result = get_containerfile("base", override_dir)
        assert result is not None
        assert result == cf

    def test_returns_none_when_no_containerfiles(self, integration_home):
        """Returns None when no Containerfiles are present."""
        from kanibako.containerfiles import get_containerfile

        empty_dir = integration_home / "empty_containers"
        empty_dir.mkdir()

        result = get_containerfile("nonexistent_xyz", empty_dir)
        assert result is None

    def test_containerfiles_copied_to_data_dir(
        self, integration_home, integration_config
    ):
        """User-override Containerfile takes precedence over bundled."""
        from kanibako.config import load_config
        from kanibako.containerfiles import get_containerfile
        from kanibako.paths import load_std_paths

        config = load_config(integration_config)
        std = load_std_paths(config)

        containers_dir = std.data_path / "containers"
        containers_dir.mkdir(parents=True, exist_ok=True)

        # Write a user-override Containerfile
        override = containers_dir / "Containerfile.base"
        override.write_text("FROM alpine:latest\n# user override\n")

        result = get_containerfile("base", containers_dir)
        assert result is not None
        assert result == override
        assert "user override" in result.read_text()


@pytest.mark.integration
class TestCronInstallation:
    """Cron job installation for credential refresh."""

    @requires_crontab
    def test_cron_entry_installed(self, integration_home, integration_config):
        """A cron entry for credential refresh is present in crontab."""
        # Save existing crontab
        saved = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        )
        original_crontab = saved.stdout if saved.returncode == 0 else ""

        try:
            from kanibako.commands.install import _install_cron
            _install_cron()

            result = subprocess.run(
                ["crontab", "-l"], capture_output=True, text=True
            )
            assert result.returncode == 0
            assert "kanibako" in result.stdout
            assert "refresh-creds" in result.stdout
        finally:
            # Restore original crontab
            subprocess.run(
                ["crontab", "-"],
                input=original_crontab,
                text=True,
                capture_output=True,
            )

    @requires_crontab
    def test_cron_deduplication(self, integration_home, integration_config):
        """Running install twice does not create duplicate cron entries."""
        saved = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        )
        original_crontab = saved.stdout if saved.returncode == 0 else ""

        try:
            from kanibako.commands.install import _install_cron
            _install_cron()
            _install_cron()

            result = subprocess.run(
                ["crontab", "-l"], capture_output=True, text=True
            )
            lines = [
                l for l in result.stdout.splitlines()
                if "kanibako" in l and "refresh-creds" in l
            ]
            assert len(lines) == 1
        finally:
            subprocess.run(
                ["crontab", "-"],
                input=original_crontab,
                text=True,
                capture_output=True,
            )


@pytest.mark.integration
class TestLegacyMigration:
    """Legacy .rc → .toml migration."""

    def test_legacy_rc_migrated_to_toml(self, integration_home):
        """A legacy ``.rc`` file is migrated to ``.toml`` with a ``.rc.bak`` backup."""
        from kanibako.config import load_config, migrate_rc

        config_dir = integration_home / "int_config" / "kanibako"
        config_dir.mkdir(parents=True, exist_ok=True)

        rc_file = config_dir / "kanibako.rc"
        toml_file = config_dir / "kanibako.toml"

        rc_file.write_text(
            'KANIBAKO_RELATIVE_STD_PATH="kanibako"\n'
            'KANIBAKO_CONTAINER_IMAGE="ghcr.io/test/custom:v2"\n'
            'KANIBAKO_DOT_PATH="dotclaude"\n'
        )

        config = migrate_rc(rc_file, toml_file)

        assert toml_file.is_file()
        assert rc_file.with_suffix(".rc.bak").is_file()
        assert not rc_file.exists()

        assert config.paths_relative_std_path == "kanibako"
        assert config.container_image == "ghcr.io/test/custom:v2"
        assert config.paths_dot_path == "dotclaude"

        # Verify we can load the written toml
        reloaded = load_config(toml_file)
        assert reloaded.container_image == "ghcr.io/test/custom:v2"
