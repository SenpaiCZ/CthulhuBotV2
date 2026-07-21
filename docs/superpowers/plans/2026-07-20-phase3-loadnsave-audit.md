# Phase 3 — loadnsave.py Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate every place in the codebase that reads/writes `data/`, `infodata/`, or `gamedata/` JSON files without going through `loadnsave.py`'s sanctioned `load_X()`/`save_X()` cache-aware API, and close the one behavioral gap that bypassing creates (stale in-memory cache after a generic admin write).

**Architecture:** No new modules, no split of `loadnsave.py` (728 lines; research confirmed it has not grown unwieldy after Phases 1-2 — the file is unchanged since before either phase, `git diff main -- loadnsave.py` is empty). This phase is a targeted bug-fix pass: 5 bypass call sites across 2 dashboard blueprint files get routed through the existing `load_X()` functions instead of the private `_load_json_file()` helper, and a small new cache-invalidation registry closes a stale-cache bug in the generic admin file-browser's save path. Every fix follows this repo's established TDD discipline (write a failing characterization test first, confirm RED, apply the minimal fix, confirm GREEN) — same pattern used for the Phase 0 DEX-formula bug fix.

**Tech Stack:** Python 3.11+, `pytest` + `pytest-asyncio` (existing dev dependencies), Quart test client (existing pattern in `tests/test_dashboard_routes.py`), `unittest.mock.patch`/`monkeypatch`.

## Global Constraints

- **Zero behavior change except two explicitly-sanctioned bug fixes.** The only behavior this phase is allowed to change: (1) the 5 bypass call sites in `grimoire.py`/`render.py` start honoring `_INFODATA_CACHE` instead of always re-reading disk, and (2) the generic admin file-browser's save path (`dashboard/blueprints/file_browser.py`'s `save_file()`) starts invalidating the correct `data/`-folder cache after a write. Every other line of behavior in the codebase must be provably unchanged.
- **No split of `loadnsave.py`.** Confirmed out of scope per user decision — the file is not unwieldy, splitting would touch 82 existing `from loadnsave import X` call sites for no measured benefit today.
- **No dependency upgrades, no database/storage format migration** (per the overall refactor's Non-Goals).
- **TDD for every fix.** Write the failing test first, run it, confirm it fails for the expected reason (RED), then apply the minimal fix, run again, confirm it passes (GREEN). Do not write the fix before the test exists and is confirmed failing.
- **By-name import / mock-patch-target discipline still applies.** Any new test that patches a function must patch it at the exact module namespace where the code under test looks it up — e.g. `dashboard.blueprints.file_browser.is_admin`, not `dashboard.app.is_admin`, because `file_browser.py` does `from dashboard.app import is_admin` (a by-name import that creates its own local binding). This is the same gotcha documented in Phases 1 and 2; re-verify the actual import statement in the file under test before choosing a patch target.
- **Leave pre-existing inconsistencies alone.** The research surfaced several loadnsave.py quirks that are NOT bypasses and NOT in scope for this phase: `smartreact_load`/`smartreact_save` and `autoroom_load`/`autoroom_save` don't follow the `load_X`/`save_X` naming convention; `game_load_player_data`/`game_save_player_data`/`game_load_questions_data`/`game_save_questions_data` and `karma_settings`/`karma_stats` have no in-memory cache at all (every call re-reads/re-writes disk by design); `load_gamemode_stats` reads `gamemode.json` (filename doesn't match the function name); a 92-line `DEFAULT_LOOT_ITEMS` constant sits inline mid-file. None of these are touched by this plan — renaming or adding caching where none exists would be an unrequested behavior/API change, not a bypass fix.
- **Full test suite stays green after every task.** Run `pytest -v` (or `.venv/bin/python -m pytest -v` if a `.venv` exists) after each task's fix step; the suite must show 0 failures before moving to the next task.

---

### Task 1: Add infodata-loader cache characterization tests

**Files:**
- Create: `tests/test_loadnsave_infodata_cache.py`

