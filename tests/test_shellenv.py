"""Tests for kanibako.shellenv."""

from __future__ import annotations

from pathlib import Path

import pytest

from kanibako.shellenv import (
    merge_env,
    read_env_file,
    set_env_var,
    unset_env_var,
    write_env_file,
)


class TestReadEnvFile:
    def test_basic_key_value(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("EDITOR=vim\nNODE_ENV=development\n")
        result = read_env_file(f)
        assert result == {"EDITOR": "vim", "NODE_ENV": "development"}

    def test_comments_ignored(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("# comment\nKEY=val\n# another\n")
        result = read_env_file(f)
        assert result == {"KEY": "val"}

    def test_empty_lines_ignored(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("\nKEY=val\n\n\n")
        result = read_env_file(f)
        assert result == {"KEY": "val"}

    def test_empty_value(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("KEY=\n")
        result = read_env_file(f)
        assert result == {"KEY": ""}

    def test_value_with_equals(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("URL=https://example.com?a=1&b=2\n")
        result = read_env_file(f)
        assert result == {"URL": "https://example.com?a=1&b=2"}

    def test_invalid_key_skipped(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("123BAD=val\nGOOD=ok\n")
        result = read_env_file(f)
        assert result == {"GOOD": "ok"}

    def test_line_without_equals_skipped(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("NOEQUALSSIGN\nKEY=val\n")
        result = read_env_file(f)
        assert result == {"KEY": "val"}

    def test_missing_file_returns_empty(self, tmp_path):
        f = tmp_path / "nonexistent"
        assert read_env_file(f) == {}

    def test_underscore_key(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("_PRIVATE=secret\nMY_VAR_2=ok\n")
        result = read_env_file(f)
        assert result == {"_PRIVATE": "secret", "MY_VAR_2": "ok"}


class TestWriteEnvFile:
    def test_writes_sorted(self, tmp_path):
        f = tmp_path / "env"
        write_env_file(f, {"Z_KEY": "z", "A_KEY": "a"})
        content = f.read_text()
        assert content == "A_KEY=a\nZ_KEY=z\n"

    def test_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "sub" / "dir" / "env"
        write_env_file(f, {"KEY": "val"})
        assert f.exists()
        assert f.read_text() == "KEY=val\n"

    def test_empty_dict_writes_empty(self, tmp_path):
        f = tmp_path / "env"
        write_env_file(f, {})
        assert f.read_text() == ""

    def test_roundtrip(self, tmp_path):
        f = tmp_path / "env"
        original = {"EDITOR": "vim", "NODE_ENV": "development", "PATH_EXT": "/usr/local/bin"}
        write_env_file(f, original)
        result = read_env_file(f)
        assert result == original


class TestSetEnvVar:
    def test_set_new_var(self, tmp_path):
        f = tmp_path / "env"
        set_env_var(f, "KEY", "val")
        assert read_env_file(f) == {"KEY": "val"}

    def test_update_existing_var(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("KEY=old\n")
        set_env_var(f, "KEY", "new")
        assert read_env_file(f) == {"KEY": "new"}

    def test_add_to_existing_file(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("A=1\n")
        set_env_var(f, "B", "2")
        assert read_env_file(f) == {"A": "1", "B": "2"}

    def test_invalid_key_raises(self, tmp_path):
        f = tmp_path / "env"
        with pytest.raises(ValueError, match="Invalid"):
            set_env_var(f, "123BAD", "val")


class TestUnsetEnvVar:
    def test_unset_existing(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("KEY=val\nOTHER=ok\n")
        assert unset_env_var(f, "KEY") is True
        assert read_env_file(f) == {"OTHER": "ok"}

    def test_unset_nonexistent(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("KEY=val\n")
        assert unset_env_var(f, "NOPE") is False
        assert read_env_file(f) == {"KEY": "val"}

    def test_unset_missing_file(self, tmp_path):
        f = tmp_path / "nonexistent"
        assert unset_env_var(f, "KEY") is False


class TestMergeEnv:
    def test_global_only(self, tmp_path):
        g = tmp_path / "global_env"
        g.write_text("GLOBAL=yes\n")
        result = merge_env(g, None)
        assert result == {"GLOBAL": "yes"}

    def test_project_only(self, tmp_path):
        p = tmp_path / "project_env"
        p.write_text("PROJECT=yes\n")
        result = merge_env(None, p)
        assert result == {"PROJECT": "yes"}

    def test_both_with_no_conflict(self, tmp_path):
        g = tmp_path / "global_env"
        g.write_text("GLOBAL=yes\n")
        p = tmp_path / "project_env"
        p.write_text("PROJECT=yes\n")
        result = merge_env(g, p)
        assert result == {"GLOBAL": "yes", "PROJECT": "yes"}

    def test_project_wins_on_conflict(self, tmp_path):
        g = tmp_path / "global_env"
        g.write_text("EDITOR=nano\n")
        p = tmp_path / "project_env"
        p.write_text("EDITOR=vim\n")
        result = merge_env(g, p)
        assert result == {"EDITOR": "vim"}

    def test_neither_returns_empty(self):
        assert merge_env(None, None) == {}
