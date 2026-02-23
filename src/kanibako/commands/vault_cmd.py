"""kanibako vault: manage vault snapshots."""

from __future__ import annotations

import argparse
import sys

from kanibako.config import config_file_path, load_config
from kanibako.paths import xdg, load_std_paths, resolve_any_project
from kanibako.snapshots import (
    _DEFAULT_MAX_SNAPSHOTS,
    create_snapshot,
    list_snapshots,
    prune_snapshots,
    restore_snapshot,
)


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "vault",
        help="Vault snapshot commands (snapshot, list, restore, prune)",
        description="Manage vault share-rw snapshots.",
    )
    vs = p.add_subparsers(dest="vault_command", metavar="COMMAND")

    # kanibako vault snapshot
    snap_p = vs.add_parser(
        "snapshot",
        help="Create a snapshot of vault share-rw",
        description="Create a point-in-time snapshot of the vault share-rw directory.",
    )
    snap_p.add_argument(
        "-p", "--project", default=None,
        help="Project directory (default: cwd)",
    )
    snap_p.set_defaults(func=run_snapshot)

    # kanibako vault list (default)
    list_p = vs.add_parser(
        "list",
        help="List vault snapshots (default)",
        description="Show all snapshots for the current project's vault.",
    )
    list_p.add_argument(
        "-p", "--project", default=None,
        help="Project directory (default: cwd)",
    )
    list_p.set_defaults(func=run_list)

    # kanibako vault restore <name>
    restore_p = vs.add_parser(
        "restore",
        help="Restore vault share-rw from a snapshot",
        description="Replace the current share-rw contents with a snapshot.",
    )
    restore_p.add_argument("name", help="Snapshot name (e.g. 20260221T103000Z.tar.xz)")
    restore_p.add_argument(
        "-p", "--project", default=None,
        help="Project directory (default: cwd)",
    )
    restore_p.set_defaults(func=run_restore)

    # kanibako vault prune [--keep N]
    prune_p = vs.add_parser(
        "prune",
        help="Remove old snapshots",
        description="Prune old vault snapshots, keeping the most recent ones.",
    )
    prune_p.add_argument(
        "--keep", type=int, default=_DEFAULT_MAX_SNAPSHOTS,
        help=f"Number of snapshots to keep (default: {_DEFAULT_MAX_SNAPSHOTS})",
    )
    prune_p.add_argument(
        "-p", "--project", default=None,
        help="Project directory (default: cwd)",
    )
    prune_p.set_defaults(func=run_prune)

    p.set_defaults(func=run_list)


def _resolve_vault_rw(project_dir: str | None):
    """Resolve the vault share-rw path for the current project."""
    config_file = config_file_path(xdg("XDG_CONFIG_HOME", ".config"))
    config = load_config(config_file)
    std = load_std_paths(config)
    proj = resolve_any_project(std, config, project_dir, initialize=False)

    if not proj.vault_enabled:
        print("Vault is disabled for this project.", file=sys.stderr)
        return None
    return proj.vault_rw_path


def run_snapshot(args: argparse.Namespace) -> int:
    project_dir = getattr(args, "project", None)
    vault_rw = _resolve_vault_rw(project_dir)
    if vault_rw is None:
        return 1

    snap = create_snapshot(vault_rw)
    if snap is None:
        print("Nothing to snapshot (share-rw is empty or missing).", file=sys.stderr)
        return 0

    print(f"Snapshot created: {snap.name}")
    return 0


def run_list(args: argparse.Namespace) -> int:
    project_dir = getattr(args, "project", None)
    vault_rw = _resolve_vault_rw(project_dir)
    if vault_rw is None:
        return 1

    snaps = list_snapshots(vault_rw)
    if not snaps:
        print("No snapshots found.")
        return 0

    for name, ts, size in snaps:
        size_str = _human_size(size)
        print(f"  {name}  {ts}  {size_str}")

    return 0


def run_restore(args: argparse.Namespace) -> int:
    project_dir = getattr(args, "project", None)
    vault_rw = _resolve_vault_rw(project_dir)
    if vault_rw is None:
        return 1

    try:
        restore_snapshot(vault_rw, args.name)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"Restored vault share-rw from {args.name}")
    return 0


def run_prune(args: argparse.Namespace) -> int:
    project_dir = getattr(args, "project", None)
    vault_rw = _resolve_vault_rw(project_dir)
    if vault_rw is None:
        return 1

    removed = prune_snapshots(vault_rw, max_keep=args.keep)
    if removed:
        print(f"Pruned {removed} snapshot(s), keeping {args.keep}.")
    else:
        print("Nothing to prune.")
    return 0


def _human_size(nbytes: int) -> str:
    """Format byte count as human-readable string."""
    size = float(nbytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
