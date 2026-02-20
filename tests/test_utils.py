"""Tests for kanibako.utils: cp_if_newer, confirm_prompt, project_hash, short_hash."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from kanibako.errors import UserCancelled
from kanibako.utils import confirm_prompt, cp_if_newer, project_hash, short_hash


# ---------------------------------------------------------------------------
# cp_if_newer
# ---------------------------------------------------------------------------

class TestCpIfNewer:
    def test_copies_when_dst_missing(self, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("hello")
        assert cp_if_newer(src, dst) is True
        assert dst.read_text() == "hello"

    def test_copies_when_src_newer(self, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        dst.write_text("old")
        # Ensure distinct mtime
        src.write_text("new")
        os.utime(dst, (0, 0))
        assert cp_if_newer(src, dst) is True
        assert dst.read_text() == "new"

    def test_skips_when_dst_newer(self, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("old")
        os.utime(src, (0, 0))
        dst.write_text("new")
        assert cp_if_newer(src, dst) is False
        assert dst.read_text() == "new"

    def test_skips_when_src_missing(self, tmp_path):
        dst = tmp_path / "dst.txt"
        assert cp_if_newer(tmp_path / "nope.txt", dst) is False
        assert not dst.exists()

    def test_creates_parent_dirs(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("data")
        dst = tmp_path / "a" / "b" / "dst.txt"
        assert cp_if_newer(src, dst) is True
        assert dst.read_text() == "data"


# ---------------------------------------------------------------------------
# confirm_prompt
# ---------------------------------------------------------------------------

class TestConfirmPrompt:
    def test_yes_passes(self):
        with patch("builtins.input", return_value="yes"):
            confirm_prompt("ok? ")  # Should not raise

    def test_no_raises(self):
        with patch("builtins.input", return_value="no"):
            with pytest.raises(UserCancelled):
                confirm_prompt("ok? ")

    def test_empty_raises(self):
        with patch("builtins.input", return_value=""):
            with pytest.raises(UserCancelled):
                confirm_prompt("ok? ")

    def test_eof_raises(self):
        with patch("builtins.input", side_effect=EOFError):
            with pytest.raises(UserCancelled):
                confirm_prompt("ok? ")

    def test_keyboard_interrupt_raises(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            with pytest.raises(UserCancelled):
                confirm_prompt("ok? ")

    def test_whitespace_yes_passes(self):
        with patch("builtins.input", return_value="  yes  "):
            confirm_prompt("ok? ")  # Should not raise


# ---------------------------------------------------------------------------
# project_hash
# ---------------------------------------------------------------------------

class TestProjectHash:
    def test_deterministic(self):
        h1 = project_hash("/some/path")
        h2 = project_hash("/some/path")
        assert h1 == h2

    def test_different_paths(self):
        h1 = project_hash("/path/a")
        h2 = project_hash("/path/b")
        assert h1 != h2

    def test_matches_sha256(self):
        path = "/my/project"
        expected = hashlib.sha256(path.encode()).hexdigest()
        assert project_hash(path) == expected


# ---------------------------------------------------------------------------
# short_hash
# ---------------------------------------------------------------------------

class TestShortHash:
    def test_default_length(self):
        h = "abcdef1234567890"
        assert short_hash(h) == "abcdef12"

    def test_custom_length(self):
        h = "abcdef1234567890"
        assert short_hash(h, 4) == "abcd"
