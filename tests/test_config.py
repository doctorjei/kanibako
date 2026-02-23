"""Tests for kanibako.config."""

from __future__ import annotations



from kanibako.config import (
    KanibakoConfig,
    _flatten_toml,
    config_file_path,
    load_config,
    load_merged_config,
    migrate_config,
    read_project_meta,
    write_global_config,
    write_project_config,
    write_project_meta,
)


class TestLoadConfig:
    def test_defaults(self, tmp_path):
        cfg = load_config(tmp_path / "nonexistent.toml")
        assert cfg.container_image == "ghcr.io/doctorjei/kanibako-base:latest"
        assert cfg.paths_boxes == "boxes"

    def test_round_trip(self, tmp_path):
        path = tmp_path / "test.toml"
        cfg = KanibakoConfig(container_image="custom:latest")
        write_global_config(path, cfg)
        loaded = load_config(path)
        assert loaded.container_image == "custom:latest"
        assert loaded.paths_data_path == ""

    def test_loads_old_field_names_via_aliases(self, tmp_path):
        """Old TOML files with paths_relative_std_path / paths_settings_path still load."""
        path = tmp_path / "old.toml"
        path.write_text(
            '[paths]\nrelative_std_path = "kanibako"\nsettings_path = "settings"\n'
            '[container]\nimage = "old:v1"\n'
        )
        cfg = load_config(path)
        assert cfg.paths_data_path == "kanibako"
        assert cfg.paths_boxes == "settings"
        assert cfg.container_image == "old:v1"


class TestMergedConfig:
    def test_project_overrides_global(self, tmp_path):
        global_path = tmp_path / "global.toml"
        project_path = tmp_path / "project.toml"

        write_global_config(global_path)
        write_project_config(project_path, "my-image:v2")

        merged = load_merged_config(global_path, project_path)
        assert merged.container_image == "my-image:v2"

    def test_cli_overrides_all(self, tmp_path):
        global_path = tmp_path / "global.toml"
        project_path = tmp_path / "project.toml"

        write_global_config(global_path)
        write_project_config(project_path, "my-image:v2")

        merged = load_merged_config(
            global_path,
            project_path,
            cli_overrides={"container_image": "cli-image:v3"},
        )
        assert merged.container_image == "cli-image:v3"


class TestFlattenToml:
    def test_nested_dict(self):
        data = {"paths": {"boxes": "x", "shell": "y"}}
        flat = _flatten_toml(data)
        assert flat == {"paths_boxes": "x", "paths_shell": "y"}

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": "deep"}}}
        flat = _flatten_toml(data)
        assert flat == {"a_b_c": "deep"}

    def test_flat_input(self):
        data = {"key": "val"}
        flat = _flatten_toml(data)
        assert flat == {"key": "val"}


class TestWriteProjectConfig:
    def test_creates_new(self, tmp_path):
        path = tmp_path / "project.toml"
        write_project_config(path, "new-image:latest")
        cfg = load_config(path)
        assert cfg.container_image == "new-image:latest"

    def test_updates_existing(self, tmp_path):
        path = tmp_path / "project.toml"
        write_project_config(path, "first:latest")
        write_project_config(path, "second:latest")
        cfg = load_config(path)
        assert cfg.container_image == "second:latest"

    def test_update_existing_image(self, tmp_path):
        p = tmp_path / "project.toml"
        write_project_config(p, "img:v1")
        assert 'image = "img:v1"' in p.read_text()
        write_project_config(p, "img:v2")
        text = p.read_text()
        assert 'image = "img:v2"' in text
        assert "img:v1" not in text

    def test_add_image_to_container_section(self, tmp_path):
        p = tmp_path / "project.toml"
        p.write_text("[container]\n# empty section\n")
        write_project_config(p, "new:img")
        text = p.read_text()
        assert 'image = "new:img"' in text

    def test_create_new_file(self, tmp_path):
        p = tmp_path / "sub" / "project.toml"
        write_project_config(p, "fresh:v1")
        assert p.exists()
        assert "[container]" in p.read_text()
        assert 'image = "fresh:v1"' in p.read_text()


