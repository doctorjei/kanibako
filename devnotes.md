# Clodbox Development Notes

> **For Claude sessions:** This file is the running development log for the
> clodbox project. When you begin a session, read this file. As you work,
> update it with any decisions made, changes implemented, and instructions
> given by the user. Record all standing instructions from the user in the
> "Standing Instructions" section so they carry across sessions.

---

## Standing Instructions

These are explicit directives from the user that apply to all future work:

1. **Flag casing convention:** Any command-line flag that changes the
   behavior/context of *Claude* (the agent) should use an **uppercase**
   letter. Flags that affect the *container* or *project* should use a
   **lowercase** letter. This helps users distinguish at a glance.
   - Uppercase (Claude): `-N` (new conversation), `-S` (safe mode)
   - Lowercase (container/project): `-c` (command/entrypoint), `-i` (image),
     `-p` (project dir)

2. **Hidden flags:** `-E`/`--entrypoint` is still accepted for backwards
   compatibility but is **not displayed** in help output. `-c`/`--command`
   is the primary flag shown to users.

3. **Maintain this file:** Edit and append to this devnotes file as work
   progresses. Record all user instructions, design decisions, and changes.

---

## Project Overview

**Clodbox** is a tool for running [Claude Code](https://claude.ai) inside
rootless containers (Podman/Docker). It manages per-project isolation,
credential forwarding, and session continuity so that each project gets its
own sandboxed Claude environment.

### Key concepts

- **Containerized Claude sessions** — Each project runs Claude Code inside a
  container with its workspace bind-mounted in. The container is ephemeral
  (`--rm`), but session state persists via mounted config directories.
- **Per-project data isolation** — Project settings are stored outside the
  project directory, keyed by a SHA-256 hash of the project's absolute path.
  This lives under `$XDG_DATA_HOME/clodbox/projects/<hash>/`.
- **Credential management** — OAuth credentials are copied from the host's
  `~/.claude/` into a central clodbox store at install time, refreshed by a
  cron job every 6 hours, and injected into each container at launch via
  environment variable and mounted config files.
- **Session continuity** — By default, `clodbox` passes `--continue` to
  Claude for existing projects so the conversation resumes where it left off.

### File inventory

| File | Purpose |
|---|---|
| `clodbox` | Main script. Parses flags, resolves project paths, launches container. |
| `clodbox-lib` | Shared shell library (sourced). Provides `_get_abspath_` helper and resolves `CLODBOX_CONFIG_FILE`. |
| `clodbox-install` | Installer. Writes `clodbox.rc`, copies credentials, builds base image, installs scripts to `~/.local/bin`, sets up cron. |
| `clodbox-refresh-credentials` | Cron script. Copies host `~/.claude/.credentials.json` into clodbox's central store. |
| `clodbox-remove` | Uninstaller. Removes config, data, cron job, and scripts. |
| `containers/Containerfile.base` | Base image (`ubuntu:devel` + Python, nano, git, jq, openssh-client, ripgrep, gh, archives, Claude Code). Pushed to `ghcr.io/<owner>/clodbox-base:latest`. |
| `containers/Containerfile.systems` | Systems programming image (base + C/C++, Rust, assemblers, QEMU, debuggers). Pushed to `ghcr.io/<owner>/clodbox-systems:latest`. |
| `containers/Containerfile.jvm` | JVM languages image (base + Java, Kotlin, Maven). Pushed to `ghcr.io/<owner>/clodbox-jvm:latest`. |
| `containers/Containerfile.android` | Android development image (jvm + Gradle, Android SDK placeholder). Pushed to `ghcr.io/<owner>/clodbox-android:latest`. |
| `containers/Containerfile.ndk` | Android NDK image (android + systems toolchain). Pushed to `ghcr.io/<owner>/clodbox-ndk:latest`. |
| `containers/Containerfile.dotnet` | .NET development image (base + .NET SDK 8.0). Pushed to `ghcr.io/<owner>/clodbox-dotnet:latest`. |
| `containers/Containerfile.behemoth` | Kitchen sink image with all toolchains (systems + jvm + android + dotnet). Pushed to `ghcr.io/<owner>/clodbox-behemoth:latest`. |
| `.github/workflows/build-images.yml` | GitHub Actions workflow. Builds and pushes all container images to ghcr.io on pushes to `main` (when `containers/` changes) or manual dispatch. |
| `archive/` | Old/superseded versions of scripts, kept for reference. |

### Configuration hierarchy

- **Global config:** `$XDG_CONFIG_HOME/clodbox/clodbox.rc` — Written by
  installer. Sets `CLODBOX_CONTAINER_IMAGE`, path layout variables, etc.
- **Per-project config:** `$PROJECT_SETTINGS_PATH/project.rc` — Optional.
  Created by user via `clodbox config`. Overrides global values.
- **CLI flags:** `-i`/`--image` overrides everything for a single run.

Precedence: **CLI flag > project.rc > clodbox.rc**

---

## State When This Session Began

The project was functional with the following capabilities:

- `clodbox` / `clodbox start` — launch a Claude session in a container
- `clodbox shell` — open a bash shell in the container
- `clodbox resume` — resume with Claude's conversation picker
- `-E`/`--entrypoint` — override container entrypoint
- `-N`/`--new` — start a new conversation
- `-S`/`--safe` — run without `--dangerously-skip-permissions`
- `--` separator for passing args through to Claude
- Automatic `--continue` for existing projects
- Install, remove, and credential refresh scripts
- Two container images (base and behemoth)

There was no per-project image configuration, no `config` subcommand, and no
`-p` project directory flag.

---

## Changes Made This Session

### 1. Renamed `-E`/`--entrypoint` to `-c`/`--command`

- `-c`/`--command` is now the primary flag (shown in help)
- `-E`/`--entrypoint` still accepted (hidden from help output)
- Internal variable remains `CLODBOX_ENTRYPOINT` (no functional change)

### 2. Added `-p`/`--project DIR` flag

- Allows specifying a project directory other than `cwd`
- `_clodbox_fetch_project_paths_` now resolves from
  `${CLODBOX_PROJECT_DIR:-$(pwd)}`

### 3. Added per-project config sourcing (`project.rc`)

- At the end of `_clodbox_fetch_project_paths_`, after project paths are
  validated, the script sources `$PROJECT_SETTINGS_PATH/project.rc` if it
  exists
- This file is **not** created by `_clodbox_init_` — it only exists when the
  user explicitly configures a project (e.g., via `clodbox config`)

### 4. Added `-i`/`--image IMAGE` flag

- Sets `CLODBOX_IMAGE_OVERRIDE`
- Applied in `_clodbox_start_` after project paths are loaded (so it wins
  over both `project.rc` and `clodbox.rc`)

### 5. Added `config` subcommand

- `clodbox config image` — prints the current effective image for the project
- `clodbox config image <IMAGE>` — writes `CLODBOX_CONTAINER_IMAGE` to
  `$PROJECT_SETTINGS_PATH/project.rc` (creates or updates)
- Dispatched before container start; loads paths, runs config, exits
- Works with `-p` for cross-project config: `clodbox -p ~/other config image`

### 6. Updated usage text

- Added `config` to commands list
- Added `-c`, `-i`, `-p` to options list
- Removed `-E`/`--entrypoint` from display (still accepted)

### 7. Created this devnotes file

- Linked from project root as `devnotes.md` (symlink to
  `docs/claude-notes/clodbox-development.md`)

---

## Changes Made This Session (CI & Container Updates)

### 1. Added GitHub Actions CI for container images

- Created `.github/workflows/build-images.yml`
- Triggers on pushes to `main` that modify `containers/**`, plus manual
  `workflow_dispatch`
- Builds and pushes two images to ghcr.io using `docker/build-push-action@v6`:
  - **Base:** `ghcr.io/<owner>/clodbox-base:latest` from `Containerfile.base`
  - **Behemoth:** `ghcr.io/<owner>/clodbox-behemoth:latest` from
    `Containerfile.behemoth`, with `BASE_IMAGE` build arg pointing to the
    base image on ghcr.io
- Uses GitHub Actions cache (`type=gha`) for Docker layer caching
- Behemoth step runs after base (sequential dependency)

### 2. Parameterized `Containerfile.behemoth` base image

- Added `ARG BASE_IMAGE=ghcr.io/doctorjei/clodbox-base:latest` before `FROM`
- CI overrides via `--build-arg`; default points to the registry image

### 3. Updated default image in `clodbox-install`

- Changed `CLODBOX_CONTAINER_IMAGE` default from `localhost/clodbox:latest` to
  `ghcr.io/doctorjei/clodbox-base:latest`
- Installer still builds a local image if none exists, but new installs now
  default to pulling from ghcr.io

### 4. Fixed UID/GID 1000 conflict in `Containerfile.base`

- `ubuntu:devel` ships with an `ubuntu` user at UID/GID 1000, which conflicted
  with creating the `agent` user
- Added cleanup logic to remove any existing user/group at 1000 before creating
  `agent`

### 5. Added `openssh-client` to base image

- Added to the base system packages list in `Containerfile.base`

### 6. Moved `devnotes.md` to project root

- File now lives at `devnotes.md` in the repo root (no longer a symlink)
- Added to `.gitignore` so it stays local

---

## Changes Made This Session (Archive & Credential Updates)

### 1. Removed OAuth token environment variable

- Deleted commented-out `OAUTH_TOKEN` extraction and `-e CLAUDE_CODE_OAUTH_TOKEN`
  from container launch in `clodbox`
- Claude Code now relies solely on mounted `.credentials.json` file for
  authentication
- Simpler and more reliable than env var approach

### 2. Updated `clodbox-install` image handling

- Changed to pull from registry first, fall back to local build if pull fails
- Checks if image exists before attempting pull or build
- Preserves local build capability as fallback

### 3. Updated `clodbox-remove` to preserve data

- Removed automatic deletion of `$CLODBOX_DATA` directory
- Now only removes config, cron job, and executables
- Prints note showing user how to manually delete project/credential data if
  desired

### 4. Added archive/clean/restore workflow

**Three new commands for managing project session data:**

#### `clodbox archive <project-path> [archive-file]`
- Packs up session data from `$PROJECT_SETTINGS_PATH` into `.txz` archive
- Default filename: `clodbox-<basename>-<hash8>-<timestamp>.txz`
- Git repository handling:
  - Checks for uncommitted changes (errors unless `--allow-uncommitted`)
  - Checks for unpushed commits (errors unless `--allow-unpushed`)
  - Records git metadata: branch, HEAD SHA, remotes
  - Warns if no git repo (only session data archived)
- Archive format:
  - `<hash>/` directory containing entire `$PROJECT_SETTINGS_PATH` tree
  - `clodbox-archive-info.txt` at root with project path and git metadata

#### `clodbox clean <project-path>`
- Removes project session data directory (`$PROJECT_SETTINGS_PATH`)
- Interactive confirmation required (shows path and hash truncated to 8 chars)
- User must type "yes" to confirm deletion
- `--force` flag skips confirmation

#### `clodbox restore <project-path> <archive-file>`
- Restores session data from archive into appropriate hash directory
- Hash validation:
  - Exact match: restore silently
  - Same basename, different path: restore silently
  - Different basename: prompt user showing both paths
- Git state validation (if archive has git metadata):
  - No git in workspace: warn and show archive git info, prompt
  - Git SHA matches: restore silently
  - Git SHA mismatch: warn showing both states (archive vs current), prompt
- All prompts require typing "yes" to confirm
- `--force` flag skips all validation prompts

### 5. Split container images into specialized variants

Created a hierarchy of container images for different development needs:

**Image hierarchy:**
```
base (Python, nano, archives, git, gh, ssh)
├── systems (base + C/C++/Rust, assemblers, QEMU, debuggers)
├── jvm (base + Java, Kotlin, Maven)
│   └── android (jvm + Gradle, Android SDK)
│       └── ndk (android + systems toolchain)
├── dotnet (base + C# SDK)
└── behemoth (base + all of the above)
```

**Base image additions:**
- `nano` — simple editor (simplicity over nerd-superiority)
- `xz-utils` — xz compression for .txz archives
- `zip`, `unzip`, `zstd` — common archive formats

**New specialized images:**
- **systems**: C/C++ (gcc, clang, llvm), Rust, assemblers (nasm, yasm), debuggers (gdb, lldb), build tools (cmake, ninja, meson), QEMU user-mode emulation, archives (p7zip, unrar)
- **jvm**: Java (OpenJDK), Kotlin, Maven
- **android**: JVM + Gradle, Android SDK placeholder (users mount their own SDK)
- **ndk**: Android + systems toolchain + NDK placeholder
- **dotnet**: .NET SDK 8.0
- **behemoth**: Kitchen sink with all toolchains (systems + jvm + android + dotnet)

**Package decisions:**
- Gradle only in android/behemoth (not jvm), as it's primarily an Android tool
- QEMU uses `qemu-user-static` (lightweight cross-compilation) instead of `qemu-system-*` (heavy full system emulators)
- Rust installed via rustup (~200-300 MB) for flexibility

**Estimated incremental sizes:**
- systems: ~800MB-1.1GB beyond base
- jvm: ~360-520MB beyond base
- android: ~2.1-4.15GB beyond jvm
- ndk: ~2.7-4.3GB beyond android
- dotnet: ~400-600MB beyond base

**Future work noted:**
- **cloud** variant: base + Go (cloud-native/backend work)
- **web** variant: base + Node.js/Deno (frontend tooling, JS ecosystem)

### 6. Auto-pull with local build fallback

**Main `clodbox` script enhancement:**
- Before starting a container, checks if the configured image exists locally
- If not found, attempts to pull from registry (ghcr.io)
- If pull fails, attempts local build using installed Containerfiles
- Automatically detects which Containerfile to use based on image name pattern

**Installer enhancement:**
- Now copies all Containerfiles to `$CLODBOX_DATA/containers/` (not just base/behemoth)
- Enables local build fallback for any variant image

This ensures users can switch between image variants (base, systems, jvm, android, ndk, dotnet, behemoth) and clodbox will automatically fetch or build as needed.

### 7. Split clodbox into modular scripts

To prepare for future Python conversion, split subcommands into separate executable scripts:

**New structure:**
- `clodbox` — Main dispatcher + start/shell/resume (core container operations)
- `clodbox-config` — Config subcommand (get/set per-project settings)
- `clodbox-archive` — Archive subcommand (pack session data + git metadata)
- `clodbox-clean` — Clean subcommand (remove session data)
- `clodbox-restore` — Restore subcommand (restore from archive)
- `clodbox-lib` — Base shared functions (path helpers, config location)
- `clodbox-lib-common` — Extended shared functions (path loading, project paths)
- `clodbox-refresh-credentials` — Cron job for credential sync
- `clodbox-remove` — Uninstaller

**Benefits:**
- Each command is self-contained and independently testable
- Can port to Python incrementally (e.g., replace `clodbox-archive` with `clodbox-archive.py`)
- Main `clodbox` becomes a thin dispatcher (exec's other scripts)
- Flags are passed via environment variables (`CLODBOX_FORCE`, `CLODBOX_ALLOW_UNCOMMITTED`, etc.)

### 8. Architecture note

**This is likely the last major feature to implement in shell scripts.** Future
development should consider rewriting in Python for better maintainability,
error handling, and testability before adding more complexity. The modular
structure now makes incremental porting feasible.
