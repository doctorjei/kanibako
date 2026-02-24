# Target ABC Resource Sharing Extension — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** Complete (2026-02-22). Note: `init_home()` signature is changing
to `init_home(home, *, auth="shared")` as part of the redesign — see
`2026-02-23-templates-and-shared-caches.md`.

**Goal:** Extend the Target ABC with methods for declaring shared vs. project-scoped resources, so kanibako can split agent home directories into shared and per-project portions.

**Architecture:** Three new methods on the `Target` ABC with sensible defaults (everything project-scoped). `ClaudeTarget` overrides them per the resource sharing design doc. No mount or init changes yet — this is interface-only.

**Tech Stack:** Python 3.11+, dataclasses, ABC, pytest

---

### Task 1: Add `ResourceScope` enum and `ResourceMapping` dataclass to `targets/base.py`

**Files:**
- Modify: `src/kanibako/targets/base.py`
- Test: `tests/test_targets/test_base.py`

**Step 1: Write the failing tests**

Add to `tests/test_targets/test_base.py`:

```python
from kanibako.targets.base import ResourceMapping, ResourceScope


class TestResourceScope:
    def test_enum_values(self):
        assert ResourceScope.SHARED.value == "shared"
        assert ResourceScope.PROJECT.value == "project"
        assert ResourceScope.SEEDED.value == "seeded"


class TestResourceMapping:
    def test_fields(self):
        rm = ResourceMapping(
            path="plugins/",
            scope=ResourceScope.SHARED,
            description="Plugin binaries and registry",
        )
        assert rm.path == "plugins/"
        assert rm.scope == ResourceScope.SHARED
        assert rm.description == "Plugin binaries and registry"

    def test_frozen(self):
        rm = ResourceMapping(
            path="plugins/",
            scope=ResourceScope.SHARED,
            description="test",
        )
        with pytest.raises(AttributeError):
            rm.path = "other/"  # type: ignore[misc]

    def test_no_description(self):
        rm = ResourceMapping(path="cache/", scope=ResourceScope.SHARED)
        assert rm.description == ""
```

**Step 2: Run tests to verify they fail**

Run: `~/.venv/bin/pytest tests/test_targets/test_base.py::TestResourceScope tests/test_targets/test_base.py::TestResourceMapping -v`
Expected: FAIL with ImportError

**Step 3: Write implementation**

Add to `src/kanibako/targets/base.py` before the `Mount` class:

```python
from enum import Enum


class ResourceScope(Enum):
    """How an agent resource is shared across projects."""

    SHARED = "shared"    # Shared at workset/account level
    PROJECT = "project"  # Per-project, starts fresh
    SEEDED = "seeded"    # Per-project, seeded from workset template at creation


@dataclass(frozen=True)
class ResourceMapping:
    """Maps an agent resource path to its sharing scope."""

    path: str                    # Relative path within agent home (e.g. "plugins/")
    scope: ResourceScope         # How this resource is shared
    description: str = ""        # Human-readable description
```

**Step 4: Run tests to verify they pass**

Run: `~/.venv/bin/pytest tests/test_targets/test_base.py::TestResourceScope tests/test_targets/test_base.py::TestResourceMapping -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/kanibako/targets/base.py tests/test_targets/test_base.py
git commit -m "Add ResourceScope enum and ResourceMapping dataclass"
```

---

### Task 2: Add `resource_mappings()` method to `Target` ABC

**Files:**
- Modify: `src/kanibako/targets/base.py`
- Modify: `tests/test_targets/test_base.py`

**Step 1: Write the failing tests**

Add to `TestTargetABC` in `tests/test_targets/test_base.py`:

```python
    def test_default_resource_mappings(self):
        """Default resource_mappings returns empty list."""

        class MinimalTarget(Target):
            @property
            def name(self) -> str:
                return "minimal"

            @property
            def display_name(self) -> str:
                return "Minimal"

            def detect(self):
                return None

            def binary_mounts(self, install):
                return []

            def init_home(self, home):
                pass

            def refresh_credentials(self, home):
                pass

            def writeback_credentials(self, home):
                pass

            def build_cli_args(self, **kwargs):
                return []

        t = MinimalTarget()
        assert t.resource_mappings() == []
```

Also update `test_concrete_subclass` to verify `resource_mappings` works:

Add after the `assert t.check_auth() is True` line:
```python
        assert t.resource_mappings() == []
```

**Step 2: Run tests to verify they fail**

Run: `~/.venv/bin/pytest tests/test_targets/test_base.py::TestTargetABC -v`
Expected: FAIL with AttributeError

**Step 3: Write implementation**

Add to the `Target` class in `src/kanibako/targets/base.py`, after
`check_auth()`:

```python
    def resource_mappings(self) -> list[ResourceMapping]:
        """Declare how agent resources are shared across projects.

        Returns a list of ResourceMapping entries describing which paths
        within the agent's home directory are shared, project-scoped, or
        seeded from workset defaults.

        The default returns an empty list, meaning all agent resources
        are treated as project-scoped (the current behavior).

        Paths are relative to the agent's config directory within the
        project shell (e.g. ".claude/" for ClaudeTarget).
        """
        return []
```

**Step 4: Run tests to verify they pass**

Run: `~/.venv/bin/pytest tests/test_targets/test_base.py::TestTargetABC -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/kanibako/targets/base.py tests/test_targets/test_base.py
git commit -m "Add resource_mappings() method to Target ABC with empty default"
```

---

### Task 3: Implement `resource_mappings()` in `ClaudeTarget`

**Files:**
- Modify: `src/kanibako/targets/claude.py`
- Modify: `tests/test_targets/test_claude.py`

**Step 1: Write the failing tests**

Add to `tests/test_targets/test_claude.py`:

```python
from kanibako.targets.base import ResourceMapping, ResourceScope


class TestResourceMappings:
    def test_returns_list(self):
        t = ClaudeTarget()
        mappings = t.resource_mappings()
        assert isinstance(mappings, list)
        assert len(mappings) > 0

    def test_all_entries_are_resource_mappings(self):
        t = ClaudeTarget()
        for m in t.resource_mappings():
            assert isinstance(m, ResourceMapping)

    def test_shared_resources(self):
        """Plugin binaries, cache, stats, statsig, telemetry are shared."""
        t = ClaudeTarget()
        mappings = {m.path: m.scope for m in t.resource_mappings()}
        assert mappings["plugins/"] == ResourceScope.SHARED
        assert mappings["cache/"] == ResourceScope.SHARED
        assert mappings["stats-cache.json"] == ResourceScope.SHARED
        assert mappings["statsig/"] == ResourceScope.SHARED
        assert mappings["telemetry/"] == ResourceScope.SHARED

    def test_seeded_resources(self):
        """settings.json and CLAUDE.md are seeded from workset."""
        t = ClaudeTarget()
        mappings = {m.path: m.scope for m in t.resource_mappings()}
        assert mappings["settings.json"] == ResourceScope.SEEDED
        assert mappings["CLAUDE.md"] == ResourceScope.SEEDED

    def test_project_resources(self):
        """Session data, history, tasks, etc. are project-scoped."""
        t = ClaudeTarget()
        mappings = {m.path: m.scope for m in t.resource_mappings()}
        project_paths = [
            "projects/", "session-env/", "history.jsonl", "tasks/",
            "todos/", "plans/", "file-history/", "backups/",
            "debug/", "paste-cache/", "shell-snapshots/",
        ]
        for path in project_paths:
            assert mappings[path] == ResourceScope.PROJECT, f"{path} should be PROJECT"
```

**Step 2: Run tests to verify they fail**

Run: `~/.venv/bin/pytest tests/test_targets/test_claude.py::TestResourceMappings -v`
Expected: FAIL (empty list returned)

**Step 3: Write implementation**

Add to `ClaudeTarget` in `src/kanibako/targets/claude.py`, after
`check_auth()` and before `refresh_credentials()`. Also add the
import at the top:

Add to imports:
```python
from kanibako.targets.base import AgentInstall, Mount, ResourceMapping, ResourceScope, Target
```

Method:
```python
    def resource_mappings(self) -> list[ResourceMapping]:
        """Declare Claude Code resource sharing scopes.

        Shared: plugin binaries, caches, telemetry (identical across projects).
        Seeded: settings.json, CLAUDE.md (copied from workset template at creation).
        Project: conversation history, session data, tasks (per-project state).
        """
        return [
            # Shared at workset/account level
            ResourceMapping("plugins/", ResourceScope.SHARED, "Plugin binaries and registry"),
            ResourceMapping("cache/", ResourceScope.SHARED, "General cache"),
            ResourceMapping("stats-cache.json", ResourceScope.SHARED, "Usage stats cache"),
            ResourceMapping("statsig/", ResourceScope.SHARED, "Feature flags"),
            ResourceMapping("telemetry/", ResourceScope.SHARED, "Telemetry data"),
            # Seeded from workset template at project creation
            ResourceMapping("settings.json", ResourceScope.SEEDED, "Permissions and enabled plugins"),
            ResourceMapping("CLAUDE.md", ResourceScope.SEEDED, "Agent instructions template"),
            # Project-specific (fresh per project)
            ResourceMapping("projects/", ResourceScope.PROJECT, "Session data and memory"),
            ResourceMapping("session-env/", ResourceScope.PROJECT, "Session environment state"),
            ResourceMapping("history.jsonl", ResourceScope.PROJECT, "Conversation history"),
            ResourceMapping("tasks/", ResourceScope.PROJECT, "Task tracking"),
            ResourceMapping("todos/", ResourceScope.PROJECT, "Todo lists"),
            ResourceMapping("plans/", ResourceScope.PROJECT, "Plan mode files"),
            ResourceMapping("file-history/", ResourceScope.PROJECT, "File edit history"),
            ResourceMapping("backups/", ResourceScope.PROJECT, "File backups"),
            ResourceMapping("debug/", ResourceScope.PROJECT, "Debug logs"),
            ResourceMapping("paste-cache/", ResourceScope.PROJECT, "Clipboard state"),
            ResourceMapping("shell-snapshots/", ResourceScope.PROJECT, "Shell state snapshots"),
        ]
```