**Interfaces:**
- Consumes: `loadnsave.load_monsters_data`, `loadnsave.load_deities_data`, `loadnsave.load_spells_data`, `loadnsave.load_weapons_data`, `loadnsave.INFODATA_FOLDER`, `loadnsave._INFODATA_CACHE` (existing, unmodified).
- Produces: nothing consumed by later tasks — this is a standalone characterization test satisfying the project's own gating rule ("if a phase touches code with no test yet, add a characterization test for that code path first"). These 4 loaders currently have zero direct unit test coverage (research finding) despite being the exact functions Tasks 2-3 will route bypass call sites through.

This task adds no fix — it proves the caching contract these 4 functions already correctly implement, before Tasks 2-3 start relying on that contract from new call sites.

- [ ] **Step 1: Write the test file**

```python
import json

import pytest

import loadnsave


INFODATA_CASES = [
    pytest.param(loadnsave.load_monsters_data, "monsters.json", {"Deep One": {"HP": 8}}, id="monsters"),
    pytest.param(loadnsave.load_deities_data, "deities.json", {"Cthulhu": {"HP": 100}}, id="deities"),
    pytest.param(loadnsave.load_spells_data, "spells.json", {"Wither Limb": {"cost": "1D6"}}, id="spells"),
    pytest.param(loadnsave.load_weapons_data, "weapons.json", {"Knife": {"damage": "1D4"}}, id="weapons"),
]


@pytest.fixture
def isolated_infodata_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "INFODATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_INFODATA_CACHE", {})
    return tmp_path


@pytest.mark.asyncio
@pytest.mark.parametrize("load_fn,filename,payload", INFODATA_CASES)
async def test_infodata_loader_serves_cached_value_after_first_read(
    isolated_infodata_dir, load_fn, filename, payload
):
    (isolated_infodata_dir / filename).write_text(json.dumps(payload), encoding="utf-8")

    first = await load_fn()
    assert first == payload

    # Mutate the on-disk file directly (simulating an external change) without
    # touching the cache. A correctly-cached loader must keep returning the
    # value it already cached, not re-read disk on every call.
    (isolated_infodata_dir / filename).write_text(json.dumps({"changed": True}), encoding="utf-8")

    second = await load_fn()
    assert second == payload
```

- [ ] **Step 2: Run the test, confirm it passes**

