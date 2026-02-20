"""migrate-from-clodbox: migrate settings and project data from clodbox to kanibako."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from kanibako.config import KanibakoConfig, load_config, write_global_config
from kanibako.paths import _bootstrap_shell, _xdg


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "migrate-from-clodbox",
        help="Migrate settings and project data from clodbox",
        description="Detect an existing clodbox installation and migrate to kanibako.",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    config_home = _xdg("XDG_CONFIG_HOME", ".config")
    data_home = _xdg("XDG_DATA_HOME", ".local/share")

    old_config_dir = config_home / "clodbox"
    old_config_file = old_config_dir / "clodbox.toml"

    new_config_dir = config_home / "kanibako"
    new_config_file = new_config_dir / "kanibako.toml"

    old_data_dir = data_home / "clodbox"
    new_data_dir = data_home / "kanibako"

    # ---------------------------------------------------------------
    # Detect old installation
    # ---------------------------------------------------------------
    if not old_config_file.exists():
        # Also check for legacy .rc
        old_rc = old_config_dir / "clodbox.rc"
        if not old_rc.exists():
            print("No clodbox installation found.", file=sys.stderr)
            return 1

    if new_config_file.exists():
        print(
            f"kanibako is already configured ({new_config_file}).\n"
            "If you want to re-migrate, remove it first.",
            file=sys.stderr,
        )
        return 1

    # ---------------------------------------------------------------
    # Read old config
    # ---------------------------------------------------------------
    if old_config_file.exists():
        old_cfg = load_config(old_config_file)
    else:
        old_cfg = KanibakoConfig()

    # Write new config with updated defaults
    new_cfg = KanibakoConfig()
    # Preserve non-default image if the user customized it
    old_default_image = "ghcr.io/doctorjei/clodbox-base:latest"
    if old_cfg.container_image != old_default_image:
        new_cfg.container_image = old_cfg.container_image

    new_config_dir.mkdir(parents=True, exist_ok=True)
    write_global_config(new_config_file, new_cfg)
    print(f"Created {new_config_file}", file=sys.stderr)

    # ---------------------------------------------------------------
    # Migrate data directories
    # ---------------------------------------------------------------
    new_data_dir.mkdir(parents=True, exist_ok=True)

    old_projects_dir = old_data_dir / old_cfg.paths_projects_path
    new_settings_dir = new_data_dir / "settings"

    if old_projects_dir.is_dir():
        new_settings_dir.mkdir(parents=True, exist_ok=True)
        for entry in old_projects_dir.iterdir():
            if not entry.is_dir():
                continue
            dest = new_settings_dir / entry.name
            if dest.exists():
                print(f"  Skipping {entry.name} (already exists)", file=sys.stderr)
                continue
            shutil.copytree(str(entry), str(dest), symlinks=True)

            # Rename dotclod → dotclaude, dotclod.json → claude.json within
            old_dot = dest / old_cfg.paths_dot_path
            new_dot = dest / "dotclaude"
            if old_dot.is_dir() and old_dot != new_dot:
                old_dot.rename(new_dot)

            old_cfg_f = dest / old_cfg.paths_cfg_file
            new_cfg_f = dest / "claude.json"
            if old_cfg_f.is_file() and old_cfg_f != new_cfg_f:
                old_cfg_f.rename(new_cfg_f)

            # Create shell directory with skeleton
            shell_dir = new_data_dir / "shell" / entry.name
            if not shell_dir.is_dir():
                shell_dir.mkdir(parents=True, exist_ok=True)
                _bootstrap_shell(shell_dir)

            print(f"  Migrated project {entry.name}", file=sys.stderr)

    # Migrate credentials
    old_creds = old_data_dir / old_cfg.paths_init_credentials_path
    new_creds = new_data_dir / "credentials"
    if old_creds.is_dir() and not new_creds.exists():
        shutil.copytree(str(old_creds), str(new_creds), symlinks=True)
        print(f"  Migrated credentials", file=sys.stderr)

    # ---------------------------------------------------------------
    # Update cron job (if any)
    # ---------------------------------------------------------------
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        )
        if result.returncode == 0 and "clodbox" in result.stdout:
            new_cron = result.stdout.replace("clodbox", "kanibako")
            subprocess.run(
                ["crontab", "-"], input=new_cron, capture_output=True, text=True
            )
            print("  Updated crontab entries", file=sys.stderr)
    except FileNotFoundError:
        pass  # crontab not available

    # ---------------------------------------------------------------
    # Rename old dirs to indicate migration
    # ---------------------------------------------------------------
    migrated_marker = old_config_dir.with_name("clodbox.migrated-to-kanibako")
    if old_config_dir.is_dir() and not migrated_marker.exists():
        old_config_dir.rename(migrated_marker)
        print(f"  Renamed {old_config_dir} → {migrated_marker.name}", file=sys.stderr)

    if old_data_dir.is_dir():
        data_marker = old_data_dir.with_name("clodbox.migrated-to-kanibako")
        if not data_marker.exists():
            old_data_dir.rename(data_marker)
            print(f"  Renamed {old_data_dir} → {data_marker.name}", file=sys.stderr)

    print("\nMigration complete! You can now use 'kanibako' instead of 'clodbox'.", file=sys.stderr)
    return 0
