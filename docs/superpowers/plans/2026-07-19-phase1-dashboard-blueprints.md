# Phase 1 — Dashboard Blueprint Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `dashboard/app.py` (4577 lines, 156 routes, all in one file) into ~24 Quart Blueprints
grouped by domain, plus a `dashboard/state.py` module for shared mutable state, so that no dashboard
file exceeds a few hundred lines and each blueprint has one clear responsibility — with **zero
behavior change**: every route keeps its exact path, methods, and handler body.

**Architecture:** This is a structural move, not a rewrite. Every task moves existing route handler
functions **verbatim** (byte-for-byte body) from `dashboard/app.py` into a new
`dashboard/blueprints/<name>.py` module, wraps them under a `Blueprint` object registered under the
same URL prefix they already have, and deletes the moved code from `app.py`. `dashboard/app.py`
becomes a thin composition root: create the app, register blueprints, keep app-wide
`before_request`/`after_request`/`context_processor`/template-filter registrations that apply
regardless of blueprint.

**Tech Stack:** Quart's `Blueprint` class (Flask-compatible API — `Blueprint(name, __name__)`,
`@bp.route(...)`, `app.register_blueprint(bp, url_prefix=...)`). No new dependencies.

## Global Constraints

- **Zero behavior change.** Every route's path, HTTP methods, status codes, and response bodies
  must be identical before and after. This phase moves code; it does not refactor logic.
