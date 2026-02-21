"""Tests for kanibako.credentials."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from kanibako.credentials import (
    filter_settings,
    refresh_host_to_project,
)


class TestRefreshHostToProject:
    def test_creates_project_from_host(self, tmp_path):
        host = tmp_path / "host" / ".credentials.json"
        host.parent.mkdir()
        host.write_text(json.dumps({"claudeAiOauth": {"token": "abc"}}))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir()

        assert refresh_host_to_project(host, project)
        data = json.loads(project.read_text())
        assert data["claudeAiOauth"]["token"] == "abc"

    def test_merges_oauth_key(self, tmp_path):
        host = tmp_path / "host" / ".credentials.json"
        host.parent.mkdir()
        host.write_text(json.dumps({"claudeAiOauth": {"token": "new"}}))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir()
        project.write_text(json.dumps({"claudeAiOauth": {"token": "old"}, "otherKey": True}))

        # Make host newer
        old_time = time.time() - 100
        os.utime(project, (old_time, old_time))

        assert refresh_host_to_project(host, project)
        data = json.loads(project.read_text())
        assert data["claudeAiOauth"]["token"] == "new"
        assert data["otherKey"] is True

    def test_skips_when_project_newer(self, tmp_path):
        host = tmp_path / "host" / ".credentials.json"
        host.parent.mkdir()
        host.write_text(json.dumps({"claudeAiOauth": {"token": "host"}}))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir()
        project.write_text(json.dumps({"claudeAiOauth": {"token": "project"}}))

        # Make host older
        old_time = time.time() - 100
        os.utime(host, (old_time, old_time))

        assert not refresh_host_to_project(host, project)
        data = json.loads(project.read_text())
        assert data["claudeAiOauth"]["token"] == "project"

    def test_missing_oauth_key_skips(self, tmp_path):
        host = tmp_path / "host" / ".credentials.json"
        host.parent.mkdir()
        host.write_text(json.dumps({"otherKey": True}))

        project = tmp_path / "project" / ".credentials.json"
        project.parent.mkdir()
        project.write_text(json.dumps({"claudeAiOauth": {"token": "old"}}))

        # Make host newer
        old_time = time.time() - 100
        os.utime(project, (old_time, old_time))

        assert not refresh_host_to_project(host, project)


class TestFilterSettings:
    def test_filters_keys(self, tmp_path):
        src = tmp_path / "source.json"
        dst = tmp_path / "dest.json"

        src.write_text(json.dumps({
            "oauthAccount": "acct",
            "hasCompletedOnboarding": False,
            "installMethod": "cli",
            "extraKey": "ignored",
        }))

        filter_settings(src, dst)
        data = json.loads(dst.read_text())
        assert data["oauthAccount"] == "acct"
        assert data["hasCompletedOnboarding"] is True  # Always set to True
        assert data["installMethod"] == "cli"
        assert "extraKey" not in data
