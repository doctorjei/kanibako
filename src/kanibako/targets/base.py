"""Target base classes: ABC for agent targets, Mount and AgentInstall dataclasses."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Mount:
    """A volume mount for a container."""

    source: Path
    destination: str
    options: str = ""  # e.g. "ro"

    def to_volume_arg(self) -> str:
        """Return the -v argument string for podman/docker."""
        base = f"{self.source}:{self.destination}"
        return f"{base}:{self.options}" if self.options else base


@dataclass
class AgentInstall:
    """Information about an agent installation on the host."""

    name: str  # e.g. "claude"
    binary: Path  # host symlink/path to agent binary
    install_dir: Path  # root of agent installation


class Target(ABC):
    """Abstract base class for agent targets.

    A target encapsulates all agent-specific logic: detection, binary mounting,
    home directory initialization, credential management, and CLI argument
    building.  Kanibako's core is agent-agnostic; all agent knowledge lives
    in Target implementations.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this target (e.g. 'claude')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name (e.g. 'Claude Code')."""
        ...

    @abstractmethod
    def detect(self) -> AgentInstall | None:
        """Detect the agent installation on the host.

        Returns an AgentInstall if found, or None if the agent is not installed.
        """
        ...

    @abstractmethod
    def binary_mounts(self, install: AgentInstall) -> list[Mount]:
        """Return volume mounts needed to make the agent binary available in the container."""
        ...

    @abstractmethod
    def init_home(self, home: Path) -> None:
        """Initialize agent-specific files in the project home directory.

        Called after kanibako core creates .bashrc/.profile.  The target
        should create its own config directories and files (e.g. .claude/).
        """
        ...

    def check_auth(self) -> bool:
        """Check if the agent is authenticated. Returns True if ok."""
        return True

    @abstractmethod
    def refresh_credentials(self, home: Path) -> None:
        """Refresh agent credentials from host into the project home."""
        ...

    @abstractmethod
    def writeback_credentials(self, home: Path) -> None:
        """Write back credentials from project home to host."""
        ...

    @abstractmethod
    def build_cli_args(
        self,
        *,
        safe_mode: bool,
        resume_mode: bool,
        new_session: bool,
        is_new_project: bool,
        extra_args: list[str],
    ) -> list[str]:
        """Build command-line arguments for the agent entrypoint."""
        ...
