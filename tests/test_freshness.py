"""Tests for kanibako.freshness: digest comparison, caching, exception swallowing."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from kanibako.freshness import check_image_freshness, _cached_remote_digest


class TestCheckImageFreshness:
    def test_fresh_image_no_warning(self, tmp_path, capsys):
        """Same digest → no note printed."""
        runtime = MagicMock()
        runtime.get_local_digest.return_value = "sha256:abc"

        with patch("kanibako.freshness.get_remote_digest", return_value="sha256:abc"):
            check_image_freshness(runtime, "img:latest", tmp_path)

        assert "newer version" not in capsys.readouterr().err

    def test_stale_image_prints_warning(self, tmp_path, capsys):
        """Different digest → warning on stderr."""
        runtime = MagicMock()
        runtime.get_local_digest.return_value = "sha256:old"

        with patch("kanibako.freshness.get_remote_digest", return_value="sha256:new"):
            check_image_freshness(runtime, "img:latest", tmp_path)

        assert "newer version" in capsys.readouterr().err

    def test_offline_silent_skip(self, tmp_path, capsys):
        """Remote digest None → no crash, no warning."""
        runtime = MagicMock()
        runtime.get_local_digest.return_value = "sha256:abc"

        with patch("kanibako.freshness.get_remote_digest", return_value=None):
            check_image_freshness(runtime, "img:latest", tmp_path)

        assert "newer version" not in capsys.readouterr().err

    def test_local_digest_none_skips(self, tmp_path, capsys):
        """No local digest → no remote query, no warning."""
        runtime = MagicMock()
        runtime.get_local_digest.return_value = None

        with patch("kanibako.freshness.get_remote_digest") as m:
            check_image_freshness(runtime, "img:latest", tmp_path)
            m.assert_not_called()

    def test_exception_swallowed(self, tmp_path, capsys):
        """Any exception is silently swallowed."""
        runtime = MagicMock()
        runtime.get_local_digest.side_effect = RuntimeError("boom")

        # Should not raise
        check_image_freshness(runtime, "img:latest", tmp_path)
        assert capsys.readouterr().err == ""


class TestCachedRemoteDigest:
    def test_cache_miss(self, tmp_path):
        """First call fetches from registry and writes cache."""
        with patch("kanibako.freshness.get_remote_digest", return_value="sha256:new") as m:
            result = _cached_remote_digest("img:latest", tmp_path)
        assert result == "sha256:new"
        m.assert_called_once()

        # Verify cache was written
        cache = json.loads((tmp_path / "digest-cache.json").read_text())
        assert cache["img:latest"]["digest"] == "sha256:new"

    def test_cache_hit(self, tmp_path):
        """Within TTL, returns cached value without network call."""
        cache = {"img:latest": {"digest": "sha256:cached", "ts": time.time()}}
        (tmp_path / "digest-cache.json").write_text(json.dumps(cache))

        with patch("kanibako.freshness.get_remote_digest") as m:
            result = _cached_remote_digest("img:latest", tmp_path)
        assert result == "sha256:cached"
        m.assert_not_called()

    def test_cache_expired(self, tmp_path):
        """Expired cache triggers a new fetch."""
        cache = {"img:latest": {"digest": "sha256:old", "ts": time.time() - 100000}}
        (tmp_path / "digest-cache.json").write_text(json.dumps(cache))

        with patch("kanibako.freshness.get_remote_digest", return_value="sha256:fresh") as m:
            result = _cached_remote_digest("img:latest", tmp_path)
        assert result == "sha256:fresh"
        m.assert_called_once()

    def test_corrupt_cache_file(self, tmp_path):
        """Corrupt cache file is handled gracefully."""
        (tmp_path / "digest-cache.json").write_text("not json!")

        with patch("kanibako.freshness.get_remote_digest", return_value="sha256:ok"):
            result = _cached_remote_digest("img:latest", tmp_path)
        assert result == "sha256:ok"
