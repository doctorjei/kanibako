"""kanibako config: get/set per-project configuration."""

from __future__ import annotations

import argparse
import sys
from dataclasses import fields

from kanibako.config import (
    ClodboxConfig,
    load_config,
    load_merged_config,
    write_project_config,
)
from kanibako.paths import _xdg, load_std_paths, resolve_project
from kanibako.utils import confirm_prompt


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "config",
        help="Get or set per-project configuration",
        description="Get or set per-project configuration values.",
    )
    p.add_argument("key", nargs="?", default=None, help="Configuration key to read or write")
    p.add_argument("value", nargs="?", default=None, help="New value to set (omit to read)")
    p.add_argument(
        "-s", "--show", action="store_true", help="Show all configuration values"
    )
    p.add_argument(
        "--clear", action="store_true",
        help="Clear project-level overrides (revert to global defaults)",
    )
    p.add_argument(
        "-p", "--project", default=None, help="Target a specific project directory"
    )
    p.set_defaults(func=run, _config_parser=p)


def run(args: argparse.Namespace) -> int:
    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)
    std = load_std_paths(config)
    proj = resolve_project(std, config, project_dir=args.project, initialize=False)

    project_toml = proj.settings_path / "project.toml"

    if args.show:
        return _show_config(config_file, project_toml, proj)

    if args.clear:
        return _clear_config(project_toml, proj)

    if args.key is None:
        args._config_parser.print_help()
        return 0

    # Load merged config (global + project)
    merged = load_merged_config(config_file, project_toml)

    key = args.key
    if key == "image":
        if args.value is None:
            print(merged.container_image)
        else:
            write_project_config(project_toml, args.value)
            print(f"Set image to {args.value} for project {proj.project_path}")
    else:
        print(f"Error: Unknown config key: {key}", file=sys.stderr)
        return 1

    return 0


def _show_config(config_file, project_toml, proj) -> int:
    """Print all merged configuration values."""
    merged = load_merged_config(config_file, project_toml)
    defaults = ClodboxConfig()

    # Determine which keys have project-level overrides.
    project_overrides: set[str] = set()
    if project_toml.exists():
        proj_cfg = load_config(project_toml)
        for fld in fields(proj_cfg):
            if getattr(proj_cfg, fld.name) != getattr(defaults, fld.name):
                project_overrides.add(fld.name)

    print(f"Project: {proj.project_path}")
    print()
    for fld in fields(merged):
        val = getattr(merged, fld.name)
        marker = " (project)" if fld.name in project_overrides else ""
        print(f"  {fld.name} = {val}{marker}")
    return 0


def _clear_config(project_toml, proj) -> int:
    """Remove the project-level config file."""
    if not project_toml.exists():
        print(f"No project config to clear for {proj.project_path}")
        return 0

    print(f"This will clear all project-level config overrides for {proj.project_path}")
    confirm_prompt("Type 'yes' to proceed: ")

    project_toml.unlink()
    print(f"Cleared project config for {proj.project_path}")
    return 0