- Every task must leave the repo in a fully working state: `pytest -v` green, `python bot.py` still
  starts the dashboard successfully (verified via the test suite's route-count/non-404 checks from
  Task 1 — this plan does not require a manual browser check per task, only at the very end of
  Task 26, per the design spec's Phase 1 testing note).
- Blueprint route bodies are **moved, not retyped** — copy the exact existing code for each handler
  function (and any private helper functions/constants it depends on) out of `dashboard/app.py` into
  the new blueprint file. Do not "clean up" or restructure the logic while moving it — that is
  explicitly out of scope for this phase (Phase 2 onward may do that in `commands/`, not here).
  Only the plumbing changes: `@app.route(...)` → `@bp.route(...)`, and imports needed by the moved
  code (`from dashboard.state import ...`, `from loadnsave import ...`, etc.) are added at the top
  of the new file.
- `dashboard/state.py` (Task 2) is a hard prerequisite for every blueprint task — blueprints import
  shared state from there, not from `dashboard.app`.
- `guild_mixers` and `server_volumes` are imported by exact module path
  (`from dashboard.app import guild_mixers, server_volumes`) in `commands/music.py:11` and (inside a
  function body) in `commands/roll.py:999-1001`. Task 2 updates both of these import sites in the
  same commit as the state extraction — a dangling import to the old path would silently create a
  second, disconnected dict and break shared mixer/volume state between the dashboard and the music
  cog.
- **`url_for()` endpoint namespacing (discovered during Task 3 — applies to every remaining
  blueprint task).** Quart always namespaces a blueprint's route endpoints as
  `<blueprint_name>.<endpoint>` (e.g. `login` becomes `core.login`), even if the route decorator
  passes an explicit `endpoint=` kwarg — that kwarg is a no-op once the route lives on a blueprint.
  Every task that moves a route MUST grep the **entire repo** (`dashboard/app.py`, every remaining
  blueprint file, every file under `dashboard/templates/*.html`) for `url_for('<old_endpoint_name>'`
  for each function it moves, and update every hit to the `<blueprint_name>.<old_endpoint_name>`
  form. Missing one silently produces a `werkzeug.routing.exceptions.BuildError` at runtime on
  whatever code path calls it — not something the route-inventory sweep's GET-based smoke test can
  catch, since `url_for()` failures happen inside a handler's own logic, not at routing time. Task 3
  had to update 23 `url_for('login')` call sites in `dashboard/app.py`, 1 `url_for('index')` inside
  its own moved `logout` handler, and 2 template references — expect a similar (usually smaller)
  fixup in most later tasks. `admin_dashboard` is a known not-yet-migrated endpoint referenced by
  `core.py`'s `login`; whichever task moves it must update that reference too.
- Route line-range references below (e.g. "lines 346–528") refer to `dashboard/app.py` **as it
  exists at the start of this plan**, i.e. after Phase 0 and the DEX-formula fix, at commit
  `ebc2393`. Line numbers will shift after each task removes code — always locate the target
  functions by **name** (grep for `def <handler_name>`), not by the line numbers below, which are
  for orientation only when reading this plan.

---

### Task 1: Route-inventory regression sweep

**Files:**
- Create: `tests/test_dashboard_route_inventory.py`

**Interfaces:**
- Consumes: `dashboard.app.app` (the Quart app instance) and its `app.url_map` (Werkzeug/Quart URL
  map, populated by every `@app.route` registration).
- Produces: a regression net every later task in this plan re-runs before committing.

This is the safety net for the whole phase: since every later task moves routes out of `app.py`, the
single biggest risk is a route silently vanishing (typo in the new prefix, forgotten registration)
or the whole app failing to start (import error in a new blueprint file). This test catches both
generically, without hand-listing all 156 paths.

- [ ] **Step 1: Write the failing test**

```python
import re
import pytest
from dashboard.app import app

# Recorded once, at the start of Phase 1 (commit ebc2393) — this is the exact number
# of registered URL rules before any blueprint split. It must not change across this
# phase's tasks: Phase 1 only moves routes between files, it never adds or removes one.
EXPECTED_RULE_COUNT = len(list(app.url_map.iter_rules()))


def _dummy_path(rule_str):
    """Replace every <converter:name> or <name> placeholder with a harmless dummy value."""
    return re.sub(r"<(?:[a-zA-Z_]+:)?([a-zA-Z_]+)>", "1", rule_str)


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


def test_registered_route_count_is_stable():
    """Phase 1 must not add or remove routes — only move them between files."""
    assert len(list(app.url_map.iter_rules())) == EXPECTED_RULE_COUNT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule_str",
    sorted({r.rule for r in app.url_map.iter_rules() if r.endpoint != "static"}),
)
async def test_every_route_resolves_without_404_or_500(client, rule_str):
    """
    Every currently-registered route must still resolve to *some* handler after a GET
    request — not a routing-level 404 (route vanished / URL prefix typo) and not a 500
    (import error, missing dependency, broken handler). A 405 (wrong HTTP method, e.g.
    GET against a POST-only route), 401/403 (auth-gated), or 302 (redirect to login) are
    all fine — they prove the route still exists and its handler ran far enough to make
    an auth/method decision.
    """
    path = _dummy_path(rule_str)
    response = await client.get(path)
    assert response.status_code not in (404, 500), (
        f"{rule_str} -> {path}: got {response.status_code}"
    )
```

- [ ] **Step 2: Run test to see current (pre-split) baseline**

Run: `pytest tests/test_dashboard_route_inventory.py -v`
Expected: all pass against the current, unsplit `dashboard/app.py`. If any route legitimately
returns 404 for its dummy-arg value because of real business logic (e.g.
`/admin/backup/download/<filename>` looking up a file named "1" that doesn't exist, and the handler
itself calls `abort(404)` after a real lookup — not because the *route* failed to match), add that
specific `rule_str` to a documented exclusion set right above the parametrize call, with a one-line
comment naming the handler and why it 404s on dummy data. Do not loosen the general assertion to
paper over a real regression — only exclude routes you've confirmed 404 from their own business
logic, not from routing failure.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: all tests pass, including the new ~156 parametrized cases (minus any documented
exclusions) plus the route-count test.

- [ ] **Step 4: Commit**

```bash
git add tests/test_dashboard_route_inventory.py
git commit -m "test: add route-inventory regression sweep for dashboard blueprint split"
```

---

### Task 2: Extract shared state into `dashboard/state.py`

**Files:**
- Create: `dashboard/state.py`
- Modify: `dashboard/app.py` (remove the moved declarations, import them back from `dashboard.state`)
- Modify: `commands/music.py:11` (update import path)
- Modify: `commands/roll.py:999-1001` (update import path)

**Interfaces:**
- Produces: `dashboard.state.guild_mixers` (`dict[str, MixingAudioSource]`),
  `dashboard.state.server_volumes` (`dict[str, dict]`),
  `dashboard.state.SOUNDBOARD_FOLDER`, `BACKUP_FOLDER`, `IMAGES_FOLDER`, `FONTS_FOLDER`,
  `OLD_FONTS_FOLDER` (path constants), `dashboard.state._failed_login_attempts`
  (`dict[str, list[float]]`), `dashboard.state._PUBLIC_API` (`set[str]`),
  `dashboard.state.MORSE_CODE_MAP` (`dict[str, str]`), `dashboard.state.BASIC_FONTS` (`list[str]`),
  `dashboard.state._APP_START` (`float`, `time.monotonic()` at import time).
- Every later blueprint task that touches soundboard, music, karma, images/fonts, login, or morse
  code imports the relevant name(s) from `dashboard.state`, not `dashboard.app`.

- [ ] **Step 1: Create `dashboard/state.py`**

Move these exact declarations out of `dashboard/app.py` (locate by grep — they are module-level,
near the top of the file, currently around lines 55–72 and 159, 1054):

```python
import os
import time

SOUNDBOARD_FOLDER = os.path.join("data", "soundboard")
BACKUP_FOLDER = os.path.join("data", "backups")
IMAGES_FOLDER = os.path.join("dashboard", "static", "images")
FONTS_FOLDER = os.path.join("dashboard", "static", "fonts")
OLD_FONTS_FOLDER = os.path.join("dashboard", "static", "fonts_old")

server_volumes = {}
guild_mixers = {}

_failed_login_attempts = {}

BASIC_FONTS = [
    "Arial", "Verdana", "Georgia", "Times New Roman", "Courier New",
    "Trebuchet MS", "Garamond", "Comic Sans MS", "Impact",
]

_PUBLIC_API = {'/api/status'}

_APP_START = time.monotonic()

MORSE_CODE_MAP = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
    'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
    'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..', '0': '-----', '1': '.----', '2': '..---',
    '3': '...--', '4': '....-', '5': '.....', '6': '-....', '7': '--...',
    '8': '---..', '9': '----.', ' ': '/',
}
```

**IMPORTANT:** the values above (paths, `BASIC_FONTS` list, `MORSE_CODE_MAP` entries) are given here
for shape/illustration — before writing the file, open `dashboard/app.py` and copy the **actual
current values** verbatim (grep for `SOUNDBOARD_FOLDER =`, `BASIC_FONTS =`, `MORSE_CODE_MAP =`,
etc.). Do not retype from memory; copy-paste from the source so values match exactly.

- [ ] **Step 2: Remove the moved declarations from `dashboard/app.py` and import them back**

Delete the declarations from their original location in `dashboard/app.py`, and add near the top of
the file (after the existing imports):

```python
from dashboard.state import (
    SOUNDBOARD_FOLDER, BACKUP_FOLDER, IMAGES_FOLDER, FONTS_FOLDER, OLD_FONTS_FOLDER,
    server_volumes, guild_mixers, _failed_login_attempts, BASIC_FONTS, _PUBLIC_API,
    _APP_START, MORSE_CODE_MAP,
)
```

This keeps every existing reference inside `dashboard/app.py` (e.g. `guild_mixers[...]`,
`_PUBLIC_API`) working unchanged, since the names are now imported into `app.py`'s namespace instead
of defined there — no other line in `app.py` needs to change for this step.

- [ ] **Step 3: Update `commands/music.py`**

Change line 11 from:
```python
from dashboard.app import guild_mixers, server_volumes
```
to:
```python
from dashboard.state import guild_mixers, server_volumes
```

- [ ] **Step 4: Update `commands/roll.py`**

Change the deferred import at lines 999–1001 from:
```python
from dashboard.app import guild_mixers, SOUNDBOARD_FOLDER
```
to:
```python
from dashboard.state import guild_mixers, SOUNDBOARD_FOLDER
```

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass, including `test_dashboard_route_inventory.py` from Task 1 (route count
and non-404/500 sweep unaffected by this purely internal refactor).

- [ ] **Step 6: Commit**

```bash
git add dashboard/state.py dashboard/app.py commands/music.py commands/roll.py
git commit -m "refactor: extract dashboard shared state into dashboard/state.py"
```

---

### Task 3: `core_bp` — index, login/logout, status, fonts/images serving

**Files:**
- Create: `dashboard/blueprints/__init__.py` (empty — marks the package)
- Create: `dashboard/blueprints/core.py`
- Modify: `dashboard/app.py` (remove moved routes, register the blueprint)

**Interfaces:**
- Produces: `dashboard.blueprints.core.core_bp` (a `quart.Blueprint`), registered in `app.py` via
  `app.register_blueprint(core_bp)` (no prefix — these routes keep their existing root-level paths).
- Consumes from `dashboard.state`: `_PUBLIC_API`, `_APP_START`, `_failed_login_attempts`,
  `IMAGES_FOLDER`, `FONTS_FOLDER`.

Moves these handlers (locate by name in the current `dashboard/app.py`; the line numbers below are
from the plan's baseline commit, for orientation): `bot_status` (~346), `serve_fonts` (~370),
`serve_image` (~381), `upload_image` (~392), `delete_image` (~444), `check_image` (~477), `index`
(~491), `login` (~495), `logout` (~523), plus the `check_rate_limit`/`record_login_failure` helper
functions used only by `login`.

- [ ] **Step 1: Create the blueprint skeleton**

```python
# dashboard/blueprints/core.py
import time
from quart import Blueprint, request, jsonify, session, redirect, url_for, render_template, send_from_directory

from dashboard.state import _PUBLIC_API, _APP_START, _failed_login_attempts, IMAGES_FOLDER, FONTS_FOLDER
from loadnsave import load_settings_async, save_settings

core_bp = Blueprint('core', __name__)
```

(Add any further imports the moved handler bodies need — e.g. `os`, `werkzeug.utils.secure_filename`
— by checking what each function actually references in its current body in `dashboard/app.py`.)

- [ ] **Step 2: Move each handler verbatim**

For each of the 9 functions named above: cut its `@app.route(...)` decorator + full function body out
of `dashboard/app.py`, paste it into `dashboard/blueprints/core.py` below the `core_bp = Blueprint(...)`
line, and change the decorator from `@app.route(...)` to `@core_bp.route(...)`. Do not alter the
route path, methods, or any line of logic inside the function bodies. Also move
`check_rate_limit`/`record_login_failure` (plain helper functions, no decorator) into this file since
only `login` uses them.

- [ ] **Step 3: Register the blueprint in `dashboard/app.py`**

Near the top of `dashboard/app.py`, after the Quart `app = Quart(__name__)` line, add:

```python
from dashboard.blueprints.core import core_bp
app.register_blueprint(core_bp)
```

- [ ] **Step 4: Run the full suite**

Run: `pytest -v`
Expected: all tests pass, including Task 1's route-count and non-404/500 sweep — the 9 moved routes
must resolve identically to before (same paths, since `core_bp` is registered with no prefix).

- [ ] **Step 5: Commit**

```bash
git add dashboard/blueprints/__init__.py dashboard/blueprints/core.py dashboard/app.py
git commit -m "refactor: move core/auth routes into dashboard/blueprints/core.py"
```

---

### Task 4: `characters_bp` — character list, retired, delete

**Files:**
- Create: `dashboard/blueprints/characters.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.characters.characters_bp`, registered with no prefix.

Moves: `characters` (~528), `retired` (~559), `delete_character` (~586, route `/api/character/delete`).

- [ ] **Step 1: Create the blueprint and move the 3 handlers verbatim.** Cut each function's
  `@app.route(...)` decorator + full body out of `dashboard/app.py`, paste it into the new file below
  the `characters_bp = Blueprint(...)` line, and change the decorator to `@characters_bp.route(...)`
  without altering the path, methods, or any line of logic. Check each function's current body for
  what it references from `loadnsave` (likely `load_player_stats`, `load_retired_characters_data`,
  and their `save_*` counterparts) and add matching imports at the top of the new file — don't guess,
  check the actual current source.

```python
# dashboard/blueprints/characters.py
from quart import Blueprint, request, jsonify, session, render_template

characters_bp = Blueprint('characters', __name__)
```

- [ ] **Step 2: Register in `dashboard/app.py`**

```python
from dashboard.blueprints.characters import characters_bp
app.register_blueprint(characters_bp)
```

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green including Task 1's sweep.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/characters.py dashboard/app.py
git commit -m "refactor: move character list/delete routes into dashboard/blueprints/characters.py"
```

---

### Task 5: `render_bp` — print/render views

**Files:**
- Create: `dashboard/blueprints/render.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.render.render_bp`, registered with `url_prefix='/render'` **only
  for the routes whose path already starts with `/render/...`** — check each moved route's existing
  path; if any non-`/render` path was grouped in this category (there are none per the structural
  map — all 21 are under `/render/`), register with `url_prefix='/render'` and strip that prefix
  from each `@render_bp.route(...)` path (e.g. `/render/character/<guild_id>/<user_id>` becomes
  `@render_bp.route('/character/<guild_id>/<user_id>')` on a blueprint registered with
  `url_prefix='/render'`).

Moves all 21 `render_*_view` functions (character, karma, monster, deity, spell, weapon, archetype,
pulp_talent, insane_talent, mania, phobia, poison, skill, invention, year, occupation, morse,
newspaper, telegram, letter, script) plus the `text_to_morse` helper function they share.

- [ ] **Step 1: Create the blueprint, move all 21 handlers + `text_to_morse` verbatim**, importing
  `MORSE_CODE_MAP` from `dashboard.state` for the morse view/helper.

```python
# dashboard/blueprints/render.py
from quart import Blueprint, request, render_template
from dashboard.state import MORSE_CODE_MAP

render_bp = Blueprint('render', __name__, url_prefix='/render')
```

Strip the `/render` prefix from each route's path string when moving it onto `@render_bp.route(...)`.

- [ ] **Step 2: Register in `dashboard/app.py`**

```python
from dashboard.blueprints.render import render_bp
app.register_blueprint(render_bp)
```

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green. Pay particular attention to
  `test_render_monster_known_name_returns_200` and the other Phase 0 render-route tests
  (`tests/test_phase3_render.py`) — these hit `/render/monster`, `/render/archetype`, etc. directly
  and will immediately catch a prefix-stripping mistake.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/render.py dashboard/app.py
git commit -m "refactor: move all /render/* routes into dashboard/blueprints/render.py"
```

---

### Task 6: `fonts_admin_bp` — fonts administration

**Files:**
- Create: `dashboard/blueprints/fonts_admin.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.fonts_admin.fonts_admin_bp`, registered with no prefix (paths are
  a mix of `/admin/fonts` and `/api/fonts/...`, already fully qualified in their route strings).

Moves: `admin_fonts` (`/admin/fonts`), `fonts_list` (`/api/fonts/list`), `fonts_upload`
(`/api/fonts/upload`), `fonts_delete` (`/api/fonts/delete`), `fonts_update_category`
(`/api/fonts/update_category`).

- [ ] **Step 1: Create the blueprint, move all 5 handlers verbatim** (import `FONTS_FOLDER`,
  `OLD_FONTS_FOLDER`, `BASIC_FONTS` from `dashboard.state`).

```python
# dashboard/blueprints/fonts_admin.py
from quart import Blueprint, request, jsonify, session, render_template
from dashboard.state import FONTS_FOLDER, OLD_FONTS_FOLDER, BASIC_FONTS

fonts_admin_bp = Blueprint('fonts_admin', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(fonts_admin_bp)` in `dashboard/app.py`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/fonts_admin.py dashboard/app.py
git commit -m "refactor: move fonts admin routes into dashboard/blueprints/fonts_admin.py"
```

---

### Task 7: `admin_bp` — admin home + design settings

**Files:**
- Create: `dashboard/blueprints/admin.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.admin.admin_bp`, registered with no prefix.

Moves: `admin_dashboard` (`/admin`), `admin_design` (`/admin/design`), `save_fonts`
(`/api/design/save_fonts`), `save_origin_fonts` (`/api/design/save_origin_fonts`), `save_design`
(`/api/design/save`).

- [ ] **Step 1: Create the blueprint, move all 5 handlers verbatim.**

```python
# dashboard/blueprints/admin.py
from quart import Blueprint, request, jsonify, session, render_template

admin_bp = Blueprint('admin', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(admin_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green (watch
  `tests/test_dashboard_routes.py::test_admin_dashboard_redirects_if_not_logged_in`, an existing
  Phase 0 test that hits `/admin` directly).

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/admin.py dashboard/app.py
git commit -m "refactor: move admin home/design routes into dashboard/blueprints/admin.py"
```

---

### Task 8: `grimoire_bp` — reference-data pages

**Files:**
- Create: `dashboard/blueprints/grimoire.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.grimoire.grimoire_bp`, registered with no prefix.

Moves: `grimoire_hub` (registered under **two** paths, `/grimoire/` and `/grimoire` — both decorators
move together onto the same function), `admin_monsters` (`/monsters`), and the deities/spells/
weapons/archetypes/pulp_talents/insane_talents/manias/phobias/poisons/skills/inventions/years/
occupations handlers (14 more functions, all unauthenticated GET reference pages).

- [ ] **Step 1: Create the blueprint, move all 15 handlers verbatim** (keep both `@app.route('/grimoire/')`
  and `@app.route('/grimoire')` decorators on `grimoire_hub`, changed to `@grimoire_bp.route(...)`).

```python
# dashboard/blueprints/grimoire.py
from quart import Blueprint, render_template
import emojis
from loadnsave import _load_json_file, INFODATA_FOLDER

grimoire_bp = Blueprint('grimoire', __name__)
```

(Verify the exact helper used for loading infodata in the current code — the structural map notes
`admin_monsters` calls `_load_json_file(INFODATA_FOLDER, 'monsters.json')`; import whatever the
actual current code imports, don't guess at a different loader.)

- [ ] **Step 2: Register** — `app.register_blueprint(grimoire_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green (watch
  `tests/test_dashboard_routes.py::test_monsters_route_renders_reference_data` and
  `tests/test_ui_unification.py`'s monsters/spells/weapons page tests from Phase 0).

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/grimoire.py dashboard/app.py
git commit -m "refactor: move grimoire/reference-data routes into dashboard/blueprints/grimoire.py"
```

---

### Task 9: `file_browser_bp` — admin file browser/editor

**Files:**
- Create: `dashboard/blueprints/file_browser.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.file_browser.file_browser_bp`, registered with no prefix.

Moves: `browse_files` (`/admin/browse/<folder_name>`), `edit_file`
(`/admin/edit/<folder_name>/<filename>`), `save_file` (`/api/save/<folder_name>/<filename>`).

- [ ] **Step 1: Create the blueprint, move all 3 handlers verbatim** (these use
  `dashboard/file_utils.py`'s sync file-op helpers per CLAUDE.md — import whatever the current code
  imports from there).

```python
# dashboard/blueprints/file_browser.py
from quart import Blueprint, request, jsonify, session, render_template

file_browser_bp = Blueprint('file_browser', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(file_browser_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green (watch
  `tests/test_phase1_utilities.py::test_file_browser_route`).

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/file_browser.py dashboard/app.py
git commit -m "refactor: move file browser/editor routes into dashboard/blueprints/file_browser.py"
```

---

### Task 10: `bot_config_bp` — bot status/prefix configuration

**Files:**
- Create: `dashboard/blueprints/bot_config.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.bot_config.bot_config_bp`, registered with no prefix.

Moves: `admin_bot_config` (`/admin/bot_config`), `save_status` (`/api/save_status`), `save_prefix`
(`/api/save_prefix`).

- [ ] **Step 1: Create the blueprint, move all 3 handlers verbatim** (import `load_bot_status`,
  `save_bot_status`, `load_server_stats`, `save_server_stats` from `loadnsave` as the current code
  does).

```python
# dashboard/blueprints/bot_config.py
from quart import Blueprint, request, jsonify, session, render_template

bot_config_bp = Blueprint('bot_config', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(bot_config_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/bot_config.py dashboard/app.py
git commit -m "refactor: move bot config routes into dashboard/blueprints/bot_config.py"
```

---

### Task 11: `game_settings_bp` — general/loot/sound game settings

**Files:**
- Create: `dashboard/blueprints/game_settings.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.game_settings.game_settings_bp`, registered with no prefix.

Moves: `admin_game_settings` (`/admin/game_settings`), the `/api/game/settings/data` and
`/api/game/settings/save_general` handlers, the `/api/game/loot/data` and `/api/game/loot/save`
handlers, the `/api/game/sounds/data` and `/api/game/sounds/save` handlers (7 functions total —
identify exact function names by grepping `dashboard/app.py` for `/api/game/` route strings).

- [ ] **Step 1: Create the blueprint, move all 7 handlers verbatim.**

```python
# dashboard/blueprints/game_settings.py
from quart import Blueprint, request, jsonify, session, render_template

game_settings_bp = Blueprint('game_settings', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(game_settings_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/game_settings.py dashboard/app.py
git commit -m "refactor: move game settings routes into dashboard/blueprints/game_settings.py"
```

---

### Task 12: `karma_bp` — karma system administration

**Files:**
- Create: `dashboard/blueprints/karma.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.karma.karma_bp`, registered with no prefix.

Moves: `admin_karma` (`/admin/karma`), the `/api/karma/save`, `/api/karma/roles/save`,
`/api/karma/users/<guild_id>`, `/api/karma/recalculate` handlers, and `detect_karma_emojis`
(`/api/karma/detect_emojis` — the one with real business logic: scans `channel.history(limit=20)`
via `app.bot`, tallies emoji reactions with `collections.Counter`). Import `Counter` from
`collections` in the new file since this handler needs it.

- [ ] **Step 1: Create the blueprint, move all 6 handlers verbatim**, including
  `detect_karma_emojis`'s full body unchanged (do not extract it into a separate service function —
  that kind of logic-reshaping is explicitly out of scope for Phase 1, which only moves code between
  files; Phase 2 may revisit it).

```python
# dashboard/blueprints/karma.py
from collections import Counter
from quart import Blueprint, request, jsonify, session, render_template
import discord

karma_bp = Blueprint('karma', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(karma_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green (watch
  `tests/test_phase2_auth.py::test_karma_notification_uses_design_system`).

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/karma.py dashboard/app.py
git commit -m "refactor: move karma admin routes into dashboard/blueprints/karma.py"
```

---

### Task 13: `soundboard_bp` — soundboard administration and playback (largest group)

**Files:**
- Create: `dashboard/blueprints/soundboard.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.soundboard.soundboard_bp`, registered with no prefix.
- Consumes from `dashboard.state`: `guild_mixers`, `server_volumes`, `SOUNDBOARD_FOLDER`.
- Consumes `get_or_join_voice_channel` and any other private helper `_soundboard_play_inner` and the
  other 20 handlers depend on — move those helpers alongside the routes that use them.

Moves all 21 soundboard routes: `admin_soundboard`, `soundboard_data`, the folder color/settings/
favorite handlers, `soundboard_play` + `_soundboard_play_inner`, `soundboard_join`,
`soundboard_leave`, `soundboard_stop`, `soundboard_volume`, folder create/delete/rename, file
delete/rename, `soundboard_upload`, and the track volume/loop/pause/remove handlers. Also move
`get_or_join_voice_channel` if it is defined in `dashboard/app.py` and used only by these routes
(check — if it's also used by non-soundboard routes, leave it in `dashboard/app.py` and import it
back, don't duplicate it).

- [ ] **Step 1: Create the blueprint, move all 21 handlers + their private helpers verbatim.**

```python
# dashboard/blueprints/soundboard.py
import os
import shutil
from quart import Blueprint, request, jsonify, session, render_template
import discord

from dashboard.state import guild_mixers, server_volumes, SOUNDBOARD_FOLDER
from dashboard.audio_mixer import MixingAudioSource

soundboard_bp = Blueprint('soundboard', __name__)
```

This is the largest single move in the plan (~21 functions). Work through them one at a time,
checking each function's current body for what module-level names it references (from `loadnsave`,
`dashboard.file_utils`, `dashboard.state`, or local helpers) and add the corresponding import at the
top of the new file — don't guess; check the actual current source for each function before moving
it.

- [ ] **Step 2: Register** — `app.register_blueprint(soundboard_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green. This is the highest-risk task
  in the plan given its size — if anything fails, re-check that `guild_mixers`/`server_volumes` are
  the same object as before (imported from `dashboard.state`, not re-created as new empty dicts in
  the blueprint file).

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/soundboard.py dashboard/app.py
git commit -m "refactor: move soundboard routes into dashboard/blueprints/soundboard.py"
```

---

### Task 14: `reaction_roles_bp` — reaction role administration

**Files:**
- Create: `dashboard/blueprints/reaction_roles.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.reaction_roles.reaction_roles_bp`, registered with no prefix.

Moves: `admin_reactionroles` (`/admin/reactionroles`), `/api/reactionroles/data`,
`reaction_roles_add` (`/api/reactionroles/add` — real logic: regex emoji-ID resolution, Discord
message fetch/validation, in-place schema migration), `/api/reactionroles/delete`.

- [ ] **Step 1: Create the blueprint, move all 4 handlers verbatim**, including
  `reaction_roles_add`'s full body unchanged (no logic extraction in this phase).

```python
# dashboard/blueprints/reaction_roles.py
import re
from quart import Blueprint, request, jsonify, session, render_template
import discord

reaction_roles_bp = Blueprint('reaction_roles', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(reaction_roles_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/reaction_roles.py dashboard/app.py
git commit -m "refactor: move reaction roles routes into dashboard/blueprints/reaction_roles.py"
```

---

### Task 15: `music_bp` — music playback control

**Files:**
- Create: `dashboard/blueprints/music.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.music.music_bp`, registered with no prefix.
- Consumes from `dashboard.state`: `guild_mixers`, `server_volumes` (shared with `commands/music.py`
  per Task 2).

Moves: `admin_music` (`/admin/music`), `/api/music/data`, `music_control` (`/api/music/control`),
`/api/music/ban`.

- [ ] **Step 1: Create the blueprint, move all 4 handlers verbatim.**

```python
# dashboard/blueprints/music.py
from quart import Blueprint, request, jsonify, session, render_template

from dashboard.state import guild_mixers, server_volumes

music_bp = Blueprint('music', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(music_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/music.py dashboard/app.py
git commit -m "refactor: move music control routes into dashboard/blueprints/music.py"
```

---

### Task 16: `rss_bp` — RSS feed administration

**Files:**
- Create: `dashboard/blueprints/rss.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.rss.rss_bp`, registered with no prefix.

Moves: `admin_rss` (`/admin/rss`), `/api/rss/data`, `rss_add` (`/api/rss/add` — uses `feedparser`),
`/api/rss/update_color`, `/api/rss/delete`.

- [ ] **Step 1: Create the blueprint, move all 5 handlers verbatim** (import `feedparser` and
  whatever `rss_utils.py` helper the current `rss_add` body uses).

```python
# dashboard/blueprints/rss.py
import feedparser
from quart import Blueprint, request, jsonify, session, render_template

rss_bp = Blueprint('rss', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(rss_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/rss.py dashboard/app.py
git commit -m "refactor: move RSS admin routes into dashboard/blueprints/rss.py"
```

---

### Task 17: `gameroles_bp` — game role administration

**Files:**
- Create: `dashboard/blueprints/gameroles.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.gameroles.gameroles_bp`, registered with no prefix.

Moves: `admin_gameroles` (`/admin/gameroles`), `/api/gameroles/data`, `/api/gameroles/emoji/set`,
`/api/gameroles/emoji/delete`, `/api/gameroles/save`, `/api/gameroles/ignore/add`,
`/api/gameroles/ignore/remove` (7 functions).

- [ ] **Step 1: Create the blueprint, move all 7 handlers verbatim.**

```python
# dashboard/blueprints/gameroles.py
from quart import Blueprint, request, jsonify, session, render_template

gameroles_bp = Blueprint('gameroles', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(gameroles_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/gameroles.py dashboard/app.py
git commit -m "refactor: move game roles routes into dashboard/blueprints/gameroles.py"
```

---

### Task 18: `autorooms_bp` — auto voice-room administration

**Files:**
- Create: `dashboard/blueprints/autorooms.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.autorooms.autorooms_bp`, registered with no prefix.

Moves: `admin_autorooms` (`/admin/autorooms`), `/api/autorooms/data`, `/api/autorooms/save`.

- [ ] **Step 1: Create the blueprint, move all 3 handlers verbatim.**

```python
# dashboard/blueprints/autorooms.py
from quart import Blueprint, request, jsonify, session, render_template

autorooms_bp = Blueprint('autorooms', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(autorooms_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/autorooms.py dashboard/app.py
git commit -m "refactor: move autorooms routes into dashboard/blueprints/autorooms.py"
```

---

### Task 19: `deleter_bp` — bulk message deletion

**Files:**
- Create: `dashboard/blueprints/deleter.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.deleter.deleter_bp`, registered with no prefix.

Moves: `admin_deleter` (`/admin/deleter`), `/api/deleter/data`, `/api/deleter/save`,
`/api/deleter/delete`, `/api/deleter/bulk_delete`.

- [ ] **Step 1: Create the blueprint, move all 5 handlers verbatim.**

```python
# dashboard/blueprints/deleter.py
from quart import Blueprint, request, jsonify, session, render_template

deleter_bp = Blueprint('deleter', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(deleter_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/deleter.py dashboard/app.py
git commit -m "refactor: move deleter routes into dashboard/blueprints/deleter.py"
```

---

### Task 20: `backup_bp` — data backup administration

**Files:**
- Create: `dashboard/blueprints/backup.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.backup.backup_bp`, registered with no prefix.
- Consumes from `dashboard.state`: `BACKUP_FOLDER`.

Moves: `admin_backup` (`/admin/backup`), `/api/backup/save`, `/api/backup/run`, the module-level
`get_system_backups` helper (not a route — used by one or more of these handlers), `/api/backup/files`,
`/api/backup/delete`, `/admin/backup/download/<filename>`.

- [ ] **Step 1: Create the blueprint, move all 6 handlers + `get_system_backups` verbatim.**

```python
# dashboard/blueprints/backup.py
import os
import shutil
from quart import Blueprint, request, jsonify, session, render_template, send_from_directory

from dashboard.state import BACKUP_FOLDER

backup_bp = Blueprint('backup', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(backup_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/backup.py dashboard/app.py
git commit -m "refactor: move backup routes into dashboard/blueprints/backup.py"
```

---

### Task 21: `pokemon_bp` — Pokémon GO event administration

**Files:**
- Create: `dashboard/blueprints/pokemon.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.pokemon.pokemon_bp`, registered with no prefix.

Moves: `admin_pokemon` (`/admin/pokemon`), `/api/pokemon/data`, `/api/pokemon/save`,
`/api/pokemon/refresh`, `/api/pokemon/push_weekly`, `/api/pokemon/push_next`.

- [ ] **Step 1: Create the blueprint, move all 6 handlers verbatim.**

```python
# dashboard/blueprints/pokemon.py
from quart import Blueprint, request, jsonify, session, render_template

pokemon_bp = Blueprint('pokemon', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(pokemon_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/pokemon.py dashboard/app.py
git commit -m "refactor: move pokemon GO routes into dashboard/blueprints/pokemon.py"
```

---

### Task 22: `giveaway_bp` — giveaway administration

**Files:**
- Create: `dashboard/blueprints/giveaway.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.giveaway.giveaway_bp`, registered with no prefix.

Moves: `admin_giveaway` (`/admin/giveaway`), `/api/giveaway/data`, `giveaway_create`
(`/api/giveaway/create` — duration-string parsing, Discord embed/view creation, includes a runtime
`from commands.giveaway import GiveawayView` import inside the handler body — keep that import
exactly where it currently is, inside the function, not moved to the top of the file, since it's
almost certainly there to avoid a circular import between `dashboard` and `commands` at module load
time), `/api/giveaway/end`, `/api/giveaway/reroll`.

- [ ] **Step 1: Create the blueprint, move all 5 handlers verbatim**, preserving `giveaway_create`'s
  in-function import exactly as-is.

```python
# dashboard/blueprints/giveaway.py
import re
import time
from quart import Blueprint, request, jsonify, session, render_template
import discord

giveaway_bp = Blueprint('giveaway', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(giveaway_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/giveaway.py dashboard/app.py
git commit -m "refactor: move giveaway routes into dashboard/blueprints/giveaway.py"
```

---

### Task 23: `polls_bp` — poll administration

**Files:**
- Create: `dashboard/blueprints/polls.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.polls.polls_bp`, registered with no prefix.

Moves: `admin_polls` (`/admin/polls`), `/api/polls/data`, `/api/polls/create`, `/api/polls/end`.

- [ ] **Step 1: Create the blueprint, move all 4 handlers verbatim.**

```python
# dashboard/blueprints/polls.py
from quart import Blueprint, request, jsonify, session, render_template

polls_bp = Blueprint('polls', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(polls_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/polls.py dashboard/app.py
git commit -m "refactor: move polls routes into dashboard/blueprints/polls.py"
```

---

### Task 24: `reminders_bp` — reminder administration

**Files:**
- Create: `dashboard/blueprints/reminders.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.reminders.reminders_bp`, registered with no prefix.

Moves: `admin_reminders` (`/admin/reminders`), `/api/reminders/data`, `/api/reminders/create`,
`/api/reminders/delete`.

- [ ] **Step 1: Create the blueprint, move all 4 handlers verbatim.**

```python
# dashboard/blueprints/reminders.py
from quart import Blueprint, request, jsonify, session, render_template

reminders_bp = Blueprint('reminders', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(reminders_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/reminders.py dashboard/app.py
git commit -m "refactor: move reminders routes into dashboard/blueprints/reminders.py"
```

---

### Task 25: `enroll_bp` — enrollment wizard + newspaper admin

**Files:**
- Create: `dashboard/blueprints/enroll.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.enroll.enroll_bp`, registered with no prefix.

Moves: `admin_enroll` (`/admin/enroll`), `admin_newspaper` (`/admin/newspaper`), `/api/enroll/data`,
`/api/enroll/save`.

- [ ] **Step 1: Create the blueprint, move all 4 handlers verbatim.**

```python
# dashboard/blueprints/enroll.py
from quart import Blueprint, request, jsonify, session, render_template

enroll_bp = Blueprint('enroll', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(enroll_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green (watch
  `tests/test_phase1_utilities.py::test_newspaper_dashboard_route`).

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/enroll.py dashboard/app.py
git commit -m "refactor: move enroll/newspaper routes into dashboard/blueprints/enroll.py"
```

---

### Task 26: `bot_update_bp` — self-update/restart

**Files:**
- Create: `dashboard/blueprints/bot_update.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces: `dashboard.blueprints.bot_update.bot_update_bp`, registered with no prefix.

Moves: `admin_update_bot` (`/api/admin/update` — spawns the `updater.py` subprocess, closes the bot,
schedules `shutdown_process` via `app.add_background_task`) and the `shutdown_process` helper it
schedules.

- [ ] **Step 1: Create the blueprint, move both functions verbatim.** `app.add_background_task` is
  called on the `current_app` proxy inside a blueprint route (Quart's `current_app` resolves to the
  same running `app` instance regardless of which blueprint the route is registered on), so no
  special handling is needed beyond importing `current_app` from `quart` if the current code doesn't
  already reference `app` directly by name.

```python
# dashboard/blueprints/bot_update.py
import subprocess
import sys
from quart import Blueprint, request, jsonify, session, current_app

bot_update_bp = Blueprint('bot_update', __name__)
```

- [ ] **Step 2: Register** — `app.register_blueprint(bot_update_bp)`.

- [ ] **Step 3: Run the full suite** — `pytest -v`, expect all green.

- [ ] **Step 4: Commit**

```bash
git add dashboard/blueprints/bot_update.py dashboard/app.py
git commit -m "refactor: move bot self-update route into dashboard/blueprints/bot_update.py"
```

---

### Task 27: Final composition-root cleanup + manual dashboard verification

**Files:**
- Modify: `dashboard/app.py`

**Interfaces:**
- Consumes: nothing new — this task only removes now-dead code and verifies what remains.

By this task, every route has moved out of `dashboard/app.py` into one of the 24 blueprints from
Tasks 3–26. What's left in `app.py` should now be: the `Quart(__name__)` construction, `app.secret_key`,
`app.bot = None`, the `check_csrf`/`check_api_auth`/`add_security_headers` `before_request`/
`after_request` functions and their registrations, `inject_user`/`inject_theme` context processors,
any `app.add_template_filter` registrations (`format_bold`, `format_custom_emoji`,
`parse_pulp_talent`), the `app_startup` `before_serving` hook, and the 24 blueprint imports +
`register_blueprint` calls.

- [ ] **Step 1: Confirm nothing was missed**

Run: `grep -n "@app.route" dashboard/app.py`
Expected: no output (zero remaining route decorators — everything moved to a blueprint).

- [ ] **Step 2: Remove now-unused imports from `dashboard/app.py`**

Any import that was only used by a since-moved route handler (e.g. `feedparser`, if `rss.py` was the
only consumer) is now dead in `app.py`. Remove imports that are no longer referenced anywhere in the
remaining file — check each import against the file's remaining content before deleting it; don't
remove anything still used by `app_startup`, the before/after-request hooks, or the context
processors/template filters.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: all tests pass, including Task 1's `test_registered_route_count_is_stable` (confirms the
total route count is still exactly what it was before Phase 1 started) and the full non-404/500
sweep across all 24 blueprints.

- [ ] **Step 4: Manual dashboard verification**

Per the design spec's testing strategy for this phase, do one manual spot-check in a browser before
sign-off: start the bot with `enable_dashboard: true` in `config.json` (or run
`python -c "import asyncio; from hypercorn.asyncio import serve; from hypercorn.config import Config; from dashboard.app import app; asyncio.run(serve(app, Config()))"`
for a dashboard-only smoke run without needing a real Discord token), open `http://localhost:5000`,
log in, and click through at least: the character list, one `/render/*` page, the admin soundboard
page, and the admin karma page — confirming each renders without a 500 and its JS-driven `/api/*`
data endpoint returns data. Note the result in this task's completion notes.

- [ ] **Step 5: Commit**

```bash
git add dashboard/app.py
git commit -m "refactor: clean up dashboard/app.py into a thin composition root"
```

---

## Definition of Done for Phase 1

- `grep -n "@app.route" dashboard/app.py` returns nothing — every route lives in a blueprint.
- `pytest -v` passes with 0 failures, including the Task 1 route-inventory sweep confirming the
  exact same set of routes resolves as before this phase started.
- No dashboard file exceeds a few hundred lines (verify with `wc -l dashboard/app.py
  dashboard/blueprints/*.py` — the former ~4577-line file should now be under 300 lines; the largest
  blueprint, `soundboard.py`, will be the biggest of the new files but still far smaller than the
  original monolith).
- `commands/music.py` and `commands/roll.py` both import `guild_mixers`/`server_volumes` from
  `dashboard.state`, not `dashboard.app` — confirmed by Task 2 and never regressed by later tasks
  (none of Tasks 3–27 touch those two files again).
- Manual browser spot-check (Task 27, Step 4) confirms the dashboard serves correctly end-to-end,
  not just per-route in isolation.
