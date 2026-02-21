"""Tests for CodexTarget."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from kanibako.targets.base import AgentInstall
from kanibako_target_codex import CodexTarget


class TestProperties:
    def test_name(self):
        assert CodexTarget().name == "codex"

    def test_display_name(self):
        assert CodexTarget().display_name == "Codex CLI"


class TestDetect:
    def test_found_with_npm_root(self, tmp_path):
        """Detect finds the npm package root by walking up."""
        # Simulate: /some/node_modules/codex/bin/codex-cli
        pkg_root = tmp_path / "node_modules" / "codex"
        pkg_root.mkdir(parents=True)
        (pkg_root / "package.json").write_text('{"name": "codex"}')
        bin_dir = pkg_root / "bin"
        bin_dir.mkdir()
        binary = bin_dir / "codex-cli"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)

        symlink = tmp_path / "codex-link"
        symlink.symlink_to(binary)

        with patch("shutil.which", return_value=str(symlink)):
            result = CodexTarget().detect()

        assert result is not None
        assert result.name == "codex"
        assert result.binary == symlink
        assert result.install_dir == pkg_root

    def test_found_fallback_no_package_json(self, tmp_path):
        """Falls back to binary parent when no npm root found."""
        binary = tmp_path / "usr" / "local" / "bin" / "codex"
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)

        with patch("shutil.which", return_value=str(binary)):
            result = CodexTarget().detect()

        assert result is not None
        assert result.install_dir == binary.resolve().parent

    def test_not_found(self):
        with patch("shutil.which", return_value=None):
            assert CodexTarget().detect() is None


class TestBinaryMounts:
    def test_mounts_install_dir_and_binary(self):
        install = AgentInstall(
            name="codex",
            binary=Path("/usr/local/bin/codex"),
            install_dir=Path("/usr/local/lib/node_modules/codex"),
        )
        mounts = CodexTarget().binary_mounts(install)
        assert len(mounts) == 2
        assert mounts[0].source == Path("/usr/local/lib/node_modules/codex")
        assert mounts[0].destination == "/home/agent/.local/share/codex"
        assert mounts[0].options == "ro"
        assert mounts[1].source == Path("/usr/local/bin/codex")
        assert mounts[1].destination == "/home/agent/.local/bin/codex"
        assert mounts[1].options == "ro"


class TestInitHome:
    def test_creates_codex_dir(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        fake_host = tmp_path / "fake_host"
        fake_host.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        CodexTarget().init_home(home)
        assert (home / ".codex").is_dir()

    def test_copies_host_config(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        fake_host = tmp_path / "fake_host"
        (fake_host / ".codex").mkdir(parents=True)
        config = {"apiKey": "sk-test"}
        (fake_host / ".codex" / "config.json").write_text(json.dumps(config))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        CodexTarget().init_home(home)
        result = json.loads((home / ".codex" / "config.json").read_text())
        assert result["apiKey"] == "sk-test"

    def test_does_not_overwrite_existing(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        (home / ".codex").mkdir(parents=True)
        (home / ".codex" / "config.json").write_text('{"existing": true}')

        fake_host = tmp_path / "fake_host"
        (fake_host / ".codex").mkdir(parents=True)
        (fake_host / ".codex" / "config.json").write_text('{"new": true}')
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        CodexTarget().init_home(home)
        result = json.loads((home / ".codex" / "config.json").read_text())
        assert result == {"existing": True}


class TestRefreshCredentials:
    def test_copies_when_project_missing(self, tmp_path, monkeypatch):
        fake_host = tmp_path / "fake_host"
        (fake_host / ".codex").mkdir(parents=True)
        (fake_host / ".codex" / "config.json").write_text('{"key": "val"}')
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        home = tmp_path / "home"
        home.mkdir()
        CodexTarget().refresh_credentials(home)

        assert (home / ".codex" / "config.json").is_file()

    def test_copies_when_host_is_newer(self, tmp_path, monkeypatch):
        fake_host = tmp_path / "fake_host"
        (fake_host / ".codex").mkdir(parents=True)

        home = tmp_path / "home"
        (home / ".codex").mkdir(parents=True)
        (home / ".codex" / "config.json").write_text('{"old": true}')

        # Ensure host file has a later mtime
        time.sleep(0.05)
        (fake_host / ".codex" / "config.json").write_text('{"new": true}')
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        CodexTarget().refresh_credentials(home)
        result = json.loads((home / ".codex" / "config.json").read_text())
        assert result == {"new": True}

    def test_skips_when_host_missing(self, tmp_path, monkeypatch):
        fake_host = tmp_path / "fake_host"
        fake_host.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        home = tmp_path / "home"
        home.mkdir()
        CodexTarget().refresh_credentials(home)
        assert not (home / ".codex" / "config.json").exists()


class TestWritebackCredentials:
    def test_copies_when_host_missing(self, tmp_path, monkeypatch):
        fake_host = tmp_path / "fake_host"
        fake_host.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        home = tmp_path / "home"
        (home / ".codex").mkdir(parents=True)
        (home / ".codex" / "config.json").write_text('{"token": "abc"}')

        CodexTarget().writeback_credentials(home)
        assert (fake_host / ".codex" / "config.json").is_file()

    def test_skips_when_project_missing(self, tmp_path, monkeypatch):
        fake_host = tmp_path / "fake_host"
        fake_host.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        home = tmp_path / "home"
        home.mkdir()
        CodexTarget().writeback_credentials(home)
        assert not (fake_host / ".codex").exists()


class TestBuildCliArgs:
    def _build(self, **overrides):
        defaults = dict(
            safe_mode=False, resume_mode=False,
            new_session=False, is_new_project=False,
            extra_args=[],
        )
        defaults.update(overrides)
        return CodexTarget().build_cli_args(**defaults)

    def test_default_full_auto(self):
        args = self._build()
        assert "--full-auto" in args

    def test_safe_mode_no_full_auto(self):
        args = self._build(safe_mode=True)
        assert "--full-auto" not in args

    def test_extra_args_passed_through(self):
        args = self._build(extra_args=["--model", "o3"])
        assert "--model" in args
        assert "o3" in args