Run: `pytest tests/test_loadnsave_infodata_cache.py -v`
Expected: all 4 parametrized cases PASS. (This is characterization, not a bug fix — these loaders are already correct; the test locks in that fact before Tasks 2-3 start depending on it.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_loadnsave_infodata_cache.py
git commit -m "test: add characterization tests for infodata loader caching (monsters/deities/spells/weapons)"
```

---

### Task 2: Fix `grimoire.py`'s 4 direct `_load_json_file` bypasses

**Files:**
- Modify: `dashboard/blueprints/grimoire.py`
- Test: `tests/test_loadnsave_bypass_structure.py` (new)

**Interfaces:**
- Consumes: `loadnsave.load_monsters_data`, `loadnsave.load_deities_data`, `loadnsave.load_spells_data`, `loadnsave.load_weapons_data` (existing, unmodified — confirmed cache-correct by Task 1).
- `grimoire.py` currently imports `_load_json_file, INFODATA_FOLDER` from `loadnsave` and calls `_load_json_file(INFODATA_FOLDER, 'monsters.json')` etc. directly in 4 routes (`/monsters`, `/deities`, `/spells`, `/weapons`), bypassing `_INFODATA_CACHE` entirely — every request re-reads disk. `INFODATA_FOLDER` is also used at line 43 in an unrelated debug `print()` statement (not part of the bypass) — that usage must be preserved, so `INFODATA_FOLDER` stays imported; only `_load_json_file` is removed from the import.

- [ ] **Step 1: Write the failing structural regression test**

```python
import dashboard.blueprints.grimoire as grimoire_module


def test_grimoire_does_not_import_private_load_json_file_bypass():
    """grimoire.py must read infodata via loadnsave's cached load_X() functions,
    not the private _load_json_file() helper directly -- a direct call always
    re-reads disk and ignores _INFODATA_CACHE, silently diverging from every
    other infodata route in this file (archetypes, pulp_talents, etc. already
    do it correctly via load_archetype_data() and friends)."""
    assert not hasattr(grimoire_module, "_load_json_file"), (
        "grimoire.py imports loadnsave._load_json_file directly -- this bypasses "
        "the infodata cache. Use the corresponding load_X_data() function instead."
    )
```

- [ ] **Step 2: Run test, confirm it fails**

Run: `pytest tests/test_loadnsave_bypass_structure.py::test_grimoire_does_not_import_private_load_json_file_bypass -v`
Expected: FAIL — `grimoire_module` currently does have a `_load_json_file` attribute (imported at the top of the file).

- [ ] **Step 3: Fix `grimoire.py`**

Change the import block (currently lines 6-11):

```python
from loadnsave import (
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data, load_occupations_data,
    _load_json_file, INFODATA_FOLDER
)
```

to:

```python
from loadnsave import (
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data, load_occupations_data,
    load_monsters_data, load_deities_data, load_spells_data, load_weapons_data,
    INFODATA_FOLDER
)
```

Change the 4 route bodies (currently lines 21-44):

```python
@grimoire_bp.route('/monsters')
async def admin_monsters():
    monsters_data = await _load_json_file(INFODATA_FOLDER, 'monsters.json')
    stat_emojis = emojis.web_symbols
    return await render_template('monsters.html', data=monsters_data, stat_emojis=stat_emojis, type_slug="monster")

@grimoire_bp.route('/deities')
async def admin_deities():
    deities_data = await _load_json_file(INFODATA_FOLDER, 'deities.json')
    stat_emojis = emojis.web_symbols
    return await render_template('deities.html', data=deities_data, stat_emojis=stat_emojis, type_slug="deity")

@grimoire_bp.route('/spells')
async def admin_spells():
    spells_data = await _load_json_file(INFODATA_FOLDER, 'spells.json')
    stat_emojis = emojis.web_symbols
    return await render_template('spells.html', data=spells_data, stat_emojis=stat_emojis, type_slug="spell")

@grimoire_bp.route('/weapons')
async def admin_weapons():
    weapons_data = await _load_json_file(INFODATA_FOLDER, 'weapons.json')
    if not weapons_data:
        print(f"Warning: Weapons data is empty or file not found. Path: {os.path.join(INFODATA_FOLDER, 'weapons.json')} CWD: {os.getcwd()}")
    return await render_template('weapons.html', data=weapons_data, type_slug="weapon")
```

to:

```python
@grimoire_bp.route('/monsters')
async def admin_monsters():
    monsters_data = await load_monsters_data()
    stat_emojis = emojis.web_symbols
    return await render_template('monsters.html', data=monsters_data, stat_emojis=stat_emojis, type_slug="monster")

@grimoire_bp.route('/deities')
async def admin_deities():
    deities_data = await load_deities_data()
    stat_emojis = emojis.web_symbols
    return await render_template('deities.html', data=deities_data, stat_emojis=stat_emojis, type_slug="deity")

@grimoire_bp.route('/spells')
async def admin_spells():
    spells_data = await load_spells_data()
    stat_emojis = emojis.web_symbols
    return await render_template('spells.html', data=spells_data, stat_emojis=stat_emojis, type_slug="spell")

@grimoire_bp.route('/weapons')
async def admin_weapons():
    weapons_data = await load_weapons_data()
    if not weapons_data:
        print(f"Warning: Weapons data is empty or file not found. Path: {os.path.join(INFODATA_FOLDER, 'weapons.json')} CWD: {os.getcwd()}")
    return await render_template('weapons.html', data=weapons_data, type_slug="weapon")
```

Note: `os` import stays (still used in the preserved debug print line).

- [ ] **Step 4: Run test, confirm it passes**

Run: `pytest tests/test_loadnsave_bypass_structure.py::test_grimoire_does_not_import_private_load_json_file_bypass -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: 0 failures, including `tests/test_dashboard_routes.py::test_monsters_route_renders_reference_data` and `tests/test_phase1_utilities.py`'s grimoire-adjacent admin routes.

- [ ] **Step 6: Commit**

```bash
git add dashboard/blueprints/grimoire.py tests/test_loadnsave_bypass_structure.py
git commit -m "fix: route grimoire.py's monsters/deities/spells/weapons pages through loadnsave's cached loaders"
```

---

### Task 3: Fix `render.py`'s 1 direct `_load_json_file` bypass

**Files:**
- Modify: `dashboard/blueprints/render.py`
- Test: `tests/test_loadnsave_bypass_structure.py` (append)

**Interfaces:**
- Consumes: `loadnsave.load_weapons_data` (already imported nowhere in `render.py` before this task — `monsters`/`deities`/`spells` are already correctly imported and used elsewhere in this same file; only `weapons` uses the bypass, at the `/render/weapon` route).
- `render.py` imports `_load_json_file, INFODATA_FOLDER` from `loadnsave` (currently lines 11-18) and calls `_load_json_file(INFODATA_FOLDER, 'weapons.json')` at line 166 (`render_weapon_view`) — its only use of either name in the whole file (confirmed via grep: `_load_json_file` and `INFODATA_FOLDER` each appear exactly twice in `render.py` — once in the import, once at line 166 — so both can be dropped from the import entirely after this fix).

- [ ] **Step 1: Append the failing structural regression test**

Append to `tests/test_loadnsave_bypass_structure.py` (created in Task 2):

```python
import dashboard.blueprints.render as render_module


def test_render_does_not_import_private_load_json_file_bypass():
    """render.py must read weapon reference data via loadnsave's cached
    load_weapons_data(), not the private _load_json_file() helper directly --
    monsters/deities/spells are already correctly imported and used elsewhere
    in this same file (render_monster_view, render_deity_view, render_spell_view)."""
    assert not hasattr(render_module, "_load_json_file"), (
        "render.py imports loadnsave._load_json_file directly -- this bypasses "
        "the infodata cache. Use load_weapons_data() instead."
    )
```

- [ ] **Step 2: Run test, confirm it fails**

Run: `pytest tests/test_loadnsave_bypass_structure.py::test_render_does_not_import_private_load_json_file_bypass -v`
Expected: FAIL — `render_module` currently has a `_load_json_file` attribute.

- [ ] **Step 3: Fix `render.py`**

Change the import block (currently lines 11-18):

```python
from loadnsave import (
    load_player_stats,
    load_monsters_data, load_deities_data, load_spells_data,
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data, load_occupations_data,
    _load_json_file, INFODATA_FOLDER
)
```

to:

```python
from loadnsave import (
    load_player_stats,
    load_monsters_data, load_deities_data, load_spells_data, load_weapons_data,
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data, load_occupations_data,
)
```

Change the route body (currently around line 160-166):

```python
@render_bp.route('/weapon')
async def render_weapon_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await _load_json_file(INFODATA_FOLDER, 'weapons.json')
```

to:

```python
@render_bp.route('/weapon')
async def render_weapon_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_weapons_data()
```

- [ ] **Step 4: Run test, confirm it passes**

Run: `pytest tests/test_loadnsave_bypass_structure.py -v`
Expected: both structural tests (grimoire + render) PASS.

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: 0 failures, including `tests/test_dashboard_routes.py::test_render_weapon_*` (weapon-view render tests).

- [ ] **Step 6: Commit**

```bash
git add dashboard/blueprints/render.py tests/test_loadnsave_bypass_structure.py
git commit -m "fix: route render.py's weapon view through loadnsave's cached load_weapons_data"
```

---

### Task 4: Add a failing test proving the file-browser stale-cache bug

**Files:**
- Create: `tests/test_loadnsave_file_browser_cache.py`

**Interfaces:**
- Consumes: `dashboard.app.app` (Quart app, existing test-client pattern from `tests/test_dashboard_routes.py`), `dashboard.blueprints.file_browser.is_admin` (by-name import from `dashboard.app` — patch at this exact location, not `dashboard.app.is_admin`), `loadnsave.load_server_stats`, `loadnsave._SERVER_STATS_CACHE`, `loadnsave.DATA_FOLDER`.
- This task adds ONLY the failing test (RED). Task 5 implements the fix and confirms GREEN.

The generic admin JSON file-browser (`dashboard/blueprints/file_browser.py`) writes to any `data/*.json` file by filename via `POST /api/save/data/<filename>`, which calls `loadnsave._save_json_file()` directly — this never touches any of the 27 module-level `_X_CACHE` globals for `data/`-folder entities (it only conditionally updates `_INFODATA_CACHE`, and only for `infodata/`-folder writes). This test proves: after saving new content for `server_stats.json` through the file browser, `load_server_stats()` (the sanctioned read path) still returns the *old* cached value instead of what was just written — i.e. the write is silently reverted from the running bot's perspective until a restart.

- [ ] **Step 1: Write the test file**

```python
import json

import pytest
from unittest.mock import patch

import loadnsave
from dashboard.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture
def isolated_data_dir_as_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_SERVER_STATS_CACHE", {"999": {"prefix": "OLD"}})
    with patch('dashboard.blueprints.file_browser.is_admin', return_value=True):
        yield tmp_path


@pytest.mark.asyncio
async def test_file_browser_save_invalidates_stale_data_cache(client, isolated_data_dir_as_admin):
    new_content = {"999": {"prefix": "NEW"}}

    response = await client.post(
        '/api/save/data/server_stats.json',
        json={"content": json.dumps(new_content)}
    )
    assert response.status_code == 200

    on_disk = json.loads((isolated_data_dir_as_admin / "server_stats.json").read_text(encoding="utf-8"))
    assert on_disk == new_content

    # The bug: save_file() writes via loadnsave._save_json_file() directly, which
    # only ever updates _INFODATA_CACHE (for infodata/ writes) -- it never resets
    # _SERVER_STATS_CACHE (a data/-folder entity cache). Without a fix,
    # load_server_stats() below would still return the stale {"999": {"prefix": "OLD"}}
    # set by the fixture, even though the file on disk now holds new_content.
    reloaded = await loadnsave.load_server_stats()
    assert reloaded == new_content
```

- [ ] **Step 2: Run test, confirm it fails**

Run: `pytest tests/test_loadnsave_file_browser_cache.py -v`
Expected: FAIL — `reloaded` will equal `{"999": {"prefix": "OLD"}}` (the stale fixture value), not `new_content`, because `_SERVER_STATS_CACHE` was never invalidated by the save.

- [ ] **Step 3: Commit**

```bash
git add tests/test_loadnsave_file_browser_cache.py
git commit -m "test: add failing characterization test for file-browser stale-cache bug"
```

---

### Task 5: Fix the file-browser stale-cache bug

**Files:**
- Modify: `loadnsave.py`
- Modify: `dashboard/blueprints/file_browser.py`

**Interfaces:**
- Produces: `loadnsave.invalidate_data_cache(filename)` — a new public function. Given a `data/`-folder JSON filename, resets that entity's in-memory cache global (if one exists) so the next `load_X()` call re-reads from disk instead of serving a stale value. No-ops silently for filenames with no registered cache (e.g. `karma_settings.json`, `karma_stats.json` — these already re-read on every call, nothing to invalidate) or unrecognized filenames.
- This is intentionally a NEW function, not a change to `_save_json_file`'s existing behavior — every one of the 31 existing `save_X()` functions already sets its own cache variable to the exact value it just wrote, immediately before calling `_save_json_file()`. Changing `_save_json_file()` itself to also reset caches would make those 31 call sites redundantly re-read disk on the next `load_X()` call (each `save_X()` already leaves the cache correctly populated) — a real behavior/performance change to 31 already-correct call sites, which the Global Constraints forbid. Scoping the fix to a separate function called only from the one genuinely-generic write path (`file_browser.py`) keeps every other call site provably untouched.

- [ ] **Step 1: Add the cache-invalidation registry and function to `loadnsave.py`**

Append at the end of `loadnsave.py` (after `save_fonts_config`, i.e. after the current final line):

```python

# --- Generic Cache Invalidation (for writers that bypass a specific save_X()) ---
# Used by the admin file-browser (dashboard/blueprints/file_browser.py), which can
# write to any data/*.json file by filename and therefore can't call a specific
# save_X() function to keep that entity's cache in sync. Every data/-folder entity
# below uses the same "module-global set to None means uncached" convention, so
# resetting to None is sufficient to force the next load_X() call to re-read disk.
_DATA_CACHE_VAR_BY_FILENAME = {
    'player_stats.json': '_PLAYER_STATS_CACHE',
    'bot_status.json': '_BOT_STATUS_CACHE',
    'server_stats.json': '_SERVER_STATS_CACHE',
    'server_volumes.json': '_SERVER_VOLUMES_CACHE',
    'smart_react.json': '_SMART_REACT_CACHE',
    'autorooms.json': '_AUTOROOM_CACHE',
    'session_data.json': '_SESSION_DATA_CACHE',
    'luck_stats.json': '_LUCK_STATS_CACHE',
    'skill_settings.json': '_SKILL_SETTINGS_CACHE',
    'chase_data.json': '_CHASE_DATA_CACHE',
    'deleter_data.json': '_DELETER_DATA_CACHE',
    'rss_data.json': '_RSS_DATA_CACHE',
    'soundboard_settings.json': '_SOUNDBOARD_SETTINGS_CACHE',
    'music_blacklist.json': '_MUSIC_BLACKLIST_CACHE',
    'reminder_data.json': '_REMINDER_DATA_CACHE',
    'retired_characters_data.json': '_RETIRED_CHARACTERS_CACHE',
    'gamemode.json': '_GAMEMODE_STATS_CACHE',
    'reaction_roles.json': '_REACTION_ROLES_CACHE',
    'pogo_settings.json': '_POGO_SETTINGS_CACHE',
    'pogo_events.json': '_POGO_EVENTS_CACHE',
    'giveaway_data.json': '_GIVEAWAY_DATA_CACHE',
    'polls_data.json': '_POLLS_DATA_CACHE',
    'journal_data.json': '_JOURNAL_DATA_CACHE',
    'gamerole_settings.json': '_GAMEROLE_SETTINGS_CACHE',
    'enroll_settings.json': '_ENROLL_SETTINGS_CACHE',
    'loot_settings.json': '_LOOT_SETTINGS_CACHE',
    'skill_sound_settings.json': '_SKILL_SOUND_SETTINGS_CACHE',
    'fonts_config.json': '_FONTS_CONFIG_CACHE',
}

def invalidate_data_cache(filename):
    """Reset the in-memory cache for a data/-folder entity, keyed by its JSON
    filename, so the next load_X() call re-reads the file from disk instead of
    serving a stale cached value. No-op for filenames with no registered cache
    (e.g. entities that never cache, like karma_settings.json) or unknown names."""
    var_name = _DATA_CACHE_VAR_BY_FILENAME.get(filename)
    if var_name is not None:
        globals()[var_name] = None
```

- [ ] **Step 2: Wire it into `file_browser.py`'s save route**

Change (currently in `save_file`, around lines 69-76):

```python
    try:
        data = await request.get_json()
        json_content = data.get('content')
        # Validate JSON
        parsed = json.loads(json_content)

        await _save_json_file(target_dir, filename, parsed)
        return jsonify({"status": "success"})
```

to:

```python
    try:
        data = await request.get_json()
        json_content = data.get('content')
        # Validate JSON
        parsed = json.loads(json_content)

        await _save_json_file(target_dir, filename, parsed)
        if target_dir == DATA_FOLDER:
            invalidate_data_cache(filename)
        return jsonify({"status": "success"})
```

Update the import line (currently line 6):

```python
from loadnsave import _load_json_file, _save_json_file, DATA_FOLDER, INFODATA_FOLDER
```

to:

```python
from loadnsave import _load_json_file, _save_json_file, invalidate_data_cache, DATA_FOLDER, INFODATA_FOLDER
```

- [ ] **Step 3: Run the Task 4 test, confirm it now passes**

Run: `pytest tests/test_loadnsave_file_browser_cache.py -v`
Expected: PASS — `load_server_stats()` now returns `new_content` after the file-browser save, because `invalidate_data_cache('server_stats.json')` reset `_SERVER_STATS_CACHE` to `None`, forcing a fresh disk read.

- [ ] **Step 4: Run the full suite**

Run: `pytest -v`
Expected: 0 failures, including `tests/test_phase1_utilities.py`'s file-browser admin route tests and `tests/test_loadnsave_roundtrip.py` (confirming the 31 existing `save_X()` call sites are genuinely untouched by this change — `invalidate_data_cache` is only called from `file_browser.py`, nowhere else).

- [ ] **Step 5: Commit**

```bash
git add loadnsave.py dashboard/blueprints/file_browser.py
git commit -m "fix: invalidate data/ entity cache after admin file-browser saves"
```

---

### Task 6: Final verification pass

**Files:**
- None modified — this task is verification only.

**Interfaces:**
- Consumes: everything from Tasks 1-5.

- [ ] **Step 1: Re-run the full bypass sweep to confirm zero remaining hits**

Run:
```bash
grep -rn "_load_json_file\|_save_json_file" --include="*.py" . | grep -v "^loadnsave.py:" | grep -v "^tests/"
```
Expected: hits only in `dashboard/blueprints/file_browser.py` (its import line, the `edit_file` route's generic read at the current line 51, and the `save_file` route's generic write at the current line 75/76 with the Task 5 `invalidate_data_cache` call added alongside it) — this file's use of the private helpers is the one legitimate, necessarily-generic exception (it edits an arbitrary admin-chosen filename, so it structurally cannot call a specific `load_X`/`save_X`), not a bypass this plan is fixing. Zero hits should remain in `grimoire.py` or `render.py`. If any hit appears in other application code (`commands/`, other `dashboard/blueprints/*.py` files, root scripts), it's a bypass this plan missed — investigate before declaring the phase done.

- [ ] **Step 2: Confirm no other `data/`/`infodata/`/`gamedata/` bypass was missed**

Run:
```bash
grep -rn "json.load(\|json.loads(\|open(" --include="*.py" . | grep -E "data/|infodata/|gamedata/" | grep -v "\.venv"
```
Expected: only the already-known, already-cleared false positives from the Phase 3 research (loadnsave.py's own `config.json` read in `load_settings()`; `dashboard/file_utils.py`'s binary uploads under `SOUNDBOARD_FOLDER`/`IMAGES_FOLDER`, which are separate top-level directories, not JSON under the 3 managed folders; `dashboard/blueprints/fonts_admin.py`'s binary font-file writes under `data/fonts/`, which correctly uses `load_fonts_config()`/`save_fonts_config()` for its JSON metadata and only writes raw font binaries directly). No new hits should appear.

- [ ] **Step 3: Run the full suite one final time**

Run: `pytest -v`
Expected: 0 failures, full green — including the 4 new test files added this phase (`test_loadnsave_infodata_cache.py`, `test_loadnsave_bypass_structure.py`, `test_loadnsave_file_browser_cache.py`) plus every pre-existing test (Phase 0's `test_loadnsave_roundtrip.py`, Phase 1's dashboard route/blueprint tests, Phase 2's cog-load sweep).

- [ ] **Step 4: Confirm `loadnsave.py`'s existing 82 call sites are untouched**

Run:
```bash
git diff --stat main -- loadnsave.py
```
Expected: `0 deletions(-)` — the diff should be purely additive (the new `invalidate_data_cache` function and its registry appended at the end), confirming every existing `load_X`/`save_X` function body is byte-for-byte unchanged.

- [ ] **Step 5: Commit** (only if any of the above steps required a fix; otherwise this task produces no commit of its own, just a clean verification pass)

## Definition of Done for Phase 3

- All 5 genuine bypass call sites (`grimoire.py` x4, `render.py` x1) route through `loadnsave.py`'s cached `load_X()` functions instead of the private `_load_json_file()` helper.
- The file-browser's generic admin save path no longer leaves a stale in-memory cache after writing to a `data/`-folder entity.
- 4 new test files lock in this phase's behavior: infodata-loader caching characterization (Task 1), structural bypass-regression guards for `grimoire.py`/`render.py` (Tasks 2-3), and the file-browser cache-invalidation fix (Tasks 4-5).
- `pytest -v` passes with 0 failures.
- `loadnsave.py`'s existing 82 call sites and all 31 `save_X()` functions are provably untouched (purely additive diff against `main`).
- `loadnsave.py` itself is NOT split into multiple files (explicit scope decision).
- No renaming of `smartreact_load`/`autoroom_load`/etc., no caching added to `karma_settings`/`karma_stats`/`game_player_data`/`game_questions_data` — these pre-existing inconsistencies are documented in this plan's Global Constraints as explicitly out of scope.
