"""kanibako setup: first-time environment setup."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from kanibako.config import (
    KanibakoConfig,
    load_config,
    write_global_config,
)
from kanibako.container import ContainerRuntime
from kanibako.containerfiles import get_containerfile
from kanibako.errors import ContainerError
from kanibako.paths import _xdg


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "setup",
        help="First-time setup (config, containers)",
        description="Set up kanibako: write config, "
        "install Containerfiles, and pull image.",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    config_home = _xdg("XDG_CONFIG_HOME", ".config")
    config_file = config_home / "kanibako" / "kanibako.toml"

    # ------------------------------------------------------------------
    # 1. Write config
    # ------------------------------------------------------------------
    if config_file.exists():
        print("Configuration file already exists, loading.")
        config = load_config(config_file)
    else:
        print("Writing general configuration file (kanibako.toml)... ", end="", flush=True)
        config = KanibakoConfig()
        write_global_config(config_file, config)
        print("done!")

    # ------------------------------------------------------------------
    # 2. Create containers directory for user overrides
    # ------------------------------------------------------------------
    data_home = _xdg("XDG_DATA_HOME", ".local/share")
    data_path = data_home / config.paths_relative_std_path
    containers_dest = data_path / "containers"
    containers_dest.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 3. Pull or build base container image
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
    # 4. Register shell completion
    # ------------------------------------------------------------------
    print("Setting up shell completion... ", end="", flush=True)
    _install_completion()
    print("done!")

    return 0


def _install_completion() -> None:
    """Register bash/zsh completion for kanibako via argcomplete."""
    completions_dir = _xdg("XDG_DATA_HOME", ".local/share") / "bash-completion" / "completions"
    completions_dir.mkdir(parents=True, exist_ok=True)
    target = completions_dir / "kanibako"

    try:
        result = subprocess.run(
            ["register-python-argcomplete", "kanibako"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            target.write_text(result.stdout)
        else:
            print("(register-python-argcomplete failed, skipping)", end=" ")
    except FileNotFoundError:
        print("(argcomplete not on PATH, skipping)", end=" ")
