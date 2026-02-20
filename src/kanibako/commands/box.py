"""kanibako box: project lifecycle management (list, migrate, duplicate, archive, purge, restore)."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from kanibako.config import load_config
from kanibako.paths import _xdg, iter_projects, load_std_paths
from kanibako.utils import confirm_prompt, project_hash, short_hash


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "box",
        help="Project lifecycle commands (list, migrate, duplicate, archive, purge, restore)",
        description="Manage per-project session data: list, migrate, duplicate, archive, purge, restore.",
    )
    box_sub = p.add_subparsers(dest="box_command", metavar="COMMAND")

    # kanibako box list (default behavior)
    list_p = box_sub.add_parser(
        "list",
        help="List known projects and their status (default)",
        description="List all known kanibako projects with their hash, status, and path.",
    )
    list_p.set_defaults(func=run_list)

    # kanibako box migrate
    migrate_p = box_sub.add_parser(
        "migrate",
        help="Remap project data from old path to new path",
        description=(
            "Move project session data from one path hash to another.\n"
            "Use this after moving or renaming a project directory."
        ),
    )
    migrate_p.add_argument("old_path", help="Original project directory path")
    migrate_p.add_argument(
        "new_path", nargs="?", default=None,
        help="New project directory path (default: current working directory)",
    )
    migrate_p.add_argument(
        "--force", action="store_true", help="Skip confirmation prompt",
    )
    migrate_p.set_defaults(func=run_migrate)

    # kanibako box duplicate
    duplicate_p = box_sub.add_parser(
        "duplicate",
        help="Duplicate a project (workspace + metadata) under a new path",
        description=(
            "Copy a project's workspace directory and kanibako metadata to a new path.\n"
            "The metadata is re-keyed under the new path's hash."
        ),
    )
    duplicate_p.add_argument("source_path", help="Existing project directory to duplicate")
    duplicate_p.add_argument("new_path", help="Destination path for the duplicate")
    duplicate_p.add_argument(
        "--bare", action="store_true",
        help="Copy only kanibako metadata, don't touch the workspace directory",
    )
    duplicate_p.add_argument(
        "--force", action="store_true",
        help="Skip confirmation, overwrite existing data/metadata at destination",
    )
    duplicate_p.set_defaults(func=run_duplicate)

    # Reuse existing subcommand modules under box.
    from kanibako.commands.archive import add_parser as add_archive_parser
    from kanibako.commands.clean import add_parser as add_purge_parser
    from kanibako.commands.restore import add_parser as add_restore_parser

    add_archive_parser(box_sub)
    add_purge_parser(box_sub)
    add_restore_parser(box_sub)

    # Default to list if no subcommand given.
    p.set_defaults(func=run_list)


def run_list(args: argparse.Namespace) -> int:
    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)
    std = load_std_paths(config)

    projects = iter_projects(std, config)
    if not projects:
        print("No known projects.")
        return 0

    print(f"{'HASH':<10} {'STATUS':<10} {'PATH'}")
    for settings_path, project_path in projects:
        h8 = short_hash(settings_path.name)
        if project_path is None:
            status = "unknown"
            label = "(no breadcrumb)"
        elif project_path.is_dir():
            status = "ok"
            label = str(project_path)
        else:
            status = "missing"
            label = str(project_path)
        print(f"{h8:<10} {status:<10} {label}")

    return 0


def run_migrate(args: argparse.Namespace) -> int:
    import os

    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)
    std = load_std_paths(config)

    # Resolve paths — old path may no longer exist, so use str directly.
    old_path = Path(args.old_path).resolve()
    new_path = Path(args.new_path).resolve() if args.new_path else Path(os.getcwd()).resolve()

    # Validate: paths must differ.
    if old_path == new_path:
        print("Error: old and new paths are the same.", file=sys.stderr)
        return 1

    # Validate: new path must exist as a directory.
    if not new_path.is_dir():
        print(f"Error: new path does not exist as a directory: {new_path}", file=sys.stderr)
        return 1

    # Compute hashes.
    old_hash = project_hash(str(old_path))
    new_hash = project_hash(str(new_path))

    projects_base = std.data_path / config.paths_projects_path
    old_settings = projects_base / old_hash
    new_settings = projects_base / new_hash

    # Validate: old project data must exist.
    if not old_settings.is_dir():
        print(
            f"Error: no project data found for old path: {old_path}",
            file=sys.stderr,
        )
        print(f"  (expected: {old_settings})", file=sys.stderr)
        return 1

    # Validate: new project data must NOT already exist.
    if new_settings.is_dir():
        print(
            f"Error: project data already exists for new path: {new_path}",
            file=sys.stderr,
        )
        print("  Use 'kanibako box purge' to remove it first.", file=sys.stderr)
        return 1

    # Warn if lock file exists.
    lock_file = old_settings / ".kanibako.lock"
    if lock_file.exists():
        print(
            "Warning: lock file found — a container may be running for this project.",
            file=sys.stderr,
        )
        if not args.force:
            try:
                confirm_prompt("Continue anyway? Type 'yes' to confirm: ")
            except Exception:
                print("Aborted.")
                return 2

    # Confirm with user.
    if not args.force:
        print(f"Migrate project data:")
        print(f"  from: {old_path}")
        print(f"    to: {new_path}")
        print()
        try:
            confirm_prompt("Type 'yes' to confirm: ")
        except Exception:
            print("Aborted.")
            return 2

    # Atomic rename (same filesystem).
    old_settings.rename(new_settings)

    # Update the breadcrumb.
    breadcrumb = new_settings / "project-path.txt"
    breadcrumb.write_text(str(new_path) + "\n")

    print(f"Migrated project data:")
    print(f"  from: {old_path} ({short_hash(old_hash)})")
    print(f"    to: {new_path} ({short_hash(new_hash)})")
    return 0


def run_duplicate(args: argparse.Namespace) -> int:
    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)
    std = load_std_paths(config)

    source_path = Path(args.source_path).resolve()
    new_path = Path(args.new_path).resolve()

    # 1. Paths must differ.
    if source_path == new_path:
        print("Error: source and destination paths are the same.", file=sys.stderr)
        return 1

    # 2. Source must be an existing directory.
    if not source_path.is_dir():
        print(f"Error: source path does not exist as a directory: {source_path}", file=sys.stderr)
        return 1

    # 3. Source must have kanibako metadata.
    source_hash = project_hash(str(source_path))
    projects_base = std.data_path / config.paths_projects_path
    source_settings = projects_base / source_hash

    if not source_settings.is_dir():
        print(
            f"Error: no project data found for source path: {source_path}",
            file=sys.stderr,
        )
        return 1

    # 4. Non-bare: destination workspace must not already exist (unless --force).
    if not args.bare and new_path.exists() and not args.force:
        print(
            f"Error: destination already exists: {new_path}",
            file=sys.stderr,
        )
        print("  Use --force to overwrite.", file=sys.stderr)
        return 1

    # 5. Destination metadata must not already exist (unless --force).
    new_hash = project_hash(str(new_path))
    new_settings = projects_base / new_hash

    if new_settings.is_dir() and not args.force:
        print(
            f"Error: project data already exists for destination: {new_path}",
            file=sys.stderr,
        )
        print("  Use --force to overwrite.", file=sys.stderr)
        return 1

    # 6. Lock file warning.
    lock_file = source_settings / ".kanibako.lock"
    if lock_file.exists():
        print(
            "Warning: lock file found — a container may be running for this project.",
            file=sys.stderr,
        )
        if not args.force:
            print("Aborted.")
            return 2

    # 7. User confirmation.
    if not args.force:
        mode = "metadata only (bare)" if args.bare else "workspace + metadata"
        print(f"Duplicate project ({mode}):")
        print(f"  from: {source_path}")
        print(f"    to: {new_path}")
        print()
        try:
            confirm_prompt("Type 'yes' to confirm: ")
        except Exception:
            print("Aborted.")
            return 2

    # Copy workspace (unless --bare).
    if not args.bare:
        shutil.copytree(source_path, new_path, dirs_exist_ok=args.force)

    # Copy metadata.
    if args.force and new_settings.is_dir():
        shutil.rmtree(new_settings)
    shutil.copytree(
        source_settings, new_settings,
        ignore=shutil.ignore_patterns(".kanibako.lock"),
    )

    # Update breadcrumb.
    breadcrumb = new_settings / "project-path.txt"
    breadcrumb.write_text(str(new_path) + "\n")

    print(f"Duplicated project:")
    print(f"  from: {source_path} ({short_hash(source_hash)})")
    print(f"    to: {new_path} ({short_hash(new_hash)})")
    return 0
