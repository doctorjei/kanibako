"""TOML config loading, writing, defaults, and merge logic."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path

# Python 3.11+ stdlib
import tomllib


# ---------------------------------------------------------------------------
# Defaults (match the old kanibako.rc values)
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "paths_relative_std_path": "kanibako",
    "paths_init_credentials_path": "credentials",
    "paths_projects_path": "projects",
    "paths_dot_path": "dotclod",
    "paths_cfg_file": "dotclod.json",
    "container_image": "ghcr.io/doctorjei/kanibako-base:latest",
}


@dataclass
class KanibakoConfig:
    """Merged configuration (hardcoded defaults < kanibako.toml < project.toml < CLI)."""

    paths_relative_std_path: str = _DEFAULTS["paths_relative_std_path"]
    paths_init_credentials_path: str = _DEFAULTS["paths_init_credentials_path"]
    paths_projects_path: str = _DEFAULTS["paths_projects_path"]
    paths_dot_path: str = _DEFAULTS["paths_dot_path"]
    paths_cfg_file: str = _DEFAULTS["paths_cfg_file"]
    container_image: str = _DEFAULTS["container_image"]


def _flatten_toml(data: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested TOML dict into underscore-joined keys.

    ``{"paths": {"dot_path": "x"}}`` → ``{"paths_dot_path": "x"}``
    """
    out: dict[str, str] = {}
    for k, v in data.items():
        key = f"{prefix}_{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten_toml(v, key))
        else:
            out[key] = str(v)
    return out


def load_config(path: Path) -> KanibakoConfig:
    """Read a single TOML file and return a KanibakoConfig with defaults filled in."""
    cfg = KanibakoConfig()
    if path.exists():
        with open(path, "rb") as f:
            data = tomllib.load(f)
        flat = _flatten_toml(data)
        valid_keys = {fld.name for fld in fields(cfg)}
        for k, v in flat.items():
            if k in valid_keys:
                setattr(cfg, k, v)
    return cfg


def load_merged_config(
    global_path: Path,
    project_path: Path | None = None,
    *,
    cli_overrides: dict[str, str] | None = None,
) -> KanibakoConfig:
    """Load global config, overlay project config, then CLI overrides.

    Precedence: CLI flags > project.toml > kanibako.toml > hardcoded defaults.
    """
    cfg = load_config(global_path)
    if project_path and project_path.exists():
        proj = load_config(project_path)
        # Only override non-default values from project config.
        defaults = KanibakoConfig()
        for fld in fields(proj):
            val = getattr(proj, fld.name)
            if val != getattr(defaults, fld.name):
                setattr(cfg, fld.name, val)
    if cli_overrides:
        valid_keys = {fld.name for fld in fields(cfg)}
        for k, v in cli_overrides.items():
            if k in valid_keys:
                setattr(cfg, k, v)
    return cfg


def write_global_config(path: Path, cfg: KanibakoConfig | None = None) -> None:
    """Write a TOML config file with the structured layout.

    If *cfg* is None, writes defaults.
    """
    if cfg is None:
        cfg = KanibakoConfig()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[paths]",
        f'relative_std_path = "{cfg.paths_relative_std_path}"',
        f'init_credentials_path = "{cfg.paths_init_credentials_path}"',
        f'projects_path = "{cfg.paths_projects_path}"',
        f'dot_path = "{cfg.paths_dot_path}"',
        f'cfg_file = "{cfg.paths_cfg_file}"',
        "",
        "[container]",
        f'image = "{cfg.container_image}"',
        "",
    ]
    path.write_text("\n".join(lines))


def write_project_config(path: Path, image: str) -> None:
    """Write or update a project.toml with the given image."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        text = path.read_text()
        # Replace existing image line
        if re.search(r'^image\s*=', text, re.MULTILINE):
            text = re.sub(
                r'^image\s*=\s*"[^"]*"',
                f'image = "{image}"',
                text,
                flags=re.MULTILINE,
            )
            path.write_text(text)
            return
        # Has [container] section but no image key
        if "[container]" in text:
            text = text.replace(
                "[container]", f'[container]\nimage = "{image}"', 1
            )
            path.write_text(text)
            return
    # New file or no [container] section
    lines = [
        "[container]",
        f'image = "{image}"',
        "",
    ]
    path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Legacy .rc migration helpers (used by `kanibako install`)
# ---------------------------------------------------------------------------

_RC_KEY_MAP = {
    "CLODBOX_RELATIVE_STD_PATH": "paths_relative_std_path",
    "CLODBOX_INIT_CREDENTIALS_PATH": "paths_init_credentials_path",
    "CLODBOX_PROJECTS_PATH": "paths_projects_path",
    "CLODBOX_DOT_PATH": "paths_dot_path",
    "CLODBOX_CFG_FILE": "paths_cfg_file",
    "CLODBOX_CONTAINER_IMAGE": "container_image",
}


def migrate_rc(rc_path: Path, toml_path: Path) -> KanibakoConfig:
    """Read legacy kanibako.rc, write equivalent kanibako.toml, rename .rc → .rc.bak."""
    cfg = KanibakoConfig()
    text = rc_path.read_text()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or line.startswith("!") or not line:
            continue
        # Strip optional 'export '
        if line.startswith("export "):
            line = line[7:]
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        mapped = _RC_KEY_MAP.get(key)
        if mapped:
            setattr(cfg, mapped, val)
    write_global_config(toml_path, cfg)
    rc_path.rename(rc_path.with_suffix(".rc.bak"))
    print(f"Migrated {rc_path} → {toml_path}", file=sys.stderr)
    return cfg
