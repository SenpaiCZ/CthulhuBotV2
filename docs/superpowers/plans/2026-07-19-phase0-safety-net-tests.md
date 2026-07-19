# Phase 0 — Safety Net Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add characterization tests for the highest-risk, currently-untested behavior
(loadnsave persistence round-trips, roll resolution math, combat weapon parsing, chase session
state, and dashboard route smoke coverage) so Phases 1–5 of the maintainability refactor have a
regression net to move code against.

**Architecture:** Pure `pytest` / `pytest-asyncio` tests added under `tests/`. No production code
changes in this phase — every test targets existing behavior as-is. Tests that need file I/O
isolate it via `monkeypatch` on `loadnsave.DATA_FOLDER` and the relevant module-level cache
globals (the pattern already used in `tests/test_data_schema.py`). Tests that need a Discord
object graph (`CombatView`, `Roll` cog) bypass `__init__` via `Cls.__new__(Cls)` and set only the
attributes the method under test reads, avoiding any real Discord gateway/bot dependency.

**Tech Stack:** pytest, pytest-asyncio (both already in `requirements.txt`), Quart test client
(already used in `tests/test_dashboard_routes.py`).

## Global Constraints

- Zero functional/behavior changes — this phase is additive test files only.
- No new dependencies — everything needed is already in `requirements.txt`.
- Every new async test function is marked `@pytest.mark.asyncio` (project has no
  `asyncio_mode = auto` config, so the marker is required — confirmed via no `pytest.ini` /
  `pyproject.toml` in the repo root).
- Follow the existing fixture pattern from `tests/test_data_schema.py`: monkeypatch
  `loadnsave.DATA_FOLDER` to a `tmp_path`, and reset the specific `_X_CACHE` global(s) the test
  touches.
- Run the full suite (`pytest`) after each task, not just the new test, to catch cross-test cache
  pollution early (module-level caches in `loadnsave.py` are process-global).

---

### Task 1: `loadnsave.py` round-trip characterization tests

**Files:**
- Create: `tests/test_loadnsave_roundtrip.py`

**Interfaces:**
- Consumes: `loadnsave.load_player_stats`, `loadnsave.save_player_stats`,
  `loadnsave.load_server_stats`, `loadnsave.save_server_stats`,
  `loadnsave.load_session_data`, `loadnsave.save_session_data`,
  `loadnsave.load_chase_data`, `loadnsave.save_chase_data`,
  `loadnsave.load_karma_stats`, `loadnsave.save_karma_stats`,
  `loadnsave.load_retired_characters_data`, `loadnsave.save_retired_characters_data`
  (all pre-existing, no signature changes).
- Produces: nothing consumed by later tasks — this task is self-contained.

- [ ] **Step 1: Write the failing tests**

```python
import json
import pytest
import loadnsave


ENTITY_CASES = [
    pytest.param(
        loadnsave.load_player_stats, loadnsave.save_player_stats,
        "player_stats.json", "_PLAYER_STATS_CACHE",
        {"123": {"456": {"NAME": "Old Man Henderson"}}},
        id="player_stats",
    ),
    pytest.param(
        loadnsave.load_server_stats, loadnsave.save_server_stats,
        "server_stats.json", "_SERVER_STATS_CACHE",
        {"123": {"prefix": "!"}},
        id="server_stats",
    ),
    pytest.param(
        loadnsave.load_session_data, loadnsave.save_session_data,
        "session_data.json", "_SESSION_DATA_CACHE",
        {"123": {"456": {"skill_uses": 1}}},
        id="session_data",
    ),
    pytest.param(
        loadnsave.load_chase_data, loadnsave.save_chase_data,
        "chase_data.json", "_CHASE_DATA_CACHE",
        {"123": {"456": {"round_number": 2}}},
        id="chase_data",
    ),
    pytest.param(
        loadnsave.load_karma_stats, loadnsave.save_karma_stats,
        "karma_stats.json", None,
        {"123": {"456": 5}},
        id="karma_stats",
    ),
    pytest.param(
        loadnsave.load_retired_characters_data, loadnsave.save_retired_characters_data,
        "retired_characters_data.json", "_RETIRED_CHARACTERS_CACHE",
        {"123": [{"NAME": "Retired Guy"}]},
        id="retired_characters_data",
    ),
]


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    for cache_name in [
        "_PLAYER_STATS_CACHE", "_SERVER_STATS_CACHE", "_SESSION_DATA_CACHE",
        "_CHASE_DATA_CACHE", "_RETIRED_CHARACTERS_CACHE",
    ]:
        monkeypatch.setattr(loadnsave, cache_name, None)
    return tmp_path


@pytest.mark.asyncio
@pytest.mark.parametrize("load_fn,save_fn,filename,cache_attr,payload", ENTITY_CASES)
async def test_save_then_load_round_trips(
    isolated_data_dir, load_fn, save_fn, filename, cache_attr, payload
):
    await save_fn(payload)

    on_disk = json.loads((isolated_data_dir / filename).read_text(encoding="utf-8"))
    assert on_disk == payload

    if cache_attr is not None:
        setattr(loadnsave, cache_attr, None)

    reloaded = await load_fn()
    assert reloaded == payload


@pytest.mark.asyncio
async def test_load_player_stats_missing_file_returns_empty_dict(isolated_data_dir):
    result = await loadnsave.load_player_stats()
    assert result == {}


@pytest.mark.asyncio
async def test_load_json_file_backs_up_corrupt_file(isolated_data_dir):
    bad_file = isolated_data_dir / "server_stats.json"
    bad_file.write_text("{not valid json", encoding="utf-8")

    result = await loadnsave.load_server_stats()

    assert result == {}
    assert (isolated_data_dir / "server_stats.json.bak").exists()
```

