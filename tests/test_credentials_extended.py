"""Extended tests for kanibako.credentials: malformed files, writeback, filter edge cases."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from kanibako.credentials import (
    filter_settings,
    refresh_host_to_project,
    writeback_project_to_host,
)


# ---------------------------------------------------------------------------
# refresh_host_to_project — error paths
# ---------------------------------------------------------------------------

class TestRefreshHostToProjectErrors:
    def test_malformed_host_json(self, tmp_path):
        host = tmp_path / "host" / ".credentials.json"
        host.parent.mkdir(parents=True)
        host.write_text("{bad json!!")

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text(json.dumps({"claudeAiOauth": {"token": "old"}}))
        # Ensure host is newer
        os.utime(project, (0, 0))

        result = refresh_host_to_project(host, project)
        assert result is False
        # Project file unchanged
        data = json.loads(project.read_text())
        assert data["claudeAiOauth"]["token"] == "old"

    def test_empty_host_file(self, tmp_path):
        host = tmp_path / "host" / ".credentials.json"
        host.parent.mkdir(parents=True)
        host.write_text("")

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text(json.dumps({"claudeAiOauth": {"token": "old"}}))
        os.utime(project, (0, 0))

        result = refresh_host_to_project(host, project)
        assert result is False

    def test_missing_oauth_key(self, tmp_path):
        host = tmp_path / "host" / ".credentials.json"
        host.parent.mkdir(parents=True)
        host.write_text(json.dumps({"someOther": "data"}))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text(json.dumps({"claudeAiOauth": {"token": "old"}}))
        os.utime(project, (0, 0))

        result = refresh_host_to_project(host, project)
        assert result is False

    def test_malformed_project_json(self, tmp_path):
        """When project JSON is malformed, it gets replaced with fresh data."""
        host = tmp_path / "host" / ".credentials.json"
        host.parent.mkdir(parents=True)
        host.write_text(json.dumps({"claudeAiOauth": {"token": "new"}}))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text("{bad json")
        os.utime(project, (0, 0))

        result = refresh_host_to_project(host, project)
        assert result is True
        data = json.loads(project.read_text())
        assert data["claudeAiOauth"]["token"] == "new"

    def test_empty_project_file(self, tmp_path):
        host = tmp_path / "host" / ".credentials.json"
        host.parent.mkdir(parents=True)
        host.write_text(json.dumps({"claudeAiOauth": {"token": "new"}}))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text("")
        os.utime(project, (0, 0))

        result = refresh_host_to_project(host, project)
        assert result is True
        data = json.loads(project.read_text())
        assert data["claudeAiOauth"]["token"] == "new"

    def test_project_missing_wholesale_copy(self, tmp_path):
        """When project creds don't exist, host is copied wholesale."""
        host = tmp_path / "host" / ".credentials.json"
        host.parent.mkdir(parents=True)
        host.write_text(json.dumps({"claudeAiOauth": {"token": "x"}, "extra": True}))

        project = tmp_path / "project" / ".credentials.json"
        # project doesn't exist
        result = refresh_host_to_project(host, project)
        assert result is True
        assert project.exists()
        data = json.loads(project.read_text())
        assert data["claudeAiOauth"]["token"] == "x"
        assert data["extra"] is True


# ---------------------------------------------------------------------------
# writeback_project_to_host
# ---------------------------------------------------------------------------

class TestWriteback:
    def test_writeback_to_host(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text(json.dumps({"claudeAiOauth": {"token": "fresh"}}))

        writeback_project_to_host(project)

        host_creds = home / ".claude" / ".credentials.json"
        assert host_creds.exists()
        host_data = json.loads(host_creds.read_text())
        assert host_data["claudeAiOauth"]["token"] == "fresh"

    def test_writeback_noop_when_no_project_creds(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        project = tmp_path / "project" / ".credentials.json"

        writeback_project_to_host(project)
        # No host creds created
        host_creds = home / ".claude" / ".credentials.json"
        assert not host_creds.exists()


# ---------------------------------------------------------------------------
# filter_settings edge cases
# ---------------------------------------------------------------------------

class TestFilterSettingsExtended:
    def test_bad_json_src(self, tmp_path):
        src = tmp_path / "src.json"
        src.write_text("{corrupt!")
        dst = tmp_path / "dst.json"
        filter_settings(src, dst)
        # dst should not be created when src is bad
        assert not dst.exists()

    def test_missing_keys(self, tmp_path):
        src = tmp_path / "src.json"
        src.write_text(json.dumps({"randomKey": 42}))
        dst = tmp_path / "dst.json"
        filter_settings(src, dst)
        data = json.loads(dst.read_text())
        # Only hasCompletedOnboarding (always True) should be present
        assert data == {"hasCompletedOnboarding": True}
