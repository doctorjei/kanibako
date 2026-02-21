"""Kanibako target plugin for Aider — minimal example.

Aider is a pip-installed Python CLI for AI pair programming.  It uses
environment variables for API keys, so credential management is a no-op.
The binary doesn't need mounting because it runs from the container's own
Python environment.

This is the simplest possible kanibako target implementation.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from kanibako.targets.base import AgentInstall, Mount, Target


class AiderTarget(Target):
    """Kanibako target for Aider (https://aider.chat)."""

    @property
    def name(self) -> str:
        return "aider"

    @property
    def display_name(self) -> str:
        return "Aider"

    def detect(self) -> AgentInstall | None:
        """Detect aider on the host via shutil.which."""
        aider_path = shutil.which("aider")
        if not aider_path:
            return None
        binary = Path(aider_path)
        return AgentInstall(
            name="aider",
            binary=binary,
            install_dir=binary.resolve().parent,
        )

    def binary_mounts(self, install: AgentInstall) -> list[Mount]:
        """No binary mounts needed — aider is a Python package."""
        return []

    def init_home(self, home: Path) -> None:
        """No agent-specific home initialization needed."""

    def refresh_credentials(self, home: Path) -> None:
        """No-op — aider uses environment variables for API keys."""

    def writeback_credentials(self, home: Path) -> None:
        """No-op — nothing to write back."""

    def build_cli_args(
        self,
        *,
        safe_mode: bool,
        resume_mode: bool,
        new_session: bool,
        is_new_project: bool,
        extra_args: list[str],
    ) -> list[str]:
        """Build CLI arguments for aider.

        Maps kanibako's safe_mode to aider's --yes flag (auto-confirm).
        """
        args: list[str] = []
        if not safe_mode:
            args.append("--yes")
        args.extend(extra_args)
        return args
