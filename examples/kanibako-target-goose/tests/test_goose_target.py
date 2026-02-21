"""Tests for GooseTarget."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from kanibako.targets.base import AgentInstall
from kanibako_target_goose import GooseTarget


class TestProperties:
    def test_name(self):
        assert GooseTarget().name == "goose"

    def test_display_name(self):
        assert GooseTarget().display_name == "Goose"


class TestDetect:
    def test_found(self, tmp_path):
        binary = tmp_path / "goose"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)

        with patch("shutil.which", return_value=str(binary)):
            result = GooseTarget().detect()

        assert result is not None
        assert result.name == "goose"
        assert result.binary == binary
        assert result.install_dir == binary.resolve().parent

    def test_not_found(self):
        with patch("shutil.which", return_value=None):
            assert GooseTarget().detect() is None


class TestBinaryMounts:
    def test_single_binary_mount(self, tmp_path):
        binary = tmp_path / "goose"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)

        install = AgentInstall(
            name="goose",
            binary=binary,
            install_dir=tmp_path,
        )
        mounts = GooseTarget().binary_mounts(install)
        assert len(mounts) == 1
        assert mounts[0].source == binary.resolve()
        assert mounts[0].destination == "/home/agent/.local/bin/goose"
        assert mounts[0].options == "ro"


class TestInitHome:
    def test_creates_config_dir(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        fake_host = tmp_path / "fake_host"
        fake_host.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        GooseTarget().init_home(home)
        assert (home / ".config" / "goose").is_dir()

    def test_copies_filtered_config(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()

        fake_host = tmp_path / "fake_host"
        host_config_dir = fake_host / ".config" / "goose"
        host_config_dir.mkdir(parents=True)
        host_data = {
            "provider": "anthropic",
            "model": "claude-4",
            "extensions": ["web"],
            "GOOSE_API_KEY": "secret-key",
            "unknown_field": "dropped",
        }
        (host_config_dir / "config.json").write_text(json.dumps(host_data))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        GooseTarget().init_home(home)

        result = json.loads((home / ".config" / "goose" / "config.json").read_text())
        assert result["provider"] == "anthropic"
        assert result["model"] == "claude-4"
        assert result["extensions"] == ["web"]
        # Credentials and unknown keys are excluded
        assert "GOOSE_API_KEY" not in result
        assert "unknown_field" not in result

    def test_idempotent(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        config_dir = home / ".config" / "goose"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"provider": "existing"}')

        fake_host = tmp_path / "fake_host"
        host_config_dir = fake_host / ".config" / "goose"
        host_config_dir.mkdir(parents=True)
        (host_config_dir / "config.json").write_text('{"provider": "new"}')
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        GooseTarget().init_home(home)

        result = json.loads((config_dir / "config.json").read_text())
        assert result["provider"] == "existing"  # Not overwritten


class TestRefreshCredentials:
    def test_merges_credentials(self, tmp_path, monkeypatch):
        fake_host = tmp_path / "fake_host"
        host_config_dir = fake_host / ".config" / "goose"
        host_config_dir.mkdir(parents=True)
        host_data = {
            "provider": "openai",
            "GOOSE_API_KEY": "host-key",
            "OPENAI_API_KEY": "openai-key",
        }
        (host_config_dir / "config.json").write_text(json.dumps(host_data))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        home = tmp_path / "home"
        config_dir = home / ".config" / "goose"
        config_dir.mkdir(parents=True)
        project_data = {"provider": "anthropic", "model": "claude-4"}
        (config_dir / "config.json").write_text(json.dumps(project_data))

        GooseTarget().refresh_credentials(home)

        result = json.loads((config_dir / "config.json").read_text())
        assert result["provider"] == "anthropic"  # Preserved
        assert result["model"] == "claude-4"  # Preserved
        assert result["GOOSE_API_KEY"] == "host-key"  # Merged
        assert result["OPENAI_API_KEY"] == "openai-key"  # Merged

    def test_noop_when_no_host_creds(self, tmp_path, monkeypatch):
        fake_host = tmp_path / "fake_host"
        host_config_dir = fake_host / ".config" / "goose"
        host_config_dir.mkdir(parents=True)
        (host_config_dir / "config.json").write_text('{"provider": "openai"}')
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        home = tmp_path / "home"
        config_dir = home / ".config" / "goose"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"model": "gpt-4"}')

        GooseTarget().refresh_credentials(home)

        result = json.loads((config_dir / "config.json").read_text())
        assert result == {"model": "gpt-4"}  # Unchanged

    def test_noop_when_no_host_config(self, tmp_path, monkeypatch):
        fake_host = tmp_path / "fake_host"
        fake_host.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        home = tmp_path / "home"
        home.mkdir()
        GooseTarget().refresh_credentials(home)


class TestWritebackCredentials:
    def test_writes_back_credentials(self, tmp_path, monkeypatch):
        fake_host = tmp_path / "fake_host"
        host_config_dir = fake_host / ".config" / "goose"
        host_config_dir.mkdir(parents=True)
        (host_config_dir / "config.json").write_text('{"provider": "openai"}')
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        home = tmp_path / "home"
        config_dir = home / ".config" / "goose"
        config_dir.mkdir(parents=True)
        project_data = {
            "provider": "anthropic",
            "GOOSE_API_KEY": "refreshed-key",
        }
        (config_dir / "config.json").write_text(json.dumps(project_data))

        GooseTarget().writeback_credentials(home)

        result = json.loads((host_config_dir / "config.json").read_text())
        assert result["provider"] == "openai"  # Host value preserved
        assert result["GOOSE_API_KEY"] == "refreshed-key"  # Written back

    def test_noop_when_no_project_creds(self, tmp_path, monkeypatch):
        fake_host = tmp_path / "fake_host"
        host_config_dir = fake_host / ".config" / "goose"
        host_config_dir.mkdir(parents=True)
        (host_config_dir / "config.json").write_text('{"provider": "openai"}')
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        home = tmp_path / "home"
        config_dir = home / ".config" / "goose"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"provider": "anthropic"}')

        GooseTarget().writeback_credentials(home)

        result = json.loads((host_config_dir / "config.json").read_text())
        assert result == {"provider": "openai"}  # Unchanged

    def test_noop_when_no_project_config(self, tmp_path, monkeypatch):
        fake_host = tmp_path / "fake_host"
        fake_host.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_host))

        home = tmp_path / "home"
        home.mkdir()
        GooseTarget().writeback_credentials(home)


class TestBuildCliArgs:
    def _build(self, **overrides):
        defaults = dict(
            safe_mode=False, resume_mode=False,
            new_session=False, is_new_project=False,
            extra_args=[],
        )
        defaults.update(overrides)
        return GooseTarget().build_cli_args(**defaults)

    def test_default_session_start_approve(self):
        args = self._build()
        assert args[:2] == ["session", "start"]
        assert "--approve-all" in args

    def test_safe_mode_no_approve(self):
        args = self._build(safe_mode=True)
        assert args[:2] == ["session", "start"]
        assert "--approve-all" not in args

    def test_resume_mode(self):
        args = self._build(resume_mode=True)
        assert args[:2] == ["session", "resume"]
        assert "--approve-all" in args

    def test_resume_safe(self):
        args = self._build(resume_mode=True, safe_mode=True)
        assert args[:2] == ["session", "resume"]
        assert "--approve-all" not in args

    def test_extra_args_passed_through(self):
        args = self._build(extra_args=["--verbose", "--no-color"])
        assert "--verbose" in args
        assert "--no-color" in args
