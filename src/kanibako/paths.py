"""XDG resolution, project hash computation, directory creation, and initialization."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from kanibako.config import KanibakoConfig, load_config
from kanibako.errors import ConfigError, ProjectError, WorksetError
from kanibako.utils import project_hash

if TYPE_CHECKING:
    from kanibako.workset import Workset


class ProjectMode(Enum):
    """How a project's persistent state is organized on disk."""

    account_centric = "account_centric"
    workset = "workset"
    decentralized = "decentralized"


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
    settings_path: Path     # ~/.local/share/kanibako/settings/{hash}
    dot_path: Path           # settings_path / "dotclaude" (→ /home/agent/.claude)
    cfg_file: Path           # settings_path / "claude.json" (→ /home/agent/.claude.json)
    shell_path: Path         # ~/.local/share/kanibako/shell/{hash} (→ /home/agent)
    vault_ro_path: Path      # {project}/vault/share-ro (→ /home/agent/share-ro)
    vault_rw_path: Path      # {project}/vault/share-rw (→ /home/agent/share-rw)
    is_new: bool = field(default=False)
    mode: ProjectMode = field(default=ProjectMode.account_centric)


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
    shell_path = std.data_path / "shell" / phash
    vault_ro_path = project_path / "vault" / "share-ro"
    vault_rw_path = project_path / "vault" / "share-rw"

    is_new = False
    if initialize and not settings_path.is_dir():
        _init_project(
            std, settings_path, dot_path, cfg_file, shell_path,
            vault_ro_path, vault_rw_path, project_path,
        )
        is_new = True

    if initialize:
        # Recovery: ensure dot_path exists even if settings_path was present.
        if not dot_path.is_dir():
            dot_path.mkdir(parents=True, exist_ok=True)
        if not cfg_file.exists():
            cfg_file.touch()
        # Ensure shell_path exists even for pre-existing projects.
        if not shell_path.is_dir():
            shell_path.mkdir(parents=True, exist_ok=True)
            _bootstrap_shell(shell_path)
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
        shell_path=shell_path,
        vault_ro_path=vault_ro_path,
        vault_rw_path=vault_rw_path,
        is_new=is_new,
        mode=ProjectMode.account_centric,
    )


def _bootstrap_shell(shell_path: Path) -> None:
    """Write minimal shell skeleton files into a new shell directory."""
    bashrc = shell_path / ".bashrc"
    if not bashrc.exists():
        bashrc.write_text(
            "# kanibako shell environment\n"
            "[ -f /etc/bashrc ] && . /etc/bashrc\n"
            'export PS1="(kanibako) \\u@\\h:\\w\\$ "\n'
        )
    profile = shell_path / ".profile"
    if not profile.exists():
        profile.write_text(
            "# kanibako login profile\n"
            "[ -f ~/.bashrc ] && . ~/.bashrc\n"
        )


