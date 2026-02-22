"""kanibako config: get/set per-project configuration."""

from __future__ import annotations

import argparse
import sys
from dataclasses import fields

from kanibako.config import (
    KanibakoConfig,
    _DEFAULTS,
    config_keys,
    load_config,
    load_merged_config,
    load_project_overrides,
    unset_project_config_key,
    write_project_config_key,
)
from kanibako.errors import UserCancelled
from kanibako.paths import xdg, load_std_paths, resolve_project
from kanibako.utils import confirm_prompt


# Friendly aliases: short name -> flat config key.
_KEY_ALIASES = {
    "image": "container_image",
}


def _resolve_key(raw: str) -> str | None:
    """Map a user-supplied key name to the canonical flat config key.

    Accepts the full flat key (``container_image``), the alias (``image``),
    or returns None if the key is not recognized.
    """
    if raw in _KEY_ALIASES:
        return _KEY_ALIASES[raw]
    valid = {fld.name for fld in fields(KanibakoConfig)}
    if raw in valid:
        return raw
    return None


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "config",
        help="Get or set per-project configuration",
        description=(
            "Get or set per-project configuration values.\n\n"
            "With no arguments, list all current project config values.\n"
            "With KEY, show the value for that key.\n"
            "With KEY VALUE, set a project-level override.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("key", nargs="?", default=None, help="Configuration key to read or write")
    p.add_argument("value", nargs="?", default=None, help="New value to set (omit to read)")
    p.add_argument(
        "-s", "--show", action="store_true", help="Show all configuration values"
    )
    p.add_argument(
        "--unset", metavar="KEY", default=None,
        help="Remove a project-level override for KEY",
    )
    p.add_argument(
        "--clear", action="store_true",
        help="Clear all project-level overrides (revert to global defaults)",
    )
    p.add_argument(
        "-p", "--project", default=None, help="Target a specific project directory"
    )
    p.set_defaults(func=run, _config_parser=p)


def run(args: argparse.Namespace) -> int:
    config_file = xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)
    std = load_std_paths(config)
    proj = resolve_project(std, config, project_dir=args.project, initialize=False)

    project_toml = proj.metadata_path / "project.toml"

    if args.show:
        return _show_config(config_file, project_toml, proj)

    if args.clear:
        return _clear_config(project_toml, proj)

    if args.unset is not None:
        return _unset_key(project_toml, proj, args.unset)

    # No key given: list all values (same as --show).
    if args.key is None:
        return _show_config(config_file, project_toml, proj)

    # Resolve the key (accept aliases like "image" -> "container_image").
    flat_key = _resolve_key(args.key)
    if flat_key is None:
        valid = config_keys()
        aliases = ", ".join(f"{a} ({v})" for a, v in _KEY_ALIASES.items())
        print(f"Error: Unknown config key: {args.key}", file=sys.stderr)
        print(f"Valid keys: {', '.join(valid)}", file=sys.stderr)
        print(f"Aliases: {aliases}", file=sys.stderr)
        return 1

    # Load merged config (global + project)
    merged = load_merged_config(config_file, project_toml)

    if args.value is None:
        # GET
        print(getattr(merged, flat_key))
    else:
        # SET
        write_project_config_key(project_toml, flat_key, args.value)
        print(f"Set {flat_key} = {args.value} for project {proj.project_path}")

    return 0


def _show_config(config_file, project_toml, proj) -> int:
    """Print all merged configuration values."""
    merged = load_merged_config(config_file, project_toml)
    overrides = load_project_overrides(project_toml)

    print(f"Project: {proj.project_path}")
    print()
    for fld in fields(merged):
        val = getattr(merged, fld.name)
        marker = " (project)" if fld.name in overrides else ""
        print(f"  {fld.name} = {val}{marker}")
    return 0


def _unset_key(project_toml, proj, raw_key: str) -> int:
    """Remove a single project-level override."""
    flat_key = _resolve_key(raw_key)
    if flat_key is None:
        print(f"Error: Unknown config key: {raw_key}", file=sys.stderr)
        return 1

    removed = unset_project_config_key(project_toml, flat_key)
    if removed:
        default_val = _DEFAULTS.get(flat_key, "(unknown)")
        print(f"Unset {flat_key} for project {proj.project_path} (reverts to default: {default_val})")
    else:
        print(f"No project-level override for {flat_key} in {proj.project_path}")
    return 0


def _clear_config(project_toml, proj) -> int:
    """Remove user-configured overrides from the project-level config file."""
    overrides = load_project_overrides(project_toml)
    if not overrides:
        print(f"No project config to clear for {proj.project_path}")
        return 0

    print(f"This will clear all project-level config overrides for {proj.project_path}")
    try:
        confirm_prompt("Type 'yes' to proceed: ")
    except UserCancelled:
        print("Aborted.", file=sys.stderr)
        return 0

    for key in overrides:
        unset_project_config_key(project_toml, key)
    print(f"Cleared project config for {proj.project_path}")
    return 0