- [ ] **Step 2: Run tests to verify they fail or pass against current behavior**

Run: `pytest tests/test_loadnsave_roundtrip.py -v`
Expected: All pass on first run (these characterize *existing* behavior — a failure here means
the assumption about current behavior was wrong and the test needs correcting, not the source).
Confirm the corrupt-file test in particular passes, since it exercises the `.bak` backup branch
in `loadnsave._load_json_file`.

- [ ] **Step 3: Run the full suite to check for cache-pollution regressions**

Run: `pytest -v`
Expected: All tests pass, including the pre-existing `tests/test_data_schema.py` tests (confirms
the new fixture's cache resets don't leak into other test modules).

- [ ] **Step 4: Commit**

```bash
git add tests/test_loadnsave_roundtrip.py
git commit -m "test: add loadnsave round-trip characterization tests"
```

---

### Task 2: Roll resolution logic characterization tests

**Files:**
- Create: `tests/test_roll_logic.py`

**Interfaces:**
- Consumes: `commands.roll.Roll.calculate_roll_result(self, roll, skill_value)` (instance method
  that does not read `self`), `commands.roll.SafeDiceParser().evaluate(expression)` (returns
  `(result_val: int, detail_str: str)`).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from commands.roll import Roll, SafeDiceParser


@pytest.fixture
def roll_cog():
    # Bypass Roll.__init__ (it registers a bot context-menu command) — the method
    # under test doesn't touch self, so an uninitialized instance is sufficient.
    return Roll.__new__(Roll)


@pytest.mark.parametrize(
    "roll,skill_value,expected_text,expected_tier",
    [
        (1, 50, "Critical Success :star2:", 5),
        (5, 50, "Extreme Success :star:", 4),
        (10, 50, "Extreme Success :star:", 4),
        (11, 50, "Hard Success :white_check_mark:", 3),
        (25, 50, "Hard Success :white_check_mark:", 3),
        (26, 50, "Regular Success :heavy_check_mark:", 2),
        (50, 50, "Regular Success :heavy_check_mark:", 2),
        (51, 50, "Fail :x:", 1),
        (95, 50, "Fail :x:", 1),
        (96, 50, "Fumble :warning:", 0),
        (100, 50, "Fumble :warning:", 0),
        (99, 60, "Fail :x:", 1),
        (100, 60, "Fumble :warning:", 0),
    ],
)
def test_calculate_roll_result(roll_cog, roll, skill_value, expected_text, expected_tier):
    text, tier = roll_cog.calculate_roll_result(roll, skill_value)
    assert text == expected_text
    assert tier == expected_tier


def test_dice_parser_simple_addition():
    parser = SafeDiceParser()
    result, detail = parser.evaluate("1+2")
    assert result == 3
    assert detail == "1 + 2"


def test_dice_parser_rejects_power_operator():
    parser = SafeDiceParser()
    with pytest.raises(ValueError, match="Power operator not allowed"):
        parser.evaluate("2**3")


