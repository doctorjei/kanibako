"""Full argparse tree with subparsers, dispatcher, and main() entry point."""

from __future__ import annotations

import argparse
import sys

from clodbox import __version__
from clodbox.errors import ClodboxError, UserCancelled


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clodbox",
        description="Run Claude Code in rootless containers with per-project isolation.",
        epilog=(
            "common switches (for default 'start' command):\n"
            "  -p, --project DIR   use DIR as the project directory (default: cwd)\n"
            "  -i, --image IMAGE   use IMAGE as the container image for this run\n"
            "  -N, --new           start a new conversation (skip default --continue)\n"
            "  -S, --safe          run without --dangerously-skip-permissions\n"
            "  -c, --command CMD   use CMD as the container entrypoint\n"
            "\n"
            "run 'clodbox COMMAND --help' for subcommand-specific options"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"clodbox {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # Import and register all subcommand parsers.
    from clodbox.commands.start import (
        add_resume_parser,
        add_shell_parser,
        add_start_parser,
    )
    from clodbox.commands.config_cmd import add_parser as add_config_parser
    from clodbox.commands.image import add_parser as add_image_parser
    from clodbox.commands.archive import add_parser as add_archive_parser
    from clodbox.commands.clean import add_parser as add_clean_parser
    from clodbox.commands.restore import add_parser as add_restore_parser
    from clodbox.commands.install import add_parser as add_install_parser
    from clodbox.commands.remove import add_parser as add_remove_parser
    from clodbox.commands.refresh_credentials import (
        add_parser as add_refresh_creds_parser,
    )

    add_start_parser(subparsers)
    add_shell_parser(subparsers)
    add_resume_parser(subparsers)
    add_config_parser(subparsers)
    add_image_parser(subparsers)
    add_archive_parser(subparsers)
    add_clean_parser(subparsers)
    add_restore_parser(subparsers)
    add_install_parser(subparsers)
    add_remove_parser(subparsers)
    add_refresh_creds_parser(subparsers)

    return parser


_SUBCOMMANDS = {
    "start", "shell", "resume", "config", "image",
    "archive", "clean", "restore", "install", "remove",
    "refresh-credentials",
}


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    effective = list(argv if argv is not None else sys.argv[1:])

    # Let --help and --version be handled by the top-level parser.
    if effective and effective[0] in ("-h", "--help", "--version"):
        args = parser.parse_args(effective)
    else:
        # If the first arg isn't a known subcommand, default to "start".
        if not effective or effective[0] not in _SUBCOMMANDS:
            effective = ["start"] + effective
        args = parser.parse_args(effective)

    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        sys.exit(0)

    try:
        rc = func(args)
    except UserCancelled:
        print("Aborted.")
        rc = 2
    except ClodboxError as e:
        print(f"Error: {e}", file=sys.stderr)
        rc = 1
    except KeyboardInterrupt:
        print()
        rc = 130

    sys.exit(rc)
