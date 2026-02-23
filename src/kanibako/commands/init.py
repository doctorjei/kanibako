"""kanibako init / new: create decentralized projects."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kanibako.config import config_file_path, load_config
from kanibako.paths import xdg, load_std_paths, resolve_decentralized_project


def add_init_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "init",
        help="Initialize a kanibako project in an existing directory",
        description="Initialize a kanibako project in the current (or given) directory.",
    )
    p.add_argument(
        "--local", action="store_true",
        help="Use decentralized mode (all state inside the project directory)",
    )
    p.add_argument(
        "-p", "--project", default=None,
        help="Path to the project directory (default: cwd)",
    )
    p.add_argument(
        "--no-vault", action="store_true",
        help="Disable vault directories (shared read-only and read-write mounts)",
    )
    p.add_argument(
        "--distinct-auth", action="store_true",
        help="Use distinct credentials (no sync from host)",
    )
    p.set_defaults(func=run_init)


def add_new_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "new",
        help="Create a new directory and initialize a kanibako project in it",
        description="Create a new directory and initialize a kanibako project.",
    )
    p.add_argument(
        "--local", action="store_true",
        help="Use decentralized mode (all state inside the project directory)",
    )
    p.add_argument(
        "path",
        help="Path to the new project directory (must not already exist)",
    )
    p.add_argument(
        "--no-vault", action="store_true",
        help="Disable vault directories (shared read-only and read-write mounts)",
    )
    p.add_argument(
        "--distinct-auth", action="store_true",
        help="Use distinct credentials (no sync from host)",
    )
    p.set_defaults(func=run_new)


def run_init(args: argparse.Namespace) -> int:
    if not args.local:
        print(
            "Please specify a project mode. Currently supported:\n"
            "  kanibako init --local",
            file=sys.stderr,
        )
        return 1

    config_file = config_file_path(xdg("XDG_CONFIG_HOME", ".config"))
    config = load_config(config_file)
    std = load_std_paths(config)

    project_dir = args.project
    vault_enabled = not getattr(args, "no_vault", False)
    auth = "distinct" if getattr(args, "distinct_auth", False) else None
    proj = resolve_decentralized_project(
        std, config, project_dir, initialize=True,
        vault_enabled=vault_enabled, auth=auth,
    )

    _write_project_gitignore(proj.project_path)

    if proj.is_new:
        print(f"Initialized decentralized project in {proj.project_path}")
    else:
        print(f"Project already initialized in {proj.project_path}")

    return 0


def run_new(args: argparse.Namespace) -> int:
    if not args.local:
        print(
            "Please specify a project mode. Currently supported:\n"
            "  kanibako new --local <path>",
            file=sys.stderr,
        )
        return 1

    target = Path(args.path)
    if target.exists():
        print(f"Error: path already exists: {target}", file=sys.stderr)
        return 1

    target.mkdir(parents=True)

    config_file = config_file_path(xdg("XDG_CONFIG_HOME", ".config"))
    config = load_config(config_file)
    std = load_std_paths(config)

    vault_enabled = not getattr(args, "no_vault", False)
    auth = "distinct" if getattr(args, "distinct_auth", False) else None
    proj = resolve_decentralized_project(
        std, config, str(target), initialize=True,
        vault_enabled=vault_enabled, auth=auth,
    )

    _write_project_gitignore(proj.project_path)

    print(f"Created decentralized project in {proj.project_path}")
    return 0


_GITIGNORE_ENTRIES = [".kanibako/"]


def _write_project_gitignore(project_path: Path) -> None:
    """Append .kanibako/ to the project's root .gitignore."""
    gitignore = project_path / ".gitignore"
    existing = ""
    if gitignore.is_file():
        existing = gitignore.read_text()

    lines_to_add = [
        entry for entry in _GITIGNORE_ENTRIES
        if entry not in existing.splitlines()
    ]

    if not lines_to_add:
        return

    with open(gitignore, "a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        for line in lines_to_add:
            f.write(line + "\n")