def test_dice_parser_rejects_oversized_dice_count():
    parser = SafeDiceParser()
    with pytest.raises(ValueError, match="Too many dice"):
        parser.evaluate("101d6")


def test_dice_parser_rejects_division_by_zero():
    parser = SafeDiceParser()
    with pytest.raises(ValueError, match="Division by zero"):
        parser.evaluate("1/0")


def test_dice_parser_dice_roll_within_bounds():
    parser = SafeDiceParser()
    result, detail = parser.evaluate("3d6")
    assert 3 <= result <= 18
    assert detail.startswith("[") and detail.endswith("]")
```

- [ ] **Step 2: Run tests to verify current behavior**

Run: `pytest tests/test_roll_logic.py -v`
Expected: All pass — this locks in the existing success-tier thresholds (critical=1,
extreme=skill/5, hard=skill/2, regular=skill, fumble=96+/100 depending on skill<50) and the
dice-parser safety limits before Phase 2 touches `roll.py`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_roll_logic.py
git commit -m "test: add roll resolution and dice parser characterization tests"
```

---

### Task 3: Combat weapon-parsing characterization tests

**Files:**
- Create: `tests/test_combat_weapon_parsing.py`

**Interfaces:**
- Consumes: `commands.combat.CombatView._parse_weapons(self)` — reads `self.char_data` (dict with
  a `"Backstory"` key containing list fields like `"Gear and Possessions"`) and `self.weapon_db`
  (dict keyed by weapon name, values containing a `"capacity"` string field). Returns a list of
  dicts with keys `key`, `display`, `clean_name`, `ammo`, `cap`, `original`, `is_jammed`.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from commands.combat import CombatView


def make_view(backstory_items, weapon_db):
    view = CombatView.__new__(CombatView)
    view.char_data = {"Backstory": {"Gear and Possessions": backstory_items}}
    view.weapon_db = weapon_db
    return view


def test_parse_weapons_exact_match_with_ammo():
    view = make_view(
        ["Shotgun [2/2]"],
        {"Shotgun": {"capacity": "2"}},
    )
    weapons = view._parse_weapons()
    assert len(weapons) == 1
    w = weapons[0]
    assert w["key"] == "Shotgun"
    assert w["ammo"] == 2
    assert w["cap"] == 2
    assert w["is_jammed"] is False


def test_parse_weapons_jammed_suffix_detected():
    view = make_view(
        ["Shotgun [1/2] (JAMMED)"],
        {"Shotgun": {"capacity": "2"}},
    )
    weapons = view._parse_weapons()
    assert weapons[0]["is_jammed"] is True
    assert weapons[0]["ammo"] == 1


def test_parse_weapons_strips_article_prefix_for_fuzzy_match():
    view = make_view(
        ["A Shotgun [2/2]"],
        {"Shotgun": {"capacity": "2"}},
    )
    weapons = view._parse_weapons()
    assert weapons[0]["key"] == "Shotgun"


def test_parse_weapons_no_bracket_defaults_to_db_capacity():
    view = make_view(
        ["Shotgun"],
        {"Shotgun": {"capacity": "2"}},
    )
    weapons = view._parse_weapons()
    assert weapons[0]["ammo"] == 2
    assert weapons[0]["cap"] == 2


def test_parse_weapons_ignores_non_weapon_inventory_items():
    view = make_view(
        ["A Mysterious Journal", "Shotgun [2/2]"],
        {"Shotgun": {"capacity": "2"}},
    )
    weapons = view._parse_weapons()
    assert len(weapons) == 1
    assert weapons[0]["key"] == "Shotgun"


def test_parse_weapons_empty_inventory_returns_empty_list():
    view = make_view([], {"Shotgun": {"capacity": "2"}})
    assert view._parse_weapons() == []
```

- [ ] **Step 2: Run tests to verify current behavior**

Run: `pytest tests/test_combat_weapon_parsing.py -v`
Expected: All pass. This locks in the regex-based inventory-string parsing
(`^(?:🔴|🟢)?\s*(.*?)\s*\[(\d+)(?:/(\d+))?\](?:\s*\(JAMMED\))?\s*$`) and the article-stripping /
fuzzy-match-to-`weapon_db` behavior before Phase 2 touches `combat.py`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_combat_weapon_parsing.py
git commit -m "test: add combat weapon inventory parsing characterization tests"
```

---

### Task 4: Chase session state characterization tests

**Files:**
- Create: `tests/test_chase_session.py`

