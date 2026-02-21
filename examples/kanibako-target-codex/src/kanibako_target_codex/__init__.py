"""Kanibako target plugin for Codex CLI — moderate example.

Codex CLI is an npm-installed Node.js coding agent from OpenAI.  This example
demonstrates:
- Binary detection with npm tree walking (similar to ClaudeTarget)
- File-based credential sync (copying config.json)
- Mounting the npm package directory + binary symlink
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from kanibako.targets.base import AgentInstall, Mount, Target


class CodexTarget(Target):
    """Kanibako target for Codex CLI (https://github.com/openai/codex)."""

    @property
    def name(self) -> str:
        return "codex"

    @property
    def display_name(self) -> str:
        return "Codex CLI"

    def detect(self) -> AgentInstall | None:
        """Detect Codex CLI on the host.

        Resolves the ``codex`` symlink and walks up the directory tree to
        find the npm package root (a directory named ``codex`` containing
        ``package.json``).
        """
        codex_path = shutil.which("codex")
        if not codex_path:
            return None

        binary = Path(codex_path)
        try:
            resolved = binary.resolve()
        except OSError:
            return None

        # Walk up from the resolved binary to find the npm package root.
        install_dir = resolved.parent
        while install_dir != install_dir.parent:
            if install_dir.name == "codex" and (install_dir / "package.json").is_file():
                break
            install_dir = install_dir.parent
        else:
            # Didn't find a codex package root; fall back to parent of binary.
            install_dir = resolved.parent

        # Handle the edge case where we walked all the way to root
        if install_dir == install_dir.parent:
            install_dir = resolved.parent

        return AgentInstall(name="codex", binary=binary, install_dir=install_dir)

    def binary_mounts(self, install: AgentInstall) -> list[Mount]:
        """Mount the npm package directory and binary symlink."""
        return [
            Mount(
                source=install.install_dir,
                destination="/home/agent/.local/share/codex",
                options="ro",
            ),
            Mount(
                source=install.binary,
                destination="/home/agent/.local/bin/codex",
                options="ro",
            ),
        ]

    def init_home(self, home: Path) -> None:
        """Initialize Codex-specific config in the project home.

        Creates ``.codex/`` and copies ``config.json`` from the host if it
        exists.  Idempotent — skips copy if config already exists.
        """
        codex_dir = home / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)

        host_config = Path.home() / ".codex" / "config.json"
        project_config = codex_dir / "config.json"
        if host_config.is_file() and not project_config.exists():
            shutil.copy2(str(host_config), str(project_config))

    def refresh_credentials(self, home: Path) -> None:
        """Sync Codex config from host into project home if host copy is newer."""
        host_config = Path.home() / ".codex" / "config.json"
        project_config = home / ".codex" / "config.json"

        if not host_config.is_file():
            return

        project_config.parent.mkdir(parents=True, exist_ok=True)

        if not project_config.exists():
            shutil.copy2(str(host_config), str(project_config))
            return

        # Copy only if host is newer.
        host_mtime = host_config.stat().st_mtime
        project_mtime = project_config.stat().st_mtime
        if host_mtime > project_mtime:
            shutil.copy2(str(host_config), str(project_config))

    def writeback_credentials(self, home: Path) -> None:
        """Write back Codex config from project home to host if project copy is newer."""
        host_config = Path.home() / ".codex" / "config.json"
        project_config = home / ".codex" / "config.json"

        if not project_config.is_file():
            return

        host_config.parent.mkdir(parents=True, exist_ok=True)

        if not host_config.exists():
            shutil.copy2(str(project_config), str(host_config))
            return

        project_mtime = project_config.stat().st_mtime
        host_mtime = host_config.stat().st_mtime
        if project_mtime > host_mtime:
            shutil.copy2(str(project_config), str(host_config))

    def build_cli_args(
        self,
        *,
        safe_mode: bool,
        resume_mode: bool,
        new_session: bool,
        is_new_project: bool,
        extra_args: list[str],
    ) -> list[str]:
        """Build CLI arguments for Codex CLI.

        In non-safe mode, passes ``--full-auto`` for autonomous operation.
        Safe mode omits this flag so the agent asks for approval.
        """
        args: list[str] = []
        if not safe_mode:
            args.append("--full-auto")
        args.extend(extra_args)
        return args
