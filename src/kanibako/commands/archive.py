"""kanibako archive: archive session data + git metadata to .txz."""

from __future__ import annotations

import argparse
import os
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from kanibako.config import load_config
from kanibako.errors import ArchiveError, GitError
from kanibako.git import check_uncommitted, check_unpushed, get_metadata, is_git_repo
from kanibako.paths import _xdg, load_std_paths, resolve_any_project
from kanibako.utils import short_hash


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "archive",
        help="Archive project session data to .txz file",
        description="Archive project session data and git metadata to a .txz file.",
    )
    p.add_argument("path", nargs="?", default=None, help="Path to the project directory")
    p.add_argument("file", nargs="?", default=None, help="Output filename (default: auto-generated)")
    p.add_argument(
        "--all", action="store_true", dest="all_projects",
        help="Archive session data for every known project",
    )
    p.add_argument("--allow-uncommitted", action="store_true",
                    help="Allow archiving with uncommitted changes")
    p.add_argument("--allow-unpushed", action="store_true",
                    help="Allow archiving with unpushed commits")
    p.add_argument("--force", action="store_true", help="Skip all confirmation prompts")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)
    std = load_std_paths(config)

    if args.all_projects:
        return _archive_all(std, config, args)

    if args.path is None:
        print("Error: specify a project path, or use --all", file=sys.stderr)
        return 1

    proj = resolve_any_project(std, config, project_dir=args.path, initialize=False)
    return _archive_one(std, config, proj, output_file=args.file, args=args)


def _archive_one(std, config, proj, *, output_file, args) -> int:
    """Archive session data for a single project."""
    if not proj.settings_path.is_dir():
        print(f"Error: No session data found for project {proj.project_path}", file=sys.stderr)
        return 1

    # Generate default archive filename
    archive_file = output_file
    if not archive_file:
        basename = proj.project_path.name
        h8 = short_hash(proj.project_hash)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_file = f"kanibako-{basename}-{h8}-{timestamp}.txz"

    # Prepare metadata
    info_file = proj.settings_path / "kanibako-archive-info.txt"
    lines = [
        f"Project path: {proj.project_path}",
        f"Project hash: {proj.project_hash}",
        f"Archive date: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
    ]

    # Git checks (only if project path exists on disk)
    if proj.project_path.is_dir() and is_git_repo(proj.project_path):
        if not args.allow_uncommitted:
            try:
                check_uncommitted(proj.project_path)
            except GitError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

        if not args.allow_unpushed:
            try:
                check_unpushed(proj.project_path)
            except GitError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

        meta = get_metadata(proj.project_path)
        if meta:
            lines.append("Git repository: yes")
            lines.append(f"Branch: {meta.branch}")
            lines.append(f"Commit: {meta.commit}")
            lines.append("Remotes:")
            for name, url in meta.remotes:
                lines.append(f"  {name}: {url}")
    else:
        if proj.project_path.is_dir():
            print(
                f"Warning: No git repository detected in {proj.project_path}",
                file=sys.stderr,
            )
            print("Only kanibako session data will be archived.", file=sys.stderr)
        lines.append("")
        lines.append("Git repository: no")

    info_file.write_text("\n".join(lines) + "\n")

    # Create archive using Python tarfile
    print(f"Creating archive {archive_file}... ", end="", flush=True)
    try:
        with tarfile.open(archive_file, "w:xz") as tar:
            tar.add(
                str(proj.settings_path),
                arcname=proj.project_hash,
            )
    except Exception as e:
        info_file.unlink(missing_ok=True)
        print(f"\nError: Failed to create archive: {e}", file=sys.stderr)
        return 1
    finally:
        info_file.unlink(missing_ok=True)

    print("done.")
    print(f"Archive created: {archive_file}")
    return 0


def _archive_all(std, config, args) -> int:
    """Archive session data for all known projects."""
    from kanibako.paths import iter_projects

    projects = iter_projects(std, config)
    if not projects:
        print("No project session data found.")
        return 0

    print(f"Found {len(projects)} project(s) to archive:")
    for settings_path, project_path in projects:
        h8 = short_hash(settings_path.name)
        label = str(project_path) if project_path else f"(unknown) {h8}"
        print(f"  {label}")
    print()

    archived = 0
    failed = 0
    for settings_path, project_path in projects:
        phash = settings_path.name
        h8 = short_hash(phash)

        if project_path:
            # Build a ProjectPaths-like object via resolve_project
            try:
                proj = resolve_project(
                    std, config, project_dir=str(project_path), initialize=False
                )
            except Exception:
                # Project path no longer exists; build a minimal stand-in
                proj = _stub_project(settings_path, phash, project_path, config)
        else:
            proj = _stub_project(settings_path, phash, None, config)

        rc = _archive_one(std, config, proj, output_file=None, args=args)
        if rc == 0:
            archived += 1
        else:
            failed += 1

    print(f"\nArchived {archived} project(s).", end="")
    if failed:
        print(f" {failed} failed.", end="")
    print()
    return 1 if failed else 0


def _stub_project(settings_path, phash, project_path, config):
    """Create a minimal ProjectPaths stand-in for projects whose path is gone."""
    from kanibako.paths import ProjectPaths

    effective_path = project_path or Path(f"(unknown-{short_hash(phash)})")
    return ProjectPaths(
        project_path=effective_path,
        project_hash=phash,
        settings_path=settings_path,
        dot_path=settings_path / config.paths_dot_path,
        cfg_file=settings_path / config.paths_cfg_file,
        shell_path=settings_path.parent.parent / "shell" / phash,
        vault_ro_path=effective_path / "vault" / "share-ro",
        vault_rw_path=effective_path / "vault" / "share-rw",
        is_new=False,
    )
