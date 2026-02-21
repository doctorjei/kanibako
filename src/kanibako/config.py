"""TOML config loading, writing, defaults, and merge logic."""

from __future__ import annotations

import os
import re
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
    "paths_settings_path": "settings",
    "paths_dot_path": "dotclaude",
    "paths_cfg_file": "claude.json",
    "container_image": "ghcr.io/doctorjei/kanibako-base:latest",
    "target_name": "",
}


@dataclass
class KanibakoConfig:
    """Merged configuration (hardcoded defaults < kanibako.toml < project.toml < CLI)."""

    paths_relative_std_path: str = _DEFAULTS["paths_relative_std_path"]
    paths_init_credentials_path: str = _DEFAULTS["paths_init_credentials_path"]
    paths_settings_path: str = _DEFAULTS["paths_settings_path"]
    paths_dot_path: str = _DEFAULTS["paths_dot_path"]
    paths_cfg_file: str = _DEFAULTS["paths_cfg_file"]
    container_image: str = _DEFAULTS["container_image"]
    target_name: str = _DEFAULTS["target_name"]


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
        f'settings_path = "{cfg.paths_settings_path}"',
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
    write_project_config_key(path, "container_image", image)


def write_project_meta(
    path: Path,
    *,
    mode: str,
    layout: str,
    workspace: str,
    shell: str,
    vault_ro: str,
    vault_rw: str,
    vault_enabled: bool = True,
) -> None:
    """Write resolved project metadata to project.toml, preserving other sections."""
    existing: dict = {}
    if path.exists():
        with open(path, "rb") as f:
            existing = tomllib.load(f)

    existing["project"] = {"mode": mode, "layout": layout, "vault_enabled": vault_enabled}
    existing.setdefault("paths", {})
    existing["paths"]["workspace"] = workspace
    existing["paths"]["shell"] = shell
    existing["paths"]["vault_ro"] = vault_ro
    existing["paths"]["vault_rw"] = vault_rw

    _write_toml(path, existing)


def read_project_meta(path: Path) -> dict | None:
    """Read stored project metadata from project.toml.

    Returns a dict with 'mode', 'workspace', 'shell', 'vault_ro', 'vault_rw'
    or None if no project metadata is stored.
    """
    if not path.exists():
        return None
    with open(path, "rb") as f:
        data = tomllib.load(f)

    project_sec = data.get("project", {})
    paths_sec = data.get("paths", {})

    if not project_sec.get("mode"):
        return None

    return {
        "mode": project_sec["mode"],
        "layout": project_sec.get("layout", ""),
        "vault_enabled": project_sec.get("vault_enabled", True),
        "workspace": paths_sec.get("workspace", ""),
        "shell": paths_sec.get("shell", ""),
        "vault_ro": paths_sec.get("vault_ro", ""),
        "vault_rw": paths_sec.get("vault_rw", ""),
    }


def _write_toml(path: Path, data: dict) -> None:
    """Write a dict as TOML. Handles one level of nesting (sections with scalar values)."""
    lines: list[str] = []
    for section_name, section_data in data.items():
        if not isinstance(section_data, dict):
            continue
        if lines:
            lines.append("")
        lines.append(f"[{section_name}]")
        for k, v in section_data.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f'{k} = "{v}"')
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def _split_config_key(flat_key: str) -> tuple[str, str]:
    """Split a flat config key into (section, toml_key).

    ``"container_image"`` → ``("container", "image")``
    ``"paths_dot_path"``  → ``("paths", "dot_path")``
    """
    for prefix in ("paths_", "container_", "target_"):
        if flat_key.startswith(prefix):
            section = prefix.rstrip("_")
            toml_key = flat_key[len(prefix):]
            return section, toml_key
    raise ValueError(f"Cannot determine TOML section for key: {flat_key}")


def config_keys() -> list[str]:
    """Return all valid flat config key names."""
    return [fld.name for fld in fields(KanibakoConfig)]


def write_project_config_key(path: Path, flat_key: str, value: str) -> None:
    """Write or update a single key in a project.toml.

    *flat_key* is the underscore-joined config name (e.g. ``"container_image"``).
    """
    section, toml_key = _split_config_key(flat_key)
    section_header = f"[{section}]"

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        text = path.read_text()
        # Replace existing key line
        if re.search(rf'^{re.escape(toml_key)}\s*=', text, re.MULTILINE):
            text = re.sub(
                rf'^{re.escape(toml_key)}\s*=\s*"[^"]*"',
                f'{toml_key} = "{value}"',
                text,
                flags=re.MULTILINE,
            )
            path.write_text(text)
            return
        # Has the right section but no matching key
        if section_header in text:
            text = text.replace(
                section_header, f'{section_header}\n{toml_key} = "{value}"', 1
            )
            path.write_text(text)
            return
        # File exists but different section — append
        if not text.endswith("\n"):
            text += "\n"
        text += f"\n{section_header}\n{toml_key} = \"{value}\"\n"
        path.write_text(text)
        return
    # New file
    lines = [
        section_header,
        f'{toml_key} = "{value}"',
        "",
    ]
    path.write_text("\n".join(lines))


def unset_project_config_key(path: Path, flat_key: str) -> bool:
    """Remove a single key from a project.toml.

    Returns True if the key was found and removed, False if it was not present.
    """
    if not path.exists():
        return False

    section, toml_key = _split_config_key(flat_key)
    text = path.read_text()

    # Remove the key line (including trailing newline)
    new_text, count = re.subn(
        rf'^{re.escape(toml_key)}\s*=\s*"[^"]*"\n?',
        "",
        text,
        flags=re.MULTILINE,
    )
    if count == 0:
        return False

    # Clean up empty sections: if the section header is followed by
    # nothing (or only blank lines) before the next section or EOF, remove it.
    new_text = re.sub(
        r'^\[[\w]+\]\n(?=\s*(?:\[|$))',
        "",
        new_text,
        flags=re.MULTILINE,
    )
    # Strip trailing whitespace
    new_text = new_text.rstrip() + "\n" if new_text.strip() else ""

    path.write_text(new_text)
    return True


def load_project_overrides(path: Path) -> dict[str, str]:
    """Load only the project-level overrides from a project.toml.

    Returns a dict of flat_key → value for keys that differ from defaults.
    """
    if not path.exists():
        return {}
    proj_cfg = load_config(path)
    defaults = KanibakoConfig()
    overrides: dict[str, str] = {}
    for fld in fields(proj_cfg):
        val = getattr(proj_cfg, fld.name)
        if val != getattr(defaults, fld.name):
            overrides[fld.name] = val
    return overrides
