"""Shared fixtures for kanibako tests."""

from __future__ import annotations

pytest_plugins = ["tests.conftest_integration"]

import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from kanibako.config import KanibakoConfig, write_global_config


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Set HOME, XDG dirs, and CWD to an isolated temp tree."""
    home = tmp_path / "home"
    home.mkdir()
    config_home = tmp_path / "config"
    data_home = tmp_path / "data"
    state_home = tmp_path / "state"
    cache_home = tmp_path / "cache"
    for d in (config_home, data_home, state_home, cache_home):
        d.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))

    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)

    return tmp_path


@pytest.fixture
def config_file(tmp_home):
    """Write a default kanibako.toml and return its path."""
    config_home = tmp_home / "config"
    cf = config_home / "kanibako" / "kanibako.toml"
    write_global_config(cf)
    return cf


@pytest.fixture
def sample_config():
    """Return a default KanibakoConfig."""
    return KanibakoConfig()


@pytest.fixture
def credentials_dir(tmp_home, config_file):
    """Create a minimal credential store and return the data path."""
    from kanibako.config import load_config
    config = load_config(config_file)
    data_home = tmp_home / "data"
    data_path = data_home / config.paths_relative_std_path
    creds_path = data_path / config.paths_init_credentials_path
    dot_template = creds_path / config.paths_dot_path
    dot_template.mkdir(parents=True, exist_ok=True)

    # Write a sample credentials file
    creds = {"claudeAiOauth": {"token": "test-token"}, "someOtherKey": True}
    (dot_template / ".credentials.json").write_text(json.dumps(creds))

    # Write a sample cfg file
    cfg = {"oauthAccount": "test", "hasCompletedOnboarding": True}
    (creds_path / config.paths_cfg_file).write_text(json.dumps(cfg))

    return data_path


@pytest.fixture
def fake_git_repo(tmp_home):
    """Create a real git repo (git init + commit) in tmp_home/project. Returns the project Path."""
    project = tmp_home / "project"
    project.mkdir(exist_ok=True)
    subprocess.run(["git", "init"], cwd=project, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=project, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=project, capture_output=True, check=True,
    )
    readme = project / "README.md"
    readme.write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=project, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=project, capture_output=True, check=True,
    )
    return project


@pytest.fixture
def corrupt_credentials(tmp_home):
    """Create credential files with various defects. Returns dict of scenario->Path."""
    base = tmp_home / "corrupt_creds"
    base.mkdir()

    malformed = base / "malformed.json"
    malformed.write_text("{bad json!!")

    empty = base / "empty.json"
    empty.write_text("")

    missing_oauth = base / "missing_oauth.json"
    missing_oauth.write_text(json.dumps({"someOtherKey": True}))

    permission_denied = base / "noperm.json"
    permission_denied.write_text(json.dumps({"claudeAiOauth": {"token": "x"}}))
    permission_denied.chmod(0o000)

    return {
        "malformed": malformed,
        "empty": empty,
        "missing_oauth": missing_oauth,
        "permission_denied": permission_denied,
    }


@pytest.fixture
def project_env(config_file, credentials_dir, tmp_home):
    """Combines config + credentials + resolve_project into a single namespace."""
    from kanibako.config import load_config
    from kanibako.paths import load_std_paths, resolve_project

    config = load_config(config_file)
    std = load_std_paths(config)
    project_dir = str(tmp_home / "project")
    proj = resolve_project(std, config, project_dir=project_dir, initialize=True)
    return SimpleNamespace(
        config=config, std=std, proj=proj, project_dir=project_dir,
        config_file=config_file, tmp_home=tmp_home,
    )


@pytest.fixture
def mock_runtime():
    """Pre-configured MagicMock of ContainerRuntime."""
    rt = MagicMock()
    rt.image_exists.return_value = False
    rt.pull.return_value = True
    rt.run.return_value = 0
    return rt


@pytest.fixture
def start_mocks():
    """Context-manager fixture that patches all external deps of _run_container.

    Yields a SimpleNamespace of all mocks for fine-grained control.
    """
    @contextmanager
    def _make():
        with (
            patch("kanibako.commands.start.load_config") as m_load_config,
            patch("kanibako.commands.start.load_std_paths") as m_load_std,
            patch("kanibako.commands.start.resolve_project") as m_resolve,
            patch("kanibako.commands.start.load_merged_config") as m_merged,
            patch("kanibako.commands.start.ContainerRuntime") as m_rt_cls,
            patch("kanibako.commands.start.refresh_host_to_central") as m_h2c,
            patch("kanibako.commands.start.refresh_central_to_project") as m_c2p,
            patch("kanibako.commands.start.writeback_project_to_central_and_host") as m_wb,
            patch("kanibako.commands.start.fcntl") as m_fcntl,
            patch("builtins.open", MagicMock()) as m_open,
        ):
            proj = MagicMock()
            proj.is_new = False
            proj.settings_path = MagicMock()
            proj.settings_path.__truediv__ = MagicMock(return_value=MagicMock())
            proj.dot_path.__truediv__ = MagicMock(return_value=MagicMock())
            m_resolve.return_value = proj

            merged = MagicMock()
            merged.container_image = "test:latest"
            m_merged.return_value = merged

            runtime = MagicMock()
            runtime.run.return_value = 0
            m_rt_cls.return_value = runtime

            yield SimpleNamespace(
                load_config=m_load_config,
                load_std_paths=m_load_std,
                resolve_project=m_resolve,
                load_merged_config=m_merged,
                runtime_cls=m_rt_cls,
                runtime=runtime,
                proj=proj,
                merged=merged,
                refresh_host_to_central=m_h2c,
                refresh_central_to_project=m_c2p,
                writeback=m_wb,
                fcntl=m_fcntl,
                open=m_open,
            )

    return _make
