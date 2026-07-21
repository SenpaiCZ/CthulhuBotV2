# Phase 5 — Conventions & Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `CLAUDE.md` and a new `docs/CONTRIBUTING.md` up to date with the architecture that Phases 1-4 produced (dashboard blueprint split, `commands/_foo.py` companion-file convention, shared `dashboard/state.py`, and the test-suite conventions established across Phases 0 and 4), so a future contributor (human or agent) can navigate and extend the codebase without re-deriving these patterns from scratch.

**Architecture:** This is a documentation-only phase — no source files are created, modified, or deleted. Two files change: `CLAUDE.md` (existing, edited in place) and `docs/CONTRIBUTING.md` (new). Every claim written into either file must be verified against the actual current repo state before being written, and re-verified in a final pass.

**Tech Stack:** Markdown only. No code, no tests in the pytest sense — "testing" a step in this plan means running a `grep`/`ls`/`wc` command against the real repo and confirming the documented claim matches reality.

## Global Constraints

- Per the original design spec (`docs/superpowers/specs/2026-07-18-maintainability-refactor-design.md`, Phase 5 section): update `CLAUDE.md` with the new module map (blueprints, companion `_foo.py` files, shared-state module) and add a short internal styleguide codifying the `_foo.py` convention and the blueprint/cog-split pattern, in `CLAUDE.md` or a new `docs/CONTRIBUTING.md`.
- **Zero source-code changes.** This phase touches only `CLAUDE.md` and `docs/CONTRIBUTING.md`. If a task's verification step reveals the docs and the code disagree, fix the docs — never "fix" the code to match a doc draft.
- Every file path, class name, and line-count claim written into either doc must be independently checkable via a command in that same task (grep, `wc -l`, `ls`) — no claims from memory or from an earlier phase's summary without re-verification, since multiple files were touched or renamed across Phases 1-4 after this plan's author last looked at them directly.
- Match the existing tone and structure of `CLAUDE.md`: short prose, bullet lists, no marketing language (that's what `README.md` is for), file-path-first ("`dashboard/state.py` — ...", not "The state module...").
- Installed discord.py in this repo is **2.7.1**, not the 2.6.4 the Phase 4 plan's Global Constraints section assumed — this was discovered and independently confirmed by three separate Phase 4 batch reviewers (Batches 8, 9, 10). Any testing-convention documentation written in this phase must state 2.7.1 as the actual installed version.

---

### Task 1: Update `CLAUDE.md`'s Dashboard, Commands, and Character System sections

**Files:**
- Modify: `CLAUDE.md` (Dashboard section, Commands section, Character System section)

**Interfaces:**
- Consumes: nothing from other tasks in this plan.
- Produces: an accurate architecture description that Task 3's final cross-check reads against.

This task corrects three sections of `CLAUDE.md` that describe pre-Phase-1/pre-Phase-2 architecture and are now factually wrong: the Dashboard section still says `app.py` holds "all web routes + API endpoints" (it's now a 297-line composition root; routes live in 24 files under `dashboard/blueprints/`), the Commands section doesn't mention the newer companion-file split from Phase 2, and the Character System section says `ERA_SKILLS` is defined in `newinvestigator.py` (it moved to `commands/_newinvestigator_data.py` in Phase 2 Task 2).

- [ ] **Step 1: Verify the current claims are stale**

Run:
```bash
grep -n "all web routes" CLAUDE.md
grep -n "Era skill base values defined in \`newinvestigator.py\`" CLAUDE.md
wc -l dashboard/app.py
ls dashboard/blueprints/*.py | wc -l
grep -n "^ERA_SKILLS" commands/_newinvestigator_data.py
```
Expected: the two `grep -n` calls against `CLAUDE.md` each print one matching line (confirming the stale claims exist verbatim); `dashboard/app.py` is under 320 lines; `dashboard/blueprints/*.py` lists 24 files (23 feature blueprints + `__init__.py`); `ERA_SKILLS` is found in `commands/_newinvestigator_data.py`, not in `commands/newinvestigator.py`.

- [ ] **Step 2: Replace the Dashboard section**

In `CLAUDE.md`, replace the existing block:
```markdown
### Dashboard: `dashboard/`
- `app.py` — Quart app; all web routes + API endpoints. Imports heavily from `loadnsave`. Shares `guild_mixers` and `server_volumes` dicts with the music cog.
- `audio_mixer.py` — `MixingAudioSource`: FFmpeg-based audio source that mixes music + soundboard streams
- `file_utils.py` — sync file ops for dashboard use (upload, extract zip, rename, delete)
```
with:
```markdown
### Dashboard: `dashboard/`
- `app.py` — composition root only (~300 lines): Quart app instance, security/CSRF/auth `before_request`/`after_request` hooks, template filters, context processors, and blueprint registration. It never defines a route directly.
- `blueprints/` — one file per feature area (24 files), each a Quart `Blueprint` registered in `app.py` near the bottom of the file. Every dashboard route lives in exactly one of these files, grouped by feature (e.g. all `/admin/karma` + `/api/karma/*` routes are in `karma.py`). Blueprints import `app` and other shared helpers back from `dashboard.app` — this circular-looking import is intentional and safe as long as `dashboard.app` (not a blueprint module) is always imported first, which is how `bot.py` and every test in this repo already does it.
- `state.py` — shared mutable state that must keep single, consistent object identity across `dashboard/app.py`, every blueprint that touches it, and the `commands/` cogs that also read/write it: `guild_mixers` and `server_volumes` (both shared with `commands/music.py`; `server_volumes` also with `commands/roll.py`), plus folder-path/constant globals (`IMAGES_FOLDER`, `FONTS_FOLDER`, `OLD_FONTS_FOLDER`, `BACKUP_FOLDER`, `SOUNDBOARD_FOLDER`, `BASIC_FONTS`, `MORSE_CODE_MAP`, `_PUBLIC_API`). Import these by reference (`from dashboard.state import server_volumes`, then mutate in place with `.update()`/`[key] = value`) — never rebind the name (`server_volumes = {...}` inside a consuming module breaks the shared identity every other importer relies on).
- `audio_mixer.py` — `MixingAudioSource`: FFmpeg-based audio source that mixes music + soundboard streams
- `file_utils.py` — sync file ops for dashboard use (upload, extract zip, rename, delete)

See `docs/CONTRIBUTING.md` for the step-by-step process to add a new dashboard route.
```

- [ ] **Step 3: Replace the Commands section**

In `CLAUDE.md`, replace the existing block:
```markdown
### Commands: `commands/`
Each file is a discord.py Cog loaded as an extension. Naming conventions:
- `_foo.py` prefix = shared View/UI helpers imported by other commands (not standalone Cogs)
- Uses `app_commands` (slash) + legacy `commands` (prefix) mixed
```
with:
```markdown
### Commands: `commands/`
Each file is a discord.py Cog loaded as an extension. Naming conventions:
- `_foo.py` prefix = a companion module holding `discord.ui.View`/`Modal`/`Select` classes split out of an oversized parent Cog file, or other shared helpers imported by other commands — **not** a standalone Cog. `bot.py` still tries to load every `.py` file in `commands/` as an extension, so a companion file must never define its own `async def setup(bot)`.
- Classes a companion file's parent Cog constructs directly are imported *by name* into the Cog module (`from commands._newinvestigator_stats import CoreStatSelectView`); classes only ever constructed by another class *within the same companion file* don't need a Cog-level import.
- A Cog occasionally imports a UI class from a companion file that isn't its own — e.g. `commands/combat.py` and `commands/_mychar_roll.py` both import `RollResultView` from `commands/_roll_views.py`, not from `commands/roll.py`'s own file. Grep the whole repo, not just the file you're editing, before assuming a class's only consumer is its original parent.
- Uses `app_commands` (slash) + legacy `commands` (prefix) mixed

Companion-file clusters as of this writing: `commands/newinvestigator.py`'s wizard splits across `_newinvestigator_data.py` (era/skill constants), `_newinvestigator_basicinfo.py`, `_newinvestigator_gamemode.py`, `_newinvestigator_stats.py`, `_newinvestigator_talents.py`, `_newinvestigator_skills.py`, `_newinvestigator_occupation.py`; `commands/roll.py` → `_roll_views.py`; `commands/codex.py` → `_codex_views.py`; `commands/karma.py` → `_karma_views.py`; `commands/journal.py` → `_journal_views.py`; `commands/mycharacter.py`'s `_mychar_view.py` hub further splits into `_mychar_inventory.py` and `_mychar_roll.py`.

See `docs/CONTRIBUTING.md` for the step-by-step process to add a new command or split a growing Cog.
```

- [ ] **Step 4: Update the Character System section**

In `CLAUDE.md`, replace the existing block:
```markdown
### Character System
- `commands/newinvestigator.py` — multi-step modal wizard; handles eras (1920s/1930s/Modern), occupations, stat rolling, skill allocation
- `commands/roll.py` — dice + skill checks; uses `rapidfuzz` for fuzzy skill name matching
- `descriptions.py` — maps stat values to flavor descriptions (thresholds, not exact match)
- Era skill base values defined in `newinvestigator.py` as `ERA_SKILLS` dict
```
with:
```markdown
### Character System
- `commands/newinvestigator.py` — multi-step modal wizard hub Cog; handles eras (1920s/1930s/Modern), occupations, stat rolling, skill allocation. Wizard-stage View/Modal classes live in the sibling `commands/_newinvestigator_*.py` companion files (see Commands section above), not in this file.
- `commands/roll.py` — dice + skill checks; uses `rapidfuzz` for fuzzy skill name matching. UI classes (roll-result view, dice tray, disambiguation) live in `commands/_roll_views.py`.
- `descriptions.py` — maps stat values to flavor descriptions (thresholds, not exact match)
- Era skill base values live in `commands/_newinvestigator_data.py` as `ERA_SKILLS` (per-era dict) and `BASE_SKILLS` (the 1920s era, aliased as the default baseline). This is game-balance-sensitive static data — treat changes to it as game-content changes, not refactors, and keep it byte-identical across any future file move.
```

- [ ] **Step 5: Verify the edits landed and re-check the claims that changed**

Run:
```bash
grep -c "all web routes" CLAUDE.md
grep -n "commands/_newinvestigator_data.py" CLAUDE.md
grep -n "commands/_roll_views.py" CLAUDE.md
```
Expected: first command prints `0` (the stale claim is gone); the other two each print at least one matching line from the edits just made.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md dashboard/commands architecture for Phases 1-2 blueprint and companion-file split"
```

---

### Task 2: Add a Testing section to `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md` (new section, insert after the Character System / Auto-Restart sections, before "## Adding a New Command")

**Interfaces:**
- Consumes: nothing from Task 1's edits directly (independent section), but should be inserted after Task 1's edits are committed to avoid a merge conflict in the same file region.
- Produces: the testing-conventions reference that Task 3 spot-checks.

Phases 0 and 4 established real, non-obvious testing conventions (Quart CSRF/session-auth pattern, discord.py 2.7.1 UI-construction quirks, patch-target discipline, `DATA_FOLDER` isolation) that exist only in `.superpowers/sdd/progress.md` (a gitignored, non-shippable file) and in the test files themselves. This task lifts the durable parts into `CLAUDE.md` so they survive independently of that ledger.

- [ ] **Step 1: Verify the claims before writing them**

Run:
```bash
ls tests/*.py | wc -l
python -c "import discord; print(discord.__version__)" 2>/dev/null || .venv/bin/python -c "import discord; print(discord.__version__)"
grep -rn "session_transaction" tests/test_blueprint_karma.py | head -3
grep -rn "_values = \[" tests/test_commands_roll_views.py | head -3
grep -rn "component._value" tests/test_commands_newinvestigator_occupation.py | head -3
```
Expected: `tests/*.py` count is 57 or more (57 as of Phase 4's completion; may be higher if more tests were added since); the discord.py version prints `2.7.1` (or whatever is currently installed — if it differs, use the real installed version in Step 2's content, not the value written in this plan); the three `grep` calls each find at least one match, confirming the patterns described below are real, not aspirational.

- [ ] **Step 2: Insert the Testing section**

In `CLAUDE.md`, insert this new section immediately after the `### Auto-Restart` section and before `## Adding a New Command`:
```markdown
## Testing

- `pytest` (+ `pytest-asyncio`) — run `python -m pytest -q` from repo root (use the project's `.venv` if one exists: `.venv/bin/python -m pytest -q`).
- One test file per source module, named after it: `dashboard/blueprints/karma.py` → `tests/test_blueprint_karma.py`; `commands/_karma_views.py` → `tests/test_commands_karma_views.py`. A `_gaps` suffix (e.g. `test_render_blueprint_gaps.py`) marks a file that supplements — not replaces — coverage already present in an earlier same-module test file; check for an existing non-`_gaps` file before creating a new one.
- **Dashboard route tests** use Quart's test client against the real blueprint-registered `app` from `dashboard.app`. Any mutating route needs two things to pass the app's `before_request` hooks: a `login(client)` helper (sets `session['logged_in'] = True` via `session_transaction()`) for `check_api_auth`, and an `Origin` header matching the test client's host for `check_csrf`.
- **discord.py UI-class tests** (Views/Modals/Selects) construct the real class directly — never go through `dashboard.app` or a Cog's slash-command entry point for this. Mock only `discord.Interaction` and the specific `.response`/`.followup` methods the code under test actually calls (grep the source for every `interaction.response.*`/`interaction.followup.*` call site first — a shared fixture that mocks only the method one test happens to need will `TypeError` on a sibling test that hits an unmocked one). Installed discord.py is **2.7.1**: `BaseView.__init__` swallows the `asyncio.get_running_loop()` `RuntimeError` when called outside a running loop rather than raising it, so both sync and `@pytest.mark.asyncio` test functions can construct a View/Modal — but any test that `await`s a callback still needs `@pytest.mark.asyncio`. A `View`'s decorated buttons/selects (`@discord.ui.button`, `@discord.ui.select`) are added to `.children` during `super().__init__()`, *before* the constructor body's own `self.add_item(...)` calls run — don't assume `view.children[0]` is the item you `add_item`'d; use `next(c for c in view.children if isinstance(c, TargetClass))` when order isn't guaranteed. Simulate a Select choice with `select._values = [...]`. For a Modal field wrapped in `discord.ui.Label`, set `modal.field_name.component._value`, not `modal.field_name._value` (the Label itself has no `_value`).
- `mock.patch()` / `monkeypatch.setattr()` must target the module where the code under test *looks the name up*, not where the name is defined — e.g. a value imported into `dashboard/blueprints/karma.py` gets patched at `dashboard.blueprints.karma.<name>`, not at `loadnsave.<name>` where it's originally defined.
- Any test that writes through `loadnsave`'s `data/` folder must isolate via a `DATA_FOLDER` monkeypatch fixture pointed at `tmp_path` — patch **both** `loadnsave.DATA_FOLDER` **and** any blueprint/module that separately imports `DATA_FOLDER` by value (some do; check with `grep -n "^from loadnsave import.*DATA_FOLDER\|^DATA_FOLDER" <module>.py` before assuming one patch site covers it), or a test can silently write into the repository's real `data/` folder.
- Never use `MagicMock(name="Something")` expecting `mock.name == "Something"` — `name=` is a reserved `Mock` constructor kwarg (controls `repr()`, not a real attribute). Set it after construction instead: `mock.name = "Something"`.
```

- [ ] **Step 3: Verify placement and content**

Run:
```bash
grep -n "^## Testing$" CLAUDE.md
grep -n "^## Adding a New Command$" CLAUDE.md
```
Expected: both lines are found, and the line number for `## Testing` is smaller than (comes before) the line number for `## Adding a New Command`.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Testing conventions section to CLAUDE.md"
```

---

### Task 3: Create `docs/CONTRIBUTING.md` styleguide and final cross-check

**Files:**
- Create: `docs/CONTRIBUTING.md`
- Verify (no modification expected unless Step 5 finds a discrepancy): `CLAUDE.md`

**Interfaces:**
- Consumes: the section structure and terminology established in Tasks 1 and 2 (this task's content cross-references `CLAUDE.md`'s Testing section by name, so Tasks 1-2 must land first).
- Produces: nothing consumed by a later task — this is the last task in the phase.

This task adds the actual step-by-step "how do I add X" walkthroughs that `CLAUDE.md`'s architecture sections now point to, and closes the phase with a repo-wide verification pass confirming every file path and class name referenced across both documents still exists.

- [ ] **Step 1: Verify the docs/ directory state before creating the file**

Run:
```bash
ls docs/
test -f docs/CONTRIBUTING.md && echo "EXISTS — STOP, do not overwrite" || echo "OK — safe to create"
```
Expected: `docs/` lists `superpowers` (and possibly other pre-existing entries); the second command prints `OK — safe to create`. If it instead prints the STOP message, read the existing file first and treat this step as an edit, not a fresh create.

- [ ] **Step 2: Create `docs/CONTRIBUTING.md`**

```markdown
# Contributing to CthulhuBotV2

Internal conventions for extending this codebase. See `CLAUDE.md` for the module map and architecture overview — this file is the step-by-step "how do I add X" companion to it.

## Adding a new dashboard route

1. Find (or create) the matching `dashboard/blueprints/<feature>.py` file — one file per feature area (e.g. all karma routes live in `karma.py`, all giveaway routes in `giveaway.py`).
2. Define the route on that blueprint's `Blueprint` object, not on `app`:
   ```python
   from quart import Blueprint
   my_feature_bp = Blueprint('my_feature', __name__)

   @my_feature_bp.route('/admin/my_feature')
   async def admin_my_feature():
       ...
   ```
   `dashboard/app.py` never defines a route directly — if you're about to write `@app.route(...)` there, put it on a blueprint instead.
3. If the route needs shared mutable state (`guild_mixers`, `server_volumes`) or a folder-path constant (`IMAGES_FOLDER`, `BACKUP_FOLDER`, etc.), import it from `dashboard.state` — never redefine or re-derive it locally.
4. If this is a brand-new blueprint file (not an addition to an existing one), register it in `dashboard/app.py` near the bottom, alongside the other `from dashboard.blueprints.<x> import <x>_bp` / `app.register_blueprint(<x>_bp)` pairs.
5. If you're *moving* an existing route rather than adding a new one, update every `url_for('old_endpoint_name')` reference across the whole codebase (templates included) — Quart namespaces every blueprint endpoint as `<blueprint>.<name>`, even if the route was declared with an explicit `endpoint=` kwarg. A stale `url_for()` call raises `BuildError` at *request* time, not at import time, so it won't be caught by simply starting the app or importing the module.
6. Add or extend `tests/test_blueprint_<feature>.py` — see `CLAUDE.md`'s Testing section for the `login(client)` / `Origin` header / `DATA_FOLDER` isolation conventions that dashboard route tests need.

## Adding a new command, and when to split its UI classes out

1. If the Cog is small and self-contained, keep everything — the Cog class plus any `discord.ui.View`/`Modal`/`Select` classes it uses — in one `commands/<name>.py` file. Don't pre-split a file that doesn't need it yet.
2. Split UI classes into a sibling `commands/_<name>_<topic>.py` companion file once the parent Cog file has grown large enough that its own logic is hard to find among the UI class definitions (a few hundred lines is a reasonable trigger to reconsider, not a hard threshold). The leading underscore marks the file as a shared/internal module, **not** a standalone Cog.
3. A companion file must never define `async def setup(bot)` — `bot.py` tries to load every `.py` file directly under `commands/` as a discord.py extension, and a companion file with its own `setup()` will either fail to load or double-register commands.
4. In the companion file, import only what its own classes need — resist importing the whole parent module back in "just in case."
5. In the parent Cog file, import each companion class *by name* wherever the Cog constructs one directly: `from commands._newinvestigator_stats import CoreStatSelectView`. A class that is only ever constructed by another class *within the same companion file* (e.g. a `Select` a sibling `View` builds internally) doesn't need a Cog-level import — adding one anyway is dead-import clutter that the next reader has to figure out is safe to ignore.
6. Before finishing a split, grep the **whole repo**, not just `commands/`, for the class names you moved — a UI class is sometimes imported from a companion file by a *different* Cog than the one it was split out of (e.g. `commands/combat.py` and `commands/_mychar_roll.py` both import `RollResultView` from `commands/_roll_views.py`, not from `commands/roll.py`). Missing one of these is a `NameError` at runtime, not at import time, so it survives a casual smoke test.
7. Add or extend `tests/test_commands_<name>_<topic>.py` (companion file) and/or `tests/test_commands_<name>.py` (the Cog itself) — see `CLAUDE.md`'s Testing section for the discord.py 2.7.1 UI-construction conventions (`children[0]` ordering, `_values` for Selects, `.component._value` for `Label`-wrapped Modal fields).

## When *not* to split a file

Don't split a file just because it's long. Split when either is true:
- A reviewer could reasonably approve one part of the file while rejecting the other — i.e. the pieces are independently testable and independently changeable.
- The file mixes genuinely distinct responsibilities that different future changes will each touch on their own (a dashboard blueprint mixing two unrelated feature areas; a Cog file mixing command logic for two unrelated game systems).

A single handler or Cog method with a long, straight-line implementation is not by itself a reason to split. Three unrelated features awkwardly sharing one file because nobody moved them apart yet, is.
```

- [ ] **Step 3: Verify the new file was written correctly**

Run:
```bash
test -f docs/CONTRIBUTING.md && wc -l docs/CONTRIBUTING.md
grep -c "^## " docs/CONTRIBUTING.md
```
Expected: the file exists and is at least 30 lines long; the second command reports 3 (three `##`-level sections: "Adding a new dashboard route", "Adding a new command, and when to split its UI classes out", "When *not* to split a file").

- [ ] **Step 4: Commit the new file**

```bash
git add docs/CONTRIBUTING.md
git commit -m "docs: add CONTRIBUTING.md styleguide for blueprint routes and command companion-file splits"
```

- [ ] **Step 5: Final cross-check — every path/class name referenced in both docs actually exists**

Run each of the following and confirm every listed path/name resolves (no "No such file or directory", no empty grep result):
```bash
for f in dashboard/app.py dashboard/state.py dashboard/audio_mixer.py dashboard/file_utils.py \
         commands/_newinvestigator_data.py commands/_newinvestigator_basicinfo.py \
         commands/_newinvestigator_gamemode.py commands/_newinvestigator_stats.py \
         commands/_newinvestigator_talents.py commands/_newinvestigator_skills.py \
         commands/_newinvestigator_occupation.py commands/_roll_views.py \
         commands/_codex_views.py commands/_karma_views.py commands/_journal_views.py \
         commands/_mychar_view.py commands/_mychar_inventory.py commands/_mychar_roll.py \
         commands/newinvestigator.py commands/roll.py commands/combat.py commands/mycharacter.py \
         commands/codex.py commands/karma.py commands/journal.py \
         descriptions.py bot.py; do
  test -f "$f" && echo "OK: $f" || echo "MISSING: $f"
done
grep -n "class RollResultView" commands/_roll_views.py
grep -n "RollResultView" commands/combat.py commands/_mychar_roll.py
```
Expected: every line prints `OK: <path>`, none print `MISSING:`; the `RollResultView` class definition is found in `_roll_views.py`, and both `combat.py` and `_mychar_roll.py` reference it (confirming the cross-companion-file import example used in both `CLAUDE.md` and `docs/CONTRIBUTING.md` is accurate). If any `MISSING:` line appears or either `RollResultView` grep comes up empty, fix the corresponding claim in `CLAUDE.md` and/or `docs/CONTRIBUTING.md` before proceeding — do not leave a known-inaccurate doc claim in place.

- [ ] **Step 6: If Step 5 required a fix, commit it separately**

Only run this if Step 5 found and fixed a discrepancy:
```bash
git add CLAUDE.md docs/CONTRIBUTING.md
git commit -m "docs: fix inaccurate path/class reference found during Phase 5 final cross-check"
```
If Step 5 found no discrepancies, skip this step — there is nothing to commit.

---

## Self-Review Notes

- **Spec coverage:** the design spec's two Phase 5 bullets ("update CLAUDE.md with the new module map" and "add a short internal styleguide... codifying the `_foo.py` convention and the blueprint/service split") map onto Tasks 1-2 (module map) and Task 3 (styleguide) respectively. Both bullets are covered.
- **Placeholder scan:** no TBD/TODO markers; every step has literal file content or literal shell commands with a stated expected output.
- **Type consistency:** N/A — this plan produces prose, not code with signatures to keep consistent across tasks.
