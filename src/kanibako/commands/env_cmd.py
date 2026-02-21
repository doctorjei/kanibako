"""kanibako env: manage per-project and global environment variables."""

from __future__ import annotations

import argparse
import sys

from kanibako.config import load_config
from kanibako.paths import _xdg, load_std_paths, resolve_any_project
from kanibako.shellenv import merge_env, read_env_file, set_env_var, unset_env_var


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "env",
        help="Manage environment variables (list, set, get, unset)",
        description="Manage per-project and global environment variables.",
    )
    vs = p.add_subparsers(dest="env_command", metavar="COMMAND")

    # kanibako env list (default)
    list_p = vs.add_parser(
        "list",
        help="Show merged env vars (default)",
        description="Show merged environment variables (global + project).",
    )
    list_p.add_argument(
        "-p", "--project", default=None,
        help="Project directory (default: cwd)",
    )
    list_p.set_defaults(func=run_list)

    # kanibako env set KEY VALUE [--global]
    set_p = vs.add_parser(
        "set",
        help="Set an environment variable",
        description="Set a project-level (or global) environment variable.",
    )
    set_p.add_argument("key", help="Environment variable name")
    set_p.add_argument("value", help="Environment variable value")
    set_p.add_argument(
        "--global", dest="is_global", action="store_true",
        help="Set in global env file instead of project",
    )
    set_p.add_argument(
        "-p", "--project", default=None,
        help="Project directory (default: cwd)",
    )
    set_p.set_defaults(func=run_set)

    # kanibako env get KEY
    get_p = vs.add_parser(
        "get",
        help="Show one env var's value",
        description="Show the value of a single environment variable.",
    )
    get_p.add_argument("key", help="Environment variable name")
    get_p.add_argument(
        "-p", "--project", default=None,
        help="Project directory (default: cwd)",
    )
    get_p.set_defaults(func=run_get)

    # kanibako env unset KEY [--global]
    unset_p = vs.add_parser(
        "unset",
        help="Remove an environment variable",
        description="Remove a project-level (or global) environment variable.",
    )
    unset_p.add_argument("key", help="Environment variable name")
    unset_p.add_argument(
        "--global", dest="is_global", action="store_true",
        help="Remove from global env file instead of project",
    )
    unset_p.add_argument(
        "-p", "--project", default=None,
        help="Project directory (default: cwd)",
    )
    unset_p.set_defaults(func=run_unset)

    p.set_defaults(func=run_list)


def _resolve_env_paths(project_dir: str | None):
    """Return (global_env_path, project_env_path)."""
    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)
    std = load_std_paths(config)
    proj = resolve_any_project(std, config, project_dir, initialize=False)
    global_env = _xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "env"
    project_env = proj.metadata_path / "env"
    return global_env, project_env


def run_list(args: argparse.Namespace) -> int:
    project_dir = getattr(args, "project", None)
    global_env, project_env = _resolve_env_paths(project_dir)
    merged = merge_env(global_env, project_env)

    if not merged:
        print("No environment variables set.")
        return 0

    for key in sorted(merged):
        print(f"{key}={merged[key]}")
    return 0


def run_set(args: argparse.Namespace) -> int:
    project_dir = getattr(args, "project", None)
    global_env, project_env = _resolve_env_paths(project_dir)
    target = global_env if args.is_global else project_env

    try:
        set_env_var(target, args.key, args.value)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    scope = "global" if args.is_global else "project"
    print(f"Set {args.key} ({scope})")
    return 0


def run_get(args: argparse.Namespace) -> int:
    project_dir = getattr(args, "project", None)
    global_env, project_env = _resolve_env_paths(project_dir)
    merged = merge_env(global_env, project_env)

    if args.key not in merged:
        print(f"{args.key} is not set.", file=sys.stderr)
        return 1

    print(merged[args.key])
    return 0


def run_unset(args: argparse.Namespace) -> int:
    project_dir = getattr(args, "project", None)
    global_env, project_env = _resolve_env_paths(project_dir)
    target = global_env if args.is_global else project_env

    if not unset_env_var(target, args.key):
        scope = "global" if args.is_global else "project"
        print(f"{args.key} is not set in {scope} env.", file=sys.stderr)
        return 1

    scope = "global" if args.is_global else "project"
    print(f"Unset {args.key} ({scope})")
    return 0
