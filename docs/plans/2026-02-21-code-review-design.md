# Code Review + Targeted Cleanup

**Date:** 2026-02-21
**Goal:** Post-build hygiene pass after 10 phases of development. Ensure code is fresh and ready to build on.
**Driver:** Maintainability, not pain. Nothing is broken; this is preventive.

## Approach: Review-then-fix

### Phase 1 — Module-by-module review

Walk all 38 source modules in dependency order (core first, then commands, then targets). For each module assess:

- Dead code / unused exports
- Actual duplication (not just structural similarity)
- Confusing or unnecessarily complex logic
- Inconsistencies (naming, patterns, error handling)
- Anything that would trip someone up reading it fresh

Produce findings grouped by severity:

- **Fix:** Genuinely needs changing (dead code, real bugs, misleading names)
- **Consider:** Would improve clarity but not strictly necessary
- **Fine as-is:** Reviewed and acceptable

### Phase 2 — Targeted fixes

Implement only "Fix" items. Present "Consider" items for user decision. Leave "Fine as-is" alone.

## Constraints

- No new abstractions or design patterns unless they eliminate real duplication
- File splits are warranted if a file is unwieldy and has a natural division point
- All tests must pass after every change
- No touching test code unless tests cover dead code
- No refactoring for its own sake — if it's fine, it's fine

## Codebase snapshot

- 38 source modules, 6,791 LOC
- 52 test modules, 12,021 LOC (738 unit + 35 integration)
- Largest files: box.py (1,070), paths.py (854), start.py (336)
- No circular dependencies, no TODO/FIXME markers
- Test-to-code ratio: 1.77:1
