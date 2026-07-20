# Phase 2 — Commands Cog Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the oversized `commands/` cog files (`newinvestigator.py` 1518 lines, `roll.py` 1154,
`codex.py` 1112, `karma.py` 880, `journal.py` 785, `_mychar_view.py` 1084) into a slim Cog file
(slash/prefix commands + business logic) plus one or more companion `_foo.py` files holding Discord
UI classes (`Modal`/`View`/`Select`), following the **existing, already-established** project
convention documented in `CLAUDE.md`: "`_foo.py` prefix = shared View/UI helpers imported by other
commands (not standalone Cogs)". Precedent already exists: `commands/_mychar_view.py`,
`commands/_backstory_common.py`, `commands/_codex_embeds.py`, `commands/_autoroom_view.py`,
`commands/_madness_view.py`, `commands/_music_view.py`. This phase applies that same pattern
consistently to the remaining oversized files — **zero behavior change**, no logic reshaping.

**Architecture:** Pure structural move, same discipline as Phase 1. Every task moves existing UI
class definitions **verbatim** (byte-for-byte body) out of a Cog file into a new `commands/_foo.py`
companion module, then updates the Cog file's imports so its command methods still reference the
same classes by the same names. Any file elsewhere in the repo that imports a moved class updates
its import path. No class logic, no command behavior, and no Discord-facing text changes.

**Tech Stack:** Python module imports only. No new dependencies. discord.py's `commands.Cog`,
`discord.ui.View`/`Modal`/`Select` classes are unaffected by which file they live in.

## Global Constraints

- **Zero behavior change.** Every slash/prefix command's behavior, every View/Modal's fields and
  callbacks, and every embed/message text must be identical before and after. This phase moves
  code; it does not refactor logic, rename anything user-facing, or fix bugs found along the way
  (log anything suspicious as a Minor/Tracked finding instead, per the Phase 0/Phase 1 precedent).
- Every task must leave the repo in a fully working state: `pytest -v` green, and — since Discord
  cogs can't be meaningfully smoke-tested via HTTP the way dashboard routes were — the Task 1
  cog-load regression sweep (below) is the safety net every subsequent task must keep passing.
- Companion file classes are **moved, not retyped** — cut the exact existing class definition out
  of the source file and paste it into the new file unchanged. Only the plumbing changes: import
  statements at the top of both files.
- **Import-path discipline (the Phase 1 `url_for`-namespacing equivalent for this phase):** any
  class a Cog's own command/callback methods reference by bare name (e.g. `BasicInfoStartView(...)`)
  must be imported **by name** into the Cog module (`from commands._newinvestigator_basicinfo import
  BasicInfoStartView`), not accessed via a module alias — because
  `tests/test_data_schema.py:53` does `patch("commands.newinvestigator.BasicInfoStartView")`,
  which requires that exact name to exist as an attribute of the `commands.newinvestigator` module
  after the split. Every task below states explicitly which classes need this treatment.
- **Cross-file import fix-ups required by this phase** (found via full dependency-mapping research
  before this plan was written — treat as ground truth, not to be re-derived per task):
  - `RollResultView` (moving out of `commands/roll.py` into `commands/_roll_views.py`) is imported
    by `commands/combat.py:8` and `commands/_mychar_view.py:10` — both need their import line
    updated to the new module path.
  - `CharacterDashboardView` stays in `commands/_mychar_view.py` (not moved) — `commands/mycharacter.py:5`'s
    import is unaffected.
  - No other file in `commands/` or `dashboard/` imports classes from `codex.py`, `karma.py`, or
    `journal.py` (confirmed via repo-wide search) — those three tasks have no external fix-ups.
