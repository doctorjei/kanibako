"""kanibako start / shell / resume: container launch with credential flow."""

from __future__ import annotations

import argparse
import fcntl
import sys
from pathlib import Path

from kanibako.config import load_config, load_merged_config
from kanibako.container import ContainerRuntime, detect_claude_install
from kanibako.credentials import (
    refresh_central_to_project,
    refresh_host_to_central,
    writeback_project_to_central_and_host,
)
from kanibako.errors import ConfigError, ContainerError
from kanibako.paths import (
    ProjectMode,
    _xdg,
    load_std_paths,
    resolve_any_project,
)
from kanibako.utils import short_hash


def add_start_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "start",
        help="Start or continue a Claude session (default)",
        description="Start or continue a Claude session in a container.",
    )
    _add_common_args(p)
    p.add_argument(
        "-i", "--image", default=None,
        help="Use IMAGE as the container image for this run",
    )
    p.add_argument(
        "-N", "--new", action="store_true",
        help="Start a new conversation (skip default --continue)",
    )
    p.add_argument(
        "-S", "--safe", action="store_true",
        help="Run without --dangerously-skip-permissions",
    )
    p.add_argument(
        "agent_args", nargs=argparse.REMAINDER,
        help="Arguments passed directly to the agent",
    )
    p.set_defaults(func=run_start)


def add_shell_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "shell",
        help="Open a bash shell in the container",
        description="Open a bash shell in the container (no Claude agent).",
    )
    _add_common_args(p)
    p.set_defaults(func=run_shell)


def add_resume_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "resume",
        help="Resume with conversation picker",
        description="Resume a previous conversation using Claude's conversation picker.",
    )
    p.add_argument(
        "-p", "--project", default=None,
        help="Use DIR as the project directory (default: cwd)",
    )
    p.add_argument(
        "-S", "--safe", action="store_true",
        help="Run without --dangerously-skip-permissions",
    )
    p.set_defaults(func=run_resume)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-c", "--command", "-E", "--entrypoint", dest="entrypoint", default=None,
        help="Use CMD as the container entrypoint",
    )
    parser.add_argument(
        "-p", "--project", default=None,
        help="Use DIR as the project directory (default: cwd)",
    )


def run_start(args: argparse.Namespace) -> int:
    entrypoint = getattr(args, "entrypoint", None)
    image_override = getattr(args, "image", None)
    new_session = getattr(args, "new", False)
    safe_mode = getattr(args, "safe", False)
    agent_args = getattr(args, "agent_args", [])
    # Strip leading '--' from REMAINDER
    if agent_args and agent_args[0] == "--":
        agent_args = agent_args[1:]

    return _run_container(
        project_dir=args.project,
        entrypoint=entrypoint,
        image_override=image_override,
        new_session=new_session,
        safe_mode=safe_mode,
        resume_mode=False,
        extra_args=agent_args,
    )


def run_shell(args: argparse.Namespace) -> int:
    entrypoint = getattr(args, "entrypoint", None) or "/bin/bash"
    return _run_container(
        project_dir=args.project,
        entrypoint=entrypoint,
        image_override=None,
        new_session=False,
        safe_mode=False,
        resume_mode=False,
        extra_args=[],
    )


def run_resume(args: argparse.Namespace) -> int:
    safe_mode = getattr(args, "safe", False)
    return _run_container(
        project_dir=args.project,
        entrypoint=None,
        image_override=None,
        new_session=False,
        safe_mode=safe_mode,
        resume_mode=True,
        extra_args=[],
    )


