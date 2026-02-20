"""Extended tests for kanibako.commands.image: API responses, edge cases."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from kanibako.commands.image import _extract_ghcr_owner, _list_remote_packages


# ---------------------------------------------------------------------------
# _list_remote_packages
# ---------------------------------------------------------------------------

class TestListRemotePackages:
    def test_successful_api_response(self, capsys):
        response_data = [
            {"name": "kanibako-base"},
            {"name": "kanibako-jvm"},
            {"name": "unrelated-pkg"},
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("kanibako.commands.image.urllib.request.urlopen", return_value=mock_resp):
            _list_remote_packages("myowner")

        out = capsys.readouterr().out
        assert "ghcr.io/myowner/kanibako-base" in out
        assert "ghcr.io/myowner/kanibako-jvm" in out
        assert "unrelated-pkg" not in out

    def test_api_timeout(self, capsys):
        import urllib.error
        with patch(
            "kanibako.commands.image.urllib.request.urlopen",
            side_effect=urllib.error.URLError("timeout"),
        ):
            _list_remote_packages("owner")

        out = capsys.readouterr().out
        assert "could not reach" in out.lower()

    def test_empty_package_list(self, capsys):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps([]).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("kanibako.commands.image.urllib.request.urlopen", return_value=mock_resp):
            _list_remote_packages("owner")

        out = capsys.readouterr().out
        assert "no kanibako packages" in out.lower()

    def test_invalid_json_response(self, capsys):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("kanibako.commands.image.urllib.request.urlopen", return_value=mock_resp):
            _list_remote_packages("owner")

        out = capsys.readouterr().out
        assert "could not reach" in out.lower()


# ---------------------------------------------------------------------------
# _extract_ghcr_owner edge cases
# ---------------------------------------------------------------------------

class TestExtractGhcrOwnerExtended:
    def test_non_ghcr_image_returns_none(self):
        assert _extract_ghcr_owner("docker.io/library/ubuntu:latest") is None

    def test_ghcr_no_slash_after_owner(self):
        """ghcr.io/owner without a slash after owner returns None."""
        assert _extract_ghcr_owner("ghcr.io/justowner") is None

    def test_ghcr_with_nested_path(self):
        assert _extract_ghcr_owner("ghcr.io/org/repo/image:tag") == "org"
