"""kanibako purge: remove project session data."""

from __future__ import annotations

import argparse
import shutil
import sys

from kanibako.config import load_config
from kanibako.errors import UserCancelled
from kanibako.paths import load_std_paths, resolve_any_project
from kanibako.utils import confirm_prompt, short_hash


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "purge",
        help="Remove all project session data",
        description="Remove all project session data (credentials, conversation history).",
    )
    p.add_argument("path", nargs="?", default=None, help="Path to the project directory")
    p.add_argument(
        "--all", action="store_true", dest="all_projects",
        help="Purge session data for every known project",
    )
    p.add_argument(
        "--force", action="store_true", help="Skip confirmation prompt"
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from kanibako.paths import _xdg
    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)
    std = load_std_paths(config)

    if args.all_projects:
        return _purge_all(std, config, force=args.force)

    if args.path is None:
        print("Error: specify a project path, or use --all", file=sys.stderr)
        return 1

    return _purge_one(std, config, args.path, force=args.force)


def _purge_one(std, config, path: str, *, force: bool) -> int:
    """Purge session data for a single project."""
    proj = resolve_any_project(std, config, project_dir=path, initialize=False)

    if not proj.settings_path.is_dir():
        print(f"No session data found for project {proj.project_path}")
        return 0

    if not force:
        h8 = short_hash(proj.project_hash)
        print(f"Project: {proj.project_path}")
        print(f"Hash: {h8}")
        print()
        try:
            confirm_prompt(
                "Delete all session data for this project? This cannot be undone.\n"
                "Type 'yes' to confirm: "
            )
        except UserCancelled:
            print("Aborted.")
            return 2

    print("Removing session data... ", end="", flush=True)
    shutil.rmtree(proj.settings_path)
    print("done.")
    print(f"Session data removed for {proj.project_path}")
    return 0


def _purge_all(std, config, *, force: bool) -> int:
    """Purge session data for all known projects."""
    from kanibako.paths import iter_projects

    projects = iter_projects(std, config)
    if not projects:
        print("No project session data found.")
        return 0

    print(f"Found {len(projects)} project(s):")
    for settings_path, project_path in projects:
        h8 = short_hash(settings_path.name)
        label = str(project_path) if project_path else f"(unknown) {h8}"
        print(f"  {label}")
    print()

    if not force:
        try:
            confirm_prompt(
                "Delete ALL session data for every project listed above? "
                "This cannot be undone.\n"
                "Type 'yes' to confirm: "
            )
        except UserCancelled:
            print("Aborted.")
            return 2

    removed = 0
    for settings_path, project_path in projects:
        label = str(project_path) if project_path else short_hash(settings_path.name)
        print(f"Removing {label}... ", end="", flush=True)
        shutil.rmtree(settings_path)
        print("done.")
        removed += 1

    print(f"\nPurged session data for {removed} project(s).")
    return 0
