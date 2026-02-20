"""Extended tests for kanibako.credentials: malformed files, writeback, filter edge cases."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from kanibako.credentials import (
    filter_settings,
    refresh_central_to_project,
    writeback_project_to_central_and_host,
)


# ---------------------------------------------------------------------------
# refresh_central_to_project — error paths
# ---------------------------------------------------------------------------

class TestRefreshCentralToProjectErrors:
    def test_malformed_central_json(self, tmp_path):
        central = tmp_path / "central" / ".credentials.json"
        central.parent.mkdir(parents=True)
        central.write_text("{bad json!!")

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text(json.dumps({"claudeAiOauth": {"token": "old"}}))
        # Ensure central is newer
        os.utime(project, (0, 0))

        result = refresh_central_to_project(central, project)
        assert result is False
        # Project file unchanged
        data = json.loads(project.read_text())
        assert data["claudeAiOauth"]["token"] == "old"

    def test_empty_central_file(self, tmp_path):
        central = tmp_path / "central" / ".credentials.json"
        central.parent.mkdir(parents=True)
        central.write_text("")

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text(json.dumps({"claudeAiOauth": {"token": "old"}}))
        os.utime(project, (0, 0))

        result = refresh_central_to_project(central, project)
        assert result is False

    def test_missing_oauth_key(self, tmp_path):
        central = tmp_path / "central" / ".credentials.json"
        central.parent.mkdir(parents=True)
        central.write_text(json.dumps({"someOther": "data"}))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text(json.dumps({"claudeAiOauth": {"token": "old"}}))
        os.utime(project, (0, 0))

        result = refresh_central_to_project(central, project)
        assert result is False

    def test_malformed_project_json(self, tmp_path):
        """When project JSON is malformed, it gets replaced with fresh data."""
        central = tmp_path / "central" / ".credentials.json"
        central.parent.mkdir(parents=True)
        central.write_text(json.dumps({"claudeAiOauth": {"token": "new"}}))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text("{bad json")
        os.utime(project, (0, 0))

        result = refresh_central_to_project(central, project)
        assert result is True
        data = json.loads(project.read_text())
        assert data["claudeAiOauth"]["token"] == "new"

    def test_empty_project_file(self, tmp_path):
        central = tmp_path / "central" / ".credentials.json"
        central.parent.mkdir(parents=True)
        central.write_text(json.dumps({"claudeAiOauth": {"token": "new"}}))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text("")
        os.utime(project, (0, 0))

        result = refresh_central_to_project(central, project)
        assert result is True
        data = json.loads(project.read_text())
        assert data["claudeAiOauth"]["token"] == "new"

    def test_project_missing_wholesale_copy(self, tmp_path):
        """When project creds don't exist, central is copied wholesale."""
        central = tmp_path / "central" / ".credentials.json"
        central.parent.mkdir(parents=True)
        central.write_text(json.dumps({"claudeAiOauth": {"token": "x"}, "extra": True}))

        project = tmp_path / "project" / ".credentials.json"
        # project doesn't exist
        result = refresh_central_to_project(central, project)
        assert result is True
        assert project.exists()
        data = json.loads(project.read_text())
        assert data["claudeAiOauth"]["token"] == "x"
        assert data["extra"] is True


# ---------------------------------------------------------------------------
# writeback_project_to_central_and_host
# ---------------------------------------------------------------------------

class TestWriteback:
    def test_writeback_both_directions(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir(parents=True)
        project.write_text(json.dumps({"claudeAiOauth": {"token": "fresh"}}))

        central = tmp_path / "central" / ".credentials.json"
        central.parent.mkdir(parents=True)
        central.write_text(json.dumps({"claudeAiOauth": {"token": "stale"}}))
        os.utime(central, (0, 0))

        writeback_project_to_central_and_host(project, central)

        central_data = json.loads(central.read_text())
        assert central_data["claudeAiOauth"]["token"] == "fresh"

        host_creds = home / ".claude" / ".credentials.json"
        assert host_creds.exists()
        host_data = json.loads(host_creds.read_text())
        assert host_data["claudeAiOauth"]["token"] == "fresh"

    def test_writeback_noop_when_no_project_creds(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        project = tmp_path / "project" / ".credentials.json"
        central = tmp_path / "central" / ".credentials.json"
        central.parent.mkdir(parents=True)
        central.write_text(json.dumps({"claudeAiOauth": {"token": "untouched"}}))

        writeback_project_to_central_and_host(project, central)
        # central unchanged
        data = json.loads(central.read_text())
        assert data["claudeAiOauth"]["token"] == "untouched"


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
