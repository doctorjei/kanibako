# Design: Agent System (7a), Shell Templates (7b), and Global Shared Caches (7c)

**Date:** 2026-02-23
**Status:** 7b and 7c implemented (2026-02-24); 7a deferred

---

## 7a: Agent Plugin System

### Overview

Agent TOML files provide per-agent configuration that applies across all
projects using that agent. They are config *for* a target plugin — no TOML
without a matching plugin.

### Agent TOML Location

```
{data_path}/agents/{agent_id}.toml
```

Agent ID = filename stem = template directory name = target plugin name.
`target_name = "claude"` selects both the target plugin and `agents/claude.toml`.

### Schema

```toml
[agent]
name = "Claude Code"         # display name
shell = "standard"           # default template variant
default_args = []            # always passed to agent binary

[state]
# model = "opus"             # uncomment to override agent's model selection
access = "permissive"        # permission/access level

[env]                        # agent-level env vars (injected into container)

[shared]                     # agent-level shared caches
plugins = ".claude/plugins"
```

**Four sections, each with a clear role:**

| Section | Role |
|---------|------|
| `[agent]` | Identity and defaults (static, descriptive) |
| `[state]` | Runtime behavior knobs (what the agent does) |
| `[env]` | Raw env vars injected into container (escape hatch) |
| `[shared]` | Agent-level shared cache paths (what gets mounted) |

### Section Details

**`[agent]`** — universal fields every agent uses:
- `name`: display name
- `shell`: default template variant (resolved via template system, 7b)
- `default_args`: list of CLI args always passed to the agent binary

**`[state]`** — common but optional behavior knobs:
- `model`: agent model selection (commented out by default — users typically
  select interactively; uncomment to override)
- `access`: permission/access level

Agents that don't support a `[state]` field ignore it. The target plugin is
responsible for translating state values into CLI args, env vars, or config
files as needed.

**`[env]`** — raw env vars, agent-agnostic. Merged with per-project and global
env vars during container launch.

**`[shared]`** — agent-level shared caches. Same mechanism as global `[shared]`
in kanibako.toml, but stored separately (see 7c for directory layout).

### TOML Creation

The target plugin generates its TOML on first use — it knows its own defaults.
`kanibako setup` also triggers generation for installed plugins.

### The `general` Agent

The no-agent default (runs `/bin/sh`). Has a real TOML file at
`agents/general.toml` (initially empty, user can customize template/env).
Uses `general/` templates.

### Target Plugin Integration

The existing target plugin system (`Target` ABC, entry points, `resolve_target()`)
gains methods to:
- Generate default agent TOML (`generate_agent_config()`)
- Translate `[state]` values into agent-specific CLI args/env
  (`apply_state(state_dict)` → CLI args + env vars)

---

## 7b: Shell Templates

### Current State

- `_bootstrap_shell()` in `paths.py` writes hardcoded `.bashrc`, `.profile`, `.shell.d/`
- `_copy_credentials_from_host()` copies `.claude/` credentials
- `Target.init_home()` exists in the ABC but is **never called**
- `KanibakoConfig.paths_templates` exists, defaults to `"templates"` (relative to data_path)

### Approach

All agent-aware initialization happens in `start.py` after target resolution,
not in `_init_common()`. This keeps `_init_common()` purely kanibako
infrastructure and avoids splitting new-project setup across two locations.

Credential copy moves out of `_init_common()` and into `target.init_home()`.
The `_copy_credentials_from_host()` call in `_init_common()` is removed.

**Init flow (new project):**

```
_init_common()              paths.py     (1) mkdir shell, bootstrap .bashrc/.profile/.shell.d
                                         (no credentials, no templates)

resolve_target()            start.py     (2) identify agent
apply_shell_template()      start.py     (3) overlay template (if proj.is_new)
target.init_home()          start.py     (4) agent-specific setup (if proj.is_new)
runtime.run()               start.py     (5) launch
```

Steps 3-4 only run when `proj.is_new` and a target is resolved.

### Naming

- **Agent ID** = directory name = plugin module name. `claude` agent →
  `templates/claude/` → plugin module `claude`.
- **Template variant ID** = subdirectory name. `standard` variant →
  `templates/claude/standard/`.
