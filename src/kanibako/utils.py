"""Utility functions: cp_if_newer, confirm_prompt, short_hash."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys

from kanibako.errors import UserCancelled


def cp_if_newer(src: str | os.PathLike, dst: str | os.PathLike) -> bool:
    """Copy *src* to *dst* only if *src* is strictly newer (by mtime).

    Creates parent directories for *dst* if needed.
    Returns True if the copy was performed.
    """
    src_s = str(src)
    dst_s = str(dst)
    if not os.path.isfile(src_s):
        return False
    do_copy = (
        not os.path.isfile(dst_s)
        or os.stat(src_s).st_mtime > os.stat(dst_s).st_mtime
    )
    if do_copy:
        os.makedirs(os.path.dirname(dst_s) or ".", exist_ok=True)
        shutil.copy2(src_s, dst_s)
    return do_copy


def confirm_prompt(message: str) -> None:
    """Print *message*, read a line, raise UserCancelled unless it is 'yes'."""
    print(message, end="", flush=True)
    try:
        response = input()
    except (EOFError, KeyboardInterrupt):
        print()
        raise UserCancelled("Aborted.")
    if response.strip() != "yes":
        raise UserCancelled("Aborted.")


def short_hash(full_hash: str, length: int = 8) -> str:
    """Return the first *length* characters of *full_hash*."""
    return full_hash[:length]


def project_hash(project_path: str) -> str:
    """SHA-256 hex digest of the project path string."""
    return hashlib.sha256(project_path.encode()).hexdigest()


def stderr(*args: object, **kwargs: object) -> None:
    """Print to stderr."""
    print(*args, file=sys.stderr, **kwargs)  # type: ignore[arg-type]