def _run_container(
    *,
    project_dir: str | None,
    entrypoint: str | None,
    image_override: str | None,
    new_session: bool,
    safe_mode: bool,
    resume_mode: bool,
    extra_args: list[str],
) -> int:
    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "kanibako" / "kanibako.toml"
    config = load_config(config_file)

    try:
        std = load_std_paths(config)
    except ConfigError:
        print("kanibako hasn't been set up yet. Run setup now? [y/N] ", end="", flush=True)
        try:
            answer = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer in ("y", "yes"):
            import argparse as _argparse
            from kanibako.commands.install import run as setup_run
            setup_run(_argparse.Namespace())
            # Retry after setup
            std = load_std_paths(config)
        else:
            print("Run 'kanibako setup' when you're ready.")
            return 1

    proj = resolve_any_project(std, config, project_dir, initialize=True)

    # Hint about orphaned project data when initializing a new project
    if proj.is_new and proj.mode == ProjectMode.account_centric:
        from kanibako.paths import iter_projects
        for _settings, _ppath in iter_projects(std, config):
            if _ppath is not None and not _ppath.is_dir():
                print(
                    "hint: orphaned project data detected — "
                    "run 'kanibako box list' or use 'kanibako box migrate' "
                    "if you moved a project.",
                    file=sys.stderr,
                )
                break

    # Load merged config (global + project)
    project_toml = proj.settings_path / "project.toml"
    merged = load_merged_config(
        config_file,
        project_toml,
        cli_overrides={"container_image": image_override} if image_override else None,
    )

    image = merged.container_image

    # Persist image override for new projects so it becomes the default
    if proj.is_new and image_override:
        from kanibako.config import write_project_config
        write_project_config(project_toml, image_override)

    # Detect container runtime and ensure image is available
    try:
        runtime = ContainerRuntime()
    except ContainerError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    containers_dir = std.data_path / "containers"
    try:
        runtime.ensure_image(image, containers_dir)
    except ContainerError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    from kanibako.freshness import check_image_freshness
    check_image_freshness(runtime, image, std.cache_path)

    # Detect host Claude installation for bind-mounting
    claude_install = detect_claude_install()
    if claude_install:
        print(
            f"Using host Claude: {claude_install.binary}",
            file=sys.stderr,
        )

    # Deterministic container name for stop/cleanup
    container_name = f"kanibako-{short_hash(proj.project_hash)}"

    # Concurrency lock (known issue #3)
    lock_file = proj.settings_path / ".kanibako.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(
            "Error: Another kanibako instance is running for this project.",
            file=sys.stderr,
        )
        lock_fd.close()
        return 1

    # Record container name so `kanibako stop` can find it
    lock_fd.write(container_name + "\n")
    lock_fd.flush()

    try:
        # Credential refresh: host → central → project
        central_creds = std.credentials_path / config.paths_dot_path / ".credentials.json"
        project_creds = proj.dot_path / ".credentials.json"

        refresh_host_to_central(central_creds)
        refresh_central_to_project(central_creds, project_creds)

        # Build CLI args for the container entrypoint
        cli_args: list[str] = []
        is_claude_mode = entrypoint is None

        if is_claude_mode:
            if not safe_mode:
                cli_args.append("--dangerously-skip-permissions")

            if resume_mode:
                cli_args.append("--resume")
            else:
                # Default to --continue for existing projects
                skip_continue = new_session or proj.is_new
                # Check if user passed --resume/-r in extra_args
                if any(a in ("--resume", "-r") for a in extra_args):
                    skip_continue = True
                if not skip_continue:
                    cli_args.append("--continue")

        cli_args.extend(extra_args)

        # Run the container
        rc = runtime.run(
            image,
            project_path=proj.project_path,
            settings_path=proj.settings_path,
            dot_path=proj.dot_path,
            cfg_file=proj.cfg_file,
            shell_path=proj.shell_path,
            vault_ro_path=proj.vault_ro_path,
            vault_rw_path=proj.vault_rw_path,
            claude_install=claude_install,
            name=container_name,
            entrypoint=entrypoint,
            cli_args=cli_args or None,
        )

        # Write back refreshed credentials
        writeback_project_to_central_and_host(project_creds, central_creds)

        return rc

    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