**Interfaces:**
- Consumes: `commands.chase.ChaseLocation`, `commands.chase.ChaseParticipant`,
  `commands.chase.ChaseSession` (all plain classes with `to_dict()`/`from_dict(cls, data)` pairs,
  plus `ChaseSession.sort_turn_order()`, `ChaseSession.next_round()`,
  `ChaseSession.ensure_track_length(target_index)`, `ChaseParticipant.set_stats(stats)`,
  `ChaseParticipant.reset_round_actions()`).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the failing tests**

```python
import random
import pytest
from commands.chase import ChaseLocation, ChaseParticipant, ChaseSession


def test_chase_location_index_zero_never_has_hazard():
    for _ in range(20):
        loc = ChaseLocation(0, "Urban")
        assert loc.hazard is None
        assert loc.description == "Clear path"


def test_chase_location_round_trip():
    random.seed(1)
    loc = ChaseLocation(3, "Wilderness")
    restored = ChaseLocation.from_dict(loc.to_dict())
    assert restored.to_dict() == loc.to_dict()


def test_chase_participant_set_stats_and_round_trip():
    p = ChaseParticipant("42", "Investigator", is_npc=False)
    p.set_stats({"MOV": 9, "DEX": 65, "STR": 55, "CON": 60, "Drive Auto": 40})

    assert p.mov == 9
    assert p.dex == 65

    restored = ChaseParticipant.from_dict(p.to_dict())
    assert restored.to_dict() == p.to_dict()


def test_chase_participant_reset_round_actions():
    p = ChaseParticipant("42", "Investigator")
    p.actions_remaining = 0
    p.move_actions_remaining = 0
    p.reset_round_actions()
    assert p.actions_remaining == 1
    assert p.move_actions_remaining == 1


def test_chase_session_initial_track_has_five_locations_with_clear_start():
    session = ChaseSession(guild_id=1, channel_id=2)
    assert len(session.track) == 5
    assert session.track[0].hazard is None
    assert session.track[0].description == "Start Line"


def test_chase_session_sort_turn_order_by_dex_descending():
    session = ChaseSession(guild_id=1, channel_id=2)
    slow = ChaseParticipant("1", "Slow")
    slow.dex = 30
    fast = ChaseParticipant("2", "Fast")
    fast.dex = 80
    session.participants = [slow, fast]

    session.sort_turn_order()

    assert session.turn_order == ["2", "1"]
    assert session.participants[0] is fast


def test_chase_session_next_round_resets_actions_and_advances_round():
    session = ChaseSession(guild_id=1, channel_id=2)
    p = ChaseParticipant("1", "Runner")
    p.actions_remaining = 0
    p.move_actions_remaining = 0
    session.participants = [p]
    session.current_turn_index = 1

    session.next_round()

    assert session.round_number == 2
    assert session.current_turn_index == 0
    assert p.actions_remaining == 1
    assert p.move_actions_remaining == 1


def test_chase_session_ensure_track_length_extends_track():
    session = ChaseSession(guild_id=1, channel_id=2)
    session.ensure_track_length(10)
    assert len(session.track) >= 12


def test_chase_session_round_trip():
    session = ChaseSession(guild_id=1, channel_id=2, environment="Driving", mode="Driving")
    p = ChaseParticipant("1", "Runner")
    p.set_stats({"MOV": 8, "DEX": 55, "STR": 50, "CON": 50, "Drive Auto": 60})
    session.participants = [p]
    session.sort_turn_order()

    restored = ChaseSession.from_dict(session.to_dict())
    assert restored.to_dict() == session.to_dict()
```

- [ ] **Step 2: Run tests to verify current behavior**

Run: `pytest tests/test_chase_session.py -v`
Expected: All pass. This locks in turn-order sorting, round-reset semantics, and the
to_dict/from_dict contract for chase state (which is what gets persisted via
`loadnsave.save_chase_data`/`load_chase_data`) before Phase 2 touches `chase.py`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_chase_session.py
git commit -m "test: add chase session state characterization tests"
```

---

### Task 5: Dashboard public-route smoke test expansion

**Files:**
- Modify: `tests/test_dashboard_routes.py`

**Interfaces:**
- Consumes: the existing `client` and `mock_dependencies` fixtures already defined in this file
  (no changes to them); `dashboard.app.app` Quart instance.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the failing tests**

Append to the end of `tests/test_dashboard_routes.py`:

```python
@pytest.mark.asyncio
async def test_api_status_route_returns_json(client):
    """Public route (in _PUBLIC_API) — must work with no session."""
    response = await client.get('/api/status')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert "is_ready" in data or "status" in data


