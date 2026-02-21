"""Environment variable file handling for per-project and global env vars."""

from __future__ import annotations

import re
from pathlib import Path

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def read_env_file(path: Path) -> dict[str, str]:
    """Read a Docker-style .env file and return key-value pairs.

    - One KEY=VALUE per line
    - Lines starting with ``#`` are comments
    - Empty lines are ignored
    - No shell expansion (values are literal)
    - Invalid lines are silently skipped
    """
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not _KEY_RE.match(key):
            continue
        env[key] = value
    return env


def write_env_file(path: Path, env: dict[str, str]) -> None:
    """Write a dict of env vars to a Docker-style .env file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for key, value in sorted(env.items()):
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n" if lines else "")


def set_env_var(path: Path, key: str, value: str) -> None:
    """Set a single env var in an env file (read-modify-write)."""
    if not _KEY_RE.match(key):
        raise ValueError(f"Invalid environment variable name: {key}")
    env = read_env_file(path)
    env[key] = value
    write_env_file(path, env)


def unset_env_var(path: Path, key: str) -> bool:
    """Remove an env var from an env file. Returns True if it existed."""
    env = read_env_file(path)
    if key not in env:
        return False
    del env[key]
    write_env_file(path, env)
    return True


def merge_env(
    global_path: Path | None,
    project_path: Path | None,
) -> dict[str, str]:
    """Merge global and project env files. Project wins on conflict."""
    env: dict[str, str] = {}
    if global_path:
        env.update(read_env_file(global_path))
    if project_path:
        env.update(read_env_file(project_path))
    return env