class TestProjectMeta:
    """Tests for write_project_meta / read_project_meta."""

    def test_write_and_read(self, tmp_path):
        toml_path = tmp_path / "project.toml"
        write_project_meta(
            toml_path,
            mode="account_centric",
            layout="default",
            workspace="/home/user/myproject",
            shell="/data/kanibako/settings/abc/shell",
            vault_ro="/home/user/myproject/vault/share-ro",
            vault_rw="/home/user/myproject/vault/share-rw",
        )
        assert toml_path.is_file()

        meta = read_project_meta(toml_path)
        assert meta is not None
        assert meta["mode"] == "account_centric"
        assert meta["workspace"] == "/home/user/myproject"
        assert meta["shell"] == "/data/kanibako/settings/abc/shell"
        assert meta["vault_ro"] == "/home/user/myproject/vault/share-ro"
        assert meta["vault_rw"] == "/home/user/myproject/vault/share-rw"

    def test_read_missing_file(self, tmp_path):
        meta = read_project_meta(tmp_path / "nonexistent.toml")
        assert meta is None

    def test_read_no_project_section(self, tmp_path):
        toml_path = tmp_path / "project.toml"
        toml_path.write_text('[container]\nimage = "foo"\n')
        meta = read_project_meta(toml_path)
        assert meta is None

    def test_preserves_existing_sections(self, tmp_path):
        toml_path = tmp_path / "project.toml"
        toml_path.write_text('[container]\nimage = "custom:v1"\n')

        write_project_meta(
            toml_path,
            mode="decentralized",
            layout="default",
            workspace="/tmp/proj",
            shell="/tmp/proj/.kanibako/shell",
            vault_ro="/tmp/proj/vault/share-ro",
            vault_rw="/tmp/proj/vault/share-rw",
        )

        # Container section preserved
        cfg = load_config(toml_path)
        assert cfg.container_image == "custom:v1"

        # Metadata also present
        meta = read_project_meta(toml_path)
        assert meta["mode"] == "decentralized"

    def test_overwrite_existing_meta(self, tmp_path):
        toml_path = tmp_path / "project.toml"
        write_project_meta(
            toml_path,
            mode="account_centric",
            layout="default",
            workspace="/old",
            shell="/old/shell",
            vault_ro="/old/vault/ro",
            vault_rw="/old/vault/rw",
        )
        write_project_meta(
            toml_path,
            mode="workset",
            layout="default",
            workspace="/new",
            shell="/new/shell",
            vault_ro="/new/vault/ro",
            vault_rw="/new/vault/rw",
        )

        meta = read_project_meta(toml_path)
        assert meta["mode"] == "workset"
        assert meta["workspace"] == "/new"


class TestConfigFilePath:
    def test_returns_new_path_when_neither_exists(self, tmp_path):
        result = config_file_path(tmp_path)
        assert result == tmp_path / "kanibako.toml"

    def test_returns_new_path_when_new_exists(self, tmp_path):
        new = tmp_path / "kanibako.toml"
        new.write_text("[paths]\n")
        result = config_file_path(tmp_path)
        assert result == new

    def test_returns_old_path_when_only_old_exists(self, tmp_path):
        old = tmp_path / "kanibako" / "kanibako.toml"
        old.parent.mkdir()
        old.write_text("[paths]\n")
        result = config_file_path(tmp_path)
        assert result == old

    def test_prefers_new_path_over_old(self, tmp_path):
        new = tmp_path / "kanibako.toml"
        new.write_text("[paths]\n")
        old = tmp_path / "kanibako" / "kanibako.toml"
        old.parent.mkdir()
        old.write_text("[paths]\n")
        result = config_file_path(tmp_path)
        assert result == new


class TestMigrateConfig:
    def test_migrates_old_to_new(self, tmp_path):
        old = tmp_path / "kanibako" / "kanibako.toml"
        old.parent.mkdir()
        old.write_text('[paths]\nboxes = "boxes"\n')

        result = migrate_config(tmp_path)
        new = tmp_path / "kanibako.toml"
        assert result == new
        assert new.exists()
        assert not old.exists()
        assert "boxes" in new.read_text()

    def test_no_op_when_new_exists(self, tmp_path):
        new = tmp_path / "kanibako.toml"
        new.write_text('[paths]\nboxes = "new"\n')
        old = tmp_path / "kanibako" / "kanibako.toml"
        old.parent.mkdir()
        old.write_text('[paths]\nboxes = "old"\n')

        result = migrate_config(tmp_path)
        assert result == new
        assert "new" in new.read_text()
        assert old.exists()  # old not removed

    def test_no_op_when_neither_exists(self, tmp_path):
        result = migrate_config(tmp_path)
        assert result == tmp_path / "kanibako.toml"

    def test_removes_empty_old_dir(self, tmp_path):
        old = tmp_path / "kanibako" / "kanibako.toml"
        old.parent.mkdir()
        old.write_text("[paths]\n")

        migrate_config(tmp_path)
        assert not old.parent.exists()

    def test_keeps_old_dir_if_not_empty(self, tmp_path):
        old_dir = tmp_path / "kanibako"
        old_dir.mkdir()
        old = old_dir / "kanibako.toml"
        old.write_text("[paths]\n")
        (old_dir / "other.txt").write_text("keep me\n")

        migrate_config(tmp_path)
        assert old_dir.exists()
        assert (old_dir / "other.txt").exists()
