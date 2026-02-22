"""kanibako reauth: manually verify or re-establish agent authentication."""

from __future__ import annotations

import argparse
import sys

from kanibako.config import load_config
from kanibako.paths import xdg
from kanibako.targets import resolve_target


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "reauth",
        help="Check authentication and login if needed",
        description="Verify agent authentication status and run interactive "
        "login if credentials are expired or missing.",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    config_file = xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)

    try:
        target = resolve_target(config.target_name or None)
    except KeyError:
        print("Error: No agent target found.", file=sys.stderr)
        return 1

    if target.check_auth():
        print(f"{target.display_name}: authenticated.", file=sys.stderr)
        return 0
    else:
        print(f"{target.display_name}: authentication failed.", file=sys.stderr)
        return 1
