"""Tests for clodbox.cli."""

from __future__ import annotations

import pytest

from clodbox.cli import build_parser


class TestParser:
    def test_version(self, capsys):
        from clodbox.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out

    def test_start_default(self):
        parser = build_parser()
        args = parser.parse_args(["start"])
        assert args.command == "start"

    def test_start_with_flags(self):
        parser = build_parser()
        args = parser.parse_args(["start", "-N", "-S", "-i", "my-image:v1"])
        assert args.new is True
        assert args.safe is True
        assert args.image == "my-image:v1"

    def test_shell_command(self):
        parser = build_parser()
        args = parser.parse_args(["shell"])
        assert args.command == "shell"

    def test_resume_command(self):
        parser = build_parser()
        args = parser.parse_args(["resume", "-S"])
        assert args.command == "resume"
        assert args.safe is True

    def test_config_get(self):
        parser = build_parser()
        args = parser.parse_args(["config", "image"])
        assert args.command == "config"
        assert args.key == "image"
        assert args.value is None

    def test_config_set(self):
        parser = build_parser()
        args = parser.parse_args(["config", "image", "new-image:v2"])
        assert args.key == "image"
        assert args.value == "new-image:v2"

    def test_config_show(self):
        parser = build_parser()
        args = parser.parse_args(["config", "--show"])
        assert args.command == "config"
        assert args.show is True
        assert args.key is None

    def test_config_show_short(self):
        parser = build_parser()
        args = parser.parse_args(["config", "-s"])
        assert args.show is True

    def test_config_clear(self):
        parser = build_parser()
        args = parser.parse_args(["config", "--clear"])
        assert args.command == "config"
        assert args.clear is True
        assert args.key is None

    def test_archive_command(self):
        parser = build_parser()
        args = parser.parse_args(["archive", "/tmp/project", "out.txz"])
        assert args.command == "archive"
        assert args.path == "/tmp/project"
        assert args.file == "out.txz"

    def test_archive_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            ["archive", "/tmp/proj", "--allow-uncommitted", "--allow-unpushed"]
        )
        assert args.allow_uncommitted is True
        assert args.allow_unpushed is True

    def test_archive_all(self):
        parser = build_parser()
        args = parser.parse_args(["archive", "--all"])
        assert args.all_projects is True
        assert args.path is None

    def test_purge_command(self):
        parser = build_parser()
        args = parser.parse_args(["purge", "/tmp/project", "--force"])
        assert args.command == "purge"
        assert args.force is True

    def test_purge_all(self):
        parser = build_parser()
        args = parser.parse_args(["purge", "--all"])
        assert args.all_projects is True
        assert args.path is None

    def test_restore_command(self):
        parser = build_parser()
        args = parser.parse_args(["restore", "/tmp/project", "archive.txz"])
        assert args.command == "restore"
        assert args.path == "/tmp/project"
        assert args.file == "archive.txz"

    def test_restore_all(self):
        parser = build_parser()
        args = parser.parse_args(["restore", "--all"])
        assert args.all_archives is True
        assert args.path is None

    def test_image_command(self):
        parser = build_parser()
        args = parser.parse_args(["image"])
        assert args.command == "image"

    def test_image_list(self):
        parser = build_parser()
        args = parser.parse_args(["image", "list"])
        assert args.command == "image"
        assert args.image_command == "list"

    def test_image_rebuild(self):
        parser = build_parser()
        args = parser.parse_args(["image", "rebuild"])
        assert args.command == "image"
        assert args.image_command == "rebuild"
        assert args.image is None
        assert args.all_images is False

    def test_image_rebuild_specific(self):
        parser = build_parser()
        args = parser.parse_args(["image", "rebuild", "clodbox-base:latest"])
        assert args.image == "clodbox-base:latest"

    def test_image_rebuild_all(self):
        parser = build_parser()
        args = parser.parse_args(["image", "rebuild", "--all"])
        assert args.all_images is True

    def test_setup_command(self):
        parser = build_parser()
        args = parser.parse_args(["setup"])
        assert args.command == "setup"

    def test_remove_command(self):
        parser = build_parser()
        args = parser.parse_args(["remove"])
        assert args.command == "remove"

    def test_refresh_creds_command(self):
        parser = build_parser()
        args = parser.parse_args(["refresh-creds"])
        assert args.command == "refresh-creds"

    def test_stop_command(self):
        parser = build_parser()
        args = parser.parse_args(["stop"])
        assert args.command == "stop"
        assert args.path is None
        assert args.all_containers is False

    def test_stop_with_path(self):
        parser = build_parser()
        args = parser.parse_args(["stop", "/tmp/myproject"])
        assert args.command == "stop"
        assert args.path == "/tmp/myproject"

    def test_stop_all(self):
        parser = build_parser()
        args = parser.parse_args(["stop", "--all"])
        assert args.command == "stop"
        assert args.all_containers is True

    def test_start_with_agent_args(self):
        parser = build_parser()
        args = parser.parse_args(["start", "--", "--some-flag", "arg"])
        assert args.agent_args == ["--", "--some-flag", "arg"]
