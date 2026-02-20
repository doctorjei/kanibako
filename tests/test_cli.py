"""Tests for kanibako.cli."""

from __future__ import annotations

import pytest

from kanibako.cli import build_parser


class TestParser:
    def test_version(self, capsys):
        from kanibako import __version__
        from kanibako.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert __version__ in captured.out

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

    def test_box_command(self):
        parser = build_parser()
        args = parser.parse_args(["box"])
        assert args.command == "box"

    def test_box_list(self):
        parser = build_parser()
        args = parser.parse_args(["box", "list"])
        assert args.command == "box"
        assert args.box_command == "list"

    def test_box_archive_command(self):
        parser = build_parser()
        args = parser.parse_args(["box", "archive", "/tmp/project", "out.txz"])
        assert args.command == "box"
        assert args.box_command == "archive"
        assert args.path == "/tmp/project"
        assert args.file == "out.txz"

    def test_box_archive_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            ["box", "archive", "/tmp/proj", "--allow-uncommitted", "--allow-unpushed"]
        )
        assert args.allow_uncommitted is True
        assert args.allow_unpushed is True

    def test_box_archive_all(self):
        parser = build_parser()
        args = parser.parse_args(["box", "archive", "--all"])
        assert args.all_projects is True
        assert args.path is None

    def test_box_purge_command(self):
        parser = build_parser()
        args = parser.parse_args(["box", "purge", "/tmp/project", "--force"])
        assert args.command == "box"
        assert args.box_command == "purge"
        assert args.force is True

    def test_box_purge_all(self):
        parser = build_parser()
        args = parser.parse_args(["box", "purge", "--all"])
        assert args.all_projects is True
        assert args.path is None

    def test_box_restore_command(self):
        parser = build_parser()
        args = parser.parse_args(["box", "restore", "/tmp/project", "archive.txz"])
        assert args.command == "box"
        assert args.box_command == "restore"
        assert args.path == "/tmp/project"
        assert args.file == "archive.txz"

    def test_box_restore_all(self):
        parser = build_parser()
        args = parser.parse_args(["box", "restore", "--all"])
        assert args.all_archives is True
        assert args.path is None

    def test_box_migrate_command(self):
        parser = build_parser()
        args = parser.parse_args(["box", "migrate", "/old", "/new"])
        assert args.command == "box"
        assert args.box_command == "migrate"
        assert args.old_path == "/old"
        assert args.new_path == "/new"

    def test_box_migrate_defaults_new_path(self):
        parser = build_parser()
        args = parser.parse_args(["box", "migrate", "/old"])
        assert args.old_path == "/old"
        assert args.new_path is None

    def test_box_migrate_force(self):
        parser = build_parser()
        args = parser.parse_args(["box", "migrate", "/old", "--force"])
        assert args.force is True

    def test_box_duplicate_command(self):
        parser = build_parser()
        args = parser.parse_args(["box", "duplicate", "/src", "/dst"])
        assert args.command == "box"
        assert args.box_command == "duplicate"
        assert args.source_path == "/src"
        assert args.new_path == "/dst"
        assert args.bare is False
        assert args.force is False

    def test_box_duplicate_bare(self):
        parser = build_parser()
        args = parser.parse_args(["box", "duplicate", "/src", "/dst", "--bare"])
        assert args.bare is True

    def test_box_duplicate_force(self):
        parser = build_parser()
        args = parser.parse_args(["box", "duplicate", "/src", "/dst", "--force"])
        assert args.force is True

    def test_box_duplicate_bare_and_force(self):
        parser = build_parser()
        args = parser.parse_args(["box", "duplicate", "/src", "/dst", "--bare", "--force"])
        assert args.bare is True
        assert args.force is True

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
        args = parser.parse_args(["image", "rebuild", "kanibako-base:latest"])
        assert args.image == "kanibako-base:latest"

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

    def test_upgrade_command(self):
        parser = build_parser()
        args = parser.parse_args(["upgrade"])
        assert args.command == "upgrade"
        assert args.check is False

    def test_upgrade_check(self):
        parser = build_parser()
        args = parser.parse_args(["upgrade", "--check"])
        assert args.command == "upgrade"
        assert args.check is True

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
