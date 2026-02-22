# Code Review Findings

**Date:** 2026-02-21
**Reviewer:** Claude
**Codebase:** kanibako v0.5.0 (38 source modules, 6,791 LOC)

## Tier 1 — Core Utilities

### `errors.py` — Fine as-is
Clean exception hierarchy. All classes used except `CredentialError` (see Consider).

### `log.py` — Fine as-is
Two functions, both tested, both used. No issues.

### `utils.py` — Fine as-is
All five public functions tested and used. Minor inconsistency: `stderr()` helper exists but the rest of the codebase uses `print(..., file=sys.stderr)` directly (see Consider).

### `registry.py` — Fine as-is
Clean single-purpose module. Network errors properly swallowed. Well tested.

### `containerfiles.py` — Fine as-is
Both public functions used and tested. Minor latent inconsistency in suffix extraction between bundled and override paths (see Consider).

### `shellenv.py` — Fine as-is
Clean read-modify-write pattern. All functions tested with edge cases.

### `snapshots.py` — Fix
Three unused imports: `os`, `subprocess`, `sys` (lines 10-13). All path operations use `pathlib.Path`. Otherwise clean and well-tested.

### `git.py` — Fine as-is
All public symbols tested and used. Minor style note: uses `Optional` import where `X | None` would be consistent with rest of codebase (see Consider).

## Tier 2 — Core Modules

### `credentials.py` — Fine as-is
Clean, well-structured, all functions used and tested. Atomic write via temp file + rename.

### `config.py` — Fine as-is (Consider)
Regex-based TOML key update (`write_project_config_key`) only handles quoted-string values and assumes unique key names across sections. Not broken today but fragile if config surface grows (see Consider).

### `workset.py` — Fine as-is
Clean data model with good separation between serialization and public API.

### `paths.py` — Fine as-is (Consider)
854 LOC. Has a natural split point (core resolution vs multi-mode extensions) but the halves are tightly coupled — splitting would not reduce complexity meaningfully. Three init functions (`_init_project`, `_init_workset_project`, `_init_decentralized_project`) share ~12 lines of identical code; `_init_project` and `_init_decentralized_project` differ by only 2 lines (breadcrumb write). `_xdg` is private by name but imported by 13 modules (see Consider).

### `container.py` — Fine as-is
All public methods used. Minor: `guess_containerfile` is a thin wrapper around `_guess_containerfile`.

### `freshness.py` — Fine as-is
Small, focused, well-tested. 24h cache is correct.

## Tier 3 — Targets

### `targets/base.py` — Fine as-is
Clean ABC. All abstract methods implemented by ClaudeTarget. `check_auth()` default returning `True` is a pragmatic choice.

### `targets/claude.py` — Fine as-is (Consider)
All methods correct, thorough tests. `import json` is deferred into method body unlike other stdlib imports at module top (see Consider). Missing test coverage for `TimeoutExpired`/`JSONDecodeError` branches in `check_auth()` (low risk — they return `True`).

### `targets/__init__.py` — Fine as-is
Plugin discovery works. Auto-detect iteration order is deterministic for single target; would need documentation if a second target is added.

## Tier 4 — Commands

### `start.py` — Fine as-is
`_run_container()` is ~198 lines but reads as a clear sequential pipeline. Breaking it up would scatter the flow across helpers with lots of parameter passing. No split needed.

### `box.py` — Fix + Consider
1,070 LOC. **Fix:** Dead `import os` in `_run_duplicate_cross_mode` (line 655). **Consider:** Natural split into `box_list.py`, `box_migrate.py`, `box_duplicate.py` — but current organization with section comments is workable. Duplication across convert/duplicate helpers is structural similarity, not extractable.

### `init.py` — Fine as-is
Clean, well-tested.

### `status.py` — Fine as-is
Clean, readable, good aligned output formatting.

### `image.py` — Fine as-is (Consider)
Cosmetic: `elif not owner and image:` — `not owner` is redundant after prior `if owner:` check.

### `archive.py` — Fine as-is
No duplication with restore.py. Clean handling of both AC and workset projects.

### `restore.py` — Fine as-is (Consider)
`_peek_archive_info` docstring says "without full extraction" but performs full extraction. Either fix docstring or optimize.

