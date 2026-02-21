"""kanibako box: project lifecycle management (list, migrate, duplicate, archive, purge, restore)."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from kanibako.config import load_config
from kanibako.errors import ProjectError
from kanibako.paths import (
    ProjectMode,
    _xdg,
    detect_project_mode,
    iter_projects,
    load_std_paths,
    resolve_any_project,
    resolve_decentralized_project,
    resolve_project,
)
from kanibako.utils import confirm_prompt, project_hash, short_hash

_MODE_CHOICES = ["account-centric", "decentralized", "workset"]


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
        help="Remap project data from old path to new path, or convert between modes",
        description=(
            "Move project session data from one path hash to another.\n"
            "Use this after moving or renaming a project directory.\n"
            "With --to, convert a project between modes (e.g. account-centric to decentralized)."
        ),
    )
    migrate_p.add_argument(
        "old_path", nargs="?", default=None,
        help="Original project directory path (for path remap), or project path (for --to)",
    )
    migrate_p.add_argument(
        "new_path", nargs="?", default=None,
        help="New project directory path (default: current working directory)",
    )
    migrate_p.add_argument(
        "--to", dest="to_mode", choices=_MODE_CHOICES, default=None,
        help="Convert project to a different mode",
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
            "The metadata is re-keyed under the new path's hash.\n"
            "With --to, duplicate into a different mode layout."
        ),
    )
    duplicate_p.add_argument("source_path", help="Existing project directory to duplicate")
    duplicate_p.add_argument("new_path", help="Destination path for the duplicate")
    duplicate_p.add_argument(
        "--bare", action="store_true",
        help="Copy only kanibako metadata, don't touch the workspace directory",
    )
    duplicate_p.add_argument(
        "--to", dest="to_mode", choices=_MODE_CHOICES, default=None,
        help="Duplicate into a different mode layout",
    )
    duplicate_p.add_argument(
        "--force", action="store_true",
        help="Skip confirmation, overwrite existing data/metadata at destination",
    )
    duplicate_p.set_defaults(func=run_duplicate)

    # kanibako box info
    info_p = box_sub.add_parser(
        "info",
        help="Show project details",
        description="Show project mode, paths, and status for a kanibako project.",
    )
    info_p.add_argument("path", nargs="?", default=None, help="Project directory (default: cwd)")
    info_p.set_defaults(func=run_info)

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

    # Cross-mode conversion.
    if getattr(args, "to_mode", None) is not None:
        return _run_convert(args, std, config)

    # Same-mode path remap: old_path is required.
    if args.old_path is None:
        print("Error: old_path is required for path remap (use --to for mode conversion).", file=sys.stderr)
        return 1

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

    # Rename settings.
    old_settings.rename(new_settings)

    # Also rename shell directory.
    shell_base = std.data_path / "shell"
    old_shell = shell_base / old_hash
    new_shell = shell_base / new_hash
    if old_shell.is_dir():
        old_shell.rename(new_shell)

    # Update the breadcrumb.
    breadcrumb = new_settings / "project-path.txt"
    breadcrumb.write_text(str(new_path) + "\n")

    print(f"Migrated project data:")
    print(f"  from: {old_path} ({short_hash(old_hash)})")
    print(f"    to: {new_path} ({short_hash(new_hash)})")
    return 0


# -- Cross-mode conversion helpers --

def _run_convert(args: argparse.Namespace, std, config) -> int:
    """Dispatch cross-mode conversion based on --to flag."""
    import os

    to_mode_str = args.to_mode

    # Workset not yet supported.
    if to_mode_str == "workset":
        print("Error: conversion to workset mode is not yet implemented.", file=sys.stderr)
        return 1

    # Resolve project path (positional arg or cwd).
    raw_path = args.old_path or os.getcwd()
    project_path = Path(raw_path).resolve()

    if not project_path.is_dir():
        print(f"Error: project path does not exist: {project_path}", file=sys.stderr)
        return 1

    # Detect current mode.
    current_mode = detect_project_mode(project_path, std, config)

    if current_mode == ProjectMode.workset:
        print("Error: conversion from workset mode is not yet implemented.", file=sys.stderr)
        return 1

    # Parse target mode.
    target_mode = ProjectMode.decentralized if to_mode_str == "decentralized" else ProjectMode.account_centric

    if current_mode == target_mode:
        print(f"Error: project is already in {current_mode.value} mode.", file=sys.stderr)
        return 1

    # Resolve current project paths.
    if current_mode == ProjectMode.account_centric:
        proj = resolve_project(std, config, project_dir=str(project_path), initialize=False)
    else:
        proj = resolve_decentralized_project(std, config, project_dir=str(project_path), initialize=False)

    # Check that project data exists.
    if not proj.settings_path.is_dir():
        print(f"Error: no project data found for {project_path}", file=sys.stderr)
        return 1

    # Lock file warning.
    lock_file = proj.settings_path / ".kanibako.lock"
    if lock_file.exists():
        print(
            "Warning: lock file found — a container may be running for this project.",
            file=sys.stderr,
        )
        if not args.force:
            print("Aborted.")
            return 2

    # Confirm with user.
    if not args.force:
        print(f"Convert project to {target_mode.value} mode:")
        print(f"  project: {project_path}")
        print(f"  from:    {current_mode.value}")
        print(f"    to:    {target_mode.value}")
        print()
        try:
            confirm_prompt("Type 'yes' to confirm: ")
        except Exception:
            print("Aborted.")
            return 2

    # Dispatch.
    if target_mode == ProjectMode.decentralized:
        _convert_ac_to_decentral(project_path, std, config, proj)
    else:
        _convert_decentral_to_ac(project_path, std, config, proj)

    print(f"Converted project to {target_mode.value} mode:")
    print(f"  project: {project_path}")
    return 0


def _convert_ac_to_decentral(project_path, std, config, proj):
    """Convert an account-centric project to decentralized layout."""
    from kanibako.commands.init import _write_project_gitignore

    dst_settings = project_path / ".kanibako"
    dst_shell = project_path / ".shell"

    # Copy settings (excluding lock file).
    shutil.copytree(
        proj.settings_path, dst_settings,
        ignore=shutil.ignore_patterns(".kanibako.lock"),
    )

    # Remove breadcrumb (decentralized doesn't use it).
    breadcrumb = dst_settings / "project-path.txt"
    if breadcrumb.exists():
        breadcrumb.unlink()

    # Copy shell.
    if proj.shell_path.is_dir():
        shutil.copytree(proj.shell_path, dst_shell)

    # Write .gitignore entries for .kanibako/ and .shell/.
    _write_project_gitignore(project_path)

    # Write vault .gitignore if vault exists but gitignore doesn't.
    vault_dir = project_path / "vault"
    if vault_dir.is_dir():
        vault_gitignore = vault_dir / ".gitignore"
        if not vault_gitignore.exists():
            vault_gitignore.write_text("share-rw/\n")

    # Clean up old AC data.
    shutil.rmtree(proj.settings_path)
    if proj.shell_path.is_dir():
        shutil.rmtree(proj.shell_path)


def _convert_decentral_to_ac(project_path, std, config, proj):
    """Convert a decentralized project to account-centric layout."""
    phash = project_hash(str(project_path))
    projects_base = std.data_path / config.paths_projects_path
    dst_settings = projects_base / phash
    shell_base = std.data_path / "shell"
    dst_shell = shell_base / phash

    # Copy settings (excluding lock file).
    shutil.copytree(
        proj.settings_path, dst_settings,
        ignore=shutil.ignore_patterns(".kanibako.lock"),
    )

    # Write breadcrumb.
    (dst_settings / "project-path.txt").write_text(str(project_path) + "\n")

    # Copy shell.
    if proj.shell_path.is_dir():
        shell_base.mkdir(parents=True, exist_ok=True)
        shutil.copytree(proj.shell_path, dst_shell)

    # Clean up old decentralized data.
    shutil.rmtree(proj.settings_path)
    if proj.shell_path.is_dir():
        shutil.rmtree(proj.shell_path)


# -- Cross-mode duplicate helpers --

def _run_duplicate_cross_mode(args: argparse.Namespace, std, config) -> int:
    """Duplicate a project into a different mode layout."""
    import os

    to_mode_str = args.to_mode

    # Workset not yet supported.
    if to_mode_str == "workset":
        print("Error: duplication to workset mode is not yet implemented.", file=sys.stderr)
        return 1

    source_path = Path(args.source_path).resolve()
    new_path = Path(args.new_path).resolve()

    if source_path == new_path:
        print("Error: source and destination paths are the same.", file=sys.stderr)
        return 1

    if not source_path.is_dir():
        print(f"Error: source path does not exist as a directory: {source_path}", file=sys.stderr)
        return 1

    # Detect source mode and resolve.
    source_mode = detect_project_mode(source_path, std, config)

    if source_mode == ProjectMode.workset:
        print("Error: duplication from workset mode is not yet implemented.", file=sys.stderr)
        return 1

    if source_mode == ProjectMode.account_centric:
        src_proj = resolve_project(std, config, project_dir=str(source_path), initialize=False)
    else:
        src_proj = resolve_decentralized_project(std, config, project_dir=str(source_path), initialize=False)

    if not src_proj.settings_path.is_dir():
        print(f"Error: no project data found for source path: {source_path}", file=sys.stderr)
        return 1

    # Lock file warning.
    lock_file = src_proj.settings_path / ".kanibako.lock"
    if lock_file.exists():
        print(
            "Warning: lock file found — a container may be running for this project.",
            file=sys.stderr,
        )
        if not args.force:
            print("Aborted.")
            return 2

    # Confirm with user.
    target_mode = ProjectMode.decentralized if to_mode_str == "decentralized" else ProjectMode.account_centric
    if not args.force:
        mode = "metadata only (bare)" if args.bare else "workspace + metadata"
        print(f"Duplicate project ({mode}) to {target_mode.value} mode:")
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

    # Copy metadata into target mode layout.
    if target_mode == ProjectMode.decentralized:
        _duplicate_to_decentral(src_proj, new_path, args.force)
    else:
        _duplicate_to_ac(src_proj, new_path, std, config, args.force)

    print(f"Duplicated project to {target_mode.value} mode:")
    print(f"  from: {source_path}")
    print(f"    to: {new_path}")
    return 0


def _duplicate_to_decentral(src_proj, new_path, force):
    """Copy metadata into decentralized layout at new_path."""
    from kanibako.commands.init import _write_project_gitignore

    dst_settings = new_path / ".kanibako"
    dst_shell = new_path / ".shell"

    # Ensure new_path exists for bare duplicates.
    new_path.mkdir(parents=True, exist_ok=True)

    if force and dst_settings.is_dir():
        shutil.rmtree(dst_settings)
    shutil.copytree(
        src_proj.settings_path, dst_settings,
        ignore=shutil.ignore_patterns(".kanibako.lock"),
    )

    # Remove breadcrumb if present (decentralized doesn't use it).
    breadcrumb = dst_settings / "project-path.txt"
    if breadcrumb.exists():
        breadcrumb.unlink()

    if src_proj.shell_path.is_dir():
        if force and dst_shell.is_dir():
            shutil.rmtree(dst_shell)
        shutil.copytree(src_proj.shell_path, dst_shell)

    _write_project_gitignore(new_path)

    # Write vault .gitignore if vault exists.
    vault_dir = new_path / "vault"
    if vault_dir.is_dir():
        vault_gitignore = vault_dir / ".gitignore"
        if not vault_gitignore.exists():
            vault_gitignore.write_text("share-rw/\n")


def _duplicate_to_ac(src_proj, new_path, std, config, force):
    """Copy metadata into account-centric layout for new_path."""
    phash = project_hash(str(new_path))
    projects_base = std.data_path / config.paths_projects_path
    dst_settings = projects_base / phash
    shell_base = std.data_path / "shell"
    dst_shell = shell_base / phash

    if force and dst_settings.is_dir():
        shutil.rmtree(dst_settings)
    shutil.copytree(
        src_proj.settings_path, dst_settings,
        ignore=shutil.ignore_patterns(".kanibako.lock"),
    )

    # Write breadcrumb.
    (dst_settings / "project-path.txt").write_text(str(new_path) + "\n")

    if src_proj.shell_path.is_dir():
        shell_base.mkdir(parents=True, exist_ok=True)
        if force and dst_shell.is_dir():
            shutil.rmtree(dst_shell)
        shutil.copytree(src_proj.shell_path, dst_shell)


def run_duplicate(args: argparse.Namespace) -> int:
    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)
    std = load_std_paths(config)

    # Cross-mode duplication.
    if getattr(args, "to_mode", None) is not None:
        return _run_duplicate_cross_mode(args, std, config)

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


def run_info(args: argparse.Namespace) -> int:
    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)
    std = load_std_paths(config)

    try:
        proj = resolve_any_project(std, config, project_dir=args.path, initialize=False)
    except ProjectError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not proj.settings_path.is_dir():
        print(f"Error: No project data found for {proj.project_path}", file=sys.stderr)
        return 1

    print(f"Mode:      {proj.mode.value}")
    print(f"Project:   {proj.project_path}")
    print(f"Hash:      {short_hash(proj.project_hash)}")
    print(f"Settings:  {proj.settings_path}")
    print(f"Shell:     {proj.shell_path}")
    print(f"Vault RO:  {proj.vault_ro_path}")
    print(f"Vault RW:  {proj.vault_rw_path}")

    lock_file = proj.settings_path / ".kanibako.lock"
    if lock_file.exists():
        print(f"Lock:      ACTIVE ({lock_file})")
    else:
        print(f"Lock:      none")

    return 0
