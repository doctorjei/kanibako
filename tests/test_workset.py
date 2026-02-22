"""Tests for kanibako.workset -- working set data model and persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from kanibako.errors import WorksetError
from kanibako.workset import (
    Workset,
    WorksetProject,
    add_project,
    create_workset,
    delete_workset,
    list_worksets,
    load_workset,
    remove_project,
)


# ---------------------------------------------------------------------------
# create_workset
# ---------------------------------------------------------------------------

class TestCreateWorkset:
    def test_creates_directory_structure(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)

        assert ws.name == "my-set"
        assert ws.root == root.resolve()
        assert ws.root.is_dir()
        assert (ws.root / "kanibako").is_dir()
        assert (ws.root / "workspaces").is_dir()
        assert (ws.root / "vault").is_dir()
        assert ws.toml_path.is_file()

    def test_writes_workset_toml(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)

        text = ws.toml_path.read_text()
        assert 'name = "my-set"' in text
        assert "created = " in text

    def test_registers_globally(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        create_workset("my-set", root, std)

        registry = list_worksets(std)
        assert "my-set" in registry
        assert registry["my-set"] == root.resolve()

    def test_sets_created_timestamp(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)

        assert ws.created  # non-empty
        assert "T" in ws.created  # looks like ISO 8601

    def test_duplicate_name_raises(self, std, tmp_home):
        root1 = tmp_home / "worksets" / "set1"
        create_workset("same-name", root1, std)

        root2 = tmp_home / "worksets" / "set2"
        with pytest.raises(WorksetError, match="already registered"):
            create_workset("same-name", root2, std)

    def test_existing_root_raises(self, std, tmp_home):
        root = tmp_home / "worksets" / "existing"
        root.mkdir(parents=True)

        with pytest.raises(WorksetError, match="already exists"):
            create_workset("existing", root, std)

    def test_empty_name_raises(self, std, tmp_home):
        root = tmp_home / "worksets" / "empty-name"
        with pytest.raises(WorksetError, match="must not be empty"):
            create_workset("", root, std)


# ---------------------------------------------------------------------------
# load_workset
# ---------------------------------------------------------------------------

class TestLoadWorkset:
    def test_roundtrip(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)

        loaded = load_workset(root)
        assert loaded.name == ws.name
        assert loaded.root == ws.root
        assert loaded.created == ws.created
        assert loaded.projects == []

    def test_roundtrip_with_projects(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)
        add_project(ws, "proj-a", tmp_home / "project")

        loaded = load_workset(root)
        assert len(loaded.projects) == 1
        assert loaded.projects[0].name == "proj-a"

    def test_missing_root_raises(self, std, tmp_home):
        with pytest.raises(WorksetError, match="does not exist"):
            load_workset(tmp_home / "nonexistent")

    def test_missing_toml_raises(self, std, tmp_home):
        root = tmp_home / "worksets" / "no-toml"
        root.mkdir(parents=True)

        with pytest.raises(WorksetError, match="No workset.toml"):
            load_workset(root)

    def test_toml_without_name_raises(self, std, tmp_home):
        root = tmp_home / "worksets" / "bad-toml"
        root.mkdir(parents=True)
        (root / "workset.toml").write_text('created = "2026-01-01"\n')

        with pytest.raises(WorksetError, match="no 'name' key"):
            load_workset(root)


# ---------------------------------------------------------------------------
# list_worksets
# ---------------------------------------------------------------------------

class TestListWorksets:
    def test_empty_when_no_registry(self, std):
        assert list_worksets(std) == {}

    def test_lists_all_registered(self, std, tmp_home):
        r1 = tmp_home / "worksets" / "alpha"
        r2 = tmp_home / "worksets" / "beta"
        create_workset("alpha", r1, std)
        create_workset("beta", r2, std)

        registry = list_worksets(std)
        assert len(registry) == 2
        assert "alpha" in registry
        assert "beta" in registry


# ---------------------------------------------------------------------------
# delete_workset
# ---------------------------------------------------------------------------

class TestDeleteWorkset:
    def test_unregisters(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        create_workset("my-set", root, std)
        assert "my-set" in list_worksets(std)

        ret = delete_workset("my-set", std)
        assert ret == root.resolve()
        assert "my-set" not in list_worksets(std)

    def test_keeps_files_by_default(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        create_workset("my-set", root, std)

        delete_workset("my-set", std)
        assert root.resolve().is_dir()

    def test_removes_files_when_requested(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        create_workset("my-set", root, std)

        delete_workset("my-set", std, remove_files=True)
        assert not root.resolve().exists()

    def test_unknown_name_raises(self, std):
        with pytest.raises(WorksetError, match="not registered"):
            delete_workset("nope", std)


# ---------------------------------------------------------------------------
# add_project / remove_project
# ---------------------------------------------------------------------------

class TestAddProject:
    def test_creates_subdirectories(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)
        add_project(ws, "cool-app", tmp_home / "project")

        resolved = root.resolve()
        assert (resolved / "kanibako" / "cool-app").is_dir()
        assert (resolved / "workspaces" / "cool-app").is_dir()
        assert (resolved / "vault" / "cool-app" / "share-ro").is_dir()
        assert (resolved / "vault" / "cool-app" / "share-rw").is_dir()

    def test_persists_to_toml(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)
        add_project(ws, "cool-app", tmp_home / "project")

        loaded = load_workset(root)
        assert len(loaded.projects) == 1
        assert loaded.projects[0].name == "cool-app"
        assert loaded.projects[0].source_path == (tmp_home / "project").resolve()

    def test_duplicate_name_raises(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)
        add_project(ws, "dup", tmp_home / "project")

        with pytest.raises(WorksetError, match="already exists"):
            add_project(ws, "dup", tmp_home / "project")

    def test_multiple_projects(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)
        proj_a = tmp_home / "proj_a"
        proj_b = tmp_home / "proj_b"
        proj_a.mkdir()
        proj_b.mkdir()
        add_project(ws, "alpha", proj_a)
        add_project(ws, "beta", proj_b)

        loaded = load_workset(root)
        assert len(loaded.projects) == 2
        names = {p.name for p in loaded.projects}
        assert names == {"alpha", "beta"}


class TestRemoveProject:
    def test_removes_from_toml(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)
        add_project(ws, "proj", tmp_home / "project")
        assert len(ws.projects) == 1

        removed = remove_project(ws, "proj")
        assert removed.name == "proj"
        assert len(ws.projects) == 0

        loaded = load_workset(root)
        assert len(loaded.projects) == 0

    def test_keeps_files_by_default(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)
        add_project(ws, "proj", tmp_home / "project")

        remove_project(ws, "proj")
        resolved = root.resolve()
        assert (resolved / "kanibako" / "proj").is_dir()

    def test_removes_files_when_requested(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)
        add_project(ws, "proj", tmp_home / "project")

        remove_project(ws, "proj", remove_files=True)
        resolved = root.resolve()
        assert not (resolved / "kanibako" / "proj").exists()
        assert not (resolved / "workspaces" / "proj").exists()
        assert not (resolved / "vault" / "proj").exists()

    def test_unknown_project_raises(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)

        with pytest.raises(WorksetError, match="not found"):
            remove_project(ws, "nonexistent")


# ---------------------------------------------------------------------------
# Workset properties
# ---------------------------------------------------------------------------

class TestWorksetProperties:
    def test_convenience_paths(self, std, tmp_home):
        root = tmp_home / "worksets" / "my-set"
        ws = create_workset("my-set", root, std)

        resolved = root.resolve()
        assert ws.projects_dir == resolved / "kanibako"
        assert ws.workspaces_dir == resolved / "workspaces"
        assert ws.vault_dir == resolved / "vault"
        assert ws.toml_path == resolved / "workset.toml"