### `stop.py` — Consider
Uses `resolve_project` (AC-only) instead of `resolve_any_project`. A user running `kanibako stop` from a decentralized or workset project may get wrong container name. Potential behavioral bug.

### `clean.py` — Fine as-is
Clean, well-tested.

### `config_cmd.py` — Fine as-is (Consider)
`_clear_config` doesn't locally catch `UserCancelled` — works via CLI dispatcher but inconsistent with other commands.

### `vault_cmd.py` — Fine as-is
Clean subcommand dispatch.

### `env_cmd.py` — Fine as-is
Clean, conventional.

### `refresh_credentials.py` — Fine as-is
Tiny delegation module. Minimal test adequate.

### `workset_cmd.py` — Fine as-is
Clean, all 6 subcommands tested.

### `install.py` — Fine as-is
Clean setup flow with good section comments.

### `remove.py` — Fine as-is
Small, focused.

### `upgrade.py` — Fine as-is
Well-structured, safe `--ff-only` default.

## Tier 5 — Entry Points

### `__init__.py` — Fine as-is
Version matches pyproject.toml. `bump2version` keeps them in sync.

### `cli.py` — Fine as-is
All 17 subcommands registered. `-v/--verbose` handled correctly. No dead exports.

### `__main__.py` — Fine as-is (Consider)
Bare `main()` call at module level; `if __name__ == "__main__":` guard would be more conventional but low risk.

### `-E/--entrypoint` visibility — Fix
Standing instruction #2 says `-E/--entrypoint` should be hidden from help. Currently all four flag names (`-c`, `--command`, `-E`, `--entrypoint`) share one `add_argument` call, making `-E` visible. Needs a separate `add_argument` with `help=argparse.SUPPRESS`.

---

## Summary

### Fix (must change)

1. **`snapshots.py`** — Remove unused imports `os`, `subprocess`, `sys` (lines 10-13)
2. **`box.py`** — Remove dead `import os` in `_run_duplicate_cross_mode` (line 655)
3. **`start.py` parser** — Hide `-E/--entrypoint` from `--help` per standing instruction #2

### Consider (user decision)

1. **`stop.py`** — Use `resolve_any_project` instead of `resolve_project` to support decentralized/workset projects. This is the closest thing to an actual bug found in the review.
2. **`paths.py`** — Unify `_init_project` and `_init_decentralized_project` (differ by 2 lines). Reduces ~35 lines of duplication.
3. **`paths.py`** — Rename `_xdg` to public name (e.g. `xdg` or `resolve_xdg_dir`) since 13 modules import it.
4. **`errors.py`** — Remove unused `CredentialError` class (dead code).
5. **`restore.py`** — Fix `_peek_archive_info` docstring (claims "without full extraction" but does full extraction).
6. **`config.py`** — Add comment documenting `write_project_config_key` constraints (string-only values, unique key names).
7. **`targets/claude.py`** — Move `import json` to module-level imports for consistency.
8. **`utils.py`** — Either adopt `stderr()` helper codebase-wide or remove it and use `print(..., file=sys.stderr)` directly.
9. **`box.py`** — Consider splitting into 3 files (~350 LOC each) if size becomes a maintenance burden.
10. **`image.py`** — Simplify `elif not owner and image:` to `elif image:` (cosmetic).
11. **`git.py`** — Use `X | None` instead of `Optional[X]` for style consistency. **DEFERRED** — requires broader discussion about codebase-wide typing convention.
12. **`__main__.py`** — Add `if __name__ == "__main__":` guard.
13. **`config_cmd.py`** — Add local `UserCancelled` handling in `_clear_config` for consistency.
14. **`containerfiles.py`** — Align suffix extraction logic between bundled and override paths.

### Fine as-is

`errors.py`, `log.py`, `registry.py`, `shellenv.py`, `credentials.py`, `workset.py`, `container.py`, `freshness.py`, `targets/base.py`, `targets/__init__.py`, `init.py`, `status.py`, `archive.py`, `clean.py`, `vault_cmd.py`, `env_cmd.py`, `refresh_credentials.py`, `workset_cmd.py`, `install.py`, `remove.py`, `upgrade.py`, `__init__.py`, `cli.py`
