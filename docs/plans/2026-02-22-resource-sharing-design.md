# Resource Sharing Design

Date: 2026-02-22

## Goal

Define which resources are shared across projects and which are
project-specific, across all three operational modes (account-centric,
workset, decentralized).

## Design Principles

- AC is treated as an implicit workset for sharing purposes.
- Host is the seed source at workset/account creation, then each
  workset is independent.
- The Target ABC is extended so each agent plugin declares which of
  its resources are shared vs. project-scoped.
- Project resources are seeded from workset defaults at project creation.
- Future: target plugins can expose settings to let users override
  sharing defaults (e.g., change plugins from shared to project-scoped).

## Resource Categories

| Category | Scope | Notes |
|----------|-------|-------|
| Shell (home dir) | Project | Dotfiles, editor configs, tool settings |
| Package caches | Workset/Account | pip, npm, cargo — shared mount, disk savings |
| Vault | Already handled | Existing mechanism unchanged |
| Agent shared resources | Workset/Account | Target plugin declares what goes here |
| Agent project resources | Project | Target plugin declares what goes here |
| Credentials/auth | Special case | Existing flow; per-workset auth deferred (#5) |

### Shell

The catch-all for home directory contents. Each project gets its own
shell (mounted as `/home/agent`). Dotfiles, editor configs, git config,
SSH keys, shell history — all project-scoped. Bootstrapped at project
init with skeleton `.bashrc` and `.profile` (existing behavior).

### Package Caches

pip, npm, cargo, Go modules. Identical content across projects, can be
large. Shared at the workset/account level via a single mount point.
Saves disk and avoids repeated downloads.

### Agent Shared vs. Project Resources

The Target ABC gets new methods to declare which resources are shared
and which are project-scoped. Each agent plugin controls its own
resource layout.

## Claude Target: `.claude/` Resource Map

### Shared (workset/account level)

Mounted once, accessible to all projects in the group.

| Item | What it is |
|------|-----------|
| `plugins/` | Plugin binaries, registry, marketplace info, blocklist |
| `cache/` | General cache |
| `stats-cache.json` | Usage stats cache |
| `statsig/` | Feature flags |
| `telemetry/` | Telemetry data |

### Project-specific (seeded from workset at creation)

Copied from the workset template when a new project is created.
Diverges independently afterward.

| Item | Seeded from |
|------|-------------|
| `settings.json` | Workset default (permissions, enabled plugins, flags) |
| `CLAUDE.md` | Workset template — kanibako provides a standard one |

### Project-specific (starts fresh)

Created empty or populated by Claude Code during use.

| Item | What it is |
|------|-----------|
| `projects/` | Per-project session data, memory |
| `session-env/` | Session environment state |
| `history.jsonl` | Conversation history |
| `tasks/` | Task tracking state |
| `todos/` | Todo list state |
| `plans/` | Plan mode files |
| `file-history/` | File edit history |
| `backups/` | File backups from edits |
| `debug/` | Debug logs |
| `paste-cache/` | Clipboard/paste state |
| `shell-snapshots/` | Shell state snapshots |

## CLAUDE.md Template Flow

1. **Workset creation** — generate a default `CLAUDE.md` from a
   kanibako-provided template. User can customize the workset template.
2. **Project creation** — copy the workset's `CLAUDE.md` template
   into the new project as a starting point.
3. **Project lifetime** — project's `CLAUDE.md` diverges as needed,
   independent from the workset template.

For AC mode, the template lives at the account settings level.

## Target ABC Extension

The `Target` base class gets new methods for declaring resource layout:

- `shared_resources()` — returns paths/patterns that should be shared
  at the workset/account level.
- `project_resources()` — returns paths/patterns that are per-project.
- `seeded_resources()` — returns paths/patterns that are per-project
  but seeded from workset defaults at creation.

Each target plugin implements these to describe its own agent's needs.
`ClaudeTarget` implements them per the table above.

## Mode Behavior

| Mode | Shared resources location | Project resources location |
|------|--------------------------|---------------------------|
| Account-centric | `settings/{hash}/shared/` | `settings/{hash}/shell/.claude/` |
| Workset | `workset_root/kanibako/shared/` | `workset_root/kanibako/{project}/shell/.claude/` |
| Decentralized | N/A (single project) | `.kanibako/shell/.claude/` |

Decentralized mode has no sharing — it's a single self-contained
project. Shared resources are simply part of the project.

## `.claude.json` (Host Settings File)

The host `.claude.json` contains account-level data (OAuth, onboarding,
feature flags, per-project settings). This is part of the existing
credential sync flow and is NOT carved up by this design. It continues
to be synced as a whole via the credential refresh mechanism.

## Open Questions

- **Package cache implementation:** Bind-mount a shared directory, or
  symlink from each project shell? Bind-mount is simpler.
- **Conflict handling for shared resources:** Last-write-wins is
  probably fine since only one project runs at a time per workset.
- **Per-workset auth differentiation:** Deferred (future work item #5).
- **Target plugin settings UI:** Future — let plugins expose settings
  so users can override sharing defaults per resource.
