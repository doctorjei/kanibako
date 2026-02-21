"""Kanibako target plugin for Goose — advanced example.

Goose is a compiled Go binary AI developer agent from Block.  This example
demonstrates:
- Single-binary detection and mounting
- YAML config filtering (copies only safe keys)
- Credential field merging from host config
- Full CLI argument mapping including session management
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from kanibako.targets.base import AgentInstall, Mount, Target

# Keys from goose config that are safe to copy into the container.
_SAFE_CONFIG_KEYS = {"provider", "model", "extensions", "instructions"}

# Keys that contain credentials — synced separately.
_CREDENTIAL_KEYS = {"GOOSE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"}


def _read_json(path: Path) -> dict:
    """Read a JSON file, returning {} if missing or invalid."""
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    """Write a dict as formatted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _filter_config(source: dict) -> dict:
    """Return only safe (non-credential) keys from a goose config."""
    return {k: v for k, v in source.items() if k in _SAFE_CONFIG_KEYS}


def _extract_credentials(config: dict) -> dict:
    """Extract credential keys from a goose config."""
    return {k: v for k, v in config.items() if k in _CREDENTIAL_KEYS}


class GooseTarget(Target):
    """Kanibako target for Goose (https://github.com/block/goose)."""

    @property
    def name(self) -> str:
        return "goose"

    @property
    def display_name(self) -> str:
        return "Goose"

    def detect(self) -> AgentInstall | None:
        """Detect the goose binary on the host."""
        goose_path = shutil.which("goose")
        if not goose_path:
            return None
        binary = Path(goose_path)
        resolved = binary.resolve()
        return AgentInstall(
            name="goose",
            binary=binary,
            install_dir=resolved.parent,
        )

    def binary_mounts(self, install: AgentInstall) -> list[Mount]:
        """Mount the goose binary into the container (read-only)."""
        return [
            Mount(
                source=install.binary.resolve(),
                destination="/home/agent/.local/bin/goose",
                options="ro",
            ),
        ]

    def init_home(self, home: Path) -> None:
        """Initialize Goose config in the project home.

        Creates ``.config/goose/`` and copies filtered config from the host.
        Only safe keys are copied; credential keys are handled separately
        by refresh_credentials().  Idempotent.
        """
        config_dir = home / ".config" / "goose"
        config_dir.mkdir(parents=True, exist_ok=True)

        project_config = config_dir / "config.json"
        if project_config.exists():
            return

        host_config = Path.home() / ".config" / "goose" / "config.json"
        host_data = _read_json(host_config)
        if host_data:
            _write_json(project_config, _filter_config(host_data))

    def refresh_credentials(self, home: Path) -> None:
        """Merge credential fields from host goose config into project config.

        Reads the host config, extracts credential keys, and merges them into
        the project config.  Non-credential keys in the project config are
        left untouched.
        """
        host_config = Path.home() / ".config" / "goose" / "config.json"
        host_data = _read_json(host_config)
        host_creds = _extract_credentials(host_data)
        if not host_creds:
            return

        project_config = home / ".config" / "goose" / "config.json"
        project_data = _read_json(project_config)
        project_data.update(host_creds)
        _write_json(project_config, project_data)

    def writeback_credentials(self, home: Path) -> None:
        """Write back credential fields from project config to host config.

        Only credential keys are written back; the host's non-credential
        config is preserved.
        """
        project_config = home / ".config" / "goose" / "config.json"
        project_data = _read_json(project_config)
        project_creds = _extract_credentials(project_data)
        if not project_creds:
            return

        host_config = Path.home() / ".config" / "goose" / "config.json"
        host_data = _read_json(host_config)
        host_data.update(project_creds)
        _write_json(host_config, host_data)

    def build_cli_args(
        self,
        *,
        safe_mode: bool,
        resume_mode: bool,
        new_session: bool,
        is_new_project: bool,
        extra_args: list[str],
    ) -> list[str]:
        """Build CLI arguments for Goose.

        Maps kanibako flags to goose CLI semantics:
        - ``safe_mode=False`` → ``--approve-all`` (auto-approve)
        - ``resume_mode=True`` → ``session resume``
        - default → ``session start``
        """
        if resume_mode:
            args = ["session", "resume"]
        else:
            args = ["session", "start"]

        if not safe_mode:
            args.append("--approve-all")

        args.extend(extra_args)
        return args
