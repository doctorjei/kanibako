"""Credential copy, JSON merge (replaces jq), and mtime-based freshness."""

from __future__ import annotations

import json
import os
from pathlib import Path

from kanibako.utils import cp_if_newer, stderr


def refresh_host_to_central(central_creds: Path) -> bool:
    """Copy host ~/.claude/.credentials.json → central store if newer.

    Returns True if a copy was performed.
    """
    host_creds = Path.home() / ".claude" / ".credentials.json"
    if not host_creds.is_file():
        return False
    central_creds.parent.mkdir(parents=True, exist_ok=True)
    return cp_if_newer(host_creds, central_creds)


def refresh_central_to_project(central_creds: Path, project_creds: Path) -> bool:
    """Merge claudeAiOauth from central credentials into project credentials.

    Only acts when the central file is newer than the project file.
    Returns True if the project file was updated.
    """
    if not central_creds.is_file():
        return False

    # If project creds don't exist, just copy central wholesale
    if not project_creds.is_file():
        project_creds.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(str(central_creds), str(project_creds))
        return True

    # mtime check
    if os.stat(central_creds).st_mtime <= os.stat(project_creds).st_mtime:
        return False

    try:
        central_data = json.loads(central_creds.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        stderr(f"Warning: Cannot read central credentials: {exc}")
        return False

    # Guard for missing key (known issue #2)
    oauth = central_data.get("claudeAiOauth")
    if oauth is None:
        stderr("Warning: Central credentials missing 'claudeAiOauth' key; skipping merge.")
        return False

    try:
        project_data = json.loads(project_creds.read_text())
    except (json.JSONDecodeError, OSError):
        project_data = {}

    project_data["claudeAiOauth"] = oauth

    tmp = project_creds.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(project_data, indent=2) + "\n")
    tmp.replace(project_creds)
    return True


def writeback_project_to_central_and_host(
    project_creds: Path,
    central_creds: Path,
) -> None:
    """Write back refreshed credentials from project → central → host (if newer)."""
    if not project_creds.is_file():
        return
    cp_if_newer(project_creds, central_creds)
    host_creds = Path.home() / ".claude" / ".credentials.json"
    cp_if_newer(project_creds, host_creds)


def filter_settings(src: Path, dst: Path) -> None:
    """Copy host .claude.json with only safe keys (replaces jq filter)."""
    try:
        data = json.loads(src.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        stderr(f"Warning: Cannot read {src}: {exc}")
        return
    filtered = {
        "oauthAccount": data.get("oauthAccount"),
        "hasCompletedOnboarding": True,
        "installMethod": data.get("installMethod"),
    }
    # Remove None values
    filtered = {k: v for k, v in filtered.items() if v is not None}
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(filtered, indent=2) + "\n")