- **`default`** is a reserved keyword meaning "use the agent's configured
  default template" (resolved at runtime, not a directory name).

### Template Resolution

```
templates_base = {data_path} / {config.paths_templates}

Resolution order (template_name defaults to "standard" until agent TOML is implemented):
  1. {templates_base}/{agent_name}/{template_name}/   (e.g. templates/claude/standard/)
  2. {templates_base}/general/{template_name}/         (e.g. templates/general/standard/)
  3. (none — "empty" template, no files applied)
```

**Layering:** `general/base` is always applied first (if it exists), then the
resolved template overlays on top:

```
  general/base/*           →  shell_path/     (common skeleton)
  claude/standard/*        →  shell_path/     (overwrites base files if names collide)
```

The "empty" template skips both steps (no base, no overlay). It's the implicit
fallback when no template directories exist.

### Template Directory Layout

```
templates/
  general/               # no-agent templates (agent ID = "general")
    base/                #   common skeleton, applied under every non-empty template
    standard/            #   shipped general template
  claude/                # Claude-specific (agent ID = "claude")
    standard/            #   shipped Claude template
```

### Template Contents

Templates are plain directory trees. Files are copied (via `shutil.copytree`
with `dirs_exist_ok=True`) into the shell directory. No variable substitution,
no special syntax — just files.

Example `templates/general/base/`:
```
.shell.d/
  aliases.sh
```

Example `templates/claude/standard/`:
```
.claude/
  CLAUDE.md          (starter instructions)
.shell.d/
  claude-helpers.sh
```

### Template Source

- `general/base` and `general/standard`: created during `kanibako setup`
  (initially empty or with minimal files)
- Agent-specific templates: shipped as package data by the target plugin
  (like containerfiles today). Installed on first use or via a setup step.
- Users customize by editing files in the template directories directly.

### New Module: `templates.py`

```python
def resolve_template(templates_base: Path, agent_name: str, template_name: str = "standard") -> Path | None:
    """Return the path to the resolved template directory, or None for 'empty'."""

def apply_shell_template(shell_path: Path, templates_base: Path, agent_name: str, template_name: str = "standard") -> None:
    """Apply base + resolved template to a shell directory. No-op if template is 'empty'."""
```

### `target.init_home()` Changes

`init_home()` gains an `auth` parameter so agents can handle credential setup
appropriately for both shared and distinct auth modes:

```python
# targets/base.py
@abstractmethod
def init_home(self, home: Path, *, auth: str = "shared") -> None:
    """Initialize agent-specific files in the project home directory."""

# targets/claude.py
def init_home(self, home: Path, *, auth: str = "shared") -> None:
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    if auth != "distinct":
        # copy credentials from host
        ...
    # always: create .claude.json (filtered or empty)
    ...
```

Called from `start.py`:

```python
if proj.is_new and target:
    target.init_home(proj.shell_path, auth=proj.auth)
```

Always called for new projects regardless of auth mode — agents may need to
create config directories, default files, etc. even without shared credentials.

---

## 7c: Global Shared Caches

### Current State