def _init_project(
    std: StandardPaths,
    settings_path: Path,
    dot_path: Path,
    cfg_file: Path,
    shell_path: Path,
    vault_ro_path: Path,
    vault_rw_path: Path,
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

    # Persistent agent home (shell).
    shell_path.mkdir(parents=True, exist_ok=True)
    _bootstrap_shell(shell_path)

    # Vault directories.
    vault_ro_path.mkdir(parents=True, exist_ok=True)
    vault_rw_path.mkdir(parents=True, exist_ok=True)
    # .gitignore in vault/ to exclude share-rw from version control.
    vault_dir = vault_ro_path.parent
    gitignore = vault_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("share-rw/\n")

    print("done.", file=sys.stderr)


def detect_project_mode(
    project_dir: Path,
    std: StandardPaths,
    config: KanibakoConfig,
) -> ProjectMode:
    """Infer which project mode applies to *project_dir*.

    Detection order:
    1. Workset — *project_dir* lives inside a registered workset root's
       ``workspaces/`` directory.
    2. Account-centric — ``settings/{hash}/`` already exists under
       *std.data_path*.
    3. Decentralized — a ``.kanibako`` **directory** exists inside
       *project_dir*.
    4. Default — ``account_centric`` (new project).
    """
    # 1. Workset check: is project_dir inside a registered workset's
    #    workspaces/ directory?
    worksets_toml = std.data_path / "worksets.toml"
    if worksets_toml.is_file():
        import tomllib as _tomllib
        with open(worksets_toml, "rb") as _f:
            _data = _tomllib.load(_f)
        for _root_str in _data.get("worksets", {}).values():
            _ws_workspaces = Path(_root_str) / "workspaces"
            try:
                project_dir.relative_to(_ws_workspaces)
                return ProjectMode.workset
            except ValueError:
                continue

    # 2. Account-centric: settings/{hash}/ already exists
    phash = project_hash(str(project_dir))
    settings_path = std.data_path / config.paths_projects_path / phash
    if settings_path.is_dir():
        return ProjectMode.account_centric

    # 3. Decentralized: .kanibako directory inside project
    if (project_dir / ".kanibako").is_dir():
        return ProjectMode.decentralized

    # 4. Default for new projects
    return ProjectMode.account_centric


def resolve_workset_project(
    ws: Workset,
    project_name: str,
    std: StandardPaths,
    config: KanibakoConfig,
    *,
    initialize: bool = False,
) -> ProjectPaths:
    """Resolve per-project paths for a project inside a workset.

    Raises ``WorksetError`` if *project_name* is not registered in *ws*.
    """
    # Look up project in workset.
    found = None
    for p in ws.projects:
        if p.name == project_name:
            found = p
            break
    if found is None:
        raise WorksetError(
            f"Project '{project_name}' not found in workset '{ws.name}'."
        )

    # Name-based paths (not hash-based).
    project_path = ws.workspaces_dir / project_name
    settings_path = ws.settings_dir / project_name
    dot_path = settings_path / config.paths_dot_path
    cfg_file = settings_path / config.paths_cfg_file
    shell_path = ws.shell_dir / project_name
    vault_ro_path = ws.vault_dir / project_name / "share-ro"
    vault_rw_path = ws.vault_dir / project_name / "share-rw"

    # Hash the resolved workspace path for container naming.
    phash = project_hash(str(project_path.resolve()))

    is_new = False
    if initialize and not dot_path.is_dir():
        _init_workset_project(std, settings_path, dot_path, cfg_file, shell_path)
        is_new = True

    if initialize:
        # Recovery: ensure dot_path exists even if settings_path was present.
        if not dot_path.is_dir():
            dot_path.mkdir(parents=True, exist_ok=True)
        if not cfg_file.exists():
            cfg_file.touch()
        if not shell_path.is_dir():
            shell_path.mkdir(parents=True, exist_ok=True)
            _bootstrap_shell(shell_path)

    return ProjectPaths(
        project_path=project_path,
        project_hash=phash,
        settings_path=settings_path,
        dot_path=dot_path,
        cfg_file=cfg_file,
        shell_path=shell_path,
        vault_ro_path=vault_ro_path,
        vault_rw_path=vault_rw_path,
        is_new=is_new,
        mode=ProjectMode.workset,
    )


def _init_workset_project(
    std: StandardPaths,
    settings_path: Path,
    dot_path: Path,
    cfg_file: Path,
    shell_path: Path,
) -> None:
    """First-time workset project setup: copy credentials and bootstrap shell.

    Unlike ``_init_project``, this does not write a ``project-path.txt``
    breadcrumb (workset.toml already records source_path) and does not create
    vault ``.gitignore`` files (vault lives under the workset root, not inside
    a user git repo).
    """
    import sys

    print(
        f"[One Time Setup] Initializing workset project in {settings_path}... ",
        end="",
        flush=True,
        file=sys.stderr,
    )
    settings_path.mkdir(parents=True, exist_ok=True)

    # Copy credential template tree into project settings.
    creds = std.credentials_path
    if creds.is_dir():
        shutil.copytree(str(creds), str(settings_path), dirs_exist_ok=True)
    else:
        dot_path.mkdir(parents=True, exist_ok=True)
        cfg_file.touch()

    # Persistent agent home (shell).
    shell_path.mkdir(parents=True, exist_ok=True)
    _bootstrap_shell(shell_path)

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


def resolve_any_project(
    std: StandardPaths,
    config: KanibakoConfig,
    project_dir: str | None = None,
    *,
    initialize: bool = False,
) -> ProjectPaths:
    """Auto-detect project mode and resolve paths accordingly."""
    raw = project_dir or os.getcwd()
    raw_dir = Path(raw).resolve()
    mode = detect_project_mode(raw_dir, std, config)
    if mode == ProjectMode.decentralized:
        return resolve_decentralized_project(std, config, project_dir, initialize=initialize)
    return resolve_project(std, config, project_dir=project_dir, initialize=initialize)


def resolve_decentralized_project(
    std: StandardPaths,
    config: KanibakoConfig,
    project_dir: str | None = None,
    *,
    initialize: bool = False,
) -> ProjectPaths:
    """Resolve (and optionally initialize) per-project paths for decentralized mode.

    All project state lives inside *project_dir* itself (``.kanibako/``,
    ``.shell/``, ``vault/``).  No data is written to ``$XDG_DATA_HOME``.
    """
    raw = project_dir or os.getcwd()
    project_path = Path(raw).resolve()

    if not project_path.is_dir():
        raise ProjectError(f"Project path '{project_path}' does not exist.")

    phash = project_hash(str(project_path))
    settings_path = project_path / ".kanibako"
    dot_path = settings_path / config.paths_dot_path
    cfg_file = settings_path / config.paths_cfg_file
    shell_path = project_path / ".shell"
    vault_ro_path = project_path / "vault" / "share-ro"
    vault_rw_path = project_path / "vault" / "share-rw"

    is_new = False
    if initialize and not settings_path.is_dir():
        _init_decentralized_project(
            std, settings_path, dot_path, cfg_file, shell_path,
            vault_ro_path, vault_rw_path, project_path,
        )
        is_new = True

    if initialize:
        # Recovery: ensure dot_path exists even if settings_path was present.
        if not dot_path.is_dir():
            dot_path.mkdir(parents=True, exist_ok=True)
        if not cfg_file.exists():
            cfg_file.touch()
        if not shell_path.is_dir():
            shell_path.mkdir(parents=True, exist_ok=True)
            _bootstrap_shell(shell_path)

    return ProjectPaths(
        project_path=project_path,
        project_hash=phash,
        settings_path=settings_path,
        dot_path=dot_path,
        cfg_file=cfg_file,
        shell_path=shell_path,
        vault_ro_path=vault_ro_path,
        vault_rw_path=vault_rw_path,
        is_new=is_new,
        mode=ProjectMode.decentralized,
    )


def _init_decentralized_project(
    std: StandardPaths,
    settings_path: Path,
    dot_path: Path,
    cfg_file: Path,
    shell_path: Path,
    vault_ro_path: Path,
    vault_rw_path: Path,
    project_path: Path,
) -> None:
    """First-time decentralized project setup: all state inside project dir.

    Unlike ``_init_project``, this does not write a ``project-path.txt``
    breadcrumb (the project is self-contained).  Unlike workset init, this
    *does* create vault directories and a ``.gitignore`` (vault lives inside
    the user's project, likely a git repo).
    """
    import sys

    print(
        f"[One Time Setup] Initializing kanibako in {project_path}... ",
        end="",
        flush=True,
        file=sys.stderr,
    )
    settings_path.mkdir(parents=True, exist_ok=True)

    # Copy credential template tree into project settings.
    creds = std.credentials_path
    if creds.is_dir():
        shutil.copytree(str(creds), str(settings_path), dirs_exist_ok=True)
    else:
        dot_path.mkdir(parents=True, exist_ok=True)
        cfg_file.touch()

    # Persistent agent home (shell).
    shell_path.mkdir(parents=True, exist_ok=True)
    _bootstrap_shell(shell_path)

    # Vault directories.
    vault_ro_path.mkdir(parents=True, exist_ok=True)
    vault_rw_path.mkdir(parents=True, exist_ok=True)
    # .gitignore in vault/ to exclude share-rw from version control.
    vault_dir = vault_ro_path.parent
    gitignore = vault_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("share-rw/\n")

    print("done.", file=sys.stderr)
