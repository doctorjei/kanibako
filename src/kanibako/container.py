"""ContainerRuntime: detect podman/docker, pull/build/run images, list images."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from kanibako.containerfiles import get_containerfile
from kanibako.errors import ContainerError


@dataclass
class ClaudeInstall:
    """Information about a Claude Code installation."""

    binary: Path  # Host symlink (e.g., ~/.local/bin/claude); podman follows it on mount
    install_dir: Path  # Root of the Claude installation (e.g., ~/.local/share/claude)


def detect_claude_install() -> ClaudeInstall | None:
    """Detect Claude Code installation on the host.

    Resolves the ``claude`` symlink to find the real binary, then walks up
    the directory tree to locate the ``claude/`` installation root.  This
    is resilient to internal layout changes (e.g. a ``versions/`` sub-
    directory being added) — we always mount the whole ``claude/`` tree.
    """
    claude_path = shutil.which("claude")
    if not claude_path:
        return None

    binary = Path(claude_path)

    try:
        resolved = binary.resolve()
    except OSError:
        return None

    # Walk up from the resolved binary to find the 'claude' directory.
    install_dir = resolved.parent
    while install_dir.name != "claude" and install_dir != install_dir.parent:
        install_dir = install_dir.parent

    # Sanity check: if we hit the filesystem root without finding 'claude',
    # fall back to the immediate parent of the binary.
    if install_dir.name != "claude":
        install_dir = resolved.parent

    return ClaudeInstall(binary=binary, install_dir=install_dir)


# Map image name patterns to Containerfile suffixes.
_IMAGE_CONTAINERFILE_MAP = {
    "kanibako-base": "base",
    "kanibako:latest": "base",
    "kanibako-systems": "systems",
    "kanibako-jvm": "jvm",
    "kanibako-android": "android",
    "kanibako-ndk": "ndk",
    "kanibako-dotnet": "dotnet",
    "kanibako-behemoth": "behemoth",
}


class ContainerRuntime:
    """Wrapper around podman/docker CLI."""

    def __init__(self, command: str | None = None) -> None:
        if command:
            self.cmd = command
        else:
            self.cmd = self._detect()

    @staticmethod
    def _detect() -> str:
        env = os.environ.get("KANIBAKO_DOCKER_CMD")
        if env:
            return env
        for name in ("podman", "docker"):
            path = shutil.which(name)
            if path:
                return path
        raise ContainerError(
            "No container runtime found. Install podman or docker."
        )

    # ------------------------------------------------------------------
    # Image operations
    # ------------------------------------------------------------------

    def image_exists(self, image: str) -> bool:
        result = subprocess.run(
            [self.cmd, "image", "inspect", image],
            capture_output=True,
        )
        return result.returncode == 0

    def pull(self, image: str, *, quiet: bool = True) -> bool:
        """Pull *image* from registry. Returns True on success."""
        result = subprocess.run(
            [self.cmd, "pull", image],
            capture_output=quiet,
        )
        return result.returncode == 0

    def build(self, image: str, containerfile: Path, context: Path) -> None:
        """Build *image* from *containerfile*. Raises ContainerError on failure."""
        result = subprocess.run(
            [self.cmd, "build", "-t", image, "-f", str(containerfile), str(context)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ContainerError(
                f"Failed to build image {image}:\n{result.stderr}"
            )

    def rebuild(self, image: str, containerfile: Path, context: Path) -> int:
        """Rebuild *image* with --no-cache, streaming output. Returns exit code."""
        result = subprocess.run(
            [
                self.cmd, "build", "--no-cache",
                "-t", image, "-f", str(containerfile), str(context),
            ],
        )
        return result.returncode

    def guess_containerfile(self, image: str) -> str | None:
        """Return the Containerfile suffix for a known image pattern, or None."""
        return self._guess_containerfile(image)

    def ensure_image(self, image: str, containers_dir: Path) -> None:
        """Make sure *image* is available locally: inspect → pull → build fallback."""
        if self.image_exists(image):
            return

        print(
            f"Container image not found locally. Pulling {image}...",
            file=sys.stderr,
        )
        if self.pull(image):
            print("Image pulled successfully.", file=sys.stderr)
            return

        print("Pull failed. Attempting local build...", file=sys.stderr)
        suffix = self._guess_containerfile(image)
        if suffix is None:
            raise ContainerError(
                f"Container image not available and cannot determine Containerfile "
                f"for: {image}"
            )
        containerfile = get_containerfile(suffix, containers_dir)
        if containerfile is None:
            raise ContainerError(
                f"Container image not available and no local Containerfile found.\n"
                f"Image: {image}"
            )
        self.build(image, containerfile, containerfile.parent)
        print("Image built successfully.", file=sys.stderr)

    @staticmethod
    def _guess_containerfile(image: str) -> str | None:
        for pattern, suffix in _IMAGE_CONTAINERFILE_MAP.items():
            if pattern in image:
                return suffix
        return None

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(
        self,
        image: str,
        *,
        project_path: Path,
        settings_path: Path,
        dot_path: Path,
        cfg_file: Path,
        shell_path: Path,
        vault_ro_path: Path,
        vault_rw_path: Path,
        claude_install: ClaudeInstall | None = None,
        name: str | None = None,
        entrypoint: str | None = None,
        cli_args: list[str] | None = None,
    ) -> int:
        """Run a container and return the exit code."""
        cmd: list[str] = [
            self.cmd, "run", "-it", "--rm", "--userns=keep-id",
            # Persistent agent home (shell)
            "-v", f"{shell_path}:/home/agent:Z,U",
            # Project workspace
            "-v", f"{project_path}:/home/agent/workspace:Z,U",
            "-w", "/home/agent/workspace",
            # Project settings (visible to agent as .kanibako)
            "-v", f"{settings_path}:/home/agent/.kanibako:Z,U",
            # Claude config mirror
            "-v", f"{dot_path}:/home/agent/.claude:Z,U",
            "-v", f"{cfg_file}:/home/agent/.claude.json:Z,U",
        ]
        # Vault mounts (only if directories exist)
        if vault_ro_path.is_dir():
            cmd += ["-v", f"{vault_ro_path}:/home/agent/share-ro:ro"]
        else:
            print(f"Note: Vault read-only directory not found ({vault_ro_path}), skipping mount.", file=sys.stderr)
        if vault_rw_path.is_dir():
            cmd += ["-v", f"{vault_rw_path}:/home/agent/share-rw:Z,U"]
        else:
            print(f"Note: Vault read-write directory not found ({vault_rw_path}), skipping mount.", file=sys.stderr)
        # Mount host's Claude installation if available
        if claude_install:
            cmd += [
                "-v", f"{claude_install.install_dir}:/home/agent/.local/share/claude:ro",
                "-v", f"{claude_install.binary}:/home/agent/.local/bin/claude:ro",
            ]
        if name:
            cmd += ["--name", name]
        if entrypoint:
            cmd += ["--entrypoint", entrypoint]
        cmd.append(image)
        if cli_args:
            cmd.extend(cli_args)

        result = subprocess.run(cmd)
        return result.returncode

    def stop(self, name: str) -> bool:
        """Stop a running container by name. Returns True if stopped."""
        result = subprocess.run(
            [self.cmd, "stop", name],
            capture_output=True,
        )
        return result.returncode == 0

    def list_running(self, prefix: str = "kanibako-") -> list[tuple[str, str, str]]:
        """Return running containers matching *prefix* as (name, image, status) tuples."""
        result = subprocess.run(
            [
                self.cmd, "ps",
                "--filter", f"name={prefix}",
                "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}",
            ],
            capture_output=True,
            text=True,
        )
        containers: list[tuple[str, str, str]] = []
        for line in result.stdout.splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3:
                containers.append((parts[0], parts[1], parts[2]))
        return containers

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def get_local_digest(self, image: str) -> str | None:
        """Return the repo digest (``sha256:...``) for a local image, or None."""
        try:
            result = subprocess.run(
                [self.cmd, "image", "inspect", image, "--format", "json"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return None
            import json
            data = json.loads(result.stdout)
            # podman returns a list, docker returns an object
            if isinstance(data, list):
                data = data[0] if data else {}
            digests = data.get("RepoDigests", [])
            if not digests:
                return None
            # Extract the sha256:... portion from e.g. "ghcr.io/x/img@sha256:abc..."
            digest = digests[0]
            if "@" in digest:
                return digest.split("@", 1)[1]
            return digest
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_local_images(self) -> list[tuple[str, str]]:
        """Return local kanibako images as (repo:tag, size) tuples."""
        result = subprocess.run(
            [self.cmd, "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.Size}}"],
            capture_output=True,
            text=True,
        )
        images: list[tuple[str, str]] = []
        for line in result.stdout.splitlines():
            if "kanibako" in line.lower():
                parts = line.split("\t", 1)
                repo = parts[0]
                size = parts[1] if len(parts) > 1 else ""
                images.append((repo, size))
        return images