- **Known dead code, do not delete:** `KarmaActionsView` (top of `commands/karma.py`, line 11) is
  defined but never instantiated anywhere in the repo. Per this phase's "move, don't reshape"
  discipline, move it as-is into the karma companion file rather than deleting it — flag it as a
  Minor/Tracked finding for a future cleanup pass, the same way Phase 1 tracked (but didn't fix)
  several dead-import/dead-code items.
- Route line-range references below refer to the files **as they exist at the start of this
  phase**, i.e. immediately after Phase 1's completion (commit `bae1bca`). Always locate target
  classes by **name** (grep for `^class ClassName`), not by the line numbers below, which are for
  orientation only — line numbers will shift after each task removes code.

---

### Task 1: Cog-load regression sweep

**Files:**
- Create: `tests/test_commands_cog_load.py`

**Interfaces:**
- Consumes: every `commands/*.py` file that is a loadable Cog (has a `def setup(bot)` function at
  module level, per the project's `bot.py` auto-load convention described in CLAUDE.md).
- Produces: a regression net every later task in this phase re-runs before committing.

This is the Phase 2 equivalent of Phase 1's route-inventory sweep. Since Discord cogs have no HTTP
surface to smoke-test, the equivalent risk is: a companion-file split silently breaks a Cog's
`setup(bot)` (e.g. a missing/renamed import), or removes a command the Cog used to register. This
test catches both generically by loading every cog module and asserting its expected slash/prefix
commands are still present, without needing a live Discord connection.

- [ ] **Step 1: Write the failing test**

```python
import importlib
import pkgutil
import pytest
from unittest.mock import MagicMock

import commands as commands_pkg


def _cog_module_names():
    """Every commands/*.py module that isn't a _foo.py shared-UI helper file."""
    names = []
    for _, name, is_pkg in pkgutil.iter_modules(commands_pkg.__path__):
        if is_pkg or name.startswith("_"):
            continue
        names.append(name)
    return sorted(names)


COG_MODULE_NAMES = _cog_module_names()


def test_at_least_expected_cog_modules_discovered():
    """Sanity check the discovery mechanism itself isn't silently finding zero files."""
    assert len(COG_MODULE_NAMES) >= 30


@pytest.mark.parametrize("module_name", COG_MODULE_NAMES)
def test_cog_module_imports_cleanly(module_name):
    """Every commands/<module>.py must import without raising — catches a missing/broken
    import left behind by a companion-file split before any bot ever tries to load it."""
    importlib.import_module(f"commands.{module_name}")


@pytest.mark.parametrize("module_name", COG_MODULE_NAMES)
def test_cog_module_has_setup_function(module_name):
    """Every non-underscore commands/*.py file must expose def setup(bot) per the project's
    auto-load convention (bot.py iterates commands/*.py and calls bot.load_extension)."""
    mod = importlib.import_module(f"commands.{module_name}")
    assert hasattr(mod, "setup"), f"commands.{module_name} has no setup(bot) function"


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name", COG_MODULE_NAMES)
async def test_cog_setup_registers_without_error(module_name):
    """Actually call setup(bot) with a mock bot and confirm it doesn't raise — this is the
    check that would catch a companion-file split breaking Cog instantiation (e.g. a UI class
    referenced in __init__ that got moved but not re-imported)."""
    mod = importlib.import_module(f"commands.{module_name}")
    bot = MagicMock()
    bot.tree = MagicMock()
    await mod.setup(bot)
    assert bot.add_cog.called, f"commands.{module_name}.setup(bot) never called bot.add_cog(...)"
```

- [ ] **Step 2: Run test to verify current (pre-split) baseline**

Run: `pytest tests/test_commands_cog_load.py -v`
Expected: all pass against the current, unsplit `commands/` directory. If any module's `setup(bot)`
call raises for a reason unrelated to this phase (e.g. it does real I/O at setup time that fails
under a `MagicMock` bot), read that module's actual `setup()` function and adjust the fixture/mock
minimally (e.g. give `bot` specific mocked attributes that function needs) rather than skipping the
module — the goal is a real, working baseline for every cog, not a loosened check.

- [ ] **Step 3: Commit**

```bash
git add tests/test_commands_cog_load.py
git commit -m "test: add cog-load regression sweep for commands/ decomposition"
```

---

### Task 2: Extract newinvestigator.py's shared wizard data

**Files:**
- Create: `commands/_newinvestigator_data.py`
- Modify: `commands/newinvestigator.py`

**Interfaces:**
- Produces: `commands._newinvestigator_data.ERA_SKILLS` (dict), `commands._newinvestigator_data.BASE_SKILLS`
  (dict, `= ERA_SKILLS["1920s Era"]`).
- Consumed by: Task 4 (`_newinvestigator_gamemode.py`'s `EraSelectView`), Task 7
  (`_newinvestigator_skills.py`'s `SkillPageSelect`/`SkillPointAllocationView`), and the `newinvestigator`
  Cog itself (`start_wizard`, `**BASE_SKILLS`).

This is a hard prerequisite for Tasks 4 and 7 — both need `ERA_SKILLS`/`BASE_SKILLS` importable from
a location that isn't the Cog file itself (to avoid a circular import once those classes move out).

- [ ] **Step 1: Move `ERA_SKILLS` and `BASE_SKILLS` verbatim**

Cut lines 18-109 of `commands/newinvestigator.py` (the `ERA_SKILLS = {...}` dict literal through
`BASE_SKILLS = ERA_SKILLS["1920s Era"]`) into a new file:

```python
# commands/_newinvestigator_data.py
ERA_SKILLS = {
    # ... exact dict contents copied verbatim from commands/newinvestigator.py's current
    # ERA_SKILLS definition — do not retype from memory, copy-paste the real current values.
}

BASE_SKILLS = ERA_SKILLS["1920s Era"]
```

- [ ] **Step 2: Update `commands/newinvestigator.py` to import from the new module**

Replace the cut lines with:

```python
from commands._newinvestigator_data import ERA_SKILLS, BASE_SKILLS
```

placed among the file's existing top-of-file imports. Every existing reference to `ERA_SKILLS`/
`BASE_SKILLS` elsewhere in `newinvestigator.py` (e.g. `Cog.start_wizard`'s `**BASE_SKILLS`) keeps
working unchanged since the names are now imported into the module's namespace instead of defined
there.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: all tests pass, including `tests/test_newinvestigator_logic.py` (Phase 0's characterization
tests for this file's pure-logic methods) and the new Task 1 cog-load sweep.

- [ ] **Step 4: Commit**

```bash
git add commands/_newinvestigator_data.py commands/newinvestigator.py
git commit -m "refactor: extract newinvestigator ERA_SKILLS/BASE_SKILLS into commands/_newinvestigator_data.py"
```

---

### Task 3: `_newinvestigator_basicinfo.py` companion (first wizard-stage split)

**Files:**
- Create: `commands/_newinvestigator_basicinfo.py`
- Modify: `commands/newinvestigator.py`

**Interfaces:**
- Produces: `commands._newinvestigator_basicinfo.BasicInfoModal`, `.RetireCharacterView`,
  `.BasicInfoStartView`.
- The Cog instantiates `RetireCharacterView` and `BasicInfoStartView` directly (per the dependency
  map) — both **must** be imported by name into `commands/newinvestigator.py`'s namespace, not
  accessed via a module alias, because `tests/test_data_schema.py:53` does
  `patch("commands.newinvestigator.BasicInfoStartView")` and requires that exact attribute path.

Moves 3 classes (`BasicInfoModal`, `RetireCharacterView`, `BasicInfoStartView`), currently at lines
118-186 of `commands/newinvestigator.py`. `BasicInfoStartView.enter_details` instantiates
`BasicInfoModal` internally — both classes are in this same companion file, so that reference needs
no import changes.

- [ ] **Step 1: Create the companion file, move the 3 classes verbatim**

```python
# commands/_newinvestigator_basicinfo.py
# (imports: copy whatever commands/newinvestigator.py currently imports that these 3 classes'
# bodies actually reference — check each class's real code, likely discord, discord.ui.Modal/View/
# TextInput, and possibly loadnsave functions used in BasicInfoModal.on_submit or
# RetireCharacterView's retire callback. Don't guess; read the real current bodies first.)
```

Cut `BasicInfoModal`, `RetireCharacterView`, `BasicInfoStartView` (lines 118-186) out of
`commands/newinvestigator.py` and paste them into the new file unchanged.

- [ ] **Step 2: Update `commands/newinvestigator.py`'s imports**

Add near the top of the file:

```python
from commands._newinvestigator_basicinfo import RetireCharacterView, BasicInfoStartView
```

(`BasicInfoModal` is only instantiated by `BasicInfoStartView`, which now lives in the same
companion file — the Cog itself doesn't need to import `BasicInfoModal` directly, per the
dependency map's Cog-instantiation list. Only import what the Cog's own methods reference by bare
name.)

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: all green, including `tests/test_data_schema.py::test_new_investigator_wizard_initial_data`
(which patches `commands.newinvestigator.BasicInfoStartView` — this is the test that would fail
loudly if the import-by-name discipline from this task's Interfaces section was violated).

- [ ] **Step 4: Commit**

```bash
git add commands/_newinvestigator_basicinfo.py commands/newinvestigator.py
git commit -m "refactor: extract basic-info wizard UI into commands/_newinvestigator_basicinfo.py"
```

---

### Task 4: `_newinvestigator_gamemode.py` companion

**Files:**
- Create: `commands/_newinvestigator_gamemode.py`
- Modify: `commands/newinvestigator.py`

**Interfaces:**
- Produces: `commands._newinvestigator_gamemode.GameModeView`, `.EraSelectView`, `.ArchetypeSelect`,
  `.ArchetypeSelectView`, `.CoreStatSelectView`.
- Consumes: `ERA_SKILLS` from `commands._newinvestigator_data` (Task 2) for `EraSelectView`.
- The Cog instantiates `GameModeView`, `EraSelectView`, `ArchetypeSelectView`, `CoreStatSelectView`
  directly — import all four by name into `commands/newinvestigator.py`. `ArchetypeSelect` is only
  instantiated by `ArchetypeSelectView` (same companion file), no Cog-level import needed.

Moves 5 classes currently at lines 192-305: `GameModeView`, `EraSelectView`, `ArchetypeSelect`,
`ArchetypeSelectView`, `CoreStatSelectView`.

- [ ] **Step 1: Create the companion file, move the 5 classes verbatim**

```python
# commands/_newinvestigator_gamemode.py
from commands._newinvestigator_data import ERA_SKILLS
# (plus whatever discord/discord.ui/loadnsave imports the real class bodies reference — check
# each class's current code before finalizing this import list.)
```

Cut `GameModeView`, `EraSelectView`, `ArchetypeSelect`, `ArchetypeSelectView`, `CoreStatSelectView`
(lines 192-305) out of `commands/newinvestigator.py` and paste them into the new file unchanged.

- [ ] **Step 2: Update `commands/newinvestigator.py`'s imports**

```python
from commands._newinvestigator_gamemode import GameModeView, EraSelectView, ArchetypeSelectView, CoreStatSelectView
```

- [ ] **Step 3: Run the full suite**

Run: `pytest -v` — expect all green, route/cog-load sweep included.

- [ ] **Step 4: Commit**

```bash
git add commands/_newinvestigator_gamemode.py commands/newinvestigator.py
git commit -m "refactor: extract game-mode/era/archetype wizard UI into commands/_newinvestigator_gamemode.py"
```

---

### Task 5: `_newinvestigator_stats.py` companion

**Files:**
- Create: `commands/_newinvestigator_stats.py`
- Modify: `commands/newinvestigator.py`

**Interfaces:**
- Produces: `commands._newinvestigator_stats.StatGenerationView`, `.StatsBulkEntryModal`,
  `.AssistedRollView`, `.StatsDeductionView`.
- The Cog instantiates `StatGenerationView`, `StatsBulkEntryModal`, `AssistedRollView`,
  `StatsDeductionView` directly (all 4) — import all four by name.

Moves 4 classes currently at lines 311-400: `StatGenerationView`, `StatsBulkEntryModal`,
`AssistedRollView`, `StatsDeductionView`. No internal cross-references between them per the
dependency map (all buttons call Cog methods, not sibling classes) — straightforward move.

- [ ] **Step 1: Create the companion file, move the 4 classes verbatim**

```python
# commands/_newinvestigator_stats.py
# (imports: whatever the real class bodies reference — check before finalizing.)
```

- [ ] **Step 2: Update `commands/newinvestigator.py`'s imports**

```python
from commands._newinvestigator_stats import StatGenerationView, StatsBulkEntryModal, AssistedRollView, StatsDeductionView
```

- [ ] **Step 3: Run the full suite**

Run: `pytest -v` — expect all green.

- [ ] **Step 4: Commit**

```bash
git add commands/_newinvestigator_stats.py commands/newinvestigator.py
git commit -m "refactor: extract stat-generation wizard UI into commands/_newinvestigator_stats.py"
```

---

### Task 6: `_newinvestigator_talents.py` companion

**Files:**
- Create: `commands/_newinvestigator_talents.py`
- Modify: `commands/newinvestigator.py`

**Interfaces:**
- Produces: `commands._newinvestigator_talents.TalentCategorySelect`, `.CategoryView`,
  `.TalentSelect`, `.TalentOptionView`.
- The Cog instantiates `CategoryView` and `TalentOptionView` directly — import both by name.
  `TalentCategorySelect` and `TalentSelect` are only instantiated by their sibling View classes in
  this same companion file.

Moves 4 classes currently at lines 406-453.

- [ ] **Step 1: Create the companion file, move the 4 classes verbatim**

```python
# commands/_newinvestigator_talents.py
# (imports: whatever the real class bodies reference — check before finalizing.)
```

- [ ] **Step 2: Update `commands/newinvestigator.py`'s imports**

```python
from commands._newinvestigator_talents import CategoryView, TalentOptionView
```

- [ ] **Step 3: Run the full suite**

Run: `pytest -v` — expect all green.

- [ ] **Step 4: Commit**

```bash
git add commands/_newinvestigator_talents.py commands/newinvestigator.py
git commit -m "refactor: extract pulp-talent wizard UI into commands/_newinvestigator_talents.py"
```

---

### Task 7: `_newinvestigator_occupation.py` companion

**Files:**
- Create: `commands/_newinvestigator_occupation.py`
- Modify: `commands/newinvestigator.py`

**Interfaces:**
- Produces: `commands._newinvestigator_occupation.OccupationSearchModal`, `.OccupationSelectView`,
  `.OccupationSelect`, `.PaginatedOccupationListView`, `.OccupationPageSelect`,
  `.OccupationSearchStartView`.
- The Cog instantiates only `OccupationSearchStartView` directly — import just that one by name.
  The other 5 classes are only reached via internal cross-references within this companion file
  (`OccupationSearchModal.on_submit` → `OccupationSelectView`; `.__init__` adds
  `OccupationSelect`/`OccupationPageSelect`; `OccupationSearchStartView`'s buttons →
  `OccupationSearchModal`/`PaginatedOccupationListView`).

Moves 6 classes currently at lines 459-620.

- [ ] **Step 1: Create the companion file, move the 6 classes verbatim**

```python
# commands/_newinvestigator_occupation.py
# (imports: whatever the real class bodies reference — check before finalizing.)
```

- [ ] **Step 2: Update `commands/newinvestigator.py`'s imports**

```python
from commands._newinvestigator_occupation import OccupationSearchStartView
```

- [ ] **Step 3: Run the full suite**

Run: `pytest -v` — expect all green.

- [ ] **Step 4: Commit**

```bash
git add commands/_newinvestigator_occupation.py commands/newinvestigator.py
git commit -m "refactor: extract occupation-search wizard UI into commands/_newinvestigator_occupation.py"
```

---

### Task 8: `_newinvestigator_skills.py` companion (last wizard-stage split)

**Files:**
- Create: `commands/_newinvestigator_skills.py`
- Modify: `commands/newinvestigator.py`

**Interfaces:**
- Produces: `commands._newinvestigator_skills.SkillPointSetModal`, `.SkillSpecializationModal`,
  `.CustomSkillModal`, `.CthulhuMythosWarningView`, `.SkillPageSelect`, `.SkillPointAllocationView`,
  `.FinishConfirmationView`.
- Consumes: `ERA_SKILLS`/`BASE_SKILLS` from `commands._newinvestigator_data` (Task 2) —
  `SkillPageSelect` and `SkillPointAllocationView` reference these.
- The Cog instantiates `SkillPointAllocationView` and `FinishConfirmationView` directly — import
  both by name. The other 5 classes are reached only via internal cross-references within this
  companion file.

Moves 7 classes currently at lines 626-993: `SkillPointSetModal`, `SkillSpecializationModal`,
`CustomSkillModal`, `CthulhuMythosWarningView`, `SkillPageSelect`, `SkillPointAllocationView`,
`FinishConfirmationView`. This is the last of the 6 wizard-stage companion files — after this task,
`commands/newinvestigator.py` should contain only the `newinvestigator` Cog class itself (plus its
imports).

- [ ] **Step 1: Create the companion file, move the 7 classes verbatim**

```python
# commands/_newinvestigator_skills.py
from commands._newinvestigator_data import ERA_SKILLS, BASE_SKILLS
# (plus whatever other imports the real class bodies reference — check before finalizing.)
```

- [ ] **Step 2: Update `commands/newinvestigator.py`'s imports**

```python
from commands._newinvestigator_skills import SkillPointAllocationView, FinishConfirmationView
```

- [ ] **Step 3: Confirm the Cog file is now UI-class-free**

Run: `grep -n "^class " commands/newinvestigator.py`
Expected: exactly one match — `class newinvestigator(commands.Cog):`. If anything else appears,
something was missed in Tasks 3-8; investigate before proceeding.

- [ ] **Step 4: Run the full suite**

Run: `pytest -v` — expect all green, including `tests/test_newinvestigator_logic.py` (this file's
pure-logic methods live on the Cog class itself, untouched by this whole 6-task split, so they
should be unaffected — this run confirms that).

- [ ] **Step 5: Commit**

```bash
git add commands/_newinvestigator_skills.py commands/newinvestigator.py
git commit -m "refactor: extract skill-allocation wizard UI into commands/_newinvestigator_skills.py"
```

---

### Task 9: `_roll_views.py` companion (roll.py split)

**Files:**
- Create: `commands/_roll_views.py`
- Modify: `commands/roll.py`, `commands/combat.py`, `commands/_mychar_view.py`

**Interfaces:**
- Produces: `commands._roll_views.SessionView`, `.DisambiguationSelect`, `.DisambiguationView`,
  `.DamageSelect`, `.DamageSelectView`, `.RollResultView`, `.QuickSkillSelect`, `.DiceTrayView`.
- **Cross-file fix-up required:** `commands/combat.py:8` currently does
  `from commands.roll import RollResultView` — update to
  `from commands._roll_views import RollResultView`. `commands/_mychar_view.py:10` has the same
  import, same fix.
- The `Roll` Cog instantiates `DiceTrayView`, `DisambiguationView`, `RollResultView`, `SessionView`
  directly — import all four by name into `commands/roll.py`. `QuickSkillSelect` is wrapped in a
  bare `discord.ui.View()` by the Cog (not constructed as a typed class), so it also needs a direct
  import. `DamageSelect`/`DamageSelectView` are only reached via `RollResultView`'s internal
  callback (same companion file), no Cog-level import needed.
- `SafeDiceParser` (pure dice-expression-parsing logic, no Discord UI) **stays in `commands/roll.py`**
  — it is not a UI class, so the `_foo.py` convention doesn't apply to it, and
  `tests/test_roll_logic.py` already imports it as `from commands.roll import Roll, SafeDiceParser`;
  moving it would be an unnecessary, unrequired import-path break for zero benefit. Leave it in place.

Moves 8 classes currently spread across lines 22-563 and 679-770 (`SafeDiceParser` at 566-677 stays
put, splitting the moved ranges around it — that's fine, just cut each class individually rather
than one contiguous block).

- [ ] **Step 1: Create the companion file, move the 8 classes verbatim**

```python
# commands/_roll_views.py
# (imports: whatever the real class bodies reference — likely discord, discord.ui.View/Select,
# loadnsave functions, rapidfuzz for skill-name matching in QuickSkillSelect, emojis helpers.
# Check each class's current code before finalizing this import list.)
```

Cut `SessionView`, `DisambiguationSelect`, `DisambiguationView`, `DamageSelect`, `DamageSelectView`,
`RollResultView`, `QuickSkillSelect`, `DiceTrayView` out of `commands/roll.py` and paste them into
the new file unchanged. Leave `SafeDiceParser` and the `Roll` Cog class in `commands/roll.py`.

- [ ] **Step 2: Update `commands/roll.py`'s imports**

```python
from commands._roll_views import SessionView, DisambiguationView, RollResultView, QuickSkillSelect, DiceTrayView
```

- [ ] **Step 3: Update `commands/combat.py`'s import**

Change:
```python
from commands.roll import RollResultView
```
to:
```python
from commands._roll_views import RollResultView
```

- [ ] **Step 4: Update `commands/_mychar_view.py`'s import**

Same change as Step 3, in this file's import block.

- [ ] **Step 5: Run the full suite**

Run: `pytest -v` — expect all green, including `tests/test_roll_logic.py` (imports `Roll`,
`SafeDiceParser` directly from `commands.roll`, both of which are unaffected by this move) and the
cog-load sweep (which would catch a broken `commands.combat`/`commands._mychar_view` import).

- [ ] **Step 6: Commit**

```bash
git add commands/_roll_views.py commands/roll.py commands/combat.py commands/_mychar_view.py
git commit -m "refactor: extract roll result/session UI into commands/_roll_views.py"
```

---

### Task 10: `_codex_views.py` companion (codex.py split)

**Files:**
- Create: `commands/_codex_views.py`
- Modify: `commands/codex.py`

**Interfaces:**
- Produces: `commands._codex_views.PaginatedListView`, `.OptionsView`, `.RenderView`, `.CodexView`,
  `.SelectionView`.
- No cross-file fix-ups needed (confirmed via repo-wide search — nothing outside `codex.py` imports
  these classes).
- The `Codex` Cog instantiates `RenderView`, `OptionsView`, `SelectionView`, `CodexView` directly —
  import all four by name. `PaginatedListView` is only instantiated by `OptionsView`/`CodexView`
  (both in this same companion file), no Cog-level import needed.
- Every one of these 5 View classes holds a `cog` reference passed at construction time and calls
  private `Codex` methods (`cog._get_entry_data`, `cog._display_entry`, `cog._render_poster`,
  `cog._get_image_file`) — this is duck-typed (no import of the `Codex` class needed in the
  companion file), matching the existing `commands/_codex_embeds.py` precedent already in this
  codebase for how View-holds-cog-reference is structured here.

Moves 5 classes currently at lines 561-1112 (everything in the file after the `Codex` Cog class,
which stays at the top).

- [ ] **Step 1: Create the companion file, move the 5 classes verbatim**

```python
# commands/_codex_views.py
# (imports: whatever the real class bodies reference — check before finalizing. No import of
# the Codex class itself needed; these Views hold a runtime `self.cog` reference, duck-typed.)
```

- [ ] **Step 2: Update `commands/codex.py`'s imports**

```python
from commands._codex_views import RenderView, OptionsView, SelectionView, CodexView
```

- [ ] **Step 3: Confirm the Cog file is now UI-class-free**

Run: `grep -n "^class " commands/codex.py`
Expected: exactly one match — `class Codex(commands.Cog):`.

- [ ] **Step 4: Run the full suite**

Run: `pytest -v` — expect all green.

- [ ] **Step 5: Commit**

```bash
git add commands/_codex_views.py commands/codex.py
git commit -m "refactor: extract codex render/lookup UI into commands/_codex_views.py"
```

---

### Task 11: `_karma_views.py` companion (karma.py split)

**Files:**
- Create: `commands/_karma_views.py`
- Modify: `commands/karma.py`

**Interfaces:**
- Produces: `commands._karma_views.KarmaActionsView`, `.KarmaRoleSetupMainView`,
  `.KarmaRoleSelectView`, `.KarmaThresholdModal`, `.KarmaRoleRemoveView`, `.KarmaRoleRemoveSelect`,
  `.LeaderboardView`, `.KarmaSetupChannelView`, `.KarmaSetupEmojiModal`, `.KarmaSetupNotifyView`.
- No cross-file fix-ups needed (confirmed via repo-wide search).
- The `Karma` Cog instantiates `KarmaSetupChannelView`, `LeaderboardView`, `KarmaRoleSetupMainView`
  directly — import all three by name. The rest of the classes are reached via
  `bot.get_cog("Karma")` lookups at runtime inside the companion file's own callbacks (not
  constructor-passed `cog` references, unlike codex.py's pattern) — this is already how the
  existing code works and needs no changes, just verbatim relocation.
- **Known dead code carried over as-is per this phase's Global Constraints:** `KarmaActionsView`
  (line 11, top of the current file) is defined but never instantiated anywhere in the repo. Move
  it verbatim into the companion file — do not delete it, do not investigate/fix it. This was
  already logged as a Minor/Tracked finding when the plan was written; no further action needed
  in this task beyond the move itself.

Moves 10 classes: `KarmaActionsView` (currently at line 11, before the Cog) plus 9 more currently
at lines 596-849 (after the Cog). The `Karma` Cog class itself (currently lines 25-595) stays in
`commands/karma.py`.

- [ ] **Step 1: Create the companion file, move all 10 classes verbatim**

```python
# commands/_karma_views.py
# (imports: whatever the real class bodies reference — check before finalizing. Note several
# classes call `self.bot.get_cog("Karma")` / `self.view.bot.get_cog("Karma")` at runtime rather
# than holding a constructor-passed cog reference — this is existing behavior, move as-is.)
```

- [ ] **Step 2: Update `commands/karma.py`'s imports**

```python
from commands._karma_views import KarmaSetupChannelView, LeaderboardView, KarmaRoleSetupMainView
```

- [ ] **Step 3: Confirm the Cog file is now UI-class-free**

Run: `grep -n "^class " commands/karma.py`
Expected: exactly one match — `class Karma(commands.Cog):`.

- [ ] **Step 4: Run the full suite**

Run: `pytest -v` — expect all green, including `tests/test_phase2_auth.py::test_karma_notification_uses_design_system`
(an existing Phase 0 test touching karma-related dashboard rendering — unrelated to this Cog split
but worth confirming it's unaffected).

- [ ] **Step 5: Commit**

```bash
git add commands/_karma_views.py commands/karma.py
git commit -m "refactor: extract karma role/setup wizard UI into commands/_karma_views.py"
```

---

### Task 12: `_journal_views.py` companion (journal.py split)

**Files:**
- Create: `commands/_journal_views.py`
- Modify: `commands/journal.py`

**Interfaces:**
- Produces: `commands._journal_views.JournalEntryModal`, `.DeleteConfirmationView`,
  `.ImageManageView`, `.DeleteImageConfirmationView`, `.JournalView`, `.ClueTargetSelect`,
  `.ClueDestinationView`.
- No cross-file fix-ups needed (confirmed via repo-wide search).
- The `Journal` Cog instantiates `JournalView`, `ClueDestinationView`, `JournalEntryModal` directly
  — import all three by name. `DeleteConfirmationView`, `ImageManageView`,
  `DeleteImageConfirmationView`, `ClueTargetSelect` are only reached via `JournalView`'s own button
  callbacks (or, for `ClueTargetSelect`, via `ClueDestinationView`) — both in this same companion
  file, no additional Cog-level imports needed.
- All 7 classes form one cluster orbiting `JournalView` (the hub) via a duck-typed
  `self.parent_view.external_refresh()` contract — this is existing behavior, move as one companion
  file (not split further), matching the dependency research's explicit recommendation.

Moves 7 classes currently at lines 9-665 (everything before the `Journal` Cog class, which stays at
the bottom of the file, currently starting at line 666).

- [ ] **Step 1: Create the companion file, move the 7 classes verbatim**

```python
# commands/_journal_views.py
# (imports: whatever the real class bodies reference — check before finalizing.)
```

- [ ] **Step 2: Update `commands/journal.py`'s imports**

```python
from commands._journal_views import JournalView, ClueDestinationView, JournalEntryModal
```

- [ ] **Step 3: Confirm the Cog file is now UI-class-free**

Run: `grep -n "^class " commands/journal.py`
Expected: exactly one match — `class Journal(commands.Cog):`.

- [ ] **Step 4: Run the full suite**

Run: `pytest -v` — expect all green.

- [ ] **Step 5: Commit**

```bash
git add commands/_journal_views.py commands/journal.py
git commit -m "refactor: extract journal entry/clue UI into commands/_journal_views.py"
```

---

### Task 13: Split `_mychar_view.py` into feature-scoped companion files (optional stretch, explicitly named in the design spec)

**Files:**
- Create: `commands/_mychar_inventory.py`, `commands/_mychar_roll.py`
- Modify: `commands/_mychar_view.py`

**Interfaces:**
- Produces: `commands._mychar_inventory.AddItemModal`, `.EditItemModal`, `.GiveUserSelect`,
  `.ItemActionsView`, `.InventorySelect`; `commands._mychar_roll.SkillSearchModal`,
  `.SkillRollSelect`.
- `commands/_mychar_view.py` keeps `QuickUpdateModal`, `QuickUpdateSelect`, and
  `CharacterDashboardView` (the hub class) — **no external import path changes** for
  `commands/mycharacter.py:5`'s existing `from commands._mychar_view import CharacterDashboardView`,
  since that class doesn't move.
- Every cross-reference between these classes and `CharacterDashboardView` is duck-typed
  (`self.dashboard_view.launch_item_actions(...)`, `self.view.dashboard_view`, etc. — confirmed via
  dependency research: no `isinstance`/type-hint on `CharacterDashboardView` anywhere), so splitting
  across 3 files carries zero circular-import risk.
- `commands/_mychar_view.py` already imports `RollResultView` from `commands._roll_views` (updated
  in Task 9) and `BackstoryCategorySelectView` from `commands._backstory_common` — neither of those
  imports need to change as part of this task; they stay wherever `SkillRollSelect` (which uses
  `RollResultView`) or whichever class needs them ends up.

This file has no Cog to extract (it's already a `_foo.py`-convention file per CLAUDE.md), so this
task is a pure size-reduction split of an already-appropriately-scoped file, explicitly named in
the original design spec (`_mychar_view.py` was listed among the 6 oversized files to address).
Unlike Tasks 3-12, there's no "Cog file" outcome here — just three smaller, single-purpose files
instead of one 1084-line one.

Moves: to `_mychar_inventory.py` — `AddItemModal`, `EditItemModal`, `GiveUserSelect`,
`ItemActionsView`, `InventorySelect` (currently lines 247-547). To `_mychar_roll.py` —
`SkillSearchModal`, `SkillRollSelect` (currently lines 15-153). `QuickUpdateModal` (154-209),
`QuickUpdateSelect` (210-246), and `CharacterDashboardView` (548-1084) stay in
`commands/_mychar_view.py`.

- [ ] **Step 1: Create `commands/_mychar_inventory.py`, move the 5 inventory classes verbatim**

```python
# commands/_mychar_inventory.py
# (imports: whatever the real class bodies reference — check before finalizing. References to
# `self.dashboard_view`/`self.view.dashboard_view` are duck-typed, no import of
# CharacterDashboardView needed here.)
```

- [ ] **Step 2: Create `commands/_mychar_roll.py`, move the 2 skill-roll classes verbatim**

```python
# commands/_mychar_roll.py
from commands._roll_views import RollResultView
# (plus whatever other imports the real class bodies reference — check before finalizing.
# SkillRollSelect's roll-execution path likely constructs a RollResultView; confirm against the
# actual current code, which itself was already importing RollResultView from commands.roll
# before Task 9 updated that to commands._roll_views.)
```

- [ ] **Step 3: Update `commands/_mychar_view.py`'s imports**

Add near the top of the file (which now only contains `QuickUpdateModal`, `QuickUpdateSelect`,
`CharacterDashboardView`):

```python
from commands._mychar_inventory import ItemActionsView, InventorySelect
from commands._mychar_roll import SkillRollSelect
```

(Only import what `CharacterDashboardView`'s own methods reference by bare name, per the same
by-name-import discipline as every other task in this plan — `AddItemModal`/`EditItemModal`/
`GiveUserSelect` are only reached via `ItemActionsView`'s own internals, in the same companion
file as `ItemActionsView`, so the Cog-equivalent file here doesn't need to import them directly.
`SkillSearchModal` is only reached via... check the actual current code for exactly which of these
2 classes `CharacterDashboardView.roll_button_callback` instantiates directly versus which are
only reached internally within `_mychar_roll.py`, and import only what's actually referenced by
bare name in the remaining `_mychar_view.py`.)

- [ ] **Step 4: Run the full suite**

Run: `pytest -v` — expect all green, including anything touching `/mycharacter` command flows.

- [ ] **Step 5: Commit**

```bash
git add commands/_mychar_inventory.py commands/_mychar_roll.py commands/_mychar_view.py
git commit -m "refactor: split _mychar_view.py into feature-scoped companion files"
```

---

### Task 14: Final verification pass

**Files:**
- None modified — this task is verification only.

**Interfaces:**
- Consumes: everything from Tasks 1-13.

- [ ] **Step 1: Confirm every target file shrank to a reasonable size**

Run: `wc -l commands/newinvestigator.py commands/roll.py commands/codex.py commands/karma.py commands/journal.py commands/_mychar_view.py commands/_newinvestigator_*.py commands/_roll_views.py commands/_codex_views.py commands/_karma_views.py commands/_journal_views.py commands/_mychar_inventory.py commands/_mychar_roll.py commands/_newinvestigator_data.py`

Report the full before/after picture. No single file from this list should be anywhere near its
original size (`newinvestigator.py` 1518 → should be well under 200 lines now that it's just the
Cog class; similarly for the other 4 Cog files).

- [ ] **Step 2: Confirm no Cog file still has UI classes**

Run: `for f in commands/newinvestigator.py commands/roll.py commands/codex.py commands/karma.py commands/journal.py; do echo "=== $f ==="; grep -n "^class " "$f"; done`

Expected: exactly one `class` line per file (the Cog itself).

- [ ] **Step 3: Run the full suite one final time**

Run: `pytest -v`
Expected: 0 failures, including the Task 1 cog-load sweep and every Phase 0 characterization test
that touches these files' pure-logic methods (`test_roll_logic.py`, `test_combat_weapon_parsing.py`,
`test_newinvestigator_logic.py`).

- [ ] **Step 4: Grep for any remaining stale import of a moved class**

Run: `grep -rn "from commands.roll import RollResultView\|from commands.newinvestigator import.*View\|from commands.newinvestigator import.*Modal" --include="*.py" .`

Expected: no hits — confirms Task 9's `combat.py`/`_mychar_view.py` fix-ups (and any other stale
import that might have been missed) are genuinely clean.

- [ ] **Step 5: Commit** (only if any of the above steps required a fix; otherwise this task
      produces no commit of its own, just a clean verification pass)

## Definition of Done for Phase 2

- Every one of the 6 originally-oversized files (`newinvestigator.py`, `roll.py`, `codex.py`,
  `karma.py`, `journal.py`, `_mychar_view.py`) is now either a slim Cog file (just the Cog class) or
  a reasonably-sized `_foo.py` shared-UI file, per the existing project convention.
- `pytest -v` passes with 0 failures, including the new Task 1 cog-load regression sweep and every
  Phase 0 characterization test.
- No stray import of a moved class references its old (pre-move) module path anywhere in the repo.
- `commands/combat.py` and `commands/_mychar_view.py` (or, after Task 13, `commands/_mychar_roll.py`)
  import `RollResultView` from `commands._roll_views`, not `commands.roll`.