**Step 4: Run tests to verify they pass**

Run: `~/.venv/bin/pytest tests/test_targets/test_claude.py::TestResourceMappings -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `~/.venv/bin/pytest tests/ -v`
Expected: 738 passed (no regressions — existing tests should not break
since resource_mappings() is additive and nothing calls it yet)

**Step 6: Run lint and type check**

Run: `ruff check src/ tests/ && mypy src/kanibako/`
Expected: All checks passed

**Step 7: Commit**

```bash
git add src/kanibako/targets/claude.py tests/test_targets/test_claude.py
git commit -m "Implement resource_mappings() in ClaudeTarget"
```

---

### Task 4: Update `__init__.py` exports and example targets

**Files:**
- Modify: `src/kanibako/targets/__init__.py`
- Modify: `tests/test_targets/test_base.py` (verify import path)

**Step 1: Write the failing test**

Add to `tests/test_targets/test_base.py`:

```python
class TestPublicExports:
    def test_resource_types_importable_from_package(self):
        from kanibako.targets import ResourceMapping, ResourceScope
        assert ResourceScope.SHARED.value == "shared"
        rm = ResourceMapping(path="x", scope=ResourceScope.PROJECT)
        assert rm.path == "x"
```

**Step 2: Run test to verify it fails**

Run: `~/.venv/bin/pytest tests/test_targets/test_base.py::TestPublicExports -v`
Expected: FAIL with ImportError

**Step 3: Write implementation**

Update `src/kanibako/targets/__init__.py`:

```python
from kanibako.targets.base import AgentInstall, Mount, ResourceMapping, ResourceScope, Target

__all__ = [
    "AgentInstall", "Mount", "ResourceMapping", "ResourceScope", "Target",
    "discover_targets", "get_target", "resolve_target",
]
```

**Step 4: Run test to verify it passes**

Run: `~/.venv/bin/pytest tests/test_targets/test_base.py::TestPublicExports -v`
Expected: PASS

**Step 5: Run full suite + lint + mypy**

Run: `~/.venv/bin/pytest tests/ -v && ruff check src/ tests/ && mypy src/kanibako/`
Expected: All pass

**Step 6: Commit**

```bash
git add src/kanibako/targets/__init__.py tests/test_targets/test_base.py
git commit -m "Export ResourceMapping and ResourceScope from targets package"
```

---

### Task 5: Update third-party target examples and docs

**Files:**
- Modify: `docs/writing-targets.md` (add resource_mappings section)
- Review: `examples/kanibako-target-*/` (no changes needed — default
  empty list is correct for examples that don't declare resource sharing)

**Step 1: Check that example targets still work with the new ABC**

The `resource_mappings()` method has a default implementation (returns
`[]`), so existing targets that don't override it will continue to work.
Verify by running example tests if they exist:

Run: `~/.venv/bin/pytest examples/ -v 2>/dev/null || echo "No example tests in pytest path"`

**Step 2: Update docs/writing-targets.md**

Add a new section after the existing method documentation:

```markdown
### `resource_mappings() -> list[ResourceMapping]`

*Optional.* Declare how agent resources should be shared across projects.

Returns a list of `ResourceMapping` entries, each mapping a path within
the agent's config directory to a `ResourceScope`:

- `SHARED` — shared at the workset/account level (e.g. plugin binaries)
- `PROJECT` — per-project, starts fresh (e.g. conversation history)
- `SEEDED` — per-project, but seeded from the workset template at
  project creation (e.g. agent settings)

The default returns an empty list, meaning all agent resources are
treated as project-scoped.

```python
from kanibako.targets.base import ResourceMapping, ResourceScope

def resource_mappings(self) -> list[ResourceMapping]:
    return [
        ResourceMapping("plugins/", ResourceScope.SHARED, "Shared plugins"),
        ResourceMapping("config.json", ResourceScope.SEEDED, "Agent config"),
        ResourceMapping("history/", ResourceScope.PROJECT, "Session history"),
    ]
```
```

**Step 3: Commit**

```bash
git add docs/writing-targets.md
git commit -m "Document resource_mappings() in target plugin guide"
```

---

## Verification

After all tasks, run full verification:

```bash
ruff check src/ tests/
mypy src/kanibako/
~/.venv/bin/pytest tests/ -v
```

Expected: all lint clean, no type errors, 738+ tests passing.
