"""OCI Distribution API client for querying remote image digests (stdlib only)."""

from __future__ import annotations

import json
import urllib.request
import urllib.error

_TIMEOUT = 5


def get_remote_digest(image: str) -> str | None:
    """Return the remote manifest digest for *image*, or None on any failure."""
    try:
        registry, repo, tag = _parse_image_ref(image)
        token = _get_anonymous_token(registry, repo)
        return _fetch_manifest_digest(registry, repo, tag, token)
    except Exception:
        return None


def _parse_image_ref(image: str) -> tuple[str, str, str]:
    """Split ``registry/owner/name:tag`` into ``(registry, owner/name, tag)``.

    Raises ``ValueError`` if the format is unrecognised.
    """
    # Strip tag
    if ":" in image.rsplit("/", 1)[-1]:
        ref, tag = image.rsplit(":", 1)
    else:
        ref, tag = image, "latest"

    parts = ref.split("/")
    if len(parts) < 3:
        raise ValueError(f"Cannot parse image reference: {image}")
    registry = parts[0]
    repo = "/".join(parts[1:])
    return registry, repo, tag


def _get_anonymous_token(registry: str, repo: str) -> str | None:
    """Obtain a bearer token for anonymous pulls (GHCR only for now)."""
    if registry != "ghcr.io":
        return None

    url = f"https://ghcr.io/token?scope=repository:{repo}:pull"
    req = urllib.request.Request(url, headers={"User-Agent": "kanibako"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read())
    return data.get("token")


def _fetch_manifest_digest(
    registry: str, repo: str, tag: str, token: str | None,
) -> str | None:
    """HEAD the manifest to read ``Docker-Content-Digest``."""
    url = f"https://{registry}/v2/{repo}/manifests/{tag}"
    headers: dict[str, str] = {
        "User-Agent": "kanibako",
        "Accept": (
            "application/vnd.docker.distribution.manifest.v2+json, "
            "application/vnd.oci.image.index.v1+json"
        ),
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, method="HEAD", headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        digest = resp.headers.get("Docker-Content-Digest")
    return digest