@pytest.mark.asyncio
async def test_monsters_route_renders_reference_data(client):
    """Public reference page reading infodata/monsters.json via loadnsave."""
    response = await client.get('/monsters')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '<title>' in html


@pytest.mark.asyncio
async def test_render_monster_missing_name_param_returns_400(client):
    response = await client.get('/render/monster')
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_render_monster_known_name_returns_200(client):
    response = await client.get('/render/monster?name=Spawn+of+Abhoth')
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_fonts_redirects_if_not_logged_in(client):
    response = await client.get('/admin/fonts')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_api_fonts_list_unauthorized_without_session(client):
    """/api/* routes require session login except _PUBLIC_API entries."""
    response = await client.get('/api/fonts/list')
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify current behavior**

Run: `pytest tests/test_dashboard_routes.py -v`
Expected: All 4 pre-existing tests plus the 6 new ones pass. If
`test_render_monster_known_name_returns_200` fails because `"Spawn of Abhoth"` no longer exists in
`infodata/monsters.json`, replace the name with the actual first entry from that file (confirm via
`python3 -c "import json; d=json.load(open('infodata/monsters.json')); print(d['monsters'][0]['monster_entry']['name'])"`)
rather than loosening the assertion.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: All tests across all five new/modified test files plus pre-existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_dashboard_routes.py
git commit -m "test: expand dashboard smoke coverage to public api/render/admin routes"
```

---

### Task 6: New investigator wizard — pure logic characterization tests

**Files:**
- Create: `tests/test_newinvestigator_logic.py`

**Interfaces:**
- Consumes: `commands.newinvestigator.newinvestigator.roll_stat_formula(self, f)`,
  `.is_skill_allowed_for_archetype(self, skill_name, allowed_list)`,
  `.get_archetype_skills(self, adjustments)`, `.get_archetype_core_options(self, adjustments)`,
  `.get_archetype_talent_reqs(self, adjustments)`,
  `.calculate_occupation_points(self, char_data, info)`,
  `.evaluate_term(self, term, edu, dex, str_stat, app, pow_stat)` — all pre-existing sync methods
  on the `newinvestigator` cog that only read their arguments (no `self.bot` access), so
  `newinvestigator.__new__(newinvestigator)` is sufficient to construct a test instance.
- Produces: nothing consumed by later tasks. This is the last task in Phase 0; after this task's
  commit, Phase 0 is complete and Phase 1 planning can begin.

- [ ] **Step 1: Write the failing tests**

```python
import random
import pytest
from commands.newinvestigator import newinvestigator


@pytest.fixture
def wizard():
    return newinvestigator.__new__(newinvestigator)


def test_roll_stat_formula_3d6x5_within_bounds(wizard):
    random.seed(1)
    for _ in range(50):
        value = wizard.roll_stat_formula("3D6 * 5")
        assert 15 <= value <= 90
        assert value % 5 == 0


def test_roll_stat_formula_2d6_plus_6_x5_within_bounds(wizard):
    random.seed(1)
    for _ in range(50):
        value = wizard.roll_stat_formula("(2D6 + 6) * 5")
        assert 40 <= value <= 90
        assert value % 5 == 0


def test_roll_stat_formula_unknown_formula_returns_zero(wizard):
    assert wizard.roll_stat_formula("not a formula") == 0


@pytest.mark.parametrize(
    "skill_name,allowed_list,expected",
    [
        ("Spot Hidden", ["Spot Hidden", "Listen"], True),
        ("Firearms (Handgun)", ["Firearms Handgun"], True),
        ("Firearms (Rifle)", ["Firearms (any)"], True),
        ("Language (French)", ["Language (Other)"], True),
        ("Language (Own)", ["Language (Other)"], False),
        ("Survival (Desert)", ["Survival (any)"], True),
        ("Psychology", ["Spot Hidden", "Listen"], False),
    ],
)
def test_is_skill_allowed_for_archetype(wizard, skill_name, allowed_list, expected):
    assert wizard.is_skill_allowed_for_archetype(skill_name, allowed_list) is expected


