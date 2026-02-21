"""Tests for resolve_decentralized_project() in kanibako.paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kanibako.config import load_config
from kanibako.errors import ProjectError
from kanibako.paths import (
    ProjectMode,
    load_std_paths,
    resolve_decentralized_project,
)
from kanibako.utils import project_hash


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def std(config_file, tmp_home):
    config = load_config(config_file)
    return load_std_paths(config)


@pytest.fixture
def config(config_file):
    return load_config(config_file)


@pytest.fixture
def project_dir(tmp_home):
    """Return the pre-existing project directory created by tmp_home."""
    return tmp_home / "project"


# ---------------------------------------------------------------------------
# TestResolveDecentralizedProject
# ---------------------------------------------------------------------------

class TestResolveDecentralizedProject:
    def test_returns_decentralized_mode(self, std, config, project_dir):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        assert proj.mode is ProjectMode.decentralized

    def test_paths_are_inside_project_dir(self, std, config, project_dir):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        resolved = project_dir.resolve()
        assert proj.project_path == resolved
        assert proj.settings_path == resolved / ".kanibako"
        assert proj.dot_path == resolved / ".kanibako" / config.paths_dot_path
        assert proj.cfg_file == resolved / ".kanibako" / config.paths_cfg_file
        assert proj.shell_path == resolved / ".shell"
        assert proj.vault_ro_path == resolved / "vault" / "share-ro"
        assert proj.vault_rw_path == resolved / "vault" / "share-rw"

    def test_project_hash_is_sha256_of_resolved_path(
        self, std, config, project_dir,
    ):
        proj = resolve_decentralized_project(std, config, str(project_dir))
        expected = project_hash(str(project_dir.resolve()))
        assert proj.project_hash == expected

    def test_nonexistent_path_raises(self, std, config, tmp_home):
        missing = tmp_home / "does-not-exist"
        with pytest.raises(ProjectError, match="does not exist"):
            resolve_decentralized_project(std, config, str(missing))

    def test_defaults_to_cwd(self, std, config, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        proj = resolve_decentralized_project(std, config, project_dir=None)
        assert proj.project_path == project_dir.resolve()

    def test_initialize_creates_settings_and_dot_path(
        self, std, config, project_dir, credentials_dir,
    ):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        assert proj.settings_path.is_dir()
        assert proj.dot_path.is_dir()

    def test_initialize_copies_credentials(
        self, std, config, project_dir, credentials_dir,
    ):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        creds_file = proj.dot_path / ".credentials.json"
        assert creds_file.is_file()
        data = json.loads(creds_file.read_text())
        assert "claudeAiOauth" in data

    def test_initialize_bootstraps_shell(
        self, std, config, project_dir, credentials_dir,
    ):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        assert (proj.shell_path / ".bashrc").is_file()
        assert (proj.shell_path / ".profile").is_file()

    def test_initialize_creates_vault_dirs(
        self, std, config, project_dir, credentials_dir,
    ):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        assert proj.vault_ro_path.is_dir()
        assert proj.vault_rw_path.is_dir()

    def test_initialize_creates_vault_gitignore(
        self, std, config, project_dir, credentials_dir,
    ):
        resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        gitignore = project_dir.resolve() / "vault" / ".gitignore"
        assert gitignore.is_file()
        assert "share-rw/" in gitignore.read_text()

    def test_no_initialize_skips_creation(self, std, config, project_dir):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=False,
        )
        assert not proj.settings_path.is_dir()
        assert not proj.is_new

    def test_is_new_true_on_first_init(
        self, std, config, project_dir, credentials_dir,
    ):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        assert proj.is_new is True

    def test_is_new_false_on_reinit(
        self, std, config, project_dir, credentials_dir,
    ):
        resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        proj2 = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        assert proj2.is_new is False

    def test_no_breadcrumb(
        self, std, config, project_dir, credentials_dir,
    ):
        """Decentralized projects should NOT create project-path.txt."""
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        assert not (proj.settings_path / "project-path.txt").exists()

    def test_recovery_missing_dot_path(
        self, std, config, project_dir, credentials_dir,
    ):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        import shutil
        shutil.rmtree(proj.dot_path)
        assert not proj.dot_path.exists()

        proj2 = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        assert proj2.dot_path.is_dir()

    def test_recovery_missing_cfg_file(
        self, std, config, project_dir, credentials_dir,
    ):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        proj.cfg_file.unlink()
        assert not proj.cfg_file.exists()

        proj2 = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        assert proj2.cfg_file.exists()

    def test_recovery_missing_shell(
        self, std, config, project_dir, credentials_dir,
    ):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        import shutil
        shutil.rmtree(proj.shell_path)
        assert not proj.shell_path.exists()

        proj2 = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        assert proj2.shell_path.is_dir()
        assert (proj2.shell_path / ".bashrc").is_file()
        assert (proj2.shell_path / ".profile").is_file()


# ---------------------------------------------------------------------------
# TestDecentralizedCredentialFlow
# ---------------------------------------------------------------------------

class TestDecentralizedCredentialFlow:
    def test_credential_paths_inside_project(
        self, std, config, project_dir, credentials_dir,
    ):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        creds_file = proj.dot_path / ".credentials.json"
        assert creds_file.is_file()
        # Path should be under .kanibako/, not $XDG_DATA_HOME.
        resolved = project_dir.resolve()
        assert str(resolved / ".kanibako") in str(creds_file)

    def test_refresh_central_to_project_works(
        self, std, config, project_dir, credentials_dir,
    ):
        proj = resolve_decentralized_project(
            std, config, str(project_dir), initialize=True,
        )
        from kanibako.credentials import refresh_central_to_project

        central = std.credentials_path / config.paths_dot_path / ".credentials.json"
        project_creds = proj.dot_path / ".credentials.json"

        # Touch central to ensure it's newer.
        import time
        time.sleep(0.05)
        central.write_text(json.dumps(
            {"claudeAiOauth": {"token": "refreshed-token"}}
        ))

        result = refresh_central_to_project(central, project_creds)
        assert result is True

        updated = json.loads(project_creds.read_text())
        assert updated["claudeAiOauth"]["token"] == "refreshed-token"
