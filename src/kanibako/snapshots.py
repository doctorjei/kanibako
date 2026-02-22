"""Snapshot engine for vault share-rw directories.

Provides point-in-time backups of ``share-rw/`` as compressed tar archives
stored in a ``.versions/`` sibling directory.  Automatic snapshots can be
triggered before each container launch.
"""

from __future__ import annotations

import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path


# Default maximum number of snapshots to retain.
_DEFAULT_MAX_SNAPSHOTS = 5


def _versions_dir(vault_rw_path: Path) -> Path:
    """Return the .versions/ directory for a vault share-rw path."""
    return vault_rw_path.parent / ".versions"


def create_snapshot(vault_rw_path: Path) -> Path | None:
    """Create a snapshot of *vault_rw_path*.

    Returns the path to the snapshot archive, or ``None`` if the directory
    is empty (nothing to snapshot).
    """
    if not vault_rw_path.is_dir():
        return None

    # Don't snapshot an empty directory.
    contents = list(vault_rw_path.iterdir())
    if not contents:
        return None

    versions = _versions_dir(vault_rw_path)
    versions.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = versions / f"{ts}.tar.xz"

    with tarfile.open(archive, "w:xz") as tar:
        for item in sorted(vault_rw_path.iterdir()):
            tar.add(str(item), arcname=item.name)

    return archive


def list_snapshots(vault_rw_path: Path) -> list[tuple[str, str, int]]:
    """List snapshots for *vault_rw_path*.

    Returns a list of ``(name, timestamp_iso, size_bytes)`` sorted by time
    (oldest first).
    """
    versions = _versions_dir(vault_rw_path)
    if not versions.is_dir():
        return []

    snapshots: list[tuple[str, str, int]] = []
    for entry in sorted(versions.iterdir()):
        if entry.suffix == ".xz" and entry.name.endswith(".tar.xz"):
            name = entry.name
            # Parse timestamp from filename: 20260221T103000Z.tar.xz
            stem = name.removesuffix(".tar.xz")
            try:
                dt = datetime.strptime(stem, "%Y%m%dT%H%M%SZ")
                ts_iso = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except ValueError:
                ts_iso = stem
            size = entry.stat().st_size
            snapshots.append((name, ts_iso, size))

    return snapshots


def restore_snapshot(vault_rw_path: Path, snapshot_name: str) -> None:
    """Restore *vault_rw_path* from the named snapshot.

    The current contents of share-rw are replaced with the snapshot contents.
    Raises ``FileNotFoundError`` if the snapshot does not exist.
    """
    versions = _versions_dir(vault_rw_path)
    archive = versions / snapshot_name
    if not archive.is_file():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_name}")

    # Clear current contents.
    if vault_rw_path.is_dir():
        for item in vault_rw_path.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    # Extract snapshot.
    with tarfile.open(archive, "r:xz") as tar:
        tar.extractall(path=str(vault_rw_path), filter="data")


def prune_snapshots(vault_rw_path: Path, max_keep: int = _DEFAULT_MAX_SNAPSHOTS) -> int:
    """Remove old snapshots, keeping at most *max_keep*.

    Returns the number of snapshots removed.
    """
    versions = _versions_dir(vault_rw_path)
    if not versions.is_dir():
        return 0

    archives = sorted(
        (f for f in versions.iterdir() if f.name.endswith(".tar.xz")),
        key=lambda p: p.name,
    )
    to_remove = archives[:-max_keep] if len(archives) > max_keep else []
    for old in to_remove:
        old.unlink()
    return len(to_remove)


def auto_snapshot(vault_rw_path: Path, *, max_keep: int = _DEFAULT_MAX_SNAPSHOTS) -> Path | None:
    """Create a snapshot and prune old ones.

    Convenience wrapper combining ``create_snapshot`` + ``prune_snapshots``.
    Returns the new snapshot path, or ``None`` if share-rw was empty.
    """
    result = create_snapshot(vault_rw_path)
    if result is not None:
        prune_snapshots(vault_rw_path, max_keep=max_keep)
    return result
