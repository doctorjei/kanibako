"""clodbox image: list built-in/local/remote container images."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

from clodbox.config import load_config, load_merged_config
from clodbox.container import ContainerRuntime
from clodbox.errors import ContainerError
from clodbox.paths import _xdg, load_std_paths, resolve_project


# Descriptions for known Containerfile variants.
_VARIANT_DESCRIPTIONS = {
    "base": "Python, nano, git, jq, ssh, gh, archives",
    "systems": "C/C++, Rust, assemblers, QEMU, debuggers",
    "jvm": "Java, Kotlin, Maven",
    "android": "JVM + Gradle, Android SDK",
    "ndk": "Android + systems toolchain",
    "dotnet": ".NET SDK 8.0",
    "behemoth": "All toolchains combined",
}


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "image",
        help="List or rebuild container images",
        description="List available container images or rebuild them.",
    )
    image_sub = p.add_subparsers(dest="image_command", metavar="COMMAND")

    # clodbox image list (default behavior)
    list_p = image_sub.add_parser(
        "list",
        help="List available container images (default)",
        description="List available container images (built-in variants, local, and remote).",
    )
    list_p.add_argument(
        "-p", "--project", default=None, help="Show current image for a specific project"
    )
    list_p.set_defaults(func=run_list)

    # clodbox image rebuild
    rebuild_p = image_sub.add_parser(
        "rebuild",
        help="Rebuild container image(s) with latest packages",
        description="Rebuild container image(s) from Containerfile with --no-cache.",
    )
    rebuild_p.add_argument(
        "image", nargs="?", default=None,
        help="Image to rebuild (default: current configured image)",
    )
    rebuild_p.add_argument(
        "--all", action="store_true", dest="all_images",
        help="Rebuild all local clodbox images",
    )
    rebuild_p.set_defaults(func=run_rebuild)

    # Default to list if no subcommand given
    p.set_defaults(func=run_list, project=None)


def run_list(args: argparse.Namespace) -> int:
    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "clodbox" / "clodbox.toml"
    config = load_config(config_file)
    std = load_std_paths(config)
    proj = resolve_project(std, config, project_dir=args.project, initialize=False)

    # Merged config for current image display
    project_toml = proj.settings_path / "project.toml"
    merged = load_merged_config(config_file, project_toml)

    # ---- Built-in Variants ----
    containers_dir = std.data_path / "containers"
    found_variants = False
    if containers_dir.is_dir():
        for cf in sorted(containers_dir.glob("Containerfile.*")):
            variant = cf.suffix.lstrip(".")
            if not found_variants:
                print("Built-in image variants:")
                found_variants = True
            desc = _VARIANT_DESCRIPTIONS.get(variant, "(no description)")
            print(f"  {variant:<12} {desc}")

    if not found_variants:
        print("Built-in image variants: (none installed -- run clodbox install first)")

    print()

    # ---- Local Images ----
    try:
        runtime = ContainerRuntime()
        print("Local images:")
        images = runtime.list_local_images()
        if images:
            for repo, size in images:
                print(f"  {repo:<50} {size}")
        else:
            print("  (none)")
    except ContainerError:
        print("Local images: (no container runtime found)")

    print()

    # ---- Remote Registry Images ----
    image = merged.container_image
    owner = _extract_ghcr_owner(image)

    print("Remote registry images:")
    if owner:
        _list_remote_packages(owner)
    elif not owner and image:
        print(f"  (registry owner not detected from image: {image})")
    else:
        print("  (image not configured)")

    print()

    # ---- Current Image ----
    print(f"Current image: {merged.container_image}")
    return 0


def _extract_ghcr_owner(image: str) -> str | None:
    """Extract GitHub owner from ghcr.io/<owner>/... image path."""
    if not image.startswith("ghcr.io/"):
        return None
    remainder = image[len("ghcr.io/"):]
    return remainder.split("/")[0] if "/" in remainder else None


def _list_remote_packages(owner: str) -> None:
    """Query GitHub API for the owner's clodbox container packages."""
    url = f"https://api.github.com/users/{owner}/packages?package_type=container"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "clodbox"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        print("  (could not reach GitHub API)")
        return

    packages = [pkg["name"] for pkg in data if "clodbox" in pkg.get("name", "").lower()]
    if packages:
        for pkg in packages:
            print(f"  ghcr.io/{owner}/{pkg}")
    else:
        print(f"  (no clodbox packages found for {owner})")


def run_rebuild(args: argparse.Namespace) -> int:
    """Rebuild container image(s) with --no-cache."""
    config_file = _xdg("XDG_CONFIG_HOME", ".config") / "clodbox" / "clodbox.toml"
    config = load_config(config_file)
    std = load_std_paths(config)
    containers_dir = std.data_path / "containers"

    try:
        runtime = ContainerRuntime()
    except ContainerError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not containers_dir.is_dir():
        print(f"Error: containers directory not found: {containers_dir}", file=sys.stderr)
        print("Run 'clodbox setup' first.", file=sys.stderr)
        return 1

    if args.all_images:
        return _rebuild_all(runtime, containers_dir)

    # Determine which image to rebuild
    image = args.image
    if image is None:
        # Use current configured image
        merged = load_merged_config(config_file, None)
        image = merged.container_image

    return _rebuild_one(runtime, image, containers_dir)


def _rebuild_one(runtime: ContainerRuntime, image: str, containers_dir: Path) -> int:
    """Rebuild a single image."""
    suffix = runtime.guess_containerfile(image)
    if suffix is None:
        print(f"Error: cannot determine Containerfile for image: {image}", file=sys.stderr)
        print("Known patterns: " + ", ".join(
            f"{p} -> Containerfile.{s}"
            for p, s in sorted(set(
                (p, runtime.guess_containerfile(p))
                for p in ["clodbox-base", "clodbox-systems", "clodbox-jvm",
                          "clodbox-android", "clodbox-ndk", "clodbox-dotnet",
                          "clodbox-behemoth"]
            ))
        ), file=sys.stderr)
        return 1

    containerfile = containers_dir / f"Containerfile.{suffix}"
    if not containerfile.is_file():
        print(f"Error: Containerfile not found: {containerfile}", file=sys.stderr)
        return 1

    print(f"Rebuilding {image} from Containerfile.{suffix}...")
    print()
    rc = runtime.rebuild(image, containerfile, containers_dir)
    if rc == 0:
        print()
        print(f"Successfully rebuilt {image}")
    else:
        print()
        print(f"Build failed with exit code {rc}", file=sys.stderr)
    return rc


def _rebuild_all(runtime: ContainerRuntime, containers_dir: Path) -> int:
    """Rebuild all local clodbox images."""
    images = runtime.list_local_images()
    if not images:
        print("No local clodbox images to rebuild.")
        return 0

    failed = 0
    for repo, _size in images:
        print(f"\n{'=' * 60}")
        print(f"Rebuilding {repo}")
        print('=' * 60)
        rc = _rebuild_one(runtime, repo, containers_dir)
        if rc != 0:
            failed += 1

    print()
    if failed:
        print(f"Rebuilt {len(images) - failed}/{len(images)} images ({failed} failed)")
        return 1
    else:
        print(f"Rebuilt {len(images)} image(s) successfully.")
        return 0