- `KanibakoConfig.paths_shared` exists (default: `"shared"`, relative to data_path)
- Design doc specifies `[shared]` TOML section with cache entries
- `[shared]` is NOT currently parsed by `load_config()` (keys would flatten
  to `shared_cargo-git` etc., which don't match any KanibakoConfig fields)
- Vault mount pattern in `container.py` is the model: conditional on `.is_dir()`

### Config Parsing

Add a dict field to `KanibakoConfig`:

```python
shared_caches: dict[str, str] = field(default_factory=dict)
```

In `load_config()`, extract `[shared]` before flattening:

```python
shared = data.pop("shared", {})
flat = _flatten_toml(data)
# ... existing field assignment ...
cfg.shared_caches = {k: str(v) for k, v in shared.items()}
```

This cleanly separates the key-value cache entries from the flattened path fields.

### Mount Generation

Each `[shared]` entry maps:
- **Key** = cache name → host directory: `{shared_path}/{name}/`
- **Value** = container-relative path → mount destination: `/home/agent/{value}`

In `start.py`, after building extra_mounts from target:

```python
for name, container_rel in merged.shared_caches.items():
    host_dir = global_shared_path / name
    if host_dir.is_dir():  # lazy — only mount if exists
        extra_mounts.append(Mount(
            source=host_dir,
            destination=f"/home/agent/{container_rel}",
            options="Z,U",
        ))
```

### Sharing Levels and Directory Layout

Three distinct levels, stored in separate directories:

| Level | Host path | Visible to | Source |
|-------|-----------|------------|--------|
| Truly global | `{data_path}/shared/global/{name}/` | All AC + all WS projects | `[shared]` in kanibako.toml |
| Agent (AC) | `{data_path}/shared/{agent_id}/{name}/` | AC projects using that agent | `[shared]` in agent TOML (7a) |
| Agent (WS) | `$worksetdir/shared/{agent_id}/{name}/` | WS projects using that agent | `[shared]` in agent TOML (7a) |

- **Truly global** caches (pip, cargo, npm, etc.) are mounted for all
  non-decentralized projects regardless of mode.
- **Agent-level** caches (from agent TOML) are never truly global. They route
  to `{data_path}/shared/{agent_id}/` in AC mode or
  `$worksetdir/shared/{agent_id}/` in WS mode. Agent subdirectories keep
  caches separate when a workset has projects with different agents.
- **Decentralized** projects get no shared caches.

For this phase (7c), only truly-global caches are implemented. Agent-level
cache mounting is added in 7a.

### Path Resolution

Add `global_shared_path: Path | None` to `ProjectPaths`:
- AC: `std.data_path / config.paths_shared / "global"`
- Workset: `std.data_path / config.paths_shared / "global"` (same — truly global)
- Decentralized: `None`

When agent-level caches arrive (7a), add a second field
`local_shared_path: Path | None`:
- AC: `std.data_path / config.paths_shared / {agent_id}`
- Workset: `$worksetdir / config.paths_shared / {agent_id}`
- Decentralized: `None`

### Lazy Creation

Per the design doc: "Shared directories are only created/mounted when they exist
on the host side (lazy creation, not eager)."

Users opt in by creating the directory. For convenience, we could:
- Document `mkdir -p $(kanibako config get paths_shared)/pip` etc.
- Add a future `kanibako shared init [name]` subcommand (not in this phase)

### Open Questions

1. **Mount options:** `Z,U` (SELinux relabel + userns remap) matches other
   read-write mounts. Should any caches be read-only? Package caches are
   written to by package managers, so probably not.

2. **Name conflicts:** If a shared cache mount destination overlaps with an
   existing shell directory (e.g., `.cache/pip` exists in the template), the
   bind mount wins at runtime (hides the template file). This is probably fine
   but worth noting.

---

## Implementation Scope

### 7a (agent plugin system) — deferred, design complete:
- New `src/kanibako/agents.py`: load/generate/write agent TOML
- Modify `targets/base.py`: add `generate_agent_config()`, `apply_state()` methods
- Modify `targets/claude.py`: implement agent config generation and state translation
- Modify `start.py`: load agent TOML, merge `[env]`, apply `[state]`, mount agent `[shared]`
- Modify `install.py` (setup): generate agent TOMLs for installed plugins
- Create `agents/general.toml` (empty default)
- Tests for TOML generation, state translation, agent shared cache mounting

### 7b (templates) — DONE (2026-02-24):
- New `src/kanibako/templates.py` (resolve + apply, ~55 lines)
- Modified `paths.py`: removed credential copy from `_init_common()`, `_init_workset_project()`, `_init_decentralized_project()`; removed `skip_credentials` param
- Modified `targets/base.py`: added `auth` kwarg to `init_home()`
- Modified `targets/claude.py`: auth-conditional credential copy in `init_home()`
- Modified `start.py`: calls `apply_shell_template()` + `target.init_home(auth=...)` for new projects
- Modified `install.py` (setup): creates `templates/general/{base,standard}/`
- 8 new template tests, updated target/path tests (774 → 797 unit tests)

### 7c (shared caches) — DONE (2026-02-24):
- Modified `config.py`: `shared_caches: dict[str, str]` field, `[shared]` section extracted before flattening, commented `[shared]` in default config
- Modified `paths.py`: `global_shared_path: Path | None` on ProjectPaths, set in all three resolvers
- Modified `start.py`: lazy shared cache mount generation
- 8 new config tests, 3 new paths tests
