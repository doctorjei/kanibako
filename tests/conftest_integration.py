"""Shared fixtures for integration tests.

Pytest auto-discovers this alongside conftest.py.  All fixtures here
support tests marked ``@pytest.mark.integration`` that exercise real
container runtimes, real git repos, and real filesystem operations.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from kanibako.config import write_global_config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LIGHTWEIGHT_IMAGE = "busybox:latest"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_runtime() -> str | None:
    """Return the absolute path to podman or docker, or *None*."""
    for name in ("podman", "docker"):
        path = shutil.which(name)
        if path is not None:
            return path
    return None


# ---------------------------------------------------------------------------
# Skip markers
# ---------------------------------------------------------------------------

requires_runtime = pytest.mark.skipif(
    _find_runtime() is None,
    reason="No container runtime (podman/docker) found on PATH",
)

requires_git = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git is not installed",
)

requires_crontab = pytest.mark.skipif(
    shutil.which("crontab") is None,
    reason="crontab is not installed",
)

# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def container_runtime_cmd() -> str:
    """Return the real podman/docker path or skip the entire session."""
    cmd = _find_runtime()
    if cmd is None:
        pytest.skip("No container runtime available")
    return cmd


@pytest.fixture(scope="session")
def pulled_image(container_runtime_cmd: str) -> str:
    """Ensure the lightweight image is pulled once per session.

    Returns the image name (``busybox:latest``).
    """
    subprocess.run(
        [container_runtime_cmd, "pull", LIGHTWEIGHT_IMAGE],
        capture_output=True,
        check=True,
    )
    return LIGHTWEIGHT_IMAGE


# ---------------------------------------------------------------------------
# Per-test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def integration_home(tmp_path, monkeypatch):
    """Isolated HOME / XDG tree for integration tests.

    Identical in spirit to ``tmp_home`` but uses a distinct name so both
    can coexist in the same session without confusion.
    """
    home = tmp_path / "int_home"
    home.mkdir()
    config_home = tmp_path / "int_config"
    data_home = tmp_path / "int_data"
    state_home = tmp_path / "int_state"
    cache_home = tmp_path / "int_cache"
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
def integration_config(integration_home):
    """Write a default ``kanibako.toml`` and return its path."""
    config_home = integration_home / "int_config"
    cf = config_home / "kanibako.toml"
    write_global_config(cf)
    return cf


@pytest.fixture
def integration_credentials(integration_home, integration_config):
    """Set up host credentials for integration tests. Returns the data path."""
    from kanibako.config import load_config

    config = load_config(integration_config)
    data_home = integration_home / "int_data"
    data_path = data_home / (config.paths_data_path or "kanibako")
    data_path.mkdir(parents=True, exist_ok=True)

    # Write host credentials (used directly by init now)
    home = integration_home / "int_home"
    host_claude = home / ".claude"
    host_claude.mkdir(parents=True, exist_ok=True)
    creds = {"claudeAiOauth": {"token": "integration-test-token"}, "extra": True}
    (host_claude / ".credentials.json").write_text(json.dumps(creds))

    cfg = {"oauthAccount": "int-test", "hasCompletedOnboarding": True}
    (home / ".claude.json").write_text(json.dumps(cfg))

    return data_path


@pytest.fixture
def real_git_repo(integration_home):
    """git init + commit inside ``integration_home/project``.

    Returns the project ``Path``.
    """
    project = integration_home / "project"
    project.mkdir(exist_ok=True)
    subprocess.run(["git", "init"], cwd=project, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "integration@test.com"],
        cwd=project,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "IntegrationTest"],
        cwd=project,
        capture_output=True,
        check=True,
    )
    readme = project / "README.md"
    readme.write_text("# integration test\n")
    subprocess.run(["git", "add", "."], cwd=project, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=project,
        capture_output=True,
        check=True,
    )
    return project