def test_get_archetype_skills_extracts_bonus_skill_list(wizard):
    adjustments = [
        "You gain 100 bonus points to spend on the following skills:** Fighting (Brawl), Firearms (Handgun), Stealth."
    ]
    result = wizard.get_archetype_skills(adjustments)
    # rstrip(".") runs on the whole joined tail before the comma-split, so only the
    # string's final trailing period is removed — "Stealth." becomes "Stealth".
    assert result == ["Fighting (Brawl)", "Firearms (Handgun)", "Stealth"]


def test_get_archetype_skills_no_match_returns_empty_list(wizard):
    assert wizard.get_archetype_skills(["Some unrelated adjustment line."]) == []


def test_get_archetype_core_options_extracts_listed_stats(wizard):
    adjustments = ["Core characteristic bonus: **STR, DEX and CON** are increased."]
    result = wizard.get_archetype_core_options(adjustments)
    assert result == ["STR", "DEX", "CON"]


def test_get_archetype_talent_reqs_detects_hardened_requirement(wizard):
    adjustments = ["Talents: This archetype must take the Hardened talent."]
    assert wizard.get_archetype_talent_reqs(adjustments) == ["Hardened"]


def test_get_archetype_talent_reqs_no_match_returns_empty_list(wizard):
    assert wizard.get_archetype_talent_reqs(["Talents: no special requirement."]) == []


def test_evaluate_term_multiplies_named_stat(wizard):
    assert wizard.evaluate_term("EDU×4", edu=60, dex=0, str_stat=0, app=0, pow_stat=0) == 240
    assert wizard.evaluate_term("DEX×2", edu=0, dex=55, str_stat=0, app=0, pow_stat=0) == 110


def test_evaluate_term_missing_multiplier_symbol_returns_zero(wizard):
    assert wizard.evaluate_term("EDU", edu=60, dex=0, str_stat=0, app=0, pow_stat=0) == 0


def test_calculate_occupation_points_simple_formula(wizard):
    char_data = {"EDU": 60, "DEX": 50, "STR": 40, "APP": 45, "POW": 55}
    info = {"skill_points": "EDU × 4"}
    assert wizard.calculate_occupation_points(char_data, info) == 240


def test_calculate_occupation_points_or_clause_picks_best_option(wizard):
    char_data = {"EDU": 60, "DEX": 80, "STR": 40, "APP": 45, "POW": 55}
    info = {"skill_points": "(EDU×2 or DEX×2)"}
    # DEX*2=160 beats EDU*2=120, so the "or" branch should select 160.
    assert wizard.calculate_occupation_points(char_data, info) == 160


def test_calculate_occupation_points_varies_formula_returns_zero(wizard):
    char_data = {"EDU": 60, "DEX": 50, "STR": 40, "APP": 45, "POW": 55}
    info = {"skill_points": "Varies"}
    assert wizard.calculate_occupation_points(char_data, info) == 0


def test_calculate_occupation_points_unparseable_formula_falls_back_to_edu_x4(wizard):
    char_data = {"EDU": 60, "DEX": 50, "STR": 40, "APP": 45, "POW": 55}
    info = {"skill_points": "???"}
    assert wizard.calculate_occupation_points(char_data, info) == 240
```

- [ ] **Step 2: Run the full new test file**

Run: `pytest tests/test_newinvestigator_logic.py -v`
Expected: All tests pass, characterizing the stat-rolling bounds, archetype skill-matching rules,
and occupation skill-point-budget formula parsing before Phase 2 touches `newinvestigator.py`.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: Every test across all Phase 0 files (`test_loadnsave_roundtrip.py`,
`test_roll_logic.py`, `test_combat_weapon_parsing.py`, `test_chase_session.py`,
`test_dashboard_routes.py`, `test_newinvestigator_logic.py`) plus all pre-existing tests passes.

- [ ] **Step 4: Commit**

```bash
git add tests/test_newinvestigator_logic.py
git commit -m "test: add newinvestigator wizard logic characterization tests"
```

---

## Definition of Done for Phase 0

- `pytest -v` run from repo root passes with 0 failures.
- No production file outside `tests/` was modified.
- The design doc's Phase 0 gate is satisfied: Phase 1 (dashboard blueprint split) can now proceed
  with the smoke tests in `tests/test_dashboard_routes.py` as its regression check, and Phase 2
  (commands cog decomposition) can proceed with `test_roll_logic.py`,
  `test_combat_weapon_parsing.py`, `test_chase_session.py`, and `test_newinvestigator_logic.py`
  as its regression checks.
