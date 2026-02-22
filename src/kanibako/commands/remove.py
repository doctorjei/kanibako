"""kanibako remove: teardown environment (config; keep data)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kanibako.config import load_config
from kanibako.paths import xdg
from kanibako.utils import confirm_prompt


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "remove",
        help="Remove kanibako configuration (keeps project data)",
        description="Remove kanibako configuration. "
        "Project data is preserved. Use 'pip uninstall kanibako' to remove the package.",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    config_home = xdg("XDG_CONFIG_HOME", ".config")
    config_file = config_home / "kanibako" / "kanibako.toml"
    config_dir = config_file.parent

    # Load config to determine data path before deleting
    rel_std_path = "kanibako"
    if config_file.exists():
        try:
            config = load_config(config_file)
            rel_std_path = config.paths_relative_std_path
        except Exception:
            pass

    data_home = xdg("XDG_DATA_HOME", ".local/share")
    data_path = data_home / rel_std_path

    # Confirmation prompt before destructive action
    print("This will remove:")
    print(f"  - Configuration: {config_dir}")
    confirm_prompt("Continue? Type 'yes' to proceed: ")

    # ------------------------------------------------------------------
    # 1. Delete configuration
    # ------------------------------------------------------------------
    print("Deleting configuration file... ", end="", flush=True)
    if config_file.exists():
        config_file.unlink()
    # Also remove legacy .rc if present
    legacy = config_file.with_name("kanibako.rc")
    if legacy.exists():
        legacy.unlink()
    # Try to remove empty config dir
    try:
        config_dir.rmdir()
    except OSError:
        pass
    print("done.")

    # ------------------------------------------------------------------
    # 2. Inform user
    # ------------------------------------------------------------------
    print()
    print(f"Note: Project data remains in {data_path}")
    print(f"To delete, run:  rm -rf {data_path}")
    print()
    print("To remove the kanibako package:  pip uninstall kanibako")
    return 0
