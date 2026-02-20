"""XDG resolution, project hash computation, directory creation, and initialization."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from kanibako.config import KanibakoConfig, load_config
from kanibako.errors import ConfigError, ProjectError
from kanibako.utils import project_hash


@dataclass
class StandardPaths:
    """Resolved XDG and kanibako standard directory paths."""

    config_home: Path
    data_home: Path
    state_home: Path
    cache_home: Path
    config_file: Path
    data_path: Path
    state_path: Path
    cache_path: Path
    credentials_path: Path


@dataclass
class ProjectPaths:
    """Resolved paths for a specific project."""

    project_path: Path
    project_hash: str
    settings_path: Path
    dot_path: Path
    cfg_file: Path
    is_new: bool = field(default=False)


def _xdg(env_var: str, default_suffix: str) -> Path:
    """Resolve an XDG directory from environment or default under $HOME."""
    val = os.environ.get(env_var, "")
    if val:
        return Path(val).resolve()
    return Path.home() / default_suffix


def load_std_paths(config: KanibakoConfig | None = None) -> StandardPaths:
    """Compute all standard kanibako directories.

    If *config* is None, it is loaded from the config file (which must exist).
    Directories are created as needed.
    """
    config_home = _xdg("XDG_CONFIG_HOME", ".config")
    data_home = _xdg("XDG_DATA_HOME", ".local/share")
    state_home = _xdg("XDG_STATE_HOME", ".local/state")
    cache_home = _xdg("XDG_CACHE_HOME", ".cache")

    config_file = config_home / "kanibako" / "kanibako.toml"

    if config is None:
        if not config_file.exists():
            # Check for legacy .rc file
            legacy = config_file.with_name("kanibako.rc")
            if legacy.exists():
                raise ConfigError(
                    f"Legacy config {legacy} found but no kanibako.toml. "
                    "Run 'kanibako setup' to migrate."
                )
            raise ConfigError(
                f"{config_file} is missing. Run 'kanibako setup' to set up."
            )
        config = load_config(config_file)

    rel = config.paths_relative_std_path
    data_path = data_home / rel
    state_path = state_home / rel
    cache_path = cache_home / rel
    credentials_path = data_path / config.paths_init_credentials_path

    # Ensure directories exist.
    config_file.parent.mkdir(parents=True, exist_ok=True)
    data_path.mkdir(parents=True, exist_ok=True)
    state_path.mkdir(parents=True, exist_ok=True)
    cache_path.mkdir(parents=True, exist_ok=True)

    return StandardPaths(
        config_home=config_home,
        data_home=data_home,
        state_home=state_home,
        cache_home=cache_home,
        config_file=config_file,
        data_path=data_path,
        state_path=state_path,
        cache_path=cache_path,
        credentials_path=credentials_path,
    )


def resolve_project(
    std: StandardPaths,
    config: KanibakoConfig,
    project_dir: str | None = None,
    *,
    initialize: bool = False,
) -> ProjectPaths:
    """Resolve (and optionally initialize) per-project paths.

    When *initialize* is True (used by ``start``), missing project directories
    are created and credential templates are copied in.  When False (used by
    subcommands like ``archive``/``purge``), the paths are merely computed.
    """
    raw = project_dir or os.getcwd()
    project_path = Path(raw).resolve()

    if not project_path.is_dir():
        raise ProjectError(f"Project path '{project_path}' does not exist.")

    phash = project_hash(str(project_path))
    settings_path = std.data_path / config.paths_projects_path / phash
    dot_path = settings_path / config.paths_dot_path
    cfg_file = settings_path / config.paths_cfg_file

    is_new = False
    if initialize and not settings_path.is_dir():
        _init_project(std, settings_path, dot_path, cfg_file, project_path)
        is_new = True

    if initialize:
        # Recovery: ensure dot_path exists even if settings_path was present.
        if not dot_path.is_dir():
            dot_path.mkdir(parents=True, exist_ok=True)
        if not cfg_file.exists():
            cfg_file.touch()
        # Backfill project-path.txt for pre-existing projects.
        breadcrumb = settings_path / "project-path.txt"
        if settings_path.is_dir() and not breadcrumb.exists():
            breadcrumb.write_text(str(project_path) + "\n")

    return ProjectPaths(
        project_path=project_path,
        project_hash=phash,
        settings_path=settings_path,
        dot_path=dot_path,
        cfg_file=cfg_file,
        is_new=is_new,
    )


def _init_project(
    std: StandardPaths,
    settings_path: Path,
    dot_path: Path,
    cfg_file: Path,
    project_path: Path,
) -> None:
    """First-time project setup: create directories, copy credential template."""
    import sys

    print(
        f"[One Time Setup] Initializing kanibako in {project_path}... ",
        end="",
        flush=True,
        file=sys.stderr,
    )
    settings_path.mkdir(parents=True, exist_ok=True)

    # Record the original project path for reverse lookup.
    (settings_path / "project-path.txt").write_text(str(project_path) + "\n")

    # Copy credential template tree into project settings.
    creds = std.credentials_path
    if creds.is_dir():
        shutil.copytree(str(creds), str(settings_path), dirs_exist_ok=True)
    else:
        dot_path.mkdir(parents=True, exist_ok=True)
        cfg_file.touch()

    print("done.", file=sys.stderr)


def iter_projects(std: StandardPaths, config: KanibakoConfig) -> list[tuple[Path, Path | None]]:
    """Return ``(settings_path, project_path | None)`` for every known project.

    *project_path* is read from the ``project-path.txt`` breadcrumb when
    available; otherwise it is ``None``.
    """
    projects_dir = std.data_path / config.paths_projects_path
    if not projects_dir.is_dir():
        return []
    results: list[tuple[Path, Path | None]] = []
    for entry in sorted(projects_dir.iterdir()):
        if not entry.is_dir():
            continue
        breadcrumb = entry / "project-path.txt"
        project_path = None
        if breadcrumb.is_file():
            text = breadcrumb.read_text().strip()
            if text:
                project_path = Path(text)
        results.append((entry, project_path))
    return results
