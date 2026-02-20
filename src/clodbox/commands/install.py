"""clodbox setup: first-time environment setup."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from clodbox.config import (
    ClodboxConfig,
    load_config,
    migrate_rc,
    write_global_config,
)
from clodbox.container import ContainerRuntime
from clodbox.containerfiles import get_containerfile
from clodbox.credentials import filter_settings
from clodbox.errors import ContainerError
from clodbox.paths import _xdg


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "setup",
        help="First-time setup (config, creds, containers, cron)",
        description="Set up clodbox: write config, copy credentials, "
        "install Containerfiles, pull image, and set up cron job.",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    config_home = _xdg("XDG_CONFIG_HOME", ".config")
    config_file = config_home / "clodbox" / "clodbox.toml"

    # ------------------------------------------------------------------
    # 1. Write config (or migrate from .rc)
    # ------------------------------------------------------------------
    legacy_rc = config_file.with_name("clodbox.rc")
    if config_file.exists():
        print("Configuration file already exists, loading.")
        config = load_config(config_file)
    elif legacy_rc.exists():
        print("Migrating legacy clodbox.rc to clodbox.toml...")
        config = migrate_rc(legacy_rc, config_file)
    else:
        print("Writing general configuration file (clodbox.toml)... ", end="", flush=True)
        config = ClodboxConfig()
        write_global_config(config_file, config)
        print("done!")

    # ------------------------------------------------------------------
    # 2. Copy host credentials into central store
    # ------------------------------------------------------------------
    data_home = _xdg("XDG_DATA_HOME", ".local/share")
    data_path = data_home / config.paths_relative_std_path
    credentials_path = data_path / config.paths_init_credentials_path
    dot_template_path = credentials_path / config.paths_dot_path
    cfg_template_file = credentials_path / config.paths_cfg_file

    print("Copying authentication credentials to clodbox store... ", end="", flush=True)
    dot_template_path.mkdir(parents=True, exist_ok=True)

    host_settings = Path.home() / ".claude.json"
    if host_settings.is_file():
        filter_settings(host_settings, cfg_template_file)

    host_creds = Path.home() / ".claude" / ".credentials.json"
    if host_creds.is_file():
        shutil.copy2(str(host_creds), str(dot_template_path / ".credentials.json"))
    print("done!")

    # ------------------------------------------------------------------
    # 3. Create containers directory for user overrides
    # ------------------------------------------------------------------
    containers_dest = data_path / "containers"
    containers_dest.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 4. Pull or build base container image
    # ------------------------------------------------------------------
    try:
        runtime = ContainerRuntime()
        image = config.container_image
        if runtime.image_exists(image):
            print("Container image already exists, skipping.")
        elif runtime.pull(image):
            print("Image pulled from registry!")
        else:
            print("Pull failed; building locally...")
            base_cf = get_containerfile("base", containers_dest)
            if base_cf is not None:
                runtime.build(image, base_cf, base_cf.parent)
                print("Base image built!")
            else:
                print("Warning: No Containerfile.base found; skipping build.", file=sys.stderr)
    except Exception as e:
        print(f"Warning: {e}", file=sys.stderr)
        print("Skipping image setup.")

    # ------------------------------------------------------------------
    # 5. Set up cron job for credential refresh
    # ------------------------------------------------------------------
    print("Installing credential refresh cron job... ", end="", flush=True)
    _install_cron()
    print("done!")

    # ------------------------------------------------------------------
    # 6. Register shell completion
    # ------------------------------------------------------------------
    print("Setting up shell completion... ", end="", flush=True)
    _install_completion()
    print("done!")

    return 0



def _install_cron() -> None:
    """Install credential refresh cron job (every 6 hours)."""
    # Find clodbox executable
    clodbox_bin = shutil.which("clodbox")
    if not clodbox_bin:
        clodbox_bin = str(Path.home() / ".local" / "bin" / "clodbox")

    cron_cmd = f"{clodbox_bin} refresh-creds"
    cron_entry = f"0 */6 * * * {cron_cmd}"

    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        )
        existing = result.stdout if result.returncode == 0 else ""
    except FileNotFoundError:
        print("(crontab not available, skipping)", end=" ")
        return

    # Remove existing clodbox cron entries, add new one
    lines = [l for l in existing.splitlines() if cron_cmd not in l]
    lines.append(cron_entry)
    new_crontab = "\n".join(lines) + "\n"

    subprocess.run(
        ["crontab", "-"],
        input=new_crontab,
        text=True,
        capture_output=True,
    )


def _install_completion() -> None:
    """Register bash/zsh completion for clodbox via argcomplete."""
    completions_dir = _xdg("XDG_DATA_HOME", ".local/share") / "bash-completion" / "completions"
    completions_dir.mkdir(parents=True, exist_ok=True)
    target = completions_dir / "clodbox"

    try:
        result = subprocess.run(
            ["register-python-argcomplete", "clodbox"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            target.write_text(result.stdout)
        else:
            print("(register-python-argcomplete failed, skipping)", end=" ")
    except FileNotFoundError:
        print("(argcomplete not on PATH, skipping)", end=" ")
