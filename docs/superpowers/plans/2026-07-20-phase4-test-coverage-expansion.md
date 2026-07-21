# Phase 4 — Test Coverage Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class unit test coverage for every module extracted or split in Phases 1-2 (24 `dashboard/blueprints/*.py` files, 12 `commands/_foo.py` companion files) that currently has zero or only smoke-level coverage, and expand regression coverage on the game-logic state machines beyond the smoke level Phase 0 established.

**Architecture:** No production code changes anywhere in this phase — every task adds a new test file (or, for a handful of blueprints that already have partial coverage, extends an existing one) against the CURRENT, unmodified behavior of the target module. This is characterization/coverage work, not refactoring: if a test reveals what looks like a bug in existing behavior, the task is to document it as a finding for the controller to triage (fix in a follow-up, or assert the existing — possibly surprising — behavior as the current contract), not to silently "fix" the code mid-task.

**Tech Stack:** Python 3.11+, `pytest` + `pytest-asyncio` (existing dev dependencies), Quart test client (`tests/test_dashboard_routes.py`'s `client` fixture pattern), `unittest.mock.patch`/`monkeypatch`/`AsyncMock`/`MagicMock`.

## Global Constraints

- **Zero production code changes.** Every task in this phase creates or extends a test file only. If an implementer finds what looks like a real bug while writing a test, they stop, document it in their report, and do NOT fix it as part of this phase — flag it for the controller to decide (matches this repo's established practice from Phases 2-3, where implementer-caught brief gaps were escalated rather than silently patched).
- **By-name import / mock-patch-target discipline.** Any test that patches a function must patch it at the exact module namespace where the code under test looks it up, not where the function is originally defined. This repo has hit this gotcha repeatedly (Phases 1-3): e.g. `dashboard/blueprints/*.py` files do `from dashboard.app import is_admin`, so patch at `dashboard.blueprints.<module>.is_admin`; `loadnsave` names imported by value into a blueprint or cog module must be patched at that importing module's own namespace if that module (not just `loadnsave` itself) needs isolating. Before writing any patch, read the actual import statement in the file under test.
- **Authenticated/mutating dashboard routes need the full auth+CSRF fixture stack.** Any test that POSTs to (or otherwise mutates via) an authenticated `/admin/*` or `/api/*` route needs: (1) a `login(client)` helper setting `session['logged_in'] = True` via `client.session_transaction()` (established pattern in `tests/test_phase1_utilities.py`), (2) an `Origin: http://localhost` header on the request (required by `dashboard/app.py`'s `check_csrf` before_request hook once logged in), and (3) if the route also has its own internal `is_admin()` gate, patch that at the correct by-name-import site. `tests/test_loadnsave_file_browser_cache.py` is the reference implementation combining all three correctly.
- **Isolate `data/`-folder writes.** Any test that exercises a route/function which reads or writes `data/`-folder JSON via `loadnsave` must isolate `DATA_FOLDER` to a `tmp_path` via `monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))` — AND, if the module under test imports `DATA_FOLDER` (or any loadnsave name) by value into its own namespace, ALSO patch that module's own binding. Getting only the `loadnsave`-level patch and missing the by-value-imported local binding caused a near-miss real-disk-write bug in Phase 3 (Task 4) — treat this as a hard requirement, not a nice-to-have, for every new test touching `data/`.
- **No duplication of existing coverage.** Before writing a test for a blueprint or module that already has SOME coverage (`render.py`, `grimoire.py`, `core.py`, `admin.py`, `fonts_admin.py`, `enroll.py`, `file_browser.py` — see each task's brief for exactly what's already covered), read the existing test file(s) first and only add genuinely missing cases.
- **Follow the `test_<module>_<aspect>.py` naming convention**, not the older `phaseN_*` naming — e.g. `test_blueprint_karma.py`, `test_commands_roll_views.py` — matching the convention already established in Phase 0/3's newer test files (`test_chase_session.py`, `test_loadnsave_*`).
- **Substituted game-logic scope.** The original design spec named "combat death/unconsciousness" and "chase escape/capture" as edge cases to test — research confirmed neither exists as code anywhere in this repo (HP is only ever displayed, never checked against a death/unconsciousness threshold; chase's "caught"/"escaped" participant states are declared but never transitioned to by any code path). Per an explicit user decision, this phase substitutes real, currently-untested state machines that serve the same "beyond smoke level" intent: combat's weapon-jam/reload/malfunction-roll flow, chase's hazard pass/fail branch and dashboard action-economy handlers, and the newinvestigator wizard's step-to-step transition chain plus its two real back-navigation handlers.
- **Full test suite stays green after every task.** Run `pytest -v` (or `.venv/bin/python -m pytest -v` if a `.venv` exists) after each task; 0 failures before moving to the next task.

### Testing discord.ui classes (applies to every `commands/_foo.py` companion-file task)

This repo runs discord.py 2.6.4. Constructing and exercising `discord.ui.View`/`Modal`/`Select` subclasses in a unit test (no real Discord connection) requires matching the library's actual internals, not guessing:

- **Async context is mandatory.** Every test that constructs a `discord.ui.View`/`Modal` subclass must be `@pytest.mark.asyncio async def` — `BaseView.__init__` calls `asyncio.get_running_loop()` unconditionally, so construction outside a running loop raises `RuntimeError`.
- **Modal field values are set via the private `_value` attribute** — `modal.field._value = "..."`, or `.field.component._value = "..."` for `Label`-wrapped fields (used throughout the newer Components-V2 modals like `SkillPointSetModal`/`BasicInfoModal`). `TextInput.value` has no public setter; `_value` is exactly what discord.py itself populates from real payloads via `refresh_state`.
- **Select/UserSelect/RoleSelect/ChannelSelect "what the user picked" is simulated via `select._values = [...]`** — same reasoning as above.
- **Decorated `@discord.ui.button`/`@discord.ui.select` callbacks are invoked as `await view.some_button.callback(interaction)`** — post-`__init__`, `view.some_button` is the real item instance and `.callback` is discord.py's `_ViewCallback` wrapper supplying `(view, interaction, item)` automatically.
- **Cog mocking splits by sync/async.** `commands/newinvestigator.py`'s step_*/pulp_*/mode_*/finish_*/proceed_*/assign_* methods are `async def` (use `AsyncMock`), but `roll_stat_formula`, `is_skill_allowed_for_archetype`, `calculate_occupation_points` are plain `def` (must be `MagicMock`, not `AsyncMock`, or unpacking the return value breaks). Same split applies to `commands/roll.py`'s `calculate_roll_result`/`evaluate_dice_expression` (both sync, used throughout `_roll_views.py` and `_mychar_roll.py`).
- **`loadnsave` patches target the importing module's namespace** (e.g. `commands._journal_views.load_journal_data`), matching the existing `patch("commands.newinvestigator.BasicInfoStartView")` convention in `tests/test_data_schema.py` — with one exception: `_mychar_roll.py::SkillRollSelect.callback` does a **local** `from loadnsave import load_luck_stats` inside the function body, so that one must be patched at `loadnsave.load_luck_stats` directly, not `commands._mychar_roll.load_luck_stats`.

---

### Task 1: Add tests for dashboard/blueprints/bot_update.py

**Files:**
- Create: `tests/test_blueprint_bot_update.py`

**Interfaces:**
- Consumes: `dashboard.blueprints.bot_update.admin_update_bot` (route `POST /api/admin/update`), `dashboard.blueprints.bot_update.shutdown_process`, module-level `os`, `sys`, `subprocess`, `app` (from `dashboard.app`)
- Fixtures reused: `client` pattern from `tests/test_dashboard_routes.py`, `mock_dependencies` autouse fixture, `login(client)` helper from `tests/test_phase1_utilities.py`, CSRF `Origin` header pattern from `tests/test_loadnsave_file_browser_cache.py`

- [ ] **Step 1: Write the test(s)**

```python
import os
import sys
import subprocess

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from dashboard.app import app
import dashboard.blueprints.bot_update as bot_update


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


@pytest.fixture(autouse=True)
def reset_bot(monkeypatch):
    # admin_update_bot() touches app.bot; keep it None unless a test opts in.
    monkeypatch.setattr(app, "bot", None)


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.mark.asyncio
async def test_admin_update_unauthorized_without_login(client):
    """Not logged in -> rejected before the destructive logic ever runs."""
    response = await client.post('/api/admin/update', json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_update_missing_updater_script_returns_500(client):
    await login(client)
    with patch('dashboard.blueprints.bot_update.os.path.exists', return_value=False), \
         patch('dashboard.blueprints.bot_update.subprocess.Popen') as mock_popen:
        response = await client.post(
            '/api/admin/update', json={}, headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 500
        data = await response.get_json()
        assert data == {"status": "error", "message": "Updater script not found"}
        mock_popen.assert_not_called()


@pytest.mark.asyncio
async def test_admin_update_success_spawns_updater_without_infodata_flag(client):
    """
    subprocess.Popen and app.add_background_task (which schedules sys.exit via
    shutdown_process) are mocked so the test process is never actually killed or
    replaced -- we only verify the *decision logic*: the right command is built
    and the right shutdown hook is registered, not that a restart truly happens.
    """
    await login(client)
    with patch('dashboard.blueprints.bot_update.os.path.exists', return_value=True), \
         patch('dashboard.blueprints.bot_update.subprocess.Popen') as mock_popen, \
         patch.object(app, 'add_background_task') as mock_add_bg:
        response = await client.post(
            '/api/admin/update', json={}, headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert data == {"status": "success", "message": "Update started. Bot is restarting..."}

        expected_cmd = [sys.executable, "updater.py", str(os.getpid())]
        assert mock_popen.call_count == 1
        called_cmd = mock_popen.call_args[0][0]
        assert called_cmd == expected_cmd
        if os.name == 'nt':
            assert mock_popen.call_args.kwargs.get('creationflags') == subprocess.CREATE_NEW_CONSOLE
        else:
            assert mock_popen.call_args.kwargs.get('start_new_session') is True

        mock_add_bg.assert_called_once_with(bot_update.shutdown_process)


@pytest.mark.asyncio
async def test_admin_update_appends_infodata_flag_when_requested(client):
    await login(client)
    with patch('dashboard.blueprints.bot_update.os.path.exists', return_value=True), \
         patch('dashboard.blueprints.bot_update.subprocess.Popen') as mock_popen, \
         patch.object(app, 'add_background_task'):
        response = await client.post(
            '/api/admin/update',
            json={"update_infodata": True},
            headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 200
        called_cmd = mock_popen.call_args[0][0]
        assert called_cmd == [sys.executable, "updater.py", str(os.getpid()), "--update-infodata"]


@pytest.mark.asyncio
async def test_admin_update_closes_bot_when_present(client, monkeypatch):
    await login(client)
    fake_bot = AsyncMock()
    monkeypatch.setattr(app, "bot", fake_bot)

    with patch('dashboard.blueprints.bot_update.os.path.exists', return_value=True), \
         patch('dashboard.blueprints.bot_update.subprocess.Popen'), \
         patch.object(app, 'add_background_task'):
        response = await client.post(
            '/api/admin/update', json={}, headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 200
        fake_bot.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_update_popen_failure_returns_500_with_error_message(client):
    await login(client)
    with patch('dashboard.blueprints.bot_update.os.path.exists', return_value=True), \
         patch('dashboard.blueprints.bot_update.subprocess.Popen', side_effect=OSError("spawn failed")), \
         patch.object(app, 'add_background_task') as mock_add_bg:
        response = await client.post(
            '/api/admin/update', json={}, headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 500
        data = await response.get_json()
        assert data == {"status": "error", "message": "spawn failed"}
        # Must not proceed to schedule a shutdown if the updater never launched.
        mock_add_bg.assert_not_called()
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_bot_update.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_bot_update.py
git commit -m "test: add coverage for dashboard/blueprints/bot_update.py"
```

---

### Task 2: Add tests for dashboard/blueprints/karma.py

**Files:**
- Create: `tests/test_blueprint_karma.py`

**Interfaces:**
- Consumes: `admin_karma` (`GET /admin/karma`), `save_karma` (`POST /api/karma/save`), `save_karma_roles` (`POST /api/karma/roles/save`), `get_karma_users` (`GET /api/karma/users/<guild_id>`), `recalculate_karma` (`POST /api/karma/recalculate`), `detect_karma_emojis` (`POST /api/karma/detect_emojis`), all in `dashboard.blueprints.karma`
- Fixtures reused: `client`, `mock_dependencies`, `login(client)`, CSRF `Origin` header, `isolated_data_dir` pattern (`monkeypatch.setattr(loadnsave, "DATA_FOLDER", ...)`) from `tests/test_loadnsave_roundtrip.py`

- [ ] **Step 1: Write the test(s)**

```python
import asyncio
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, patch

import loadnsave
from dashboard.app import app
import dashboard.blueprints.karma as karma


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


@pytest.fixture(autouse=True)
def reset_bot(monkeypatch):
    monkeypatch.setattr(app, "bot", None)


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    # karma_settings.json has no in-memory cache in loadnsave.py, only DATA_FOLDER
    # needs isolating -- karma.py imports load/save_karma_settings by value, but
    # those functions still execute against loadnsave's own module globals.
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    return tmp_path


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


class FakeRole:
    def __init__(self, id, name, is_default=False, managed=False):
        self.id = id
        self.name = name
        self._is_default = is_default
        self.managed = managed

    def is_default(self):
        return self._is_default


class FakeChannel:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class FakeReaction:
    def __init__(self, emoji, count):
        self.emoji = emoji
        self.count = count


class FakeMessage:
    def __init__(self, reactions=None):
        self.reactions = reactions or []


class FakeChannelWithHistory(FakeChannel):
    def __init__(self, id, name, messages=None):
        super().__init__(id, name)
        self._messages = messages or []

    async def history(self, limit=20):
        for m in self._messages[:limit]:
            yield m


class FakeGuild:
    def __init__(self, id, name, text_channels=None, roles=None):
        self.id = id
        self.name = name
        self.text_channels = text_channels or []
        self.roles = roles or []

    def get_role(self, role_id):
        return next((r for r in self.roles if r.id == role_id), None)

    def get_channel(self, channel_id):
        return next((c for c in self.text_channels if c.id == channel_id), None)


class FakeLoop:
    def __init__(self):
        self.tasks = []

    def create_task(self, coro):
        task = asyncio.ensure_future(coro)
        self.tasks.append(task)
        return task


class FakeKarmaCog:
    def __init__(self, leaderboard_data=None):
        self.run_guild_karma_update_calls = []
        self.recalculate_karma_calls = []
        self.leaderboard_data = leaderboard_data or []

    async def run_guild_karma_update(self, guild_id):
        self.run_guild_karma_update_calls.append(guild_id)

    async def recalculate_karma(self, guild_id):
        self.recalculate_karma_calls.append(guild_id)

    async def get_guild_leaderboard_data(self, guild_id):
        return self.leaderboard_data


class FakeBot:
    def __init__(self, guilds=None, cogs=None):
        self.guilds = guilds or []
        self._cogs = cogs or {}
        self.loop = FakeLoop()

    def get_guild(self, guild_id):
        return next((g for g in self.guilds if g.id == guild_id), None)

    def get_cog(self, name):
        return self._cogs.get(name)


# --- /admin/karma ---

@pytest.mark.asyncio
async def test_admin_karma_redirects_if_not_logged_in(client):
    response = await client.get('/admin/karma')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_admin_karma_bot_not_initialized_returns_500(client):
    await login(client)
    response = await client.get('/admin/karma')
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_admin_karma_resolves_roles_and_flags_unknown_role(client, isolated_data_dir, monkeypatch):
    await login(client)
    guild = FakeGuild(
        id=555,
        name="TestGuild",
        text_channels=[FakeChannel(1, "general")],
        roles=[
            FakeRole(111, "Investigator", is_default=False, managed=False),
            FakeRole(555, "@everyone", is_default=True),
            FakeRole(777, "BotIntegration", managed=True),
        ],
    )
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    await loadnsave.save_karma_settings({
        "555": {"channel_id": 1, "roles": {"10": "111", "50": "999"}}
    })

    response = await client.get('/admin/karma')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert "Investigator" in html
    assert "Unknown Role (999)" in html
    # @everyone / managed roles must be filtered out of the dropdown list.
    assert "BotIntegration" not in html


# --- /api/karma/save ---

@pytest.mark.asyncio
async def test_save_karma_missing_guild_id_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/karma/save', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_karma_channel_none_deletes_existing_settings(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_karma_settings({"555": {"channel_id": 1, "roles": {}}})

    response = await client.post(
        '/api/karma/save',
        json={"guild_id": "555", "channel_id": "none"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_karma_settings()
    assert "555" not in reloaded


@pytest.mark.asyncio
async def test_save_karma_preserves_existing_roles_and_defaults_emojis(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_karma_settings({"555": {"channel_id": 1, "roles": {"10": "111"}}})

    response = await client.post(
        '/api/karma/save',
        json={"guild_id": "555", "channel_id": "2"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_karma_settings()
    assert reloaded["555"]["channel_id"] == 2
    assert reloaded["555"]["roles"] == {"10": "111"}
    assert reloaded["555"]["upvote_emoji"] == "👌"
    assert reloaded["555"]["downvote_emoji"] == "🤏"


# --- /api/karma/roles/save ---

@pytest.mark.asyncio
async def test_save_karma_roles_missing_guild_id_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/karma/roles/save', json={"roles": []}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_karma_roles_converts_list_to_map_and_triggers_cog_update(client, isolated_data_dir, monkeypatch):
    await login(client)
    cog = FakeKarmaCog()
    monkeypatch.setattr(app, "bot", FakeBot(cogs={"Karma": cog}))

    response = await client.post(
        '/api/karma/roles/save',
        json={"guild_id": "555", "roles": [{"threshold": 10, "role_id": 111}, {"threshold": 50, "role_id": 222}]},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_karma_settings()
    assert reloaded["555"]["roles"] == {"10": 111, "50": 222}

    await asyncio.sleep(0)
    assert cog.run_guild_karma_update_calls == ["555"]


# --- /api/karma/users/<guild_id> ---

@pytest.mark.asyncio
async def test_get_karma_users_no_bot_returns_empty_list(client):
    await login(client)
    response = await client.get('/api/karma/users/555')
    assert response.status_code == 200
    assert await response.get_json() == []


@pytest.mark.asyncio
async def test_get_karma_users_delegates_to_cog(client, monkeypatch):
    await login(client)
    cog = FakeKarmaCog(leaderboard_data=[{"user_id": "1", "karma": 42}])
    monkeypatch.setattr(app, "bot", FakeBot(cogs={"Karma": cog}))

    response = await client.get('/api/karma/users/555')
    assert response.status_code == 200
    assert await response.get_json() == [{"user_id": "1", "karma": 42}]


# --- /api/karma/recalculate ---

@pytest.mark.asyncio
async def test_recalculate_karma_missing_guild_id_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/karma/recalculate', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_recalculate_karma_no_cog_returns_500(client, monkeypatch):
    await login(client)
    monkeypatch.setattr(app, "bot", FakeBot())
    response = await client.post(
        '/api/karma/recalculate', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_recalculate_karma_schedules_background_task(client, monkeypatch):
    await login(client)
    cog = FakeKarmaCog()
    monkeypatch.setattr(app, "bot", FakeBot(cogs={"Karma": cog}))

    response = await client.post(
        '/api/karma/recalculate', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "success"

    await asyncio.sleep(0)
    assert cog.recalculate_karma_calls == ["555"]


# --- /api/karma/detect_emojis ---

@pytest.mark.asyncio
async def test_detect_emojis_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/karma/detect_emojis', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_detect_emojis_guild_not_found_returns_404(client, monkeypatch):
    await login(client)
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[]))
    response = await client.post(
        '/api/karma/detect_emojis',
        json={"guild_id": "555", "channel_id": "1"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_detect_emojis_no_reactions_returns_400(client, monkeypatch):
    await login(client)
    channel = FakeChannelWithHistory(1, "general", messages=[FakeMessage(reactions=[])])
    guild = FakeGuild(555, "TestGuild", text_channels=[channel])
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    response = await client.post(
        '/api/karma/detect_emojis',
        json={"guild_id": "555", "channel_id": "1"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400
    data = await response.get_json()
    assert "No reactions found" in data["message"]


@pytest.mark.asyncio
async def test_detect_emojis_insufficient_unique_emojis_returns_400(client, monkeypatch):
    await login(client)
    messages = [FakeMessage(reactions=[FakeReaction("👍", 3)])]
    channel = FakeChannelWithHistory(1, "general", messages=messages)
    guild = FakeGuild(555, "TestGuild", text_channels=[channel])
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    response = await client.post(
        '/api/karma/detect_emojis',
        json={"guild_id": "555", "channel_id": "1"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400
    data = await response.get_json()
    assert "Insufficient data" in data["message"]


@pytest.mark.asyncio
async def test_detect_emojis_returns_top_two_by_reaction_count(client, monkeypatch):
    await login(client)
    messages = [
        FakeMessage(reactions=[FakeReaction("👍", 5), FakeReaction("👎", 3), FakeReaction("😂", 1)]),
        FakeMessage(reactions=[FakeReaction("👍", 2)]),
    ]
    channel = FakeChannelWithHistory(1, "general", messages=messages)
    guild = FakeGuild(555, "TestGuild", text_channels=[channel])
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    response = await client.post(
        '/api/karma/detect_emojis',
        json={"guild_id": "555", "channel_id": "1"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "success"
    assert data["upvote"] == "👍"   # total count 7, highest
    assert data["downvote"] == "👎"  # total count 3, second highest
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_karma.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_karma.py
git commit -m "test: add coverage for dashboard/blueprints/karma.py"
```

---

### Task 3: Add tests for dashboard/blueprints/music.py

**Files:**
- Create: `tests/test_blueprint_music.py`

**Interfaces:**
- Consumes: `music_data` (`GET /api/music/data`), `music_control` (`POST /api/music/control`, actions `pause`/`resume`/`skip`/`loop`/`volume`/`remove`), `music_ban` (`POST /api/music/ban`), all in `dashboard.blueprints.music`
- Fixtures reused: `client`, `mock_dependencies`, `login(client)`, CSRF `Origin` header, `isolated_data_dir` (`loadnsave.DATA_FOLDER` + relevant caches)

- [ ] **Step 1: Write the test(s)**

```python
import pytest
from unittest.mock import AsyncMock, patch

import loadnsave
from dashboard.app import app
import dashboard.blueprints.music as music


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


@pytest.fixture(autouse=True)
def reset_bot(monkeypatch):
    monkeypatch.setattr(app, "bot", None)


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_SERVER_VOLUMES_CACHE", None)
    monkeypatch.setattr(loadnsave, "_MUSIC_BLACKLIST_CACHE", None)
    # music.py does `from dashboard.state import server_volumes` -- a dict
    # object, imported by reference, so mutating it in the route mutates the
    # same dict everywhere. We swap the blueprint's own binding for a fresh
    # dict so tests don't leak state into each other or into dashboard.state.
    monkeypatch.setattr(music, "server_volumes", {})
    return tmp_path


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


class FakeTrack:
    def __init__(self, title="Song", url="http://example.com/song", thumbnail="thumb.png",
                 volume=1.0, loop=False, paused=False, finished=False, duration=100, elapsed=1.5):
        self.metadata = {"title": title, "original_url": url, "thumbnail": thumbnail, "duration": duration}
        self.volume = volume
        self.loop = loop
        self.paused = paused
        self.finished = finished
        self.elapsed = elapsed


class FakeMusicCog:
    def __init__(self):
        self.current_track = {}
        self.queue = {}
        self.loop_mode = {}
        self.blacklist = []
        self.process_queue_calls = []

    async def _process_queue(self, guild_id):
        self.process_queue_calls.append(guild_id)


class FakeVoiceClient:
    def __init__(self):
        self.paused = False
        self.resumed = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.resumed = True


class FakeGuild:
    def __init__(self, id, voice_client=None):
        self.id = id
        self.name = f"Guild{id}"
        self.voice_client = voice_client


class FakeBot:
    def __init__(self, music_cog, guilds=None):
        self.music_cog = music_cog
        self.guilds = guilds or []

    def get_guild(self, guild_id):
        return next((g for g in self.guilds if g.id == guild_id), None)


@pytest.mark.asyncio
async def test_music_data_no_bot_returns_empty_guilds(client):
    await login(client)
    response = await client.get('/api/music/data')
    assert response.status_code == 200
    assert await response.get_json() == {"guilds": {}}


@pytest.mark.asyncio
async def test_music_data_reports_current_track_and_queue(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    cog.current_track["555"] = FakeTrack(title="Ia Ia", volume=0.75, loop=True)
    cog.loop_mode["555"] = "track"
    cog.queue["555"] = [{"title": "Next", "original_url": "u", "thumbnail": "t", "duration": 50}]
    cog.blacklist = ["http://banned"]
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.get('/api/music/data')
    assert response.status_code == 200
    data = await response.get_json()
    assert data["guilds"]["555"]["current_track"]["title"] == "Ia Ia"
    assert data["guilds"]["555"]["current_track"]["volume"] == 75
    assert data["guilds"]["555"]["current_track"]["loop_mode"] == "track"
    assert data["guilds"]["555"]["queue"][0]["title"] == "Next"
    assert data["blacklist"] == ["http://banned"]


@pytest.mark.asyncio
async def test_music_data_hides_finished_track(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    cog.current_track["555"] = FakeTrack(finished=True)
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.get('/api/music/data')
    data = await response.get_json()
    assert data["guilds"]["555"]["current_track"] is None


@pytest.mark.asyncio
async def test_music_control_pause_pauses_track_and_voice_client(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    track = FakeTrack(paused=False)
    cog.current_track["555"] = track
    vc = FakeVoiceClient()
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555, voice_client=vc)]))

    response = await client.post(
        '/api/music/control',
        json={"action": "pause", "guild_id": "555"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert track.paused is True
    assert vc.paused is True


@pytest.mark.asyncio
async def test_music_control_skip_marks_finished_and_processes_queue(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    track = FakeTrack(finished=False)
    cog.current_track["555"] = track
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/control',
        json={"action": "skip", "guild_id": "555"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert track.finished is True
    assert cog.process_queue_calls == ["555"]


@pytest.mark.asyncio
async def test_music_control_loop_cycles_off_to_track_to_queue_to_off(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    track = FakeTrack(finished=False)
    cog.current_track["555"] = track
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    async def cycle():
        return await client.post(
            '/api/music/control',
            json={"action": "loop", "guild_id": "555"},
            headers={"Origin": "http://localhost"}
        )

    await cycle()
    assert cog.loop_mode["555"] == "track"
    assert track.loop is True

    await cycle()
    assert cog.loop_mode["555"] == "queue"
    assert track.loop is False

    await cycle()
    assert cog.loop_mode["555"] == "off"
    assert track.loop is False


@pytest.mark.asyncio
async def test_music_control_volume_clamps_and_persists(client, isolated_data_dir, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    track = FakeTrack()
    cog.current_track["555"] = track
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/control',
        json={"action": "volume", "guild_id": "555", "volume": 150},  # out of range
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert music.server_volumes["555"]["music"] == 1.0  # clamped to 100 -> 1.0
    assert track.volume == 1.0 ** 2

    reloaded = await loadnsave.load_server_volumes()
    assert reloaded["555"]["music"] == 1.0


@pytest.mark.asyncio
async def test_music_control_remove_pops_queue_index(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    cog.queue["555"] = [{"title": "A"}, {"title": "B"}]
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/control',
        json={"action": "remove", "guild_id": "555", "index": 0},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.queue["555"] == [{"title": "B"}]


@pytest.mark.asyncio
async def test_music_ban_missing_url_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/music/ban', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_music_ban_adds_url_persists_and_skips_playing_track(client, isolated_data_dir, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    track = FakeTrack(url="http://example.com/banned", finished=False)
    cog.current_track["555"] = track
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/ban',
        json={"url": "http://example.com/banned"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.blacklist == ["http://example.com/banned"]
    assert track.finished is True

    reloaded = await loadnsave.load_music_blacklist()
    assert reloaded == ["http://example.com/banned"]


@pytest.mark.asyncio
async def test_music_ban_does_not_duplicate_existing_entry(client, isolated_data_dir, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    cog.blacklist = ["http://example.com/banned"]
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/ban',
        json={"url": "http://example.com/banned"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.blacklist == ["http://example.com/banned"]
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_music.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_music.py
git commit -m "test: add coverage for dashboard/blueprints/music.py"
```

---

### Task 4: Add tests for dashboard/blueprints/reaction_roles.py

**Files:**
- Create: `tests/test_blueprint_reaction_roles.py`

**Interfaces:**
- Consumes: `reaction_roles_data` (`GET /api/reactionroles/data`), `reaction_roles_add` (`POST /api/reactionroles/add`), `reaction_roles_delete` (`POST /api/reactionroles/delete`), all in `dashboard.blueprints.reaction_roles`
- Fixtures reused: `client`, `mock_dependencies`, `login(client)`, CSRF `Origin` header, `isolated_data_dir` (`loadnsave.DATA_FOLDER` + `_REACTION_ROLES_CACHE`)

- [ ] **Step 1: Write the test(s)**

```python
from types import SimpleNamespace

import pytest
import discord
from unittest.mock import AsyncMock, patch

import loadnsave
from dashboard.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


@pytest.fixture(autouse=True)
def reset_bot(monkeypatch):
    monkeypatch.setattr(app, "bot", None)


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_REACTION_ROLES_CACHE", None)
    return tmp_path


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


class FakeRole:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class FakeMessage:
    def __init__(self, id):
        self.id = id
        self.reactions_added = []


class FakeChannel:
    def __init__(self, id, name, message=None, raise_exc=None):
        self.id = id
        self.name = name
        self._message = message
        self._raise_exc = raise_exc

    async def fetch_message(self, message_id):
        if self._raise_exc:
            raise self._raise_exc
        if self._message and self._message.id == int(message_id):
            self._message.add_reaction = AsyncMock(
                side_effect=lambda e: self._message.reactions_added.append(e)
            )
            return self._message
        raise discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "Unknown Message")


class FakeGuild:
    def __init__(self, id, name, text_channels=None, roles=None):
        self.id = id
        self.name = name
        self.text_channels = text_channels or []
        self.roles = roles or []

    def get_role(self, role_id):
        return next((r for r in self.roles if r.id == role_id), None)

    def get_channel(self, channel_id):
        return next((c for c in self.text_channels if c.id == channel_id), None)


class FakeBot:
    def __init__(self, guilds=None, emojis=None, user=None):
        self.guilds = guilds or []
        self.emojis = emojis or []
        self.user = user or SimpleNamespace(id=999)
        self.cached_messages = []

    def get_guild(self, guild_id):
        return next((g for g in self.guilds if g.id == guild_id), None)

    def get_emoji(self, emoji_id):
        return next((e for e in self.emojis if e.id == emoji_id), None)


# --- GET /api/reactionroles/data ---

@pytest.mark.asyncio
async def test_reaction_roles_data_no_bot_returns_empty(client):
    await login(client)
    response = await client.get('/api/reactionroles/data')
    assert response.status_code == 200
    assert await response.get_json() == {"guilds": [], "rules": []}


@pytest.mark.asyncio
async def test_reaction_roles_data_builds_rules_new_format(client, isolated_data_dir, monkeypatch):
    await login(client)
    role = FakeRole(111, "Cultist")
    guild = FakeGuild(555, "TestGuild", roles=[role])
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    await loadnsave.save_reaction_roles({
        "555": {"1000": {"channel_id": "1", "roles": {"👍": "111"}}}
    })

    response = await client.get('/api/reactionroles/data')
    data = await response.get_json()
    assert data["rules"] == [{
        "guild_id": "555", "guild_name": "TestGuild", "message_id": "1000",
        "emoji": "👍", "role_id": "111", "role_name": "Cultist"
    }]


@pytest.mark.asyncio
async def test_reaction_roles_data_builds_rules_old_format(client, isolated_data_dir, monkeypatch):
    await login(client)
    role = FakeRole(111, "Cultist")
    guild = FakeGuild(555, "TestGuild", roles=[role])
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    # Old format: message_data IS the emoji->role_id map directly.
    await loadnsave.save_reaction_roles({"555": {"1000": {"👍": "111"}}})

    response = await client.get('/api/reactionroles/data')
    data = await response.get_json()
    assert data["rules"][0]["role_name"] == "Cultist"


@pytest.mark.asyncio
async def test_reaction_roles_data_flags_deleted_role_and_unknown_guild(client, isolated_data_dir, monkeypatch):
    await login(client)
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[]))  # guild_id 555 not present

    await loadnsave.save_reaction_roles({"555": {"1000": {"roles": {"👍": "999"}}}})

    response = await client.get('/api/reactionroles/data')
    data = await response.get_json()
    assert data["rules"][0]["guild_name"] == "Unknown Guild (555)"
    assert data["rules"][0]["role_name"] == "Unknown Role"


# --- POST /api/reactionroles/add ---

@pytest.mark.asyncio
async def test_reaction_roles_add_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/reactionroles/add', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reaction_roles_add_guild_not_found_returns_400(client, monkeypatch):
    await login(client)
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[]))
    response = await client.post(
        '/api/reactionroles/add',
        json={"guild_id": "555", "message_id": "1", "role_id": "111", "emoji": "👍", "channel_id": "1"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400
    data = await response.get_json()
    assert "Guild not found" in data["message"]


@pytest.mark.asyncio
async def test_reaction_roles_add_message_not_found_returns_400(client, monkeypatch):
    await login(client)
    channel = FakeChannel(1, "general", raise_exc=discord.NotFound(
        SimpleNamespace(status=404, reason="Not Found"), "Unknown Message"
    ))
    guild = FakeGuild(555, "TestGuild", text_channels=[channel])
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    response = await client.post(
        '/api/reactionroles/add',
        json={"guild_id": "555", "message_id": "1", "role_id": "111", "emoji": "👍", "channel_id": "1"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400
    data = await response.get_json()
    assert "not found" in data["message"]


@pytest.mark.asyncio
async def test_reaction_roles_add_forbidden_returns_400(client, monkeypatch):
    await login(client)
    channel = FakeChannel(1, "general", raise_exc=discord.Forbidden(
        SimpleNamespace(status=403, reason="Forbidden"), "Missing Access"
    ))
    guild = FakeGuild(555, "TestGuild", text_channels=[channel])
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    response = await client.post(
        '/api/reactionroles/add',
        json={"guild_id": "555", "message_id": "1", "role_id": "111", "emoji": "👍", "channel_id": "1"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400
    data = await response.get_json()
    assert "permission" in data["message"]


@pytest.mark.asyncio
async def test_reaction_roles_add_success_creates_new_entry_and_reacts(client, isolated_data_dir, monkeypatch):
    await login(client)
    message = FakeMessage(id=1000)
    channel = FakeChannel(1, "general", message=message)
    guild = FakeGuild(555, "TestGuild", text_channels=[channel])
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    response = await client.post(
        '/api/reactionroles/add',
        json={"guild_id": "555", "message_id": "1000", "role_id": "111", "emoji": "👍", "channel_id": "1"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200

    reloaded = await loadnsave.load_reaction_roles()
    assert reloaded["555"]["1000"]["channel_id"] == "1"
    assert reloaded["555"]["1000"]["roles"] == {"👍": "111"}
    assert message.reactions_added == ["👍"]


@pytest.mark.asyncio
async def test_reaction_roles_add_migrates_old_format_and_merges(client, isolated_data_dir, monkeypatch):
    await login(client)
    message = FakeMessage(id=1000)
    channel = FakeChannel(1, "general", message=message)
    guild = FakeGuild(555, "TestGuild", text_channels=[channel])
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    await loadnsave.save_reaction_roles({"555": {"1000": {"👎": "222"}}})  # old bare-dict format

    response = await client.post(
        '/api/reactionroles/add',
        json={"guild_id": "555", "message_id": "1000", "role_id": "111", "emoji": "👍", "channel_id": "1"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_reaction_roles()
    assert reloaded["555"]["1000"]["roles"] == {"👎": "222", "👍": "111"}


# --- POST /api/reactionroles/delete ---

@pytest.mark.asyncio
async def test_reaction_roles_delete_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/reactionroles/delete', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reaction_roles_delete_rule_not_found_returns_404(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/reactionroles/delete',
        json={"guild_id": "555", "message_id": "1000", "emoji": "👍"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reaction_roles_delete_removes_entry_and_cleans_up_empty_dicts(client, isolated_data_dir):
    await login(client)
    # app.bot is None (default fixture) -- the discord-side reaction removal
    # block is entirely guarded by `if app.bot:`, so deletion logic is still
    # exercised without needing to fake message/channel discovery.
    await loadnsave.save_reaction_roles({"555": {"1000": {"channel_id": "1", "roles": {"👍": "111"}}}})

    response = await client.post(
        '/api/reactionroles/delete',
        json={"guild_id": "555", "message_id": "1000", "emoji": "👍"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_reaction_roles()
    assert "555" not in reloaded


@pytest.mark.asyncio
async def test_reaction_roles_delete_partial_cleanup_keeps_remaining_emoji(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_reaction_roles({
        "555": {"1000": {"channel_id": "1", "roles": {"👍": "111", "👎": "222"}}}
    })

    response = await client.post(
        '/api/reactionroles/delete',
        json={"guild_id": "555", "message_id": "1000", "emoji": "👍"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_reaction_roles()
    assert reloaded["555"]["1000"]["roles"] == {"👎": "222"}
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_reaction_roles.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_reaction_roles.py
git commit -m "test: add coverage for dashboard/blueprints/reaction_roles.py"
```

---

### Task 5: Add tests for dashboard/blueprints/gameroles.py

**Files:**
- Create: `tests/test_blueprint_gameroles.py`

**Interfaces:**
- Consumes: `gameroles_data` (`GET /api/gameroles/data`), `gameroles_emoji_set`/`gameroles_emoji_delete` (`POST /api/gameroles/emoji/set|delete`), `gameroles_save` (`POST /api/gameroles/save`), `gameroles_ignore_add`/`gameroles_ignore_remove` (`POST /api/gameroles/ignore/add|remove`), all in `dashboard.blueprints.gameroles`
- Fixtures reused: `client`, `mock_dependencies`, `login(client)`, CSRF `Origin` header, `isolated_data_dir` (`loadnsave.DATA_FOLDER` + `_GAMEROLE_SETTINGS_CACHE`)

- [ ] **Step 1: Write the test(s)**

```python
import pytest
from unittest.mock import AsyncMock, patch

import loadnsave
from dashboard.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


@pytest.fixture(autouse=True)
def reset_bot(monkeypatch):
    monkeypatch.setattr(app, "bot", None)


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_GAMEROLE_SETTINGS_CACHE", None)
    return tmp_path


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


class FakeGuild:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class FakeBot:
    def __init__(self, guilds=None, cogs=None):
        self.guilds = guilds or []
        self._cogs = cogs or {}

    def get_guild(self, guild_id):
        return next((g for g in self.guilds if g.id == guild_id), None)

    def get_cog(self, name):
        return self._cogs.get(name)


class FakeGamerRolesCog:
    def __init__(self):
        self.settings = {}
        self.emoji_calls = []

    async def get_settings(self, guild_id):
        return self.settings.setdefault(str(guild_id), {"ignored_activities": ["Custom Status"]})

    async def update_settings(self, guild_id, key, value):
        self.settings.setdefault(str(guild_id), {})[key] = value

    async def update_activity_emoji(self, guild, activity, emoji_char):
        self.emoji_calls.append((guild.id, activity, emoji_char))


@pytest.mark.asyncio
async def test_gameroles_data_no_bot_returns_empty(client):
    await login(client)
    response = await client.get('/api/gameroles/data')
    assert await response.get_json() == {"guilds": []}


@pytest.mark.asyncio
async def test_gameroles_data_applies_defaults(client, monkeypatch):
    await login(client)
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[FakeGuild(555, "TestGuild")]))

    response = await client.get('/api/gameroles/data')
    data = await response.get_json()
    assert data["guilds"][0]["settings"]["enabled"] is False
    assert data["guilds"][0]["settings"]["color"] == "#0000FF"
    assert data["guilds"][0]["settings"]["ignored_activities"] == ["Custom Status"]


@pytest.mark.asyncio
async def test_gameroles_emoji_set_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/gameroles/emoji/set', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_gameroles_emoji_set_guild_not_found_returns_404(client, monkeypatch):
    await login(client)
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[]))
    response = await client.post(
        '/api/gameroles/emoji/set',
        json={"guild_id": "555", "activity": "Playing", "emoji": "🎮"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_gameroles_emoji_set_delegates_to_cog(client, monkeypatch):
    await login(client)
    cog = FakeGamerRolesCog()
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[FakeGuild(555, "TestGuild")], cogs={"GamerRoles": cog}))

    response = await client.post(
        '/api/gameroles/emoji/set',
        json={"guild_id": "555", "activity": "Playing", "emoji": "🎮"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.emoji_calls == [(555, "Playing", "🎮")]


@pytest.mark.asyncio
async def test_gameroles_emoji_delete_delegates_to_cog_with_none(client, monkeypatch):
    await login(client)
    cog = FakeGamerRolesCog()
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[FakeGuild(555, "TestGuild")], cogs={"GamerRoles": cog}))

    response = await client.post(
        '/api/gameroles/emoji/delete',
        json={"guild_id": "555", "activity": "Playing"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.emoji_calls == [(555, "Playing", None)]


@pytest.mark.asyncio
async def test_gameroles_save_missing_guild_id_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/gameroles/save', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_gameroles_save_rejects_invalid_hex_color_via_cog(client, monkeypatch):
    await login(client)
    cog = FakeGamerRolesCog()
    monkeypatch.setattr(app, "bot", FakeBot(cogs={"GamerRoles": cog}))

    response = await client.post(
        '/api/gameroles/save',
        json={"guild_id": "555", "color": "not-a-color"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert "color" not in cog.settings.get("555", {})


@pytest.mark.asyncio
async def test_gameroles_save_falls_back_to_loadnsave_when_no_bot(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/gameroles/save',
        json={"guild_id": "555", "enabled": True, "color": "#ABCDEF"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_gamerole_settings()
    assert reloaded["555"]["enabled"] is True
    assert reloaded["555"]["color"] == "#ABCDEF"


@pytest.mark.asyncio
async def test_gameroles_ignore_add_appends_without_duplicating(client, monkeypatch):
    await login(client)
    cog = FakeGamerRolesCog()
    cog.settings["555"] = {"ignored_activities": ["Custom Status"]}
    monkeypatch.setattr(app, "bot", FakeBot(cogs={"GamerRoles": cog}))

    response = await client.post(
        '/api/gameroles/ignore/add',
        json={"guild_id": "555", "activity": "Spotify"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.settings["555"]["ignored_activities"] == ["Custom Status", "Spotify"]

    # Adding the same activity again must not duplicate it.
    await client.post(
        '/api/gameroles/ignore/add',
        json={"guild_id": "555", "activity": "Spotify"},
        headers={"Origin": "http://localhost"}
    )
    assert cog.settings["555"]["ignored_activities"] == ["Custom Status", "Spotify"]


@pytest.mark.asyncio
async def test_gameroles_ignore_remove_removes_activity(client, monkeypatch):
    await login(client)
    cog = FakeGamerRolesCog()
    cog.settings["555"] = {"ignored_activities": ["Custom Status", "Spotify"]}
    monkeypatch.setattr(app, "bot", FakeBot(cogs={"GamerRoles": cog}))

    response = await client.post(
        '/api/gameroles/ignore/remove',
        json={"guild_id": "555", "activity": "Spotify"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.settings["555"]["ignored_activities"] == ["Custom Status"]
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_gameroles.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_gameroles.py
git commit -m "test: add coverage for dashboard/blueprints/gameroles.py"
```

---

### Task 6: Add tests for dashboard/blueprints/pokemon.py

**Files:**
- Create: `tests/test_blueprint_pokemon.py`

**Interfaces:**
- Consumes: `pokemon_data` (`GET /api/pokemon/data`), `pokemon_save` (`POST /api/pokemon/save`), `pokemon_refresh` (`POST /api/pokemon/refresh`), `pokemon_push_weekly`/`pokemon_push_next` (`POST /api/pokemon/push_weekly|push_next`), all in `dashboard.blueprints.pokemon`
- Fixtures reused: `client`, `mock_dependencies`, `login(client)`, CSRF `Origin` header, `isolated_data_dir` (`loadnsave.DATA_FOLDER` + `_POGO_SETTINGS_CACHE`/`_POGO_EVENTS_CACHE`)

- [ ] **Step 1: Write the test(s)**

```python
import pytest
from unittest.mock import AsyncMock, patch

import loadnsave
from dashboard.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


@pytest.fixture(autouse=True)
def reset_bot(monkeypatch):
    monkeypatch.setattr(app, "bot", None)


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_POGO_SETTINGS_CACHE", None)
    monkeypatch.setattr(loadnsave, "_POGO_EVENTS_CACHE", None)
    return tmp_path


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


class FakeRole:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class FakeGuild:
    def __init__(self, id, name, roles=None):
        self.id = id
        self.name = name
        self.roles = roles or []

    def get_role(self, role_id):
        return next((r for r in self.roles if r.id == role_id), None)


class FakeBot:
    def __init__(self, guilds=None, cogs=None):
        self.guilds = guilds or []
        self._cogs = cogs or {}

    def get_cog(self, name):
        return self._cogs.get(name)


class FakePokemonCog:
    def __init__(self):
        self.settings = None
        self.events = []
        self.scrape_calls = 0
        self.weekly_calls = []
        self.next_calls = []
        self.weekly_result = (True, "Weekly summary sent")
        self.next_result = (True, "Next event sent")

    async def scrape_events(self):
        self.scrape_calls += 1
        self.events = [{"name": "Community Day"}]

    async def send_weekly_summary_to_guild(self, guild_id, ping=False):
        self.weekly_calls.append((guild_id, ping))
        return self.weekly_result

    async def send_next_event_to_guild(self, guild_id, ping=False):
        self.next_calls.append((guild_id, ping))
        return self.next_result


@pytest.mark.asyncio
async def test_pokemon_data_no_bot_returns_empty(client):
    await login(client)
    response = await client.get('/api/pokemon/data')
    assert await response.get_json() == {"guilds": [], "events": []}


@pytest.mark.asyncio
async def test_pokemon_data_resolves_role_name(client, isolated_data_dir, monkeypatch):
    await login(client)
    role = FakeRole(111, "Trainer")
    guild = FakeGuild(555, "TestGuild", roles=[role])
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))
    await loadnsave.save_pogo_settings({"555": {"role_id": 111, "channel_id": 1}})

    response = await client.get('/api/pokemon/data')
    data = await response.get_json()
    assert data["guilds"][0]["config"]["role_name"] == "Trainer"


@pytest.mark.asyncio
async def test_pokemon_save_missing_guild_id_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/pokemon/save', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_pokemon_save_persists_fields_and_clears_channel_when_blank(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_pogo_settings({"555": {"channel_id": 1}})

    response = await client.post(
        '/api/pokemon/save',
        json={
            "guild_id": "555", "channel_id": "", "role_id": "222",
            "daily_summary_enabled": False, "advance_minutes": "45"
        },
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_pogo_settings()
    assert "channel_id" not in reloaded["555"]
    assert reloaded["555"]["role_id"] == 222
    assert reloaded["555"]["daily_summary_enabled"] is False
    assert reloaded["555"]["advance_minutes"] == 45


@pytest.mark.asyncio
async def test_pokemon_save_ignores_invalid_advance_minutes(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/pokemon/save',
        json={"guild_id": "555", "advance_minutes": "not-a-number"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_pogo_settings()
    assert "advance_minutes" not in reloaded["555"]


@pytest.mark.asyncio
async def test_pokemon_save_reloads_cog_settings(client, isolated_data_dir, monkeypatch):
    await login(client)
    cog = FakePokemonCog()
    monkeypatch.setattr(app, "bot", FakeBot(cogs={"PokemonGo": cog}))

    await client.post(
        '/api/pokemon/save',
        json={"guild_id": "555", "channel_id": "1"},
        headers={"Origin": "http://localhost"}
    )
    assert cog.settings["555"]["channel_id"] == 1


@pytest.mark.asyncio
async def test_pokemon_refresh_no_bot_returns_500(client):
    await login(client)
    response = await client.post(
        '/api/pokemon/refresh', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_pokemon_refresh_triggers_scrape_and_returns_count(client, monkeypatch):
    await login(client)
    cog = FakePokemonCog()
    monkeypatch.setattr(app, "bot", FakeBot(cogs={"PokemonGo": cog}))

    response = await client.post(
        '/api/pokemon/refresh', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert cog.scrape_calls == 1
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_pokemon_push_weekly_missing_guild_id_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/pokemon/push_weekly', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_pokemon_push_weekly_success(client, monkeypatch):
    await login(client)
    cog = FakePokemonCog()
    monkeypatch.setattr(app, "bot", FakeBot(cogs={"PokemonGo": cog}))

    response = await client.post(
        '/api/pokemon/push_weekly', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.weekly_calls == [("555", False)]


@pytest.mark.asyncio
async def test_pokemon_push_weekly_failure_returns_500(client, monkeypatch):
    await login(client)
    cog = FakePokemonCog()
    cog.weekly_result = (False, "No channel configured")
    monkeypatch.setattr(app, "bot", FakeBot(cogs={"PokemonGo": cog}))

    response = await client.post(
        '/api/pokemon/push_weekly', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 500
    data = await response.get_json()
    assert data["message"] == "No channel configured"


@pytest.mark.asyncio
async def test_pokemon_push_next_success(client, monkeypatch):
    await login(client)
    cog = FakePokemonCog()
    monkeypatch.setattr(app, "bot", FakeBot(cogs={"PokemonGo": cog}))

    response = await client.post(
        '/api/pokemon/push_next', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.next_calls == [("555", False)]
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_pokemon.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_pokemon.py
git commit -m "test: add coverage for dashboard/blueprints/pokemon.py"
```

---

### Task 7: Add tests for dashboard/blueprints/soundboard.py — playback & live control routes

**Files:**
- Create: `tests/test_blueprint_soundboard_playback.py`

**Interfaces:**
- Consumes: `soundboard_data` (`GET /api/soundboard/data`), `soundboard_play`/`_soundboard_play_inner` (`POST /api/soundboard/play`), `soundboard_join` (`POST /api/soundboard/join`), `soundboard_leave` (`POST /api/soundboard/leave`), `soundboard_stop` (`POST /api/soundboard/stop`), `soundboard_volume` (`POST /api/soundboard/volume`), `track_volume`/`track_loop`/`track_pause`/`track_remove` (`POST /api/soundboard/track/*`), all in `dashboard.blueprints.soundboard`
- Fixtures reused: `client`, `mock_dependencies`, `login(client)`, CSRF `Origin` header, `isolated_data_dir` (`loadnsave.DATA_FOLDER` + `_SOUNDBOARD_SETTINGS_CACHE`/`_SERVER_VOLUMES_CACHE`); blueprint-local `server_volumes`/`guild_mixers`/`SOUNDBOARD_FOLDER` patched on the blueprint module itself (by-value imports)

- [ ] **Step 1: Write the test(s)**

```python
import os

import pytest
import discord
from unittest.mock import AsyncMock, patch

import loadnsave
from dashboard.app import app
import dashboard.blueprints.soundboard as soundboard


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


@pytest.fixture(autouse=True)
def reset_bot(monkeypatch):
    monkeypatch.setattr(app, "bot", None)


@pytest.fixture
def isolated_soundboard_env(tmp_path, monkeypatch):
    # soundboard.py does `from dashboard.state import SOUNDBOARD_FOLDER, server_volumes,
    # guild_mixers` -- SOUNDBOARD_FOLDER is a plain string, imported BY VALUE, so
    # patching dashboard.state.SOUNDBOARD_FOLDER would NOT affect this blueprint's
    # own copy. It must be patched on the blueprint module directly.
    # server_volumes/guild_mixers are dicts (mutable, imported by reference) but we
    # still swap in fresh ones per-test to avoid cross-test leakage.
    soundboard_dir = tmp_path / "soundboard"
    soundboard_dir.mkdir()
    monkeypatch.setattr(soundboard, "SOUNDBOARD_FOLDER", str(soundboard_dir))
    monkeypatch.setattr(soundboard, "server_volumes", {})
    monkeypatch.setattr(soundboard, "guild_mixers", {})

    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path / "data"))
    monkeypatch.setattr(loadnsave, "_SOUNDBOARD_SETTINGS_CACHE", None)
    monkeypatch.setattr(loadnsave, "_SERVER_VOLUMES_CACHE", None)
    return soundboard_dir


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


class FakeMixer(discord.AudioSource):
    """
    Stands in for audio_mixer.MixingAudioSource. Subclassing discord.AudioSource
    lets it pass through discord.PCMVolumeTransformer's real isinstance/is_opus
    checks unmodified, while add_track/get_track/remove_track/cleanup are
    lightweight and never spawn ffmpeg (unlike the real Track class).
    """
    def __init__(self):
        self._tracks = {}
        self._next_id = 1
        self.cleaned_up = False

    def read(self):
        return b""

    def add_track(self, file_path, volume=0.5, loop=False, metadata=None):
        track_id = str(self._next_id)
        self._next_id += 1
        track = type("FakeTrack", (), {})()
        track.id = track_id
        track.file_path = file_path
        track.volume = volume
        track.loop = loop
        track.paused = False
        track.finished = False
        track.metadata = metadata or {}
        self._tracks[track_id] = track
        return track

    def get_track(self, track_id):
        return self._tracks.get(track_id)

    def remove_track(self, track_id):
        return self._tracks.pop(track_id, None) is not None

    def cleanup(self):
        self.cleaned_up = True
        self._tracks.clear()

    @property
    def tracks(self):
        return list(self._tracks.values())

    @property
    def lock(self):
        import threading
        return threading.Lock()


class FakeVoiceClient:
    def __init__(self, connected=True, playing=False, channel=None):
        self._connected = connected
        self._playing = playing
        self.channel = channel
        self.source = None
        self.stopped = False
        self.disconnected = False

    def is_connected(self):
        return self._connected

    def is_playing(self):
        return self._playing

    def play(self, source):
        self.source = source
        self._playing = True

    def stop(self):
        self.stopped = True
        self._playing = False

    async def disconnect(self, force=False):
        self.disconnected = True


class FakeGuild:
    def __init__(self, id, voice_client=None):
        self.id = id
        self.name = f"Guild{id}"
        self.voice_channels = []
        self.voice_client = voice_client


class FakeBot:
    def __init__(self, guilds=None):
        self.guilds = guilds or []

    def get_guild(self, guild_id):
        return next((g for g in self.guilds if g.id == guild_id), None)


def make_audio_file(soundboard_dir, name="sound.mp3"):
    path = soundboard_dir / name
    path.write_bytes(b"fake-audio-bytes")
    return name


# --- /api/soundboard/data ---

@pytest.mark.asyncio
async def test_soundboard_data_no_bot_returns_empty(client):
    await login(client)
    response = await client.get('/api/soundboard/data')
    assert response.status_code == 200
    data = await response.get_json()
    assert data == {"guilds": [], "files": {}, "status": {}, "settings": {}}


# --- /api/soundboard/play ---

@pytest.mark.asyncio
async def test_soundboard_play_missing_arguments_returns_400(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/play', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_soundboard_play_blocks_path_traversal(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/play',
        json={"guild_id": "555", "channel_id": "1", "file_path": "../../etc/passwd"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400
    data = await response.get_json()
    assert "Invalid file path" in data["message"]


@pytest.mark.asyncio
async def test_soundboard_play_file_not_found_returns_404(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/play',
        json={"guild_id": "555", "channel_id": "1", "file_path": "missing.mp3"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_soundboard_play_voice_join_failure_returns_500(client, isolated_soundboard_env):
    await login(client)
    filename = make_audio_file(isolated_soundboard_env)
    with patch('dashboard.blueprints.soundboard.get_or_join_voice_channel',
               new_callable=AsyncMock) as mock_join:
        mock_join.return_value = (None, "Connection timed out.")
        response = await client.post(
            '/api/soundboard/play',
            json={"guild_id": "555", "channel_id": "1", "file_path": filename},
            headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 500
        data = await response.get_json()
        assert data["message"] == "Connection timed out."


@pytest.mark.asyncio
async def test_soundboard_play_creates_mixer_and_adds_track_with_computed_volume(client, isolated_soundboard_env):
    await login(client)
    filename = make_audio_file(isolated_soundboard_env)
    vc = FakeVoiceClient(connected=True, playing=False)

    soundboard.server_volumes["555"] = {"music": 1.0, "soundboard": 0.5}

    with patch('dashboard.blueprints.soundboard.get_or_join_voice_channel',
               new_callable=AsyncMock) as mock_join:
        mock_join.return_value = (vc, None)
        response = await client.post(
            '/api/soundboard/play',
            json={"guild_id": "555", "channel_id": "1", "file_path": filename, "volume_modifier": 0.5},
            headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 200

        mixer = soundboard.guild_mixers["555"]
        assert isinstance(mixer, discord.AudioSource)
        assert len(mixer.tracks) == 1
        track = mixer.tracks[0]
        assert track.volume == pytest.approx(0.5 * 0.5)  # sb_vol(0.5) * volume_modifier(0.5)
        assert vc.source is not None  # voice_client.play() was called


@pytest.mark.asyncio
async def test_soundboard_play_reuses_existing_mixer_object(client, isolated_soundboard_env):
    await login(client)
    filename = make_audio_file(isolated_soundboard_env)
    existing_mixer = FakeMixer()
    soundboard.guild_mixers["555"] = existing_mixer
    vc = FakeVoiceClient(connected=True, playing=False)

    with patch('dashboard.blueprints.soundboard.get_or_join_voice_channel',
               new_callable=AsyncMock) as mock_join:
        mock_join.return_value = (vc, None)
        response = await client.post(
            '/api/soundboard/play',
            json={"guild_id": "555", "channel_id": "1", "file_path": filename},
            headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 200
        assert soundboard.guild_mixers["555"] is existing_mixer
        assert len(existing_mixer.tracks) == 1


# --- /api/soundboard/join, /leave, /stop ---

@pytest.mark.asyncio
async def test_soundboard_join_missing_arguments_returns_400(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/join', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_soundboard_leave_disconnects_and_cleans_mixer(client, isolated_soundboard_env, monkeypatch):
    await login(client)
    vc = FakeVoiceClient()
    guild = FakeGuild(555, voice_client=vc)
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    mixer = FakeMixer()
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/leave', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert vc.disconnected is True
    assert mixer.cleaned_up is True
    assert "555" not in soundboard.guild_mixers


@pytest.mark.asyncio
async def test_soundboard_stop_clears_mixer_tracks_without_disconnecting(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    mixer.add_track("x.mp3")
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/stop', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert mixer.cleaned_up is True


# --- /api/soundboard/volume (master) ---

@pytest.mark.asyncio
async def test_soundboard_volume_clamps_and_updates_active_soundboard_tracks(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    track = mixer.add_track("x.mp3", volume=0.1, metadata={"type": "soundboard", "volume_modifier": 0.5})
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/volume',
        json={"guild_id": "555", "volume": 200},  # out of range, clamps to 100
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert soundboard.server_volumes["555"]["soundboard"] == 1.0
    assert track.volume == pytest.approx(1.0 * 0.5)

    reloaded = await loadnsave.load_server_volumes()
    assert reloaded["555"]["soundboard"] == 1.0


@pytest.mark.asyncio
async def test_soundboard_volume_invalid_value_returns_400(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/volume',
        json={"guild_id": "555", "volume": "not-a-number"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


# --- /api/soundboard/track/* ---

@pytest.mark.asyncio
async def test_track_volume_no_active_mixer_returns_404(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/track/volume',
        json={"guild_id": "555", "track_id": "1", "volume": 50},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_track_volume_updates_clamped_value(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    track = mixer.add_track("x.mp3")
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/track/volume',
        json={"guild_id": "555", "track_id": track.id, "volume": 150},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert track.volume == 1.0


@pytest.mark.asyncio
async def test_track_loop_toggles_flag(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    track = mixer.add_track("x.mp3", loop=False)
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/track/loop',
        json={"guild_id": "555", "track_id": track.id, "loop": True},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert track.loop is True


@pytest.mark.asyncio
async def test_track_pause_sets_flag(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    track = mixer.add_track("x.mp3")
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/track/pause',
        json={"guild_id": "555", "track_id": track.id, "paused": True},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert track.paused is True


@pytest.mark.asyncio
async def test_track_remove_not_found_returns_404(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/track/remove',
        json={"guild_id": "555", "track_id": "nonexistent"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_track_remove_success(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    track = mixer.add_track("x.mp3")
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/track/remove',
        json={"guild_id": "555", "track_id": track.id},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert mixer.get_track(track.id) is None
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_soundboard_playback.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_soundboard_playback.py
git commit -m "test: add coverage for dashboard/blueprints/soundboard.py playback routes"
```

---

### Task 8: Add tests for dashboard/blueprints/soundboard.py — file/folder management routes

**Files:**
- Create: `tests/test_blueprint_soundboard_files.py`

**Interfaces:**
- Consumes: `soundboard_folder_color`, `soundboard_file_settings`, `soundboard_file_favorite`, `soundboard_create_folder`, `soundboard_delete_folder`, `soundboard_rename_folder`, `soundboard_delete_file`, `soundboard_rename_file`, `soundboard_upload`, all in `dashboard.blueprints.soundboard`
- Fixtures reused: `client`, `mock_dependencies`, `login(client)`, CSRF `Origin` header, `isolated_data_dir`-style patching of `loadnsave.DATA_FOLDER`/`_SOUNDBOARD_SETTINGS_CACHE`, and the blueprint-local `SOUNDBOARD_FOLDER` override (same by-value-import concern as the playback task)

- [ ] **Step 1: Write the test(s)**

```python
import io
import zipfile

import pytest
from unittest.mock import AsyncMock, patch
from werkzeug.datastructures import FileStorage

import loadnsave
from dashboard.app import app
import dashboard.blueprints.soundboard as soundboard


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


@pytest.fixture(autouse=True)
def reset_bot(monkeypatch):
    monkeypatch.setattr(app, "bot", None)


@pytest.fixture
def isolated_soundboard_env(tmp_path, monkeypatch):
    soundboard_dir = tmp_path / "soundboard"
    soundboard_dir.mkdir()
    # SOUNDBOARD_FOLDER is imported BY VALUE (`from dashboard.state import
    # SOUNDBOARD_FOLDER`), so the blueprint's own module-level binding must be
    # patched directly -- patching dashboard.state.SOUNDBOARD_FOLDER has no effect
    # on code in soundboard.py.
    monkeypatch.setattr(soundboard, "SOUNDBOARD_FOLDER", str(soundboard_dir))
    monkeypatch.setattr(soundboard, "server_volumes", {})
    monkeypatch.setattr(soundboard, "guild_mixers", {})

    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path / "data"))
    monkeypatch.setattr(loadnsave, "_SOUNDBOARD_SETTINGS_CACHE", None)
    return soundboard_dir


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


# --- /api/soundboard/folder/color ---

@pytest.mark.asyncio
async def test_folder_color_missing_arguments_returns_400(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/folder/color', json={"folder_name": "Foo"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_folder_color_persists_setting(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/folder/color',
        json={"folder_name": "Chants", "color": "#ff0000"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_soundboard_settings()
    assert reloaded["folder_colors"]["Chants"] == "#ff0000"


# --- /api/soundboard/file/settings ---

@pytest.mark.asyncio
async def test_file_settings_blocks_path_traversal(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/file/settings',
        json={"file_path": "../outside.mp3", "volume": 50, "loop": False},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_file_settings_stores_non_default_values(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/file/settings',
        json={"file_path": "sound.mp3", "volume": 60, "loop": True},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_soundboard_settings()
    assert reloaded["files"]["sound.mp3"] == {"volume": 60, "loop": True}


@pytest.mark.asyncio
async def test_file_settings_removes_entry_when_reset_to_defaults(client, isolated_soundboard_env):
    await login(client)
    await loadnsave.save_soundboard_settings({"files": {"sound.mp3": {"volume": 60, "loop": True}}})

    response = await client.post(
        '/api/soundboard/file/settings',
        json={"file_path": "sound.mp3", "volume": 100, "loop": False},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_soundboard_settings()
    assert "files" not in reloaded  # cleaned up because it became empty


# --- /api/soundboard/file/favorite ---

@pytest.mark.asyncio
async def test_file_favorite_add_and_remove(client, isolated_soundboard_env):
    await login(client)
    add_response = await client.post(
        '/api/soundboard/file/favorite',
        json={"file_path": "sound.mp3", "favorited": True},
        headers={"Origin": "http://localhost"}
    )
    assert add_response.status_code == 200
    settings = await loadnsave.load_soundboard_settings()
    assert settings["favorites"] == ["sound.mp3"]

    remove_response = await client.post(
        '/api/soundboard/file/favorite',
        json={"file_path": "sound.mp3", "favorited": False},
        headers={"Origin": "http://localhost"}
    )
    assert remove_response.status_code == 200
    settings = await loadnsave.load_soundboard_settings()
    assert settings["favorites"] == []


# --- /api/soundboard/folder/create, /delete, /rename ---

@pytest.mark.asyncio
async def test_create_folder_missing_name_returns_400(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/folder/create', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_folder_sanitizes_name_and_creates_directory(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/folder/create',
        json={"folder_name": "My Chants!!"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert data["folder"] == "My_Chants__"
    assert (isolated_soundboard_env / "My_Chants__").is_dir()


@pytest.mark.asyncio
async def test_create_folder_rejects_existing(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "Existing").mkdir()
    response = await client.post(
        '/api/soundboard/folder/create',
        json={"folder_name": "Existing"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_folder_protects_root(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/folder/delete', json={"folder_name": ""}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_folder_removes_directory(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "Removable").mkdir()

    response = await client.post(
        '/api/soundboard/folder/delete',
        json={"folder_name": "Removable"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert not (isolated_soundboard_env / "Removable").exists()


@pytest.mark.asyncio
async def test_rename_folder_updates_settings_keys(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "OldName").mkdir()
    await loadnsave.save_soundboard_settings({
        "folder_colors": {"OldName": "#123456"},
        "files": {"OldName/song.mp3": {"volume": 80, "loop": False}},
        "favorites": ["OldName/song.mp3"],
    })

    response = await client.post(
        '/api/soundboard/folder/rename',
        json={"old_name": "OldName", "new_name": "NewName"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert (isolated_soundboard_env / "NewName").is_dir()

    reloaded = await loadnsave.load_soundboard_settings()
    assert reloaded["folder_colors"]["NewName"] == "#123456"
    assert "NewName/song.mp3" in reloaded["files"]
    assert reloaded["favorites"] == ["NewName/song.mp3"]


# --- /api/soundboard/file/delete, /file/rename ---

@pytest.mark.asyncio
async def test_delete_file_blocks_path_traversal(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/file/delete',
        json={"file_path": "../outside.mp3"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_file_removes_file_and_settings_entry(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "sound.mp3").write_bytes(b"data")
    await loadnsave.save_soundboard_settings({"files": {"sound.mp3": {"volume": 50, "loop": False}}})

    response = await client.post(
        '/api/soundboard/file/delete',
        json={"file_path": "sound.mp3"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert not (isolated_soundboard_env / "sound.mp3").exists()
    reloaded = await loadnsave.load_soundboard_settings()
    assert "sound.mp3" not in reloaded.get("files", {})


@pytest.mark.asyncio
async def test_rename_file_preserves_extension_and_updates_settings(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "old.mp3").write_bytes(b"data")
    await loadnsave.save_soundboard_settings({
        "files": {"old.mp3": {"volume": 70, "loop": True}},
        "favorites": ["old.mp3"],
    })

    response = await client.post(
        '/api/soundboard/file/rename',
        json={"file_path": "old.mp3", "new_name": "new name!!"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert data["new_path"] == "new_name__.mp3"
    assert (isolated_soundboard_env / "new_name__.mp3").exists()

    reloaded = await loadnsave.load_soundboard_settings()
    assert reloaded["files"]["new_name__.mp3"] == {"volume": 70, "loop": True}
    assert reloaded["favorites"] == ["new_name__.mp3"]


@pytest.mark.asyncio
async def test_rename_file_rejects_existing_target(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "old.mp3").write_bytes(b"data")
    (isolated_soundboard_env / "new.mp3").write_bytes(b"data")

    response = await client.post(
        '/api/soundboard/file/rename',
        json={"file_path": "old.mp3", "new_name": "new"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


# --- /api/soundboard/upload ---

@pytest.mark.asyncio
async def test_upload_rejects_disallowed_extension(client, isolated_soundboard_env):
    await login(client)
    file_storage = FileStorage(stream=io.BytesIO(b"not audio"), filename="malware.exe")

    response = await client.post(
        '/api/soundboard/upload',
        form={"folder": ""},
        files={"files": file_storage},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert any("Skipped" in r for r in data["results"])
    assert not (isolated_soundboard_env / "malware.exe").exists()


@pytest.mark.asyncio
async def test_upload_saves_allowed_audio_file(client, isolated_soundboard_env):
    await login(client)
    file_storage = FileStorage(stream=io.BytesIO(b"fake-mp3-bytes"), filename="new sound!!.mp3")

    response = await client.post(
        '/api/soundboard/upload',
        form={"folder": ""},
        files={"files": file_storage},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert any("Uploaded" in r for r in data["results"])
    assert (isolated_soundboard_env / "new_sound__.mp3").exists()


@pytest.mark.asyncio
async def test_upload_extracts_zip_of_audio_files(client, isolated_soundboard_env):
    await login(client)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr("track.mp3", b"fake-mp3-bytes")
        zf.writestr("notes.txt", b"ignored, not an audio extension")
    buf.seek(0)
    file_storage = FileStorage(stream=buf, filename="pack.zip")

    response = await client.post(
        '/api/soundboard/upload',
        form={"folder": ""},
        files={"files": file_storage},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert any("Unzipped" in r for r in data["results"])
    assert (isolated_soundboard_env / "pack" / "track.mp3").exists()
    assert not (isolated_soundboard_env / "pack" / "notes.txt").exists()
    # The temp zip must be cleaned up after extraction.
    assert not (isolated_soundboard_env / "temp_pack.zip").exists()
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_soundboard_files.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_soundboard_files.py
git commit -m "test: add coverage for dashboard/blueprints/soundboard.py file management routes"
```

---


### Task 9: Fill test gaps in dashboard/blueprints/render.py's untested reference-data and static-render routes

**Files:**
- Create: `tests/test_render_blueprint_gaps.py` — `test_phase3_render.py` is narrowly scoped to oklch-palette assertions on the 6 already-covered routes; diluting it with 15 more routes' worth of behavioral tests would blur its purpose. A new file dedicated to render.py's remaining route behavior is cleaner.

**Interfaces:**
- Consumes: `/render/deity`, `/render/spell`, `/render/weapon`, `/render/pulp_talent`, `/render/insane_talent`, `/render/mania`, `/render/phobia`, `/render/skill`, `/render/invention`, `/render/year`, `/render/morse`, `/render/newspaper`, `/render/telegram`, `/render/letter`, `/render/script` (all in `dashboard/blueprints/render.py`)
- Mocks (by exact name, patched at `dashboard.blueprints.render.<name>`): `load_deities_data`, `load_spells_data`, `load_weapons_data`, `load_pulp_talents_data`, `load_madness_insane_talent_data`, `load_manias_data`, `load_phobias_data`, `load_skills_data`, `load_inventions_data`, `load_years_data`
- Reuses: the `client` fixture and `mock_dependencies` autouse fixture pattern from `tests/test_dashboard_routes.py`

**Findings discovered while verifying these tests against the real app (documented as code comments, not fixed — production code untouched per Global Constraints):** (1) `render.py`'s insane_talent/mania/phobia/skill routes pass `description=` to `render_simple_entry.html`, which actually reads `{{ content }}` — so the description text silently never renders (title/type still do); tests below assert the real current behavior. (2) `render_script.html` never uses the `font_name` variable the route computes — not exercised by these tests since it's not user-visible.

- [ ] **Step 1: Write the test(s)**

```python
import pytest
from dashboard.app import app
from unittest.mock import AsyncMock, patch


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


NAME_REQUIRED_ROUTES = [
    '/render/deity', '/render/spell', '/render/weapon', '/render/pulp_talent',
    '/render/insane_talent', '/render/mania', '/render/phobia', '/render/skill',
    '/render/invention', '/render/year',
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", NAME_REQUIRED_ROUTES)
async def test_render_routes_missing_name_param_returns_400(client, path):
    response = await client.get(path)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_render_deity_known_name_returns_200(client):
    with patch('dashboard.blueprints.render.load_deities_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"deities": [{"deity_entry": {"name": "Cthulhu", "classification": "Great Old One"}}]}
        response = await client.get('/render/deity?name=Cthulhu')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'Cthulhu' in html


@pytest.mark.asyncio
async def test_render_deity_unknown_name_returns_404(client):
    with patch('dashboard.blueprints.render.load_deities_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"deities": []}
        response = await client.get('/render/deity?name=Nobody')
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_render_spell_known_name_returns_200(client):
    with patch('dashboard.blueprints.render.load_spells_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"spells": [{"spell_entry": {"name": "Wither Limb", "category": "Contact"}}]}
        response = await client.get('/render/spell?name=Wither+Limb')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'Wither Limb' in html


@pytest.mark.asyncio
async def test_render_spell_unknown_name_returns_404(client):
    with patch('dashboard.blueprints.render.load_spells_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"spells": []}
        response = await client.get('/render/spell?name=Nobody')
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_render_weapon_known_name_returns_200(client):
    with patch('dashboard.blueprints.render.load_weapons_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Knife": {"damage": "1D4", "range": "Touch"}}
        response = await client.get('/render/weapon?name=Knife')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'Knife' in html


@pytest.mark.asyncio
async def test_render_weapon_case_insensitive_lookup(client):
    with patch('dashboard.blueprints.render.load_weapons_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Knife": {"damage": "1D4", "range": "Touch"}}
        response = await client.get('/render/weapon?name=KNIFE')
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_render_weapon_unknown_name_returns_404(client):
    with patch('dashboard.blueprints.render.load_weapons_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Knife": {"damage": "1D4"}}
        response = await client.get('/render/weapon?name=Nonexistent')
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_render_pulp_talent_known_name_returns_200(client):
    with patch('dashboard.blueprints.render.load_pulp_talents_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Physical": ["**Keen Vision**: gain a bonus die to Spot Hidden rolls"]}
        response = await client.get('/render/pulp_talent?name=Keen+Vision')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'Keen Vision' in html
        assert 'bonus die to Spot Hidden' in html


@pytest.mark.asyncio
async def test_render_pulp_talent_unknown_name_returns_404(client):
    with patch('dashboard.blueprints.render.load_pulp_talents_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Physical": ["**Keen Vision**: gain a bonus die to Spot Hidden rolls"]}
        response = await client.get('/render/pulp_talent?name=Nonexistent')
        assert response.status_code == 404


SIMPLE_ENTRY_CASES = [
    pytest.param('load_madness_insane_talent_data', '/render/insane_talent', "Insane strength", id="insane_talent"),
    pytest.param('load_manias_data', '/render/mania', "Ablutomania", id="mania"),
    pytest.param('load_phobias_data', '/render/phobia', "Ablutophobia", id="phobia"),
    pytest.param('load_skills_data', '/render/skill', "Accounting", id="skill"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("loader_name,path,key", SIMPLE_ENTRY_CASES)
async def test_render_simple_entry_routes_known_name_returns_200(client, loader_name, path, key):
    # NOTE: render_simple_entry.html renders `{{ content }}`, but these routes pass
    # `description=` (not `content=`) — so only the title/type render; the description
    # text itself is silently dropped. This test asserts current behavior, not intent.
    with patch(f'dashboard.blueprints.render.{loader_name}', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {key: "Some description text."}
        response = await client.get(f'{path}?name={key}')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert key in html


@pytest.mark.asyncio
@pytest.mark.parametrize("loader_name,path,key", SIMPLE_ENTRY_CASES)
async def test_render_simple_entry_routes_unknown_name_returns_404(client, loader_name, path, key):
    with patch(f'dashboard.blueprints.render.{loader_name}', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {key: "Some description text."}
        response = await client.get(f'{path}?name=Nonexistent')
        assert response.status_code == 404


TIMELINE_CASES = [
    pytest.param('load_inventions_data', '/render/invention', "1920s", ["The radio becomes popular."], id="invention"),
    pytest.param('load_years_data', '/render/year', "1920", ["Prohibition begins in the United States."], id="year"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("loader_name,path,key,events", TIMELINE_CASES)
async def test_render_timeline_routes_known_key_returns_200(client, loader_name, path, key, events):
    with patch(f'dashboard.blueprints.render.{loader_name}', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {key: events}
        response = await client.get(f'{path}?name={key}')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert key in html
        assert events[0] in html


@pytest.mark.asyncio
@pytest.mark.parametrize("loader_name,path,key,events", TIMELINE_CASES)
async def test_render_timeline_routes_unknown_key_returns_404(client, loader_name, path, key, events):
    with patch(f'dashboard.blueprints.render.{loader_name}', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {key: events}
        response = await client.get(f'{path}?name=Nonexistent')
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_render_morse_default_encodes_sos(client):
    response = await client.get('/render/morse')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '.../---/...' in html


@pytest.mark.asyncio
async def test_render_morse_custom_text(client):
    response = await client.get('/render/morse?text=HI')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '..../..' in html


@pytest.mark.asyncio
async def test_render_newspaper_defaults(client):
    response = await client.get('/render/newspaper')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'Arkham' in html
    assert 'The Arkham Advertiser' in html


@pytest.mark.asyncio
async def test_render_newspaper_custom_params(client):
    response = await client.get('/render/newspaper?headline=Doom&body=It+happened&city=Innsmouth')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'DOOM' in html.upper()
    assert 'Innsmouth' in html


@pytest.mark.asyncio
async def test_render_telegram_defaults(client):
    response = await client.get('/render/telegram')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'STOP' in html


@pytest.mark.asyncio
async def test_render_telegram_custom_params(client):
    response = await client.get('/render/telegram?body=help&sender=investigator')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'HELP' in html
    assert 'INVESTIGATOR' in html


@pytest.mark.asyncio
async def test_render_letter_defaults(client):
    response = await client.get('/render/letter')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'Dearest Friend' in html


@pytest.mark.asyncio
async def test_render_letter_custom_params(client):
    response = await client.get('/render/letter?body=Come+quickly&signature=Yours')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'Come quickly' in html
    assert 'Yours' in html


@pytest.mark.asyncio
async def test_render_script_default_text(client):
    response = await client.get('/render/script')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    # apostrophes are HTML-escaped by the template, so match substrings without them
    assert "nglui mglw" in html
    assert "Cthulhu R" in html


@pytest.mark.asyncio
async def test_render_script_custom_text(client):
    response = await client.get('/render/script?text=Iaaaa')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'Iaaaa' in html
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_render_blueprint_gaps.py -v`
Expected: all 41 cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_render_blueprint_gaps.py
git commit -m "test: fill coverage gaps in dashboard/blueprints/render.py"
```

---

### Task 10: Fill test gaps in dashboard/blueprints/grimoire.py's untested reference-data hub routes

**Files:**
- Create: `tests/test_grimoire_blueprint_gaps.py` — `tests/test_ui_unification.py` is scoped specifically to an emoji-absence regression check on the 3 already-covered routes; adding unrelated "does this route render with this data" assertions there would mix concerns. A new file matches the existing convention of one purpose per test file.

**Interfaces:**
- Consumes: `/deities`, `/archetypes`, `/pulp_talents`, `/insane_talents`, `/manias`, `/phobias`, `/poisons`, `/skills`, `/inventions`, `/years`, `/occupations` (all in `dashboard/blueprints/grimoire.py`)
- Mocks (patched at `dashboard.blueprints.grimoire.<name>`): `load_deities_data`, `load_archetype_data`, `load_pulp_talents_data`, `load_madness_insane_talent_data`, `load_manias_data`, `load_phobias_data`, `load_poisons_data`, `load_skills_data`, `load_inventions_data`, `load_years_data`, `load_occupations_data`
- Reuses: the `client`/`mock_dependencies` fixture pattern from `tests/test_dashboard_routes.py`

- [ ] **Step 1: Write the test(s)**

```python
import pytest
from dashboard.app import app
from unittest.mock import AsyncMock, patch


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


GRIMOIRE_CASES = [
    pytest.param('load_deities_data', '/deities', {"deities": [{"deity_entry": {"name": "Cthulhu"}}]}, "Cthulhu", id="deities"),
    pytest.param('load_archetype_data', '/archetypes', {"Adventurer": {"description": "A brave soul.", "adjustments": []}}, "Adventurer", id="archetypes"),
    pytest.param('load_pulp_talents_data', '/pulp_talents', {"Physical": ["**Keen Vision**: gain a bonus die to Spot Hidden rolls"]}, "Keen Vision", id="pulp_talents"),
    pytest.param('load_madness_insane_talent_data', '/insane_talents', {"Insane strength": "Gain a bonus die to a STR roll."}, "Insane strength", id="insane_talents"),
    pytest.param('load_manias_data', '/manias', {"Ablutomania": "Compulsion for washing oneself."}, "Ablutomania", id="manias"),
    pytest.param('load_phobias_data', '/phobias', {"Ablutophobia": "Fear of washing or bathing."}, "Ablutophobia", id="phobias"),
    pytest.param('load_poisons_data', '/poisons', {"Arsenic": {"Onset Time": "Minutes", "Symptoms": "Death", "Damage": "1D10", "Note": "Bad."}}, "Arsenic", id="poisons"),
    pytest.param('load_skills_data', '/skills', {"Accounting": "Understanding financial operations."}, "Accounting", id="skills"),
    pytest.param('load_inventions_data', '/inventions', {"1920s": ["The radio becomes popular."]}, "1920s", id="inventions"),
    pytest.param('load_years_data', '/years', {"1920": ["Prohibition begins."]}, "1920", id="years"),
    pytest.param('load_occupations_data', '/occupations', {"Antiquarian": {"description": "Old stuff.", "skills": "History"}}, "Antiquarian", id="occupations"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("loader_name,path,payload,expected_text", GRIMOIRE_CASES)
async def test_grimoire_reference_route_renders_data(client, loader_name, path, payload, expected_text):
    with patch(f'dashboard.blueprints.grimoire.{loader_name}', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = payload
        response = await client.get(path)
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert expected_text in html


@pytest.mark.asyncio
async def test_grimoire_deities_route_empty_data_renders_200(client):
    with patch('dashboard.blueprints.grimoire.load_deities_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"deities": []}
        response = await client.get('/deities')
        assert response.status_code == 200
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_grimoire_blueprint_gaps.py -v`
Expected: all 12 cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_grimoire_blueprint_gaps.py
git commit -m "test: fill coverage gaps in dashboard/blueprints/grimoire.py"
```

---

### Task 11: Fill test gaps in dashboard/blueprints/core.py's untested login POST and image API routes

**Files:**
- Create: `tests/test_core_blueprint_gaps.py` — `test_dashboard_routes.py` and `test_phase2_auth.py` cover GET-only smoke tests; none exercise POST /login or the /api/images/* handlers, so a new file avoids retrofitting unrelated files with a different testing shape (multipart uploads, CSRF headers).

**Interfaces:**
- Consumes: `POST /login`, `GET/POST /api/images/check`, `POST /api/images/upload`, `POST /api/images/delete` (all in `dashboard/blueprints/core.py`)
- Reuses: the `client`/`mock_dependencies` pattern, and the CSRF `Origin` header requirement from `tests/test_loadnsave_file_browser_cache.py`

**Important finding:** `core.py` does `from loadnsave import load_settings_async` at module scope, so the repo-wide `mock_dependencies` autouse fixture (which patches `dashboard.app.load_settings_async`) does **not** cover the login route's own binding — it must be patched separately at `dashboard.blueprints.core.load_settings_async` for the POST-login tests, or the real `config.json`/default password gets used and both success/failure paths misbehave.

- [ ] **Step 1: Write the test(s)**

```python
import io
import json
import pytest
from dashboard.app import app
from unittest.mock import AsyncMock, patch
from werkzeug.datastructures import FileStorage


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.mark.asyncio
async def test_login_post_correct_password_redirects_to_admin(client):
    # core.py imports load_settings_async directly (`from loadnsave import
    # load_settings_async`), so the autouse mock_dependencies fixture -- which
    # only patches dashboard.app.load_settings_async -- does not cover this
    # module's own binding. It must be patched separately here.
    with patch('dashboard.blueprints.core.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {'admin_password': 'testpassword'}
        response = await client.post(
            '/login',
            form={'password': 'testpassword'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 302
        assert '/admin' in response.headers['Location']
        async with client.session_transaction() as sess:
            assert sess.get('logged_in') is True


@pytest.mark.asyncio
async def test_login_post_wrong_password_renders_error(client):
    with patch('dashboard.blueprints.core.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {'admin_password': 'testpassword'}
        response = await client.post(
            '/login',
            form={'password': 'wrongpassword'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'Invalid Password' in html
        async with client.session_transaction() as sess:
            assert not sess.get('logged_in')


@pytest.mark.asyncio
async def test_api_images_check_missing_args_returns_400(client):
    # /api/images/check is not in _PUBLIC_API, so it needs a session even
    # though the handler itself does not call is_admin().
    await login(client)
    response = await client.get('/api/images/check')
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data['found'] is False


@pytest.mark.asyncio
async def test_api_images_check_found(client):
    await login(client)
    with patch('dashboard.blueprints.core.get_image_url', return_value='/images/monster/deep_one.png') as mock_url:
        response = await client.get('/api/images/check?type_slug=monster&name=Deep+One')
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"found": True, "url": "/images/monster/deep_one.png"}
        mock_url.assert_called_once_with('monster', 'Deep One')


@pytest.mark.asyncio
async def test_api_images_check_not_found(client):
    await login(client)
    with patch('dashboard.blueprints.core.get_image_url', return_value=None):
        response = await client.get('/api/images/check?type_slug=monster&name=Nonexistent')
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"found": False}


@pytest.mark.asyncio
async def test_api_images_upload_unauthorized_without_session(client):
    response = await client.post(
        '/api/images/upload',
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_images_upload_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/images/upload',
        form={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data['status'] == 'error'


@pytest.mark.asyncio
async def test_api_images_upload_success(client, tmp_path):
    await login(client)
    upload = FileStorage(stream=io.BytesIO(b'fake-image-bytes'), filename='deepone.png')
    with patch('dashboard.blueprints.core.IMAGES_FOLDER', str(tmp_path)):
        response = await client.post(
            '/api/images/upload',
            form={'type_slug': 'monster', 'name': 'Deep One'},
            files={'file': upload},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data['status'] == 'success'
        assert data['url'].startswith('/images/monster/')
        assert (tmp_path / 'monster').exists()


@pytest.mark.asyncio
async def test_api_images_delete_unauthorized_without_session(client):
    response = await client.post(
        '/api/images/delete',
        json={'type_slug': 'monster', 'name': 'Deep One'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_images_delete_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/images/delete',
        json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_api_images_delete_not_found_returns_404(client, tmp_path):
    await login(client)
    with patch('dashboard.blueprints.core.IMAGES_FOLDER', str(tmp_path)):
        response = await client.post(
            '/api/images/delete',
            json={'type_slug': 'monster', 'name': 'Nonexistent'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_images_delete_success(client, tmp_path):
    await login(client)
    target_dir = tmp_path / 'monster'
    target_dir.mkdir()
    (target_dir / 'Deep_One.png').write_bytes(b'fake')
    with patch('dashboard.blueprints.core.IMAGES_FOLDER', str(tmp_path)), \
         patch('dashboard.blueprints.core.sanitize_filename', side_effect=lambda x: x.replace(' ', '_')):
        response = await client.post(
            '/api/images/delete',
            json={'type_slug': 'monster', 'name': 'Deep One'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data['status'] == 'success'
        assert not (target_dir / 'Deep_One.png').exists()
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_core_blueprint_gaps.py -v`
Expected: all 12 cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_core_blueprint_gaps.py
git commit -m "test: fill coverage gaps in dashboard/blueprints/core.py"
```

---

### Task 12: Fill test gaps in dashboard/blueprints/admin.py's authenticated design routes

**Files:**
- Create: `tests/test_admin_blueprint_gaps.py` — only `/admin`'s unauthenticated redirect is currently tested anywhere; there's no existing admin-focused test file to extend.

**Interfaces:**
- Consumes: `GET /admin/design`, `POST /api/design/save_fonts`, `POST /api/design/save_origin_fonts`, `POST /api/design/save` (all in `dashboard/blueprints/admin.py`)
- Reuses: the `client`/`mock_dependencies`/`login()` pattern from `tests/test_phase1_utilities.py`; CSRF `Origin` header from `tests/test_loadnsave_file_browser_cache.py`
- Mocks (patched at `dashboard.blueprints.admin.<name>`): `load_settings_async`, `save_settings`

- [ ] **Step 1: Write the test(s)**

```python
import json
import pytest
from dashboard.app import app
from unittest.mock import AsyncMock, patch


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.mark.asyncio
async def test_admin_design_redirects_if_not_logged_in(client):
    response = await client.get('/admin/design')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_admin_design_authenticated_renders_dashboard(client):
    await login(client)
    with patch('dashboard.blueprints.admin.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': 'Arial', 'body': '', 'special': ''},
            'origin_fonts': {},
        }
        response = await client.get('/admin/design')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert '<title>' in html


@pytest.mark.asyncio
async def test_save_fonts_unauthorized_without_session(client):
    response = await client.post(
        '/api/design/save_fonts',
        json={'headers': 'Arial', 'body': 'Georgia', 'special': 'Cinzel'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_save_fonts_authenticated_persists_settings(client):
    await login(client)
    with patch('dashboard.blueprints.admin.load_settings_async', new_callable=AsyncMock) as mock_load, \
         patch('dashboard.blueprints.admin.save_settings', new_callable=AsyncMock) as mock_save:
        mock_load.return_value = {}
        response = await client.post(
            '/api/design/save_fonts',
            json={'headers': 'Arial', 'body': 'Georgia', 'special': 'Cinzel'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        mock_save.assert_awaited_once()
        saved_settings = mock_save.await_args.args[0]
        assert saved_settings['dashboard_fonts'] == {'headers': 'Arial', 'body': 'Georgia', 'special': 'Cinzel'}


@pytest.mark.asyncio
async def test_save_origin_fonts_unauthorized_without_session(client):
    response = await client.post(
        '/api/design/save_origin_fonts',
        json={'headers': 'Arial', 'body': 'Georgia', 'special': 'Cinzel'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_save_origin_fonts_authenticated_persists_settings(client):
    await login(client)
    with patch('dashboard.blueprints.admin.load_settings_async', new_callable=AsyncMock) as mock_load, \
         patch('dashboard.blueprints.admin.save_settings', new_callable=AsyncMock) as mock_save:
        mock_load.return_value = {}
        response = await client.post(
            '/api/design/save_origin_fonts',
            json={'headers': 'Special Elite', 'body': 'Nanum Myeongjo', 'special': 'Dancing Script'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        saved_settings = mock_save.await_args.args[0]
        assert saved_settings['origin_fonts'] == {
            'headers': 'Special Elite', 'body': 'Nanum Myeongjo', 'special': 'Dancing Script'
        }


@pytest.mark.asyncio
async def test_save_design_unauthorized_without_session(client):
    response = await client.post(
        '/api/design/save',
        json={'theme': 'cthulhu'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_save_design_missing_theme_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/design/save',
        json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data['status'] == 'error'


@pytest.mark.asyncio
async def test_save_design_authenticated_persists_theme(client):
    await login(client)
    with patch('dashboard.blueprints.admin.load_settings_async', new_callable=AsyncMock) as mock_load, \
         patch('dashboard.blueprints.admin.save_settings', new_callable=AsyncMock) as mock_save:
        mock_load.return_value = {}
        response = await client.post(
            '/api/design/save',
            json={'theme': 'delta_green'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        saved_settings = mock_save.await_args.args[0]
        assert saved_settings['dashboard_theme'] == 'delta_green'
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_admin_blueprint_gaps.py -v`
Expected: all 9 cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_admin_blueprint_gaps.py
git commit -m "test: fill coverage gaps in dashboard/blueprints/admin.py"
```

---

### Task 13: Fill test gaps in dashboard/blueprints/fonts_admin.py's authenticated font management routes

**Files:**
- Create: `tests/test_fonts_admin_blueprint_gaps.py` — no existing file tests fonts_admin.py's authenticated behavior at all (only the 401/redirect paths are covered elsewhere).

**Interfaces:**
- Consumes: `GET /admin/fonts`, `GET /api/fonts/list`, `POST /api/fonts/upload`, `POST /api/fonts/delete`, `POST /api/fonts/update_category` (all in `dashboard/blueprints/fonts_admin.py`)
- Reuses: the `client`/`mock_dependencies`/`login()` pattern; CSRF `Origin` header requirement from `tests/test_loadnsave_file_browser_cache.py`
- Mocks (patched at `dashboard.blueprints.fonts_admin.<name>`): `FONTS_FOLDER`, `load_fonts_config`, `save_fonts_config`

- [ ] **Step 1: Write the test(s)**

```python
import io
import json
import pytest
from dashboard.app import app
from unittest.mock import AsyncMock, patch
from werkzeug.datastructures import FileStorage


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.mark.asyncio
async def test_admin_fonts_authenticated_renders_dashboard(client):
    await login(client)
    response = await client.get('/admin/fonts')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '<title>' in html


@pytest.mark.asyncio
async def test_fonts_list_authenticated_returns_configured_fonts(client, tmp_path):
    await login(client)
    (tmp_path / 'Cinzel.ttf').write_bytes(b'fake-font')
    (tmp_path / 'ignored.txt').write_text('not a font')
    with patch('dashboard.blueprints.fonts_admin.FONTS_FOLDER', str(tmp_path)), \
         patch('dashboard.blueprints.fonts_admin.load_fonts_config', new_callable=AsyncMock) as mock_cfg:
        mock_cfg.return_value = {'Cinzel.ttf': 'Display'}
        response = await client.get('/api/fonts/list')
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"fonts": [{"filename": "Cinzel.ttf", "category": "Display"}]}


@pytest.mark.asyncio
async def test_fonts_upload_no_files_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/fonts/upload',
        form={'category': 'Decorative'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_fonts_upload_authenticated_saves_file_and_config(client, tmp_path):
    await login(client)
    upload = FileStorage(stream=io.BytesIO(b'fake-font-bytes'), filename='Special Elite.ttf')
    with patch('dashboard.blueprints.fonts_admin.FONTS_FOLDER', str(tmp_path)), \
         patch('dashboard.blueprints.fonts_admin.load_fonts_config', new_callable=AsyncMock) as mock_load_cfg, \
         patch('dashboard.blueprints.fonts_admin.save_fonts_config', new_callable=AsyncMock) as mock_save_cfg:
        mock_load_cfg.return_value = {}
        response = await client.post(
            '/api/fonts/upload',
            form={'category': 'Handwriting'},
            files={'files': upload},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data['status'] == 'success'
        assert len(list(tmp_path.iterdir())) == 1
        mock_save_cfg.assert_awaited_once()
        saved_config = mock_save_cfg.await_args.args[0]
        assert list(saved_config.values()) == ['Handwriting']


@pytest.mark.asyncio
async def test_fonts_delete_missing_filename_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/fonts/delete',
        json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_fonts_delete_rejects_path_traversal(client):
    await login(client)
    response = await client.post(
        '/api/fonts/delete',
        json={'filename': '../../etc/passwd'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_fonts_delete_not_found_returns_404(client, tmp_path):
    await login(client)
    with patch('dashboard.blueprints.fonts_admin.FONTS_FOLDER', str(tmp_path)):
        response = await client.post(
            '/api/fonts/delete',
            json={'filename': 'Nonexistent.ttf'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_fonts_delete_authenticated_removes_file_and_config_entry(client, tmp_path):
    await login(client)
    (tmp_path / 'Cinzel.ttf').write_bytes(b'fake-font')
    with patch('dashboard.blueprints.fonts_admin.FONTS_FOLDER', str(tmp_path)), \
         patch('dashboard.blueprints.fonts_admin.load_fonts_config', new_callable=AsyncMock) as mock_load_cfg, \
         patch('dashboard.blueprints.fonts_admin.save_fonts_config', new_callable=AsyncMock) as mock_save_cfg:
        mock_load_cfg.return_value = {'Cinzel.ttf': 'Display'}
        response = await client.post(
            '/api/fonts/delete',
            json={'filename': 'Cinzel.ttf'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        assert not (tmp_path / 'Cinzel.ttf').exists()
        mock_save_cfg.assert_awaited_once_with({})


@pytest.mark.asyncio
async def test_fonts_update_category_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/fonts/update_category',
        json={'filename': 'Cinzel.ttf'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_fonts_update_category_authenticated_persists_category(client):
    await login(client)
    with patch('dashboard.blueprints.fonts_admin.load_fonts_config', new_callable=AsyncMock) as mock_load_cfg, \
         patch('dashboard.blueprints.fonts_admin.save_fonts_config', new_callable=AsyncMock) as mock_save_cfg:
        mock_load_cfg.return_value = {}
        response = await client.post(
            '/api/fonts/update_category',
            json={'filename': 'Cinzel.ttf', 'category': 'Display'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        mock_save_cfg.assert_awaited_once_with({'Cinzel.ttf': 'Display'})
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_fonts_admin_blueprint_gaps.py -v`
Expected: all 10 cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_fonts_admin_blueprint_gaps.py
git commit -m "test: fill coverage gaps in dashboard/blueprints/fonts_admin.py"
```

---

### Task 14: Fill test gaps in dashboard/blueprints/enroll.py's untested enrollment wizard routes

**Files:**
- Create: `tests/test_enroll_blueprint_gaps.py` — the one existing enroll.py test (`admin_newspaper` GET) lives in `tests/test_phase1_utilities.py`, which is really a file_browser-focused file that happens to include one enroll-blueprint route; adding 3 more enroll routes (including a Discord-object-heavy guild/role listing test) belongs in its own file rather than growing that unrelated file's scope.

**Interfaces:**
- Consumes: `GET /admin/enroll`, `GET /api/enroll/data`, `POST /api/enroll/save` (all in `dashboard/blueprints/enroll.py`)
- Reuses: the `client`/`mock_dependencies`/`login()` pattern; CSRF `Origin` header from `tests/test_loadnsave_file_browser_cache.py`
- Mocks (patched at `dashboard.blueprints.enroll.<name>`): `app` (for `app.bot`), `load_enroll_settings`, `save_enroll_settings`

- [ ] **Step 1: Write the test(s)**

```python
import json
import pytest
from dashboard.app import app
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.mark.asyncio
async def test_admin_enroll_redirects_if_not_logged_in(client):
    response = await client.get('/admin/enroll')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_admin_enroll_authenticated_renders_dashboard(client):
    await login(client)
    response = await client.get('/admin/enroll')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '<title>' in html


@pytest.mark.asyncio
async def test_enroll_data_unauthorized_without_session(client):
    response = await client.get('/api/enroll/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_enroll_data_no_bot_returns_empty_guilds(client):
    await login(client)
    with patch('dashboard.blueprints.enroll.app') as mock_app:
        mock_app.bot = None
        response = await client.get('/api/enroll/data')
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"guilds": []}


@pytest.mark.asyncio
async def test_enroll_data_authenticated_lists_guilds_and_roles(client):
    await login(client)

    mock_role_default = MagicMock()
    mock_role_default.is_default.return_value = True
    mock_role_default.managed = False

    mock_role_managed = MagicMock()
    mock_role_managed.is_default.return_value = False
    mock_role_managed.managed = True

    mock_role_normal = MagicMock()
    mock_role_normal.is_default.return_value = False
    mock_role_normal.managed = False
    mock_role_normal.id = 555
    mock_role_normal.name = "Investigator"
    mock_role_normal.color = "#ff0000"

    mock_guild = MagicMock()
    mock_guild.id = 123
    mock_guild.name = "Arkham Society"
    mock_guild.roles = [mock_role_default, mock_role_managed, mock_role_normal]

    with patch('dashboard.blueprints.enroll.app') as mock_app, \
         patch('dashboard.blueprints.enroll.load_enroll_settings', new_callable=AsyncMock) as mock_settings:
        mock_app.bot.guilds = [mock_guild]
        mock_settings.return_value = {
            "123": {"enabled": True, "final_message": "Welcome!", "pages": [{"title": "Intro"}]}
        }

        response = await client.get('/api/enroll/data')
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert len(data["guilds"]) == 1
        guild_data = data["guilds"][0]
        assert guild_data["id"] == "123"
        assert guild_data["name"] == "Arkham Society"
        assert guild_data["roles"] == [{"id": "555", "name": "Investigator", "color": "#ff0000"}]
        assert guild_data["config"] == {
            "enabled": True, "final_message": "Welcome!", "pages": [{"title": "Intro"}]
        }


@pytest.mark.asyncio
async def test_enroll_save_unauthorized_without_session(client):
    response = await client.post(
        '/api/enroll/save',
        json={'guild_id': '123'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_enroll_save_missing_guild_id_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/enroll/save',
        json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_enroll_save_authenticated_persists_settings(client):
    await login(client)
    with patch('dashboard.blueprints.enroll.load_enroll_settings', new_callable=AsyncMock) as mock_load, \
         patch('dashboard.blueprints.enroll.save_enroll_settings', new_callable=AsyncMock) as mock_save:
        mock_load.return_value = {}
        response = await client.post(
            '/api/enroll/save',
            json={
                'guild_id': '123',
                'enabled': True,
                'final_message': 'Thanks for joining!',
                'pages': [{"title": "Intro"}],
            },
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        mock_save.assert_awaited_once_with({
            "123": {
                "enabled": True,
                "final_message": "Thanks for joining!",
                "pages": [{"title": "Intro"}],
            }
        })
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_enroll_blueprint_gaps.py -v`
Expected: all 8 cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_enroll_blueprint_gaps.py
git commit -m "test: fill coverage gaps in dashboard/blueprints/enroll.py"
```

---

### Task 15: Add missing error-path coverage to dashboard/blueprints/file_browser.py's folder/filename validation

**file_browser.py finding:** Its 3 routes' happy paths ARE already fully covered (`browse_files`/`edit_file` by `tests/test_phase1_utilities.py`, `save_file`'s cache-invalidation fix by `tests/test_loadnsave_file_browser_cache.py`). But none of the existing tests exercise the `if folder_name not in (...): return "Invalid folder", 400` branches (all 3 routes) or the `if '..' in filename or '/' in filename` guard (`edit_file`, `save_file`), or `save_file`'s `json.JSONDecodeError` handler. These are genuine, security-relevant gaps (path-traversal validation, arbitrary-folder rejection), so this is not a "no task needed" file — one small task covers them.

**Files:**
- Modify: `tests/test_phase1_utilities.py` — it already contains file_browser's only other route tests (`test_file_browser_route`, `test_json_editor_route`), so its scope is really "file_browser + one enroll route", and these new cases are a natural, small extension of the existing file_browser coverage there rather than a reason to fork a new file.

**Interfaces:**
- Consumes: `GET /admin/browse/<folder_name>`, `GET /admin/edit/<folder_name>/<filename>`, `POST /api/save/<folder_name>/<filename>` (all in `dashboard/blueprints/file_browser.py`)
- Reuses: the `login()` helper already defined in `tests/test_phase1_utilities.py`

**Important finding (verified by running against the real routes):** a URL-encoded `%2F` in the `<filename>` segment 404s at Quart/Werkzeug's routing layer before the handler ever runs — the default converter won't match a path separator. So the handler's own `'/' in filename` guard is effectively unreachable via normal HTTP requests; only the `'..' in filename` half of the guard is exercisable, and only via a filename that contains `..` as a bare substring (not a real `../` traversal, since a literal `/` can't reach the handler either).

- [ ] **Step 1: Add the test(s) to the existing file**

```python
@pytest.mark.asyncio
async def test_browse_files_invalid_folder_returns_400(client):
    await login(client)
    response = await client.get('/admin/browse/nonsense')
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_edit_file_invalid_folder_returns_400(client):
    await login(client)
    response = await client.get('/admin/edit/nonsense/monsters.json')
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_edit_file_path_traversal_filename_returns_400(client):
    # A bare ".." segment 404s at the routing layer before reaching the
    # handler (Werkzeug's default converter won't match a path separator),
    # so the handler's own "'..' in filename" guard is only reachable via a
    # filename that merely contains ".." as a substring.
    await login(client)
    response = await client.get('/admin/edit/infodata/..monsters.json')
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_file_invalid_folder_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/save/nonsense/monsters.json',
        json={"content": "{}"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_file_path_traversal_filename_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/save/infodata/..monsters.json',
        json={"content": "{}"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_file_invalid_json_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/save/infodata/monsters.json',
        json={"content": "{not valid json"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data['message'] == 'Invalid JSON format'
```

Note: this appends to the existing `tests/test_phase1_utilities.py`, so it needs its `import json` added at the top of the file if not already present (it currently imports `pytest`, `dashboard.app.app`, and `unittest.mock`).

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_phase1_utilities.py -v`
Expected: all cases PASS, including the 3 pre-existing tests in the file.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase1_utilities.py
git commit -m "test: add folder/filename validation coverage to dashboard/blueprints/file_browser.py"
```

---

### Task 16: Add tests for dashboard/blueprints/giveaway.py

**Files:**
- Create: `tests/test_blueprint_giveaway.py`

**Interfaces:**
- Consumes: `giveaway_bp` routes `/admin/giveaway` (GET), `/api/giveaway/data` (GET), `/api/giveaway/create` (POST), `/api/giveaway/end` (POST), `/api/giveaway/reroll` (POST) from `dashboard/blueprints/giveaway.py`
- Consumes: `loadnsave.save_giveaway_data`, `loadnsave.load_giveaway_data` (cache attr `loadnsave._GIVEAWAY_DATA_CACHE`, file `giveaway_data.json`)
- Reuses: `client`/`mock_dependencies`/`login()` pattern from `tests/test_dashboard_routes.py` and `tests/test_phase1_utilities.py`; `isolated_data_dir`-style `DATA_FOLDER` monkeypatch from `tests/test_loadnsave_roundtrip.py`; CSRF `Origin` header pattern from `tests/test_loadnsave_file_browser_cache.py`
- Patches `dashboard.app.app.bot` directly (per `tests/test_phase2_auth.py`) since blueprints access `app.bot` via attribute lookup on the shared `app` object, not a by-value import

- [ ] **Step 1: Write the test(s)**

```python
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import loadnsave
from dashboard.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_GIVEAWAY_DATA_CACHE", None)
    return tmp_path


def make_channel(channel_id, name):
    channel = MagicMock()
    channel.id = channel_id
    channel.name = name
    return channel


def make_member(member_id, display_name):
    member = MagicMock()
    member.id = member_id
    member.display_name = display_name
    return member


def make_guild(guild_id=111, name="Test Guild", channels=None, members=None):
    guild = MagicMock()
    guild.id = guild_id
    guild.name = name
    guild.text_channels = channels or []
    channel_by_id = {c.id: c for c in (channels or [])}
    member_by_id = {m.id: m for m in (members or [])}
    guild.get_channel.side_effect = lambda cid: channel_by_id.get(cid)
    guild.get_member.side_effect = lambda uid: member_by_id.get(uid)
    return guild


@pytest.mark.asyncio
async def test_admin_giveaway_redirects_if_not_logged_in(client):
    response = await client.get('/admin/giveaway')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_giveaway_data_unauthorized_without_session(client):
    response = await client.get('/api/giveaway/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_giveaway_data_no_bot_returns_empty_guilds(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.get('/api/giveaway/data')
        assert response.status_code == 200
        import json
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"guilds": []}


@pytest.mark.asyncio
async def test_giveaway_data_resolves_names_and_sorts_active_first(client, isolated_data_dir):
    await login(client)

    channel = make_channel(555, "announcements")
    member = make_member(777, "TheWinner")
    guild = make_guild(guild_id=123, name="Test Guild", channels=[channel], members=[member])

    await loadnsave.save_giveaway_data({
        "123": {
            "1": {
                "channel_id": "555",
                "title": "Ended One",
                "status": "ended",
                "participants": ["1", "2"],
                "winner_id": "777",
            },
            "2": {
                "channel_id": "555",
                "title": "Active One",
                "status": "active",
                "participants": ["1"],
            },
        }
    })

    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/api/giveaway/data')

    assert response.status_code == 200
    import json
    data = json.loads(await response.get_data(as_text=True))
    guild_data = data["guilds"][0]
    assert guild_data["id"] == "123"

    giveaways = guild_data["giveaways"]
    assert giveaways[0]["status"] == "active"
    assert giveaways[0]["title"] == "Active One"
    assert giveaways[0]["participant_count"] == 1
    assert giveaways[0]["channel_name"] == "announcements"

    ended = giveaways[1]
    assert ended["status"] == "ended"
    assert ended["participant_count"] == 2
    assert ended["winner_name"] == "TheWinner"


@pytest.mark.asyncio
async def test_giveaway_create_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/giveaway/create',
        json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    import json
    data = json.loads(await response.get_data(as_text=True))
    assert data["status"] == "error"


@pytest.mark.asyncio
async def test_giveaway_create_bot_not_ready_returns_500(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.post(
            '/api/giveaway/create',
            json={
                "guild_id": "1", "channel_id": "2",
                "title": "Prize", "prize_secret": "answer",
            },
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_giveaway_create_persists_with_computed_end_time(client, isolated_data_dir):
    await login(client)

    channel = make_channel(2, "general")
    guild = make_guild(guild_id=1, channels=[channel])
    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    mock_bot.get_guild.side_effect = lambda gid: guild if gid == 1 else None
    mock_bot.user = MagicMock(id=999)

    sent_message = MagicMock()
    sent_message.id = 4242
    channel.send = AsyncMock(return_value=sent_message)

    before = time.time()
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/giveaway/create',
            json={
                "guild_id": "1", "channel_id": "2", "title": "Prize",
                "description": "A prize", "prize_secret": "answer",
                "duration": "1d",
            },
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    import json
    data = json.loads(await response.get_data(as_text=True))
    assert data["status"] == "success"
    assert data["message_id"] == "4242"

    saved = await loadnsave.load_giveaway_data()
    entry = saved["1"]["4242"]
    assert entry["title"] == "Prize"
    assert entry["prize_secret"] == "answer"
    assert entry["status"] == "active"
    assert entry["participants"] == []
    assert entry["end_time"] == pytest.approx(before + 86400, abs=5)


@pytest.mark.asyncio
async def test_giveaway_create_forever_duration_has_no_end_time(client, isolated_data_dir):
    await login(client)

    channel = make_channel(2, "general")
    guild = make_guild(guild_id=1, channels=[channel])
    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    mock_bot.get_guild.side_effect = lambda gid: guild if gid == 1 else None
    mock_bot.user = MagicMock(id=999)

    sent_message = MagicMock()
    sent_message.id = 4343
    channel.send = AsyncMock(return_value=sent_message)

    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/giveaway/create',
            json={
                "guild_id": "1", "channel_id": "2", "title": "Prize",
                "prize_secret": "answer", "duration": "forever",
            },
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    saved = await loadnsave.load_giveaway_data()
    assert saved["1"]["4343"]["end_time"] is None


@pytest.mark.asyncio
async def test_giveaway_end_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/giveaway/end', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_giveaway_end_cog_not_loaded_returns_500(client):
    await login(client)
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = None
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/giveaway/end',
            json={"guild_id": "1", "message_id": "2"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_giveaway_end_success_calls_cog(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.api_end_giveaway = AsyncMock(return_value=(True, "Giveaway ended"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/giveaway/end',
            json={"guild_id": "1", "message_id": "2"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 200
    import json
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success", "message": "Giveaway ended"}
    mock_cog.api_end_giveaway.assert_awaited_once_with("1", "2")


@pytest.mark.asyncio
async def test_giveaway_reroll_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/giveaway/reroll', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_giveaway_reroll_failure_returns_500_with_message(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.api_reroll_giveaway = AsyncMock(return_value=(False, "No participants"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/giveaway/reroll',
            json={"guild_id": "1", "message_id": "2"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500
    import json
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "error", "message": "No participants"}
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_giveaway.py -v` (or `.venv/bin/python -m pytest ...` if needed)
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_giveaway.py
git commit -m "test: add coverage for dashboard/blueprints/giveaway.py"
```

---

### Task 17: Add tests for dashboard/blueprints/polls.py

**Files:**
- Create: `tests/test_blueprint_polls.py`

**Interfaces:**
- Consumes: `polls_bp` routes `/admin/polls` (GET), `/api/polls/data` (GET), `/api/polls/create` (POST), `/api/polls/end` (POST) from `dashboard/blueprints/polls.py`
- Consumes: `loadnsave.save_polls_data`, `loadnsave.load_polls_data` (cache attr `loadnsave._POLLS_DATA_CACHE`, file `polls_data.json`)
- Reuses: `client`/`mock_dependencies`/`login()` from `tests/test_dashboard_routes.py` / `tests/test_phase1_utilities.py`; `isolated_data_dir` `DATA_FOLDER` monkeypatch pattern from `tests/test_loadnsave_roundtrip.py`; CSRF `Origin` header from `tests/test_loadnsave_file_browser_cache.py`

- [ ] **Step 1: Write the test(s)**

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import loadnsave
from dashboard.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_POLLS_DATA_CACHE", None)
    return tmp_path


def make_channel(channel_id, name):
    channel = MagicMock()
    channel.id = channel_id
    channel.name = name
    return channel


def make_guild(guild_id=111, name="Test Guild", channels=None):
    guild = MagicMock()
    guild.id = guild_id
    guild.name = name
    guild.text_channels = channels or []
    channel_by_id = {c.id: c for c in (channels or [])}
    guild.get_channel.side_effect = lambda cid: channel_by_id.get(cid)
    return guild


@pytest.mark.asyncio
async def test_admin_polls_redirects_if_not_logged_in(client):
    response = await client.get('/admin/polls')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_polls_data_unauthorized_without_session(client):
    response = await client.get('/api/polls/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_polls_data_no_bot_returns_empty_guilds(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.get('/api/polls/data')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"guilds": []}


@pytest.mark.asyncio
async def test_polls_data_filters_by_guild_and_resolves_channel_and_votes(client, isolated_data_dir):
    await login(client)

    channel = make_channel(555, "polls-channel")
    guild = make_guild(guild_id=123, channels=[channel])
    other_guild = make_guild(guild_id=999, name="Other Guild")

    await loadnsave.save_polls_data({
        "1": {
            "guild_id": "123", "channel_id": 555,
            "question": "Best Mythos?", "votes": {"1": 0, "2": 1},
        },
        "2": {
            "guild_id": "999", "channel_id": 1,
            "question": "Other guild poll", "votes": {},
        },
    })

    mock_bot = MagicMock()
    mock_bot.guilds = [guild, other_guild]
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/api/polls/data')

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))

    guild_123 = next(g for g in data["guilds"] if g["id"] == "123")
    assert len(guild_123["polls"]) == 1
    poll = guild_123["polls"][0]
    assert poll["message_id"] == "1"
    assert poll["channel_name"] == "polls-channel"
    assert poll["vote_count"] == 2

    guild_999 = next(g for g in data["guilds"] if g["id"] == "999")
    assert len(guild_999["polls"]) == 1
    assert guild_999["polls"][0]["channel_name"] == "Unknown"


@pytest.mark.asyncio
async def test_polls_create_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/polls/create', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_polls_create_bot_not_ready_returns_500(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.post(
            '/api/polls/create',
            json={
                "guild_id": "1", "channel_id": "2",
                "question": "Q?", "options": "a,b",
            },
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_polls_create_cog_not_loaded_returns_500(client):
    await login(client)
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = None
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/create',
            json={
                "guild_id": "1", "channel_id": "2",
                "question": "Q?", "options": "a,b",
            },
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_polls_create_splits_comma_separated_options_string(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.create_poll_api = AsyncMock(return_value=(True, "poll-42"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/create',
            json={
                "guild_id": "1", "channel_id": "2",
                "question": "Best?", "options": "Cats,Dogs,Fish",
            },
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success", "poll_id": "poll-42"}
    mock_cog.create_poll_api.assert_awaited_once_with("1", "2", "Best?", ["Cats", "Dogs", "Fish"])


@pytest.mark.asyncio
async def test_polls_create_passes_list_options_unchanged(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.create_poll_api = AsyncMock(return_value=(True, "poll-1"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/create',
            json={
                "guild_id": "1", "channel_id": "2",
                "question": "Best?", "options": ["Cats", "Dogs"],
            },
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    mock_cog.create_poll_api.assert_awaited_once_with("1", "2", "Best?", ["Cats", "Dogs"])


@pytest.mark.asyncio
async def test_polls_create_failure_returns_500_with_message(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.create_poll_api = AsyncMock(return_value=(False, "Could not send poll"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/create',
            json={
                "guild_id": "1", "channel_id": "2",
                "question": "Best?", "options": "a,b",
            },
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 500
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "error", "message": "Could not send poll"}


@pytest.mark.asyncio
async def test_polls_end_missing_poll_id_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/polls/end', json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_polls_end_bot_not_ready_returns_500(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.post(
            '/api/polls/end', json={"poll_id": "1"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_polls_end_cog_not_loaded_returns_500(client):
    await login(client)
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = None
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/end', json={"poll_id": "1"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_polls_end_success(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.end_poll_api = AsyncMock(return_value=(True, None))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/end', json={"poll_id": "1"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}
    mock_cog.end_poll_api.assert_awaited_once_with("1")
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_polls.py -v` (or `.venv/bin/python -m pytest ...` if needed)
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_polls.py
git commit -m "test: add coverage for dashboard/blueprints/polls.py"
```

---

### Task 18: Add tests for dashboard/blueprints/reminders.py

**Files:**
- Create: `tests/test_blueprint_reminders.py`

**Interfaces:**
- Consumes: `reminders_bp` routes `/admin/reminders` (GET), `/api/reminders/data` (GET), `/api/reminders/create` (POST), `/api/reminders/delete` (POST) from `dashboard/blueprints/reminders.py`
- Consumes: `loadnsave.save_reminder_data`, `loadnsave.load_reminder_data` (cache attr `loadnsave._REMINDER_DATA_CACHE`, file `reminder_data.json`)
- Reuses: same `client`/`mock_dependencies`/`login()`, `isolated_data_dir` `DATA_FOLDER` monkeypatch, CSRF `Origin` header — same sources as above

- [ ] **Step 1: Write the test(s)**

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import loadnsave
from dashboard.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_REMINDER_DATA_CACHE", None)
    return tmp_path


def make_channel(channel_id, name):
    channel = MagicMock()
    channel.id = channel_id
    channel.name = name
    return channel


def make_member(member_id, display_name):
    member = MagicMock()
    member.id = member_id
    member.display_name = display_name
    return member


def make_guild(guild_id=111, name="Test Guild", channels=None, members=None):
    guild = MagicMock()
    guild.id = guild_id
    guild.name = name
    guild.text_channels = channels or []
    guild.members = members or []
    channel_by_id = {c.id: c for c in (channels or [])}
    member_by_id = {m.id: m for m in (members or [])}
    guild.get_channel.side_effect = lambda cid: channel_by_id.get(cid)
    guild.get_member.side_effect = lambda uid: member_by_id.get(uid)
    return guild


@pytest.mark.asyncio
async def test_admin_reminders_redirects_if_not_logged_in(client):
    response = await client.get('/admin/reminders')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_reminders_data_unauthorized_without_session(client):
    response = await client.get('/api/reminders/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reminders_data_no_bot_returns_empty_guilds(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.get('/api/reminders/data')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"guilds": []}


@pytest.mark.asyncio
async def test_reminders_data_resolves_channel_and_user_names(client, isolated_data_dir):
    await login(client)

    channel = make_channel(555, "reminders-channel")
    member = make_member(777, "SomeUser")
    guild = make_guild(guild_id=123, channels=[channel], members=[member])

    await loadnsave.save_reminder_data({
        "123": [
            {"channel_id": "555", "user_id": "777", "message": "Do the thing"},
            {"channel_id": "999", "user_id": "888", "message": "Unresolved"},
        ]
    })

    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/api/reminders/data')

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    guild_data = data["guilds"][0]

    assert guild_data["users"] == [{"id": "777", "name": "SomeUser"}]

    reminders = guild_data["reminders"]
    assert reminders[0]["channel_name"] == "reminders-channel"
    assert reminders[0]["user_name"] == "SomeUser"
    assert reminders[1]["channel_name"] == "Unknown"
    assert reminders[1]["user_name"] == "User 888"


@pytest.mark.asyncio
async def test_reminders_create_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/reminders/create', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reminders_create_bot_not_ready_returns_500(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.post(
            '/api/reminders/create',
            json={
                "guild_id": "1", "channel_id": "2", "user_id": "3",
                "message": "Hi", "duration": "5m",
            },
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_reminders_create_invalid_duration_returns_400(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.parse_duration.return_value = 0
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/reminders/create',
            json={
                "guild_id": "1", "channel_id": "2", "user_id": "3",
                "message": "Hi", "duration": "bogus",
            },
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Invalid duration"
    mock_cog.parse_duration.assert_called_once_with("bogus")


@pytest.mark.asyncio
async def test_reminders_create_success_uses_parsed_seconds(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.parse_duration.return_value = 300
    mock_cog.create_reminder_api = AsyncMock(return_value=(True, None))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/reminders/create',
            json={
                "guild_id": "1", "channel_id": "2", "user_id": "3",
                "message": "Hi", "duration": "5m",
            },
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}
    mock_cog.create_reminder_api.assert_awaited_once_with("1", "2", "3", "Hi", 300)


@pytest.mark.asyncio
async def test_reminders_create_failure_returns_500_with_message(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.parse_duration.return_value = 300
    mock_cog.create_reminder_api = AsyncMock(return_value=(False, "DM closed"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/reminders/create',
            json={
                "guild_id": "1", "channel_id": "2", "user_id": "3",
                "message": "Hi", "duration": "5m",
            },
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "error", "message": "DM closed"}


@pytest.mark.asyncio
async def test_reminders_delete_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/reminders/delete', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reminders_delete_bot_not_ready_returns_500(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.post(
            '/api/reminders/delete',
            json={"guild_id": "1", "reminder_id": "2"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_reminders_delete_cog_not_loaded_returns_500(client):
    await login(client)
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = None
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/reminders/delete',
            json={"guild_id": "1", "reminder_id": "2"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_reminders_delete_success(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.delete_reminder_api = AsyncMock(return_value=(True, None))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/reminders/delete',
            json={"guild_id": "1", "reminder_id": "2"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}
    mock_cog.delete_reminder_api.assert_awaited_once_with("1", "2")
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_reminders.py -v` (or `.venv/bin/python -m pytest ...` if needed)
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_reminders.py
git commit -m "test: add coverage for dashboard/blueprints/reminders.py"
```

---

### Task 19: Add tests for dashboard/blueprints/deleter.py

**Files:**
- Create: `tests/test_blueprint_deleter.py`

**Interfaces:**
- Consumes: `deleter_bp` routes `/admin/deleter` (GET), `/api/deleter/data` (GET), `/api/deleter/save` (POST), `/api/deleter/delete` (POST), `/api/deleter/bulk_delete` (POST) from `dashboard/blueprints/deleter.py`
- Consumes: `loadnsave.load_deleter_data`, `loadnsave.save_deleter_data` (cache attr `loadnsave._DELETER_DATA_CACHE`, file `deleter_data.json`)
- Reuses: same `client`/`mock_dependencies`/`login()`, `isolated_data_dir`, CSRF `Origin` header patterns as above

- [ ] **Step 1: Write the test(s)**

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import loadnsave
from dashboard.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_DELETER_DATA_CACHE", None)
    return tmp_path


def make_channel(channel_id, name):
    channel = MagicMock()
    channel.id = channel_id
    channel.name = name
    return channel


def make_guild(guild_id=111, name="Test Guild", channels=None):
    guild = MagicMock()
    guild.id = guild_id
    guild.name = name
    guild.text_channels = channels or []
    return guild


@pytest.mark.asyncio
async def test_admin_deleter_redirects_if_not_logged_in(client):
    response = await client.get('/admin/deleter')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_deleter_data_unauthorized_without_session(client):
    response = await client.get('/api/deleter/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deleter_data_no_bot_returns_empty_guilds(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.get('/api/deleter/data')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"guilds": []}


@pytest.mark.asyncio
async def test_deleter_data_marks_active_channels_with_seconds(client, isolated_data_dir):
    await login(client)

    active_channel = make_channel(555, "spam-channel")
    idle_channel = make_channel(556, "general")
    guild = make_guild(channels=[active_channel, idle_channel])

    await loadnsave.save_deleter_data({"555": 30})

    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/api/deleter/data')

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    channels = {c["id"]: c for c in data["guilds"][0]["channels"]}

    assert channels["555"]["is_active"] is True
    assert channels["555"]["seconds"] == 30
    assert channels["556"]["is_active"] is False
    assert channels["556"]["seconds"] == 0


@pytest.mark.asyncio
async def test_deleter_save_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/deleter/save', json={"channel_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_deleter_save_negative_seconds_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/deleter/save', json={"channel_id": "1", "seconds": -5},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Invalid time limit"


@pytest.mark.asyncio
async def test_deleter_save_non_numeric_seconds_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/deleter/save', json={"channel_id": "1", "seconds": "abc"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_deleter_save_persists_rule(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/deleter/save', json={"channel_id": "555", "seconds": "45"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    saved = await loadnsave.load_deleter_data()
    assert saved == {"555": 45}


@pytest.mark.asyncio
async def test_deleter_delete_missing_channel_id_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/deleter/delete', json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_deleter_delete_rule_not_found_returns_404(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/deleter/delete', json={"channel_id": "999"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_deleter_delete_removes_existing_rule(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_deleter_data({"555": 30, "556": 60})

    response = await client.post(
        '/api/deleter/delete', json={"channel_id": "555"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    saved = await loadnsave.load_deleter_data()
    assert saved == {"556": 60}


@pytest.mark.asyncio
async def test_deleter_bulk_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/deleter/bulk_delete', json={"channel_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_deleter_bulk_bot_not_ready_returns_500(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.post(
            '/api/deleter/bulk_delete',
            json={"channel_id": "1", "amount": "10"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_deleter_bulk_cog_not_loaded_returns_500(client):
    await login(client)
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = None
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/deleter/bulk_delete',
            json={"channel_id": "1", "amount": "10"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_deleter_bulk_success_returns_count(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.api_bulk_delete = AsyncMock(return_value=(True, 7))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/deleter/bulk_delete',
            json={"channel_id": "1", "amount": "10"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success", "count": 7}
    mock_bot.get_cog.assert_called_once_with("deleter")
    mock_cog.api_bulk_delete.assert_awaited_once_with("1", "10")
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_deleter.py -v` (or `.venv/bin/python -m pytest ...` if needed)
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_deleter.py
git commit -m "test: add coverage for dashboard/blueprints/deleter.py"
```

---

### Task 20: Add tests for dashboard/blueprints/backup.py

**Files:**
- Create: `tests/test_blueprint_backup.py`

**Interfaces:**
- Consumes: `backup_bp` routes `/admin/backup` (GET), `/api/backup/save` (POST), `/api/backup/run` (POST), `/api/backup/files` (GET), `/api/backup/delete` (POST), `/admin/backup/download/<filename>` (GET) and helper `get_system_backups()` from `dashboard/blueprints/backup.py`
- Consumes: `dashboard.blueprints.backup.BACKUP_FOLDER` (by-value import from `dashboard.state.BACKUP_FOLDER` — must patch the blueprint's own binding, not `dashboard.state.BACKUP_FOLDER`), `dashboard.blueprints.backup.load_settings_async` / `dashboard.blueprints.backup.save_settings` (by-value imports from `loadnsave` — must patch the blueprint's own binding, not `dashboard.app.load_settings_async`)
- Reuses: same `client`/`mock_dependencies`/`login()`, CSRF `Origin` header patterns as above

- [ ] **Step 1: Write the test(s)**

```python
import json
import os
import zipfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from dashboard.app import app
import dashboard.blueprints.backup as backup


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.fixture
def isolated_backup_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "BACKUP_FOLDER", str(tmp_path))
    return tmp_path


def make_zip(folder, name, content=b"data"):
    path = os.path.join(str(folder), name)
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr("file.txt", content)
    return path


@pytest.mark.asyncio
async def test_admin_backup_redirects_if_not_logged_in(client):
    response = await client.get('/admin/backup')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_admin_backup_renders_configured_backup_time(client):
    await login(client)
    with patch.object(backup, 'load_settings_async', new=AsyncMock(return_value={'backup_time': '03:30'})):
        response = await client.get('/admin/backup')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '03:30' in html


@pytest.mark.asyncio
async def test_backup_save_invalid_time_format_returns_400(client):
    await login(client)
    with patch.object(backup, 'load_settings_async', new=AsyncMock(return_value={})), \
         patch.object(backup, 'save_settings', new=AsyncMock()) as mock_save:
        response = await client.post(
            '/api/backup/save', json={"backup_time": "not-a-time"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 400
    mock_save.assert_not_called()


@pytest.mark.asyncio
async def test_backup_save_persists_valid_time(client):
    await login(client)
    settings = {"admin_password": "x"}
    with patch.object(backup, 'load_settings_async', new=AsyncMock(return_value=settings)), \
         patch.object(backup, 'save_settings', new=AsyncMock()) as mock_save:
        response = await client.post(
            '/api/backup/save', json={"backup_time": "04:15"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}
    mock_save.assert_awaited_once_with({"admin_password": "x", "backup_time": "04:15"})


@pytest.mark.asyncio
async def test_backup_run_bot_not_ready_returns_500(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.post('/api/backup/run', headers={"Origin": "http://localhost"})
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_backup_run_cog_not_loaded_returns_500(client):
    await login(client)
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = None
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post('/api/backup/run', headers={"Origin": "http://localhost"})
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_backup_run_success_returns_filename(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.perform_backup = AsyncMock(return_value=(True, "backup_20260718.zip"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post('/api/backup/run', headers={"Origin": "http://localhost"})
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success", "filename": "backup_20260718.zip"}


@pytest.mark.asyncio
async def test_backup_run_failure_returns_500_with_message(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.perform_backup = AsyncMock(return_value=(False, "Disk full"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post('/api/backup/run', headers={"Origin": "http://localhost"})
    assert response.status_code == 500
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "error", "message": "Disk full"}


@pytest.mark.asyncio
async def test_backup_files_list_sorted_newest_first(client, isolated_backup_folder):
    await login(client)
    older = make_zip(isolated_backup_folder, "old.zip")
    newer = make_zip(isolated_backup_folder, "new.zip")
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    response = await client.get('/api/backup/files')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    names = [f["name"] for f in data]
    assert names == ["new.zip", "old.zip"]
    assert data[0]["size"] > 0


@pytest.mark.asyncio
async def test_backup_files_list_empty_folder_returns_empty_list(client, isolated_backup_folder):
    await login(client)
    response = await client.get('/api/backup/files')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == []


@pytest.mark.asyncio
async def test_backup_delete_missing_filename_returns_400(client, isolated_backup_folder):
    await login(client)
    response = await client.post(
        '/api/backup/delete', json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_backup_delete_rejects_non_zip_extension(client, isolated_backup_folder):
    await login(client)
    response = await client.post(
        '/api/backup/delete', json={"filename": "notes.txt"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Invalid file type"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_filename", ["../evil.zip", "sub/evil.zip", "sub\\evil.zip"])
async def test_backup_delete_rejects_path_traversal(client, isolated_backup_folder, bad_filename):
    await login(client)
    response = await client.post(
        '/api/backup/delete', json={"filename": bad_filename},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Invalid filename"


@pytest.mark.asyncio
async def test_backup_delete_file_not_found_returns_404(client, isolated_backup_folder):
    await login(client)
    response = await client.post(
        '/api/backup/delete', json={"filename": "missing.zip"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_backup_delete_removes_existing_file(client, isolated_backup_folder):
    await login(client)
    make_zip(isolated_backup_folder, "gone.zip")

    response = await client.post(
        '/api/backup/delete', json={"filename": "gone.zip"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}
    assert not os.path.exists(os.path.join(str(isolated_backup_folder), "gone.zip"))


@pytest.mark.asyncio
async def test_backup_download_redirects_if_not_logged_in(client):
    response = await client.get('/admin/backup/download/some.zip')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_backup_download_file_not_found_returns_404(client, isolated_backup_folder):
    await login(client)
    response = await client.get('/admin/backup/download/missing.zip')
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_backup_download_rejects_path_traversal(client, isolated_backup_folder):
    await login(client)
    response = await client.get('/admin/backup/download/..%2F..%2Fetc%2Fpasswd')
    assert response.status_code in (400, 404)


@pytest.mark.asyncio
async def test_backup_download_returns_file_contents(client, isolated_backup_folder):
    await login(client)
    make_zip(isolated_backup_folder, "download_me.zip", content=b"payload-bytes")

    response = await client.get('/admin/backup/download/download_me.zip')
    assert response.status_code == 200
    body = await response.get_data(as_text=False)
    assert body[:2] == b"PK"
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_backup.py -v` (or `.venv/bin/python -m pytest ...` if needed)
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_backup.py
git commit -m "test: add coverage for dashboard/blueprints/backup.py"
```

---

### Task 21: Add tests for dashboard/blueprints/rss.py

**Files:**
- Create: `tests/test_blueprint_rss.py`

**Interfaces:**
- Consumes: `rss_bp` routes `/admin/rss` (GET), `/api/rss/data` (GET), `/api/rss/add` (POST), `/api/rss/update_color` (POST), `/api/rss/delete` (POST) from `dashboard/blueprints/rss.py`
- Consumes: `loadnsave.load_rss_data`, `loadnsave.save_rss_data` (cache attr `loadnsave._RSS_DATA_CACHE`, file `rss_data.json`); `dashboard.blueprints.rss.feedparser.parse` (module-level `import feedparser`, patched via `patch.object(rss.feedparser, 'parse', ...)`); `dashboard.blueprints.rss.get_youtube_rss_url` (by-value import from `rss_utils` — must patch the blueprint's own binding)
- Reuses: same `client`/`mock_dependencies`/`login()`, `isolated_data_dir`, CSRF `Origin` header patterns as above

- [ ] **Step 1: Write the test(s)**

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import loadnsave
from dashboard.app import app
import dashboard.blueprints.rss as rss


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_RSS_DATA_CACHE", None)
    return tmp_path


def make_channel(channel_id, name):
    channel = MagicMock()
    channel.id = channel_id
    channel.name = name
    return channel


def make_guild(guild_id=111, name="Test Guild", channels=None):
    guild = MagicMock()
    guild.id = guild_id
    guild.name = name
    guild.text_channels = channels or []
    channel_by_id = {c.id: c for c in (channels or [])}
    guild.get_channel.side_effect = lambda cid: channel_by_id.get(cid)
    return guild


def make_feed(entries, feed_title="A Feed"):
    feed = MagicMock()
    feed.entries = entries
    feed.feed = {"title": feed_title}
    return feed


def make_entry(title, link, entry_id=None):
    entry = MagicMock()
    entry.title = title
    entry.link = link
    entry.id = entry_id or link
    return entry


@pytest.mark.asyncio
async def test_admin_rss_redirects_if_not_logged_in(client):
    response = await client.get('/admin/rss')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_rss_data_unauthorized_without_session(client):
    response = await client.get('/api/rss/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rss_data_resolves_guild_and_channel_names(client, isolated_data_dir):
    await login(client)

    channel = make_channel(555, "news-channel")
    guild = make_guild(guild_id=123, channels=[channel])

    await loadnsave.save_rss_data({
        "123": [
            {"channel_id": 555, "link": "http://example.com/feed", "last_message": "Latest", "color": "#ABCDEF"},
        ],
        "999": [
            {"channel_id": 1, "link": "http://unknown.com/feed"},
        ],
    })

    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    mock_bot.get_guild.side_effect = lambda gid: guild if gid == 123 else None
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/api/rss/data')

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    feeds = {f["link"]: f for f in data["feeds"]}

    known = feeds["http://example.com/feed"]
    assert known["guild_name"] == "Test Guild"
    assert known["channel_name"] == "news-channel"
    assert known["color"] == "#ABCDEF"

    unknown = feeds["http://unknown.com/feed"]
    assert unknown["guild_name"] == "Unknown Guild (999)"
    assert unknown["channel_name"] == "Unknown Channel (1)"
    assert unknown["color"] == "#2E8B57"


@pytest.mark.asyncio
async def test_rss_add_missing_arguments_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/rss/add', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_rss_add_feed_with_no_entries_returns_400(client, isolated_data_dir):
    await login(client)
    empty_feed = make_feed(entries=[])
    with patch.object(rss, 'get_youtube_rss_url', new=AsyncMock(return_value=None)), \
         patch.object(rss.feedparser, 'parse', return_value=empty_feed):
        response = await client.post(
            '/api/rss/add',
            json={"guild_id": "1", "channel_id": "2", "link": "http://example.com/feed"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "No items found in RSS feed"


@pytest.mark.asyncio
async def test_rss_add_persists_new_subscription(client, isolated_data_dir):
    await login(client)
    entry = make_entry("Episode 1", "http://example.com/ep1")
    feed = make_feed(entries=[entry])
    with patch.object(rss, 'get_youtube_rss_url', new=AsyncMock(return_value=None)), \
         patch.object(rss.feedparser, 'parse', return_value=feed):
        response = await client.post(
            '/api/rss/add',
            json={"guild_id": "1", "channel_id": "2", "link": "http://example.com/feed", "color": "#123456"},
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    saved = await loadnsave.load_rss_data()
    entries = saved["1"]
    assert len(entries) == 1
    assert entries[0]["link"] == "http://example.com/feed"
    assert entries[0]["channel_id"] == 2
    assert entries[0]["last_message"] == "Episode 1"
    assert entries[0]["color"] == "#123456"


@pytest.mark.asyncio
async def test_rss_add_rejects_duplicate_subscription(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_rss_data({
        "1": [{"link": "http://example.com/feed", "channel_id": 2, "last_message": "x", "color": "#fff"}]
    })

    entry = make_entry("Episode 2", "http://example.com/ep2")
    feed = make_feed(entries=[entry])
    with patch.object(rss, 'get_youtube_rss_url', new=AsyncMock(return_value=None)), \
         patch.object(rss.feedparser, 'parse', return_value=feed):
        response = await client.post(
            '/api/rss/add',
            json={"guild_id": "1", "channel_id": "2", "link": "http://example.com/feed"},
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Feed already subscribed in this channel"


@pytest.mark.asyncio
async def test_rss_add_resolves_youtube_channel_url_to_rss(client, isolated_data_dir):
    await login(client)
    entry = make_entry("YT Video", "http://youtube.com/watch?v=abc")
    feed = make_feed(entries=[entry])
    with patch.object(rss, 'get_youtube_rss_url', new=AsyncMock(return_value="http://youtube.com/feeds/videos.xml?channel_id=xyz")) as mock_yt, \
         patch.object(rss.feedparser, 'parse', return_value=feed):
        response = await client.post(
            '/api/rss/add',
            json={"guild_id": "1", "channel_id": "2", "link": "http://youtube.com/channel/xyz"},
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    mock_yt.assert_awaited_once_with("http://youtube.com/channel/xyz")

    saved = await loadnsave.load_rss_data()
    assert saved["1"][0]["link"] == "http://youtube.com/feeds/videos.xml?channel_id=xyz"


@pytest.mark.asyncio
async def test_rss_update_color_missing_arguments_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/rss/update_color', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_rss_update_color_feed_not_found_returns_404(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/rss/update_color',
        json={"guild_id": "1", "link": "http://missing.com/feed", "color": "#000"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rss_update_color_persists_new_color(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_rss_data({
        "1": [{"link": "http://example.com/feed", "channel_id": 2, "last_message": "x", "color": "#fff"}]
    })

    response = await client.post(
        '/api/rss/update_color',
        json={"guild_id": "1", "link": "http://example.com/feed", "color": "#abcabc"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    saved = await loadnsave.load_rss_data()
    assert saved["1"][0]["color"] == "#abcabc"


@pytest.mark.asyncio
async def test_rss_delete_missing_arguments_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/rss/delete', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_rss_delete_no_feeds_for_guild_returns_404(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/rss/delete',
        json={"guild_id": "1", "link": "http://example.com/feed"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rss_delete_removes_feed_and_cleans_empty_guild_entry(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_rss_data({
        "1": [{"link": "http://example.com/feed", "channel_id": 2, "last_message": "x", "color": "#fff"}]
    })

    response = await client.post(
        '/api/rss/delete',
        json={"guild_id": "1", "link": "http://example.com/feed"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    saved = await loadnsave.load_rss_data()
    assert "1" not in saved


@pytest.mark.asyncio
async def test_rss_delete_unknown_link_returns_404(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_rss_data({
        "1": [{"link": "http://example.com/feed", "channel_id": 2, "last_message": "x", "color": "#fff"}]
    })

    response = await client.post(
        '/api/rss/delete',
        json={"guild_id": "1", "link": "http://other.com/feed"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_rss.py -v` (or `.venv/bin/python -m pytest ...` if needed)
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_rss.py
git commit -m "test: add coverage for dashboard/blueprints/rss.py"
```

---

### Task 22: Add tests for dashboard/blueprints/autorooms.py

**Files:**
- Create: `tests/test_blueprint_autorooms.py`

**Interfaces:**
- Consumes: `autorooms_bp` routes `/admin/autorooms` (GET), `/api/autorooms/data` (GET), `/api/autorooms/save` (POST) from `dashboard/blueprints/autorooms.py`
- Consumes: `loadnsave.autoroom_load`, `loadnsave.autoroom_save` (cache attr `loadnsave._AUTOROOM_CACHE`, file `autorooms.json`)
- Reuses: same `client`/`mock_dependencies`/`login()`, `isolated_data_dir`, CSRF `Origin` header patterns as above

- [ ] **Step 1: Write the test(s)**

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import loadnsave
from dashboard.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_AUTOROOM_CACHE", None)
    return tmp_path


def make_named(item_id, name):
    obj = MagicMock()
    obj.id = item_id
    obj.name = name
    return obj


def make_guild(guild_id=111, name="Test Guild", voice_channels=None, categories=None):
    guild = MagicMock()
    guild.id = guild_id
    guild.name = name
    guild.voice_channels = voice_channels or []
    guild.categories = categories or []
    return guild


@pytest.mark.asyncio
async def test_admin_autorooms_redirects_if_not_logged_in(client):
    response = await client.get('/admin/autorooms')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_autorooms_data_unauthorized_without_session(client):
    response = await client.get('/api/autorooms/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_autorooms_data_no_bot_returns_empty_guilds(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.get('/api/autorooms/data')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"guilds": []}


@pytest.mark.asyncio
async def test_autorooms_data_reports_current_config(client, isolated_data_dir):
    await login(client)

    vc = make_named(10, "Join to Create")
    category = make_named(20, "Voice Rooms")
    guild = make_guild(guild_id=123, voice_channels=[vc], categories=[category])

    await loadnsave.autoroom_save({"123": {"channel_id": 10, "category_id": 20}})

    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/api/autorooms/data')

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    guild_data = data["guilds"][0]
    assert guild_data["voice_channels"] == [{"id": "10", "name": "Join to Create"}]
    assert guild_data["categories"] == [{"id": "20", "name": "Voice Rooms"}]
    assert guild_data["config"] == {"channel_id": "10", "category_id": "20"}


@pytest.mark.asyncio
async def test_autorooms_data_defaults_config_to_empty_strings_when_unset(client, isolated_data_dir):
    await login(client)
    guild = make_guild(guild_id=123)
    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/api/autorooms/data')

    data = json.loads(await response.get_data(as_text=True))
    assert data["guilds"][0]["config"] == {"channel_id": "", "category_id": ""}


@pytest.mark.asyncio
async def test_autorooms_save_missing_guild_id_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/autorooms/save', json={"channel_id": "10"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_autorooms_save_persists_channel_and_category_as_ints(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/autorooms/save',
        json={"guild_id": "123", "channel_id": "10", "category_id": "20"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    saved = await loadnsave.autoroom_load()
    assert saved["123"] == {"channel_id": 10, "category_id": 20}


@pytest.mark.asyncio
async def test_autorooms_save_clears_channel_id_when_omitted(client, isolated_data_dir):
    await login(client)
    await loadnsave.autoroom_save({"123": {"channel_id": 10, "category_id": 20}})

    response = await client.post(
        '/api/autorooms/save',
        json={"guild_id": "123", "channel_id": "", "category_id": "20"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200

    saved = await loadnsave.autoroom_load()
    assert "channel_id" not in saved["123"]
    assert saved["123"]["category_id"] == 20
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_autorooms.py -v` (or `.venv/bin/python -m pytest ...` if needed)
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_autorooms.py
git commit -m "test: add coverage for dashboard/blueprints/autorooms.py"
```

---

### Task 23: Add tests for dashboard/blueprints/bot_config.py

**Files:**
- Create: `tests/test_blueprint_bot_config.py`

**Interfaces:**
- Consumes: `bot_config_bp` routes `/admin/bot_config` (GET), `/api/save_status` (POST), `/api/save_prefix` (POST) from `dashboard/blueprints/bot_config.py`
- Consumes: `loadnsave.load_server_stats`/`save_server_stats` (cache `_SERVER_STATS_CACHE`, file `server_stats.json`) and `loadnsave.load_bot_status`/`save_bot_status` (cache `_BOT_STATUS_CACHE`, file `bot_status.json`)
- Reuses: same `client`/`mock_dependencies`/`login()`, `isolated_data_dir`, CSRF `Origin` header patterns as above

- [ ] **Step 1: Write the test(s)**

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import loadnsave
from dashboard.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_SERVER_STATS_CACHE", None)
    monkeypatch.setattr(loadnsave, "_BOT_STATUS_CACHE", None)
    return tmp_path


def make_guild(guild_id=111, name="Test Guild"):
    guild = MagicMock()
    guild.id = guild_id
    guild.name = name
    return guild


@pytest.mark.asyncio
async def test_admin_bot_config_redirects_if_not_logged_in(client):
    response = await client.get('/admin/bot_config')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_admin_bot_config_returns_500_when_bot_not_initialized(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.get('/admin/bot_config')
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_admin_bot_config_renders_guild_prefixes(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_server_stats({"123": "?"})

    guild = make_guild(guild_id=123, name="Test Guild")
    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/admin/bot_config')

    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert "Test Guild" in html


@pytest.mark.asyncio
async def test_save_status_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/save_status', json={"type": "playing"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_status_persists_and_updates_presence(client, isolated_data_dir):
    await login(client)

    mock_bot = MagicMock()
    mock_bot.is_ready.return_value = True
    mock_bot.change_presence = AsyncMock()

    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/save_status',
            json={"type": "watching", "text": "the stars"},
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    saved = await loadnsave.load_bot_status()
    assert saved == {"type": "watching", "text": "the stars"}

    mock_bot.change_presence.assert_awaited_once()
    _, kwargs = mock_bot.change_presence.call_args
    activity = kwargs["activity"]
    assert activity.name == "the stars"


@pytest.mark.asyncio
async def test_save_status_skips_presence_update_when_bot_not_ready(client, isolated_data_dir):
    await login(client)
    mock_bot = MagicMock()
    mock_bot.is_ready.return_value = False
    mock_bot.change_presence = AsyncMock()

    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/save_status',
            json={"type": "playing", "text": "a game"},
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    mock_bot.change_presence.assert_not_called()


@pytest.mark.asyncio
async def test_save_prefix_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/save_prefix', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_prefix_persists_new_prefix(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/save_prefix',
        json={"guild_id": "123", "prefix": "?"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    saved = await loadnsave.load_server_stats()
    assert saved["123"] == "?"
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_bot_config.py -v` (or `.venv/bin/python -m pytest ...` if needed)
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_bot_config.py
git commit -m "test: add coverage for dashboard/blueprints/bot_config.py"
```

---

### Task 24: Add tests for dashboard/blueprints/characters.py

**Files:**
- Create: `tests/test_blueprint_characters.py`

**Interfaces:**
- Consumes: `characters_bp` routes `/characters` (GET, public), `/retired` (GET, public), `/api/character/delete` (POST) from `dashboard/blueprints/characters.py`
- Consumes: `loadnsave.load_player_stats`/`save_player_stats` (cache `_PLAYER_STATS_CACHE`, file `player_stats.json`) and `loadnsave.load_retired_characters_data`/`save_retired_characters_data` (cache `_RETIRED_CHARACTERS_CACHE`, file `retired_characters_data.json`)
- Reuses: same `isolated_data_dir` and `login()` patterns as above; `/characters` and `/retired` are NOT gated by `is_admin`/`check_api_auth` (not under `/api/`), so they're tested without `login()`

- [ ] **Step 1: Write the test(s)**

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import loadnsave
from dashboard.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_PLAYER_STATS_CACHE", None)
    monkeypatch.setattr(loadnsave, "_RETIRED_CHARACTERS_CACHE", None)
    return tmp_path


CHAR_TEMPLATE = {
    "NAME": "Old Man Henderson",
    "Backstory": {
        "Personal Description": [], "Ideology/Beliefs": [], "Significant People": [],
        "Meaningful Locations": [], "Treasured Possessions": [], "Traits": []
    },
    "Connections": []
}


@pytest.mark.asyncio
async def test_characters_route_is_public_and_resolves_user_names(client, isolated_data_dir):
    await loadnsave.save_player_stats({"123": {"456": dict(CHAR_TEMPLATE)}})

    mock_user = MagicMock()
    mock_user.display_name = "PlayerOne"
    mock_bot = MagicMock()
    mock_bot.get_user.side_effect = lambda uid: mock_user if uid == 456 else None

    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/characters')

    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert "PlayerOne" in html


@pytest.mark.asyncio
async def test_characters_route_falls_back_to_user_id_when_unresolvable(client, isolated_data_dir):
    await loadnsave.save_player_stats({"123": {"456": dict(CHAR_TEMPLATE)}})
    mock_bot = MagicMock()
    mock_bot.get_user.return_value = None

    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/characters')

    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert "User 456" in html


@pytest.mark.asyncio
async def test_retired_route_is_public(client, isolated_data_dir):
    await loadnsave.save_retired_characters_data({"456": [dict(CHAR_TEMPLATE)]})
    with patch('dashboard.app.app.bot', None):
        response = await client.get('/retired')
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_character_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/character/delete', json={"type": "active"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_active_character_missing_ids_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/character/delete',
        json={"type": "active", "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_active_character_name_mismatch_returns_400(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_player_stats({"123": {"456": dict(CHAR_TEMPLATE)}})

    response = await client.post(
        '/api/character/delete',
        json={"type": "active", "server_id": "123", "user_id": "456", "name": "Wrong Name"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert "do not match" in data["message"]

    remaining = await loadnsave.load_player_stats()
    assert "456" in remaining["123"]


@pytest.mark.asyncio
async def test_delete_active_character_not_found_returns_404(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_player_stats({})
    response = await client.post(
        '/api/character/delete',
        json={"type": "active", "server_id": "123", "user_id": "456", "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_active_character_success_cleans_empty_guild(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_player_stats({"123": {"456": dict(CHAR_TEMPLATE)}})

    response = await client.post(
        '/api/character/delete',
        json={"type": "active", "server_id": "123", "user_id": "456", "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    remaining = await loadnsave.load_player_stats()
    assert "123" not in remaining


@pytest.mark.asyncio
async def test_delete_retired_character_missing_ids_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_retired_character_invalid_index_returns_400(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_retired_characters_data({"456": [dict(CHAR_TEMPLATE)]})

    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "user_id": "456", "index": 5, "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Invalid index"


@pytest.mark.asyncio
async def test_delete_retired_character_name_mismatch_returns_400(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_retired_characters_data({"456": [dict(CHAR_TEMPLATE)]})

    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "user_id": "456", "index": 0, "name": "Wrong Name"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_retired_character_user_not_found_returns_404(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_retired_characters_data({})

    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "user_id": "999", "index": 0, "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_retired_character_success_cleans_empty_list(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_retired_characters_data({"456": [dict(CHAR_TEMPLATE)]})

    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "user_id": "456", "index": 0, "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    remaining = await loadnsave.load_retired_characters_data()
    assert "456" not in remaining


@pytest.mark.asyncio
async def test_delete_character_invalid_type_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/character/delete',
        json={"type": "bogus", "name": "x"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_characters.py -v` (or `.venv/bin/python -m pytest ...` if needed)
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_characters.py
git commit -m "test: add coverage for dashboard/blueprints/characters.py"
```

---

### Task 25: Add tests for dashboard/blueprints/game_settings.py

**Files:**
- Create: `tests/test_blueprint_game_settings.py`

**Interfaces:**
- Consumes: `game_settings_bp` routes `/admin/game_settings` (GET), `/api/game/settings/data` (GET), `/api/game/settings/save_general` (POST), `/api/game/loot/data` (GET), `/api/game/loot/save` (POST), `/api/game/sounds/data` (GET), `/api/game/sounds/save` (POST) from `dashboard/blueprints/game_settings.py`
- Consumes: `loadnsave.load_luck_stats`/`save_luck_stats` (`_LUCK_STATS_CACHE`, `luck_stats.json`), `load_skill_settings`/`save_skill_settings` (`_SKILL_SETTINGS_CACHE`, `skill_settings.json`), `load_loot_settings`/`save_loot_settings` (`_LOOT_SETTINGS_CACHE`, `loot_settings.json`), `load_skill_sound_settings`/`save_skill_sound_settings` (`_SKILL_SOUND_SETTINGS_CACHE`, `skill_sound_settings.json`); `dashboard.blueprints.game_settings.sync_get_soundboard_files` (by-value import from `..file_utils` — patched directly rather than touching the real soundboard folder)
- Reuses: same `client`/`mock_dependencies`/`login()`, `isolated_data_dir`, CSRF `Origin` header patterns as above

- [ ] **Step 1: Write the test(s)**

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import loadnsave
from dashboard.app import app
import dashboard.blueprints.game_settings as game_settings


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_LUCK_STATS_CACHE", None)
    monkeypatch.setattr(loadnsave, "_SKILL_SETTINGS_CACHE", None)
    monkeypatch.setattr(loadnsave, "_LOOT_SETTINGS_CACHE", None)
    monkeypatch.setattr(loadnsave, "_SKILL_SOUND_SETTINGS_CACHE", None)
    return tmp_path


def make_guild(guild_id=111, name="Test Guild"):
    guild = MagicMock()
    guild.id = guild_id
    guild.name = name
    return guild


@pytest.mark.asyncio
async def test_admin_game_settings_redirects_if_not_logged_in(client):
    response = await client.get('/admin/game_settings')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_admin_game_settings_renders_when_logged_in(client):
    await login(client)
    response = await client.get('/admin/game_settings')
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_game_settings_data_unauthorized_without_session(client):
    response = await client.get('/api/game/settings/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_game_settings_data_no_bot_returns_empty_guilds(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.get('/api/game/settings/data')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"guilds": []}


@pytest.mark.asyncio
async def test_game_settings_data_uses_defaults_when_unset(client, isolated_data_dir):
    await login(client)
    guild = make_guild(guild_id=123)
    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/api/game/settings/data')

    data = json.loads(await response.get_data(as_text=True))
    guild_data = data["guilds"][0]
    assert guild_data["luck_threshold"] == 10
    assert guild_data["max_starting_skill"] == 75


@pytest.mark.asyncio
async def test_game_settings_data_reports_saved_values(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_luck_stats({"123": 25})
    await loadnsave.save_skill_settings({"123": {"max_starting_skill": 60}})

    guild = make_guild(guild_id=123)
    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/api/game/settings/data')

    data = json.loads(await response.get_data(as_text=True))
    guild_data = data["guilds"][0]
    assert guild_data["luck_threshold"] == 25
    assert guild_data["max_starting_skill"] == 60


@pytest.mark.asyncio
async def test_save_general_settings_missing_guild_id_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/game/settings/save_general', json={"luck_value": 10},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_general_settings_invalid_luck_value_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/game/settings/save_general',
        json={"guild_id": "123", "luck_value": -5},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Invalid luck value"


@pytest.mark.asyncio
async def test_save_general_settings_invalid_max_skill_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/game/settings/save_general',
        json={"guild_id": "123", "max_skill_value": 150},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Invalid max skill value (1-99)"


@pytest.mark.asyncio
async def test_save_general_settings_persists_both_values(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/game/settings/save_general',
        json={"guild_id": "123", "luck_value": 20, "max_skill_value": 80},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    luck = await loadnsave.load_luck_stats()
    skill = await loadnsave.load_skill_settings()
    assert luck["123"] == 20
    assert skill["123"]["max_starting_skill"] == 80


@pytest.mark.asyncio
async def test_game_loot_data_unauthorized_without_session(client):
    response = await client.get('/api/game/loot/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_game_loot_data_returns_defaults_when_unset(client, isolated_data_dir):
    await login(client)
    response = await client.get('/api/game/loot/data')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data["money_chance"] == 25
    assert data["currency_symbol"] == "$"
    assert isinstance(data["items"], list) and len(data["items"]) > 0


@pytest.mark.asyncio
async def test_game_loot_save_sanitizes_and_applies_defaults(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/game/loot/save',
        json={"items": ["A Rock"], "money_chance": "10", "currency_symbol": "gp"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    saved = await loadnsave.load_loot_settings()
    assert saved == {
        "items": ["A Rock"],
        "money_chance": 10,
        "money_min": 0.01,
        "money_max": 5.00,
        "currency_symbol": "gp",
        "num_items_min": 1,
        "num_items_max": 5,
    }


@pytest.mark.asyncio
async def test_game_loot_save_invalid_numeric_field_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/game/loot/save',
        json={"money_chance": "not-a-number"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["status"] == "error"


@pytest.mark.asyncio
async def test_game_sounds_data_flattens_and_sorts_files(client, isolated_data_dir):
    await login(client)
    files = {
        "Root": [{"name": "b.mp3", "path": "b.mp3"}],
        "Sub": [{"name": "a.mp3", "path": "Sub\\a.mp3"}],
    }
    with patch.object(game_settings, 'sync_get_soundboard_files', return_value=files):
        response = await client.get('/api/game/sounds/data')

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data["files"] == ["Sub/a.mp3", "b.mp3"]
    assert data["settings"] == {}


@pytest.mark.asyncio
async def test_game_sounds_save_missing_guild_id_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/game/sounds/save', json={"default": {}},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_game_sounds_save_persists_nested_structure(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/game/sounds/save',
        json={
            "guild_id": "123",
            "default": {"critical": "yay.mp3"},
            "skills": {"Spot Hidden": {"critical": "found.mp3"}},
        },
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    saved = await loadnsave.load_skill_sound_settings()
    assert saved["123"] == {
        "default": {"critical": "yay.mp3"},
        "skills": {"Spot Hidden": {"critical": "found.mp3"}},
    }
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_blueprint_game_settings.py -v` (or `.venv/bin/python -m pytest ...` if needed)
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_blueprint_game_settings.py
git commit -m "test: add coverage for dashboard/blueprints/game_settings.py"
```

---


1. Every test constructing a discord.ui.View/Modal subclass is `@pytest.mark.asyncio async def` — discord.py 2.6.4's BaseView.__init__ calls `asyncio.get_running_loop()` unconditionally, so construction outside a running loop raises RuntimeError.
2. Modal field values are set via the private `_value` attribute (`modal.field._value = "..."` or `.field.component._value = "..."` for Label-wrapped fields) — `TextInput.value` has no public setter; `_value` is exactly what discord.py itself populates from real payloads.
3. Select/UserSelect/RoleSelect/ChannelSelect "what the user picked" is simulated via `select._values = [...]` — same reasoning, mirrors the library's own `refresh_state`.
4. Decorated `@discord.ui.button`/`@discord.ui.select` callbacks are invoked as `await view.some_button.callback(interaction)` — post-`__init__`, `view.some_button` is the real item instance and `.callback` is discord.py's `_ViewCallback` wrapper supplying `(view, interaction, item)`.
5. Cog mocking has to split by sync/async: `commands/newinvestigator.py`'s step_*/pulp_*/mode_*/finish_*/proceed_*/assign_* methods are `async def` (AsyncMock), but `roll_stat_formula`, `is_skill_allowed_for_archetype`, `calculate_occupation_points` are plain `def` (MagicMock) — same split for `commands/roll.py`'s `calculate_roll_result`/`evaluate_dice_expression` (both sync, used throughout _roll_views.py and _mychar_roll.py).
6. loadnsave patches target the importing module's namespace (e.g. `commands._journal_views.load_journal_data`) per the existing `test_data_schema.py` convention — except `_mychar_roll.py::SkillRollSelect.callback`, which does a **local** `from loadnsave import load_luck_stats` inside the function body, so that one must be patched at `loadnsave.load_luck_stats` directly.

---

### Task 26: Add tests for commands/_newinvestigator_talents.py (incl. back-navigation)

**Files:**
- Create: `tests/test_commands_newinvestigator_talents.py`

**Interfaces:**
- Consumes: `TalentCategorySelect.__init__`/`.callback`, `CategoryView.__init__`, `TalentSelect.__init__`/`.callback`, `TalentOptionView.__init__`/`.back_button` (all from `commands/_newinvestigator_talents.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from commands._newinvestigator_talents import (
    TalentCategorySelect,
    CategoryView,
    TalentSelect,
    TalentOptionView,
)


def make_interaction():
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    return interaction


@pytest.fixture
def cog():
    c = AsyncMock()
    return c


@pytest.fixture
def pulp_data():
    return {
        "mundane": ["**Fast Talker**: Gain bonus to Fast Talk.", "**Tough**: Gain bonus HP."],
        "combat": ["**Gunslinger**: Bonus to Firearms."],
    }


class TestTalentCategorySelect:
    def test_options_are_capitalized_category_names(self, pulp_data):
        select = TalentCategorySelect(pulp_data)
        labels = {opt.label for opt in select.options}
        assert labels == {"Mundane", "Combat"}
        values = {opt.value for opt in select.options}
        assert values == {"mundane", "combat"}

    @pytest.mark.asyncio
    async def test_callback_delegates_to_cog_with_full_context(self, cog, pulp_data):
        char_data = {"NAME": "Jane"}
        player_stats = {"1": {"2": char_data}}
        view = CategoryView(cog, pulp_data, ["a_talent"], 2, {"a_talent": "mundane"}, char_data, player_stats)
        select = view.children[0]
        assert isinstance(select, TalentCategorySelect)

        select._values = ["mundane"]
        interaction = make_interaction()
        await select.callback(interaction)

        cog.pulp_talent_category_selected.assert_awaited_once_with(
            interaction, "mundane", pulp_data, ["a_talent"], 2, {"a_talent": "mundane"}, char_data, player_stats
        )


class TestCategoryView:
    def test_stores_context_and_adds_select(self, cog, pulp_data):
        char_data = {}
        player_stats = {}
        view = CategoryView(cog, pulp_data, [], 3, {}, char_data, player_stats)

        assert view.cog is cog
        assert view.pulp_data is pulp_data
        assert view.slots_total == 3
        assert view.char_data is char_data
        assert view.player_stats is player_stats
        assert len(view.children) == 1
        assert isinstance(view.children[0], TalentCategorySelect)


class TestTalentSelect:
    def test_filters_already_selected_and_parses_name_description(self):
        talents = ["**Fast Talker**: Gain bonus to Fast Talk.", "**Tough**: Gain bonus HP."]
        select = TalentSelect(talents, already_selected=["Tough"])
        assert len(select.options) == 1
        opt = select.options[0]
        assert opt.label == "Fast Talker"
        assert opt.description == "Gain bonus to Fast Talk."
        assert opt.value == "Fast Talker"

    def test_no_options_available_falls_back_to_placeholder_option(self):
        select = TalentSelect(["**Tough**: desc"], already_selected=["Tough"])
        assert len(select.options) == 1
        assert select.options[0].value == "none"

    @pytest.mark.asyncio
    async def test_callback_delegates_to_cog_with_full_context(self, cog):
        char_data = {"NAME": "Jane"}
        player_stats = {"1": {"2": char_data}}
        view = TalentOptionView(
            cog, ["**Fast Talker**: desc"], [], {"Fast Talker": "mundane"},
            {"mundane": ["**Fast Talker**: desc"]}, ["current"], 2, char_data, player_stats,
        )
        select = view.children[0]
        assert isinstance(select, TalentSelect)

        select._values = ["Fast Talker"]
        interaction = make_interaction()
        await select.callback(interaction)

        cog.pulp_talent_selected.assert_awaited_once_with(
            interaction, "Fast Talker", {"mundane": ["**Fast Talker**: desc"]}, ["current"], 2,
            {"Fast Talker": "mundane"}, char_data, player_stats,
        )


class TestTalentOptionViewBackNavigation:
    @pytest.mark.asyncio
    async def test_back_button_returns_to_pulp_talent_selection_loop_with_original_state(self, cog):
        char_data = {"NAME": "Jane"}
        player_stats = {"1": {"2": char_data}}
        pulp_data = {"mundane": ["**Fast Talker**: desc"]}
        current_list = ["Fast Talker", "Tough"]
        full_map = {"Fast Talker": "mundane"}

        view = TalentOptionView(
            cog, ["**Fast Talker**: desc"], [], full_map, pulp_data, current_list, 2, char_data, player_stats,
        )
        interaction = make_interaction()

        await view.back_button.callback(interaction)

        # Back navigation must return to the category/talent selection loop with the
        # exact same char_data/player_stats/pulp_data/current_list/slots/full_map it was
        # constructed with -- i.e. no state is mutated or reset on Back.
        cog.pulp_talent_selection_loop.assert_awaited_once_with(
            interaction, char_data, player_stats, pulp_data, current_list, 2, full_map
        )

    def test_back_button_present_on_view(self, cog):
        view = TalentOptionView(cog, ["**Fast Talker**: desc"], [], {}, {}, [], 0, {}, {})
        assert any(getattr(c, "label", None) == "Back" for c in view.children)
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_newinvestigator_talents.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_newinvestigator_talents.py
git commit -m "test: add coverage for commands/_newinvestigator_talents.py"
```

---

### Task 27: Add tests for commands/_newinvestigator_skills.py (incl. back-navigation)

**Files:**
- Create: `tests/test_commands_newinvestigator_skills.py`

**Interfaces:**
- Consumes: `SkillPointSetModal.on_submit`, `SkillSpecializationModal.on_submit`, `CustomSkillModal.on_submit`, `CthulhuMythosWarningView.assign`/`.cancel`, `SkillPageSelect.callback`, `SkillPointAllocationView.__init__`/`.update_view`/`.get_embed`/`.finish`/`.prev_page`/`.next_page`/`.add_custom_skill`, `FinishConfirmationView.yes`/`.no` (all from `commands/_newinvestigator_skills.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from commands._newinvestigator_skills import (
    SkillPointSetModal,
    SkillSpecializationModal,
    CustomSkillModal,
    CthulhuMythosWarningView,
    SkillPageSelect,
    SkillPointAllocationView,
    FinishConfirmationView,
)


def make_interaction():
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    return interaction


def make_view(**overrides):
    view = MagicMock()
    view.char_data = overrides.get("char_data", {"Spot Hidden": 25})
    view.max_skill = overrides.get("max_skill", 75)
    view.remaining_points = overrides.get("remaining_points", 50)
    view.min_cr = overrides.get("min_cr", 0)
    view.max_cr = overrides.get("max_cr", 99)
    view.all_skills = overrides.get("all_skills", ["Spot Hidden"])
    view.refresh = AsyncMock()
    return view


class TestSkillPointSetModal:
    @pytest.mark.asyncio
    async def test_valid_increase_applies_cost_and_refreshes(self):
        view = make_view()
        modal = SkillPointSetModal(view, "Spot Hidden", current_val=25, base_val=25)
        modal.value_input.component._value = "40"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert view.char_data["Spot Hidden"] == 40
        assert view.remaining_points == 50 - 15
        view.refresh.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_non_numeric_value_rejected(self):
        view = make_view()
        modal = SkillPointSetModal(view, "Spot Hidden", current_val=25, base_val=25)
        modal.value_input.component._value = "not-a-number"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "valid number" in interaction.response.send_message.call_args.args[0]
        view.refresh.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_credit_rating_uses_min_max_cr_bounds(self):
        view = make_view(min_cr=10, max_cr=90, char_data={"Credit Rating": 10}, remaining_points=100)
        modal = SkillPointSetModal(view, "Credit Rating", current_val=10, base_val=10)
        modal.value_input.component._value = "5"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "Credit Rating must be between" in interaction.response.send_message.call_args.args[0]

    @pytest.mark.asyncio
    async def test_below_base_value_rejected(self):
        view = make_view()
        modal = SkillPointSetModal(view, "Spot Hidden", current_val=25, base_val=25)
        modal.value_input.component._value = "10"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "below base value" in interaction.response.send_message.call_args.args[0]

    @pytest.mark.asyncio
    async def test_not_enough_points_rejected(self):
        view = make_view(remaining_points=5)
        modal = SkillPointSetModal(view, "Spot Hidden", current_val=25, base_val=25)
        modal.value_input.component._value = "50"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "Not enough points" in interaction.response.send_message.call_args.args[0]
        assert view.char_data["Spot Hidden"] == 25


class TestSkillSpecializationModal:
    @pytest.mark.asyncio
    async def test_creates_new_named_specialization(self):
        view = make_view(char_data={}, all_skills=[], remaining_points=50)
        modal = SkillSpecializationModal(view, "Art/Craft (Any)", base_val=5)
        modal.spec_name.component._value = "Painting"
        modal.value_input.component._value = "30"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert view.char_data["Art/Craft (Painting)"] == 30
        assert view.remaining_points == 50 - 25
        assert "Art/Craft (Painting)" in view.all_skills
        view.refresh.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_duplicate_specialization_rejected(self):
        view = make_view(char_data={"Art/Craft (Painting)": 30})
        modal = SkillSpecializationModal(view, "Art/Craft (Any)", base_val=5)
        modal.spec_name.component._value = "Painting"
        modal.value_input.component._value = "30"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "already have this specialization" in interaction.response.send_message.call_args.args[0]


class TestCustomSkillModal:
    @pytest.mark.asyncio
    async def test_adds_custom_skill_with_emoji(self):
        view = make_view(char_data={}, all_skills=[], remaining_points=50)
        modal = CustomSkillModal(view)
        modal.skill_name.component._value = "Lore (Vampires)"
        modal.base_val.component._value = "5"
        modal.value_input.component._value = "20"
        modal.emoji_input.component._value = "🧛"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert view.char_data["Lore (Vampires)"] == 20
        assert view.remaining_points == 50 - 15
        assert "Lore (Vampires)" in view.all_skills
        assert view.char_data["Custom Emojis"]["Lore (Vampires)"] == "🧛"
        view.refresh.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_duplicate_skill_name_rejected(self):
        view = make_view(char_data={"Lore (Vampires)": 20})
        modal = CustomSkillModal(view)
        modal.skill_name.component._value = "Lore (Vampires)"
        modal.base_val.component._value = "5"
        modal.value_input.component._value = "20"
        modal.emoji_input.component._value = ""

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "already exists" in interaction.response.send_message.call_args.args[0]


class TestCthulhuMythosWarningView:
    @pytest.mark.asyncio
    async def test_assign_opens_skill_point_set_modal(self):
        parent_view = make_view()
        view = CthulhuMythosWarningView(parent_view, "Cthulhu Mythos", current_val=0, base_val=0)
        interaction = make_interaction()

        await view.assign.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.call_args.args[0]
        assert isinstance(modal, SkillPointSetModal)
        assert modal.skill_name == "Cthulhu Mythos"

    @pytest.mark.asyncio
    async def test_cancel_edits_message_and_clears_view(self):
        parent_view = make_view()
        view = CthulhuMythosWarningView(parent_view, "Cthulhu Mythos", current_val=0, base_val=0)
        interaction = make_interaction()

        await view.cancel.callback(interaction)

        interaction.response.edit_message.assert_awaited_once_with(content="Action cancelled.", view=None)


class TestSkillPageSelect:
    @pytest.mark.asyncio
    async def test_selecting_cthulhu_mythos_shows_warning_view(self):
        parent_view = make_view(char_data={"Cthulhu Mythos": 0})
        options = [discord.SelectOption(label="Cthulhu Mythos: 0%", value="Cthulhu Mythos")]
        select = SkillPageSelect(options)
        select._view = parent_view
        select._values = ["Cthulhu Mythos"]

        interaction = make_interaction()
        await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], CthulhuMythosWarningView)

    @pytest.mark.asyncio
    async def test_selecting_any_skill_opens_specialization_modal(self):
        parent_view = make_view(char_data={"Art/Craft (Any)": 5})
        options = [discord.SelectOption(label="Art/Craft (Any): 5%", value="Art/Craft (Any)")]
        select = SkillPageSelect(options)
        select._view = parent_view
        select._values = ["Art/Craft (Any)"]

        interaction = make_interaction()
        await select.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], SkillSpecializationModal)

    @pytest.mark.asyncio
    async def test_selecting_normal_skill_opens_point_set_modal(self):
        parent_view = make_view(char_data={"Spot Hidden": 25})
        options = [discord.SelectOption(label="Spot Hidden: 25%", value="Spot Hidden")]
        select = SkillPageSelect(options)
        select._view = parent_view
        select._values = ["Spot Hidden"]

        interaction = make_interaction()
        await select.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], SkillPointSetModal)


@pytest.fixture
def alloc_cog():
    cog = MagicMock()
    cog.is_skill_allowed_for_archetype = MagicMock(return_value=True)
    cog.finish_skill_assignment = AsyncMock()
    return cog


class TestSkillPointAllocationView:
    @pytest.mark.asyncio
    async def test_get_skill_list_excludes_known_metadata_keys(self, alloc_cog):
        char_data = {
            "NAME": "Jane", "STR": 50, "Spot Hidden": 25, "Listen": 20, "Age": 24,
            "Backstory": {}, "Credit Rating": 10,
        }
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=50, min_cr=0, max_cr=99, is_occupation=False)

        assert "NAME" not in view.all_skills
        assert "STR" not in view.all_skills
        assert "Age" not in view.all_skills
        assert "Backstory" not in view.all_skills
        assert "Spot Hidden" in view.all_skills
        assert "Listen" in view.all_skills
        assert "Credit Rating" in view.all_skills

    @pytest.mark.asyncio
    async def test_finish_button_disabled_while_points_remain(self, alloc_cog):
        char_data = {"Spot Hidden": 25, "Credit Rating": 0}
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=10, min_cr=0, max_cr=99, is_occupation=False)

        finish_btn = next(c for c in view.children if getattr(c, "label", None) == "Finish")
        assert finish_btn.disabled is True

    @pytest.mark.asyncio
    async def test_finish_button_enabled_when_no_points_remain(self, alloc_cog):
        char_data = {"Spot Hidden": 25, "Credit Rating": 0}
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=0, min_cr=0, max_cr=99, is_occupation=False)

        finish_btn = next(c for c in view.children if getattr(c, "label", None) == "Finish")
        assert finish_btn.disabled is False

    @pytest.mark.asyncio
    async def test_finish_calls_cog_finish_skill_assignment(self, alloc_cog):
        char_data = {"Spot Hidden": 25, "Credit Rating": 0}
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=0, min_cr=0, max_cr=99, is_occupation=False)
        interaction = make_interaction()

        finish_btn = next(c for c in view.children if getattr(c, "label", None) == "Finish")
        await finish_btn.callback(interaction)

        alloc_cog.finish_skill_assignment.assert_awaited_once_with(interaction, view)

    @pytest.mark.asyncio
    async def test_pagination_next_and_prev(self, alloc_cog):
        char_data = {f"Skill {i}": i for i in range(30)}
        char_data["Credit Rating"] = 0
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=50, min_cr=0, max_cr=99, is_occupation=False)
        interaction = make_interaction()

        next_btn = next(c for c in view.children if getattr(c, "label", None) == "Next")
        await next_btn.callback(interaction)
        assert view.page == 1
        interaction.response.edit_message.assert_awaited_once()

        interaction2 = make_interaction()
        prev_btn = next(c for c in view.children if getattr(c, "label", None) == "Previous")
        await prev_btn.callback(interaction2)
        assert view.page == 0

    @pytest.mark.asyncio
    async def test_add_custom_skill_opens_modal(self, alloc_cog):
        char_data = {"Spot Hidden": 25, "Credit Rating": 0}
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=50, min_cr=0, max_cr=99, is_occupation=False)
        interaction = make_interaction()

        custom_btn = next(c for c in view.children if getattr(c, "label", None) == "Add Custom Skill")
        await custom_btn.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], CustomSkillModal)

    def test_get_embed_lists_suggested_occupation_skills(self, alloc_cog):
        char_data = {
            "Spot Hidden": 40, "Credit Rating": 0,
            "Occupation Info": {"skills": "Spot Hidden, Listen"},
        }
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=10, min_cr=0, max_cr=99, is_occupation=True)
        embed = view.get_embed()
        assert "Suggested Occupation Skills" in embed.description
        assert "Improved Skills" in [f.name for f in embed.fields]


class TestFinishConfirmationViewBackNavigation:
    @pytest.mark.asyncio
    async def test_yes_proceeds_via_cog(self):
        cog = AsyncMock()
        parent_view = make_view()
        view = FinishConfirmationView(cog, parent_view, message=MagicMock())
        interaction = make_interaction()

        await view.yes.callback(interaction)

        cog.proceed_after_skills.assert_awaited_once_with(interaction, parent_view)

    @pytest.mark.asyncio
    async def test_no_back_button_only_sends_message_and_does_not_touch_cog_or_parent_state(self):
        # This is the wizard's "NO (Back)" step: unlike other back-navigations in this
        # codebase it does NOT re-render a prior view or call any cog method -- it simply
        # tells the user to keep using the still-open SkillPointAllocationView underneath.
        # It must not mutate remaining_points/char_data on the parent view at all.
        cog = AsyncMock()
        parent_view = make_view(remaining_points=5, char_data={"Spot Hidden": 25})
        view = FinishConfirmationView(cog, parent_view, message=MagicMock())
        interaction = make_interaction()

        await view.no.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "Cancelled. Continue assigning points.", ephemeral=True
        )
        cog.proceed_after_skills.assert_not_awaited()
        assert parent_view.remaining_points == 5
        assert parent_view.char_data == {"Spot Hidden": 25}
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_newinvestigator_skills.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_newinvestigator_skills.py
git commit -m "test: add coverage for commands/_newinvestigator_skills.py"
```

---

### Task 28: Add tests for commands/_roll_views.py

**Files:**
- Create: `tests/test_commands_roll_views.py`

**Interfaces:**
- Consumes: `SessionView.yes_button`/`.no_button`, `DisambiguationSelect.callback`, `DisambiguationView.cancel`/`.interaction_check`, `DamageSelect.callback`, `RollResultView.__init__`/`.add_bonus_btn`/`.add_penalty_btn`/`.luck_button`/`.push_button`/`.done_button`/`.damage_btn`/`.interaction_check`, `QuickSkillSelect.__init__`/`.callback`, `DiceTrayView.add_term`/`.clear`/`.roll_btn`/`.interaction_check` (all from `commands/_roll_views.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._roll_views import (
    SessionView,
    DisambiguationSelect,
    DisambiguationView,
    DamageSelect,
    DamageSelectView,
    RollResultView,
    QuickSkillSelect,
    DiceTrayView,
)


def make_interaction(user=None):
    interaction = MagicMock()
    interaction.user = user or MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup.send = AsyncMock()
    interaction.message = MagicMock(embeds=[discord.Embed(description="orig")])
    interaction.message.edit = AsyncMock()
    return interaction


class TestSessionView:
    @pytest.mark.asyncio
    async def test_yes_by_author_sets_create_session_true_and_disables_buttons(self):
        author = MagicMock()
        ctx = MagicMock(author=author)
        view = SessionView(ctx)
        interaction = make_interaction(user=author)

        await view.yes_button.callback(interaction)

        assert view.create_session is True
        assert all(c.disabled for c in view.children)
        interaction.response.edit_message.assert_awaited_once_with(view=view)

    @pytest.mark.asyncio
    async def test_no_by_non_author_is_rejected(self):
        ctx = MagicMock(author=MagicMock())
        view = SessionView(ctx)
        other_user = MagicMock()
        interaction = make_interaction(user=other_user)

        await view.no_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Not for you!", ephemeral=True)
        assert view.create_session is False  # unchanged default, not flipped by rejected click


class TestDisambiguation:
    @pytest.mark.asyncio
    async def test_select_sets_selected_stat_and_stops_view(self):
        ctx = MagicMock(author=MagicMock())
        view = DisambiguationView(ctx, ["Spot Hidden", "Listen"])
        select = view.children[0]
        assert isinstance(select, DisambiguationSelect)
        select._values = ["Listen"]

        interaction = make_interaction()
        interaction.response.defer = AsyncMock()
        await select.callback(interaction)

        assert view.selected_stat == "Listen"
        interaction.response.defer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_other_users(self):
        author = MagicMock()
        ctx = MagicMock(author=author)
        view = DisambiguationView(ctx, ["Spot Hidden"])
        interaction = make_interaction(user=MagicMock())

        result = await view.interaction_check(interaction)

        assert result is False
        interaction.response.send_message.assert_awaited_once_with("Not your session!", ephemeral=True)


class TestDamageSelect:
    @pytest.mark.asyncio
    async def test_callback_dispatches_chosen_formula_and_label(self):
        damage_data = [{"label": "1d6", "value": "1d6"}, {"label": "1d8+1", "value": "1d8+1"}]
        parent_view = MagicMock(damage_data=damage_data)
        parent_view.perform_damage_roll = AsyncMock()
        select = DamageSelect(damage_data, parent_view)
        select._values = ["1d8+1"]

        interaction = make_interaction()
        await select.callback(interaction)

        parent_view.perform_damage_roll.assert_awaited_once_with(interaction, "1d8+1", "1d8+1")


def make_roll_view(**overrides):
    cog = MagicMock()
    cog.calculate_roll_result = MagicMock(return_value=("Regular Success", 2))
    cog.evaluate_dice_expression = MagicMock(return_value=(5, "1d6 -> 5"))

    ctx = MagicMock(author=overrides.get("author", MagicMock()))
    player_stats = overrides.get(
        "player_stats", {"srv": {"usr": {"LUCK": 50}}}
    )
    kwargs = dict(
        ctx=ctx, cog=cog, player_stats=player_stats, server_id="srv", user_id="usr",
        stat_name="Spot Hidden", current_value=50, ones_roll=5, tens_rolls=[20],
        net_dice=0, result_tier=2, luck_threshold=10,
    )
    kwargs.update(overrides.get("kwargs", {}))
    return RollResultView(**kwargs), cog, ctx, player_stats


class TestRollResultView:
    @pytest.mark.asyncio
    async def test_constructor_removes_damage_button_when_no_damage_data(self):
        view, *_ = make_roll_view()
        assert not any(getattr(c, "label", None) == "Roll Damage" for c in view.children)

    @pytest.mark.asyncio
    async def test_constructor_enables_damage_button_on_success_with_damage_data(self):
        view, *_ = make_roll_view(kwargs={"damage_data": [{"label": "1d6", "value": "1d6"}], "damage_bonus": "0"})
        damage_btn = next(c for c in view.children if getattr(c, "label", None) == "Roll Damage")
        assert damage_btn.disabled is False

    @pytest.mark.asyncio
    async def test_constructor_detects_malfunction_and_overrides_success(self):
        view, *_ = make_roll_view(kwargs={"malfunction_threshold": "20"})
        # roll = tens(20) + ones(5) = 25 >= limit 20 -> malfunction
        assert view.is_malfunction is True
        assert view.success is False

    @pytest.mark.asyncio
    async def test_bonus_die_increments_net_dice_and_recalculates(self):
        view, cog, *_ = make_roll_view()
        interaction = make_interaction()

        await view.add_bonus_btn.callback(interaction)

        assert view.net_dice == 1
        assert len(view.tens_rolls) >= 2
        cog.calculate_roll_result.assert_called_once()
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_penalty_die_decrements_net_dice(self):
        view, cog, *_ = make_roll_view()
        interaction = make_interaction()

        await view.add_penalty_btn.callback(interaction)

        assert view.net_dice == -1

    @pytest.mark.asyncio
    async def test_luck_button_deducts_cost_and_marks_used(self):
        # Fail tier(1) target = current_value(50); roll = 25 -> target_val=50 means cost negative;
        # use a Fail-tier roll so cost is positive and luck applies cleanly.
        view, cog, ctx, player_stats = make_roll_view(kwargs={"result_tier": 1, "ones_roll": 9, "tens_rolls": [90]})
        # roll = 99, target = current_value (50) on a Fail -> Regular upgrade, cost = 49
        interaction = make_interaction()

        await view.luck_button.callback(interaction)

        assert view.luck_used is True
        assert view.success is True
        assert view.result_tier == 2
        assert player_stats["srv"]["usr"]["LUCK"] == 50 - 49
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_push_roll_disables_all_buttons_and_clears_view(self):
        view, cog, *_ = make_roll_view(kwargs={"result_tier": 1})
        cog.calculate_roll_result = MagicMock(return_value=("Failure", 0))
        interaction = make_interaction()

        with patch("commands._roll_views.random.randint", return_value=1):
            await view.push_button.callback(interaction)

        assert all(c.disabled for c in view.children)
        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        assert kwargs["view"] is None

    @pytest.mark.asyncio
    async def test_done_button_invokes_async_on_complete_and_stops(self):
        on_complete = AsyncMock()
        view, *_ = make_roll_view(kwargs={"on_complete": on_complete})
        interaction = make_interaction()

        await view.done_button.callback(interaction)

        on_complete.assert_awaited_once_with(view.roll, view.result_tier, view.is_malfunction)
        assert view.is_finished()
        interaction.message.edit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_done_button_invokes_sync_on_complete(self):
        on_complete = MagicMock()
        view, *_ = make_roll_view(kwargs={"on_complete": on_complete})
        interaction = make_interaction()

        await view.done_button.callback(interaction)

        on_complete.assert_called_once_with(view.roll, view.result_tier, view.is_malfunction)

    @pytest.mark.asyncio
    async def test_damage_btn_single_item_rolls_directly(self):
        view, cog, *_ = make_roll_view(
            kwargs={"damage_data": [{"label": "1d6", "value": "1d6"}], "damage_bonus": "0"}
        )
        interaction = make_interaction()

        await view.damage_btn.callback(interaction)

        cog.evaluate_dice_expression.assert_called_once_with("1d6")
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_damage_btn_multiple_items_shows_selection_view(self):
        damage_data = [{"label": "1d6", "value": "1d6"}, {"label": "1d8", "value": "1d8"}]
        view, cog, *_ = make_roll_view(kwargs={"damage_data": damage_data, "damage_bonus": "0"})
        interaction = make_interaction()

        await view.damage_btn.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], DamageSelectView)

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_non_author(self):
        view, *_ = make_roll_view()
        interaction = make_interaction(user=MagicMock())

        result = await view.interaction_check(interaction)

        assert result is False


class TestQuickSkillSelect:
    def test_options_limited_to_top_25_skills_sorted_descending(self):
        char_data = {f"Skill{i}": i for i in range(30)}
        select = QuickSkillSelect(char_data, "srv", "usr")
        assert len(select.options) == 25
        assert select.options[0].value == "Skill29"

    @pytest.mark.asyncio
    async def test_callback_rolls_and_sends_channel_message(self):
        char_data = {"Spot Hidden": 50}
        select = QuickSkillSelect(char_data, "srv", "usr")
        select._values = ["Spot Hidden"]

        roll_cog = MagicMock()
        roll_cog.calculate_roll_result = MagicMock(return_value=("Regular Success", 2))

        interaction = make_interaction()
        interaction.client.get_cog = MagicMock(return_value=roll_cog)
        sent_message = MagicMock()
        interaction.channel.send = AsyncMock(return_value=sent_message)

        with patch("commands._roll_views.load_luck_stats", new=AsyncMock(return_value={"srv": 10})), \
             patch("commands._roll_views.load_player_stats", new=AsyncMock(return_value={"srv": {"usr": char_data}})):
            await select.callback(interaction)

        interaction.channel.send.assert_awaited_once()
        _, kwargs = interaction.channel.send.call_args
        assert isinstance(kwargs["view"], RollResultView)
        assert kwargs["view"].message is sent_message
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_callback_noop_when_roll_cog_missing(self):
        char_data = {"Spot Hidden": 50}
        select = QuickSkillSelect(char_data, "srv", "usr")
        select._values = ["Spot Hidden"]

        interaction = make_interaction()
        interaction.client.get_cog = MagicMock(return_value=None)

        await select.callback(interaction)

        interaction.response.send_message.assert_not_awaited()


class TestDiceTrayView:
    @pytest.mark.asyncio
    async def test_add_term_appends_expression_and_updates_display(self):
        view = DiceTrayView(MagicMock(), MagicMock())
        interaction = make_interaction()

        await view.d6.callback(interaction)
        assert view.expression == "1d6"
        interaction.response.edit_message.assert_awaited_once()

        interaction2 = make_interaction()
        await view.d20.callback(interaction2)
        assert view.expression == "1d6 + 1d20"

    @pytest.mark.asyncio
    async def test_clear_resets_expression(self):
        view = DiceTrayView(MagicMock(), MagicMock())
        view.expression = "1d6 + 5"
        interaction = make_interaction()

        await view.clear.callback(interaction)

        assert view.expression == ""

    @pytest.mark.asyncio
    async def test_roll_with_empty_expression_is_rejected(self):
        cog = MagicMock()
        cog._perform_roll = AsyncMock()
        view = DiceTrayView(cog, MagicMock())
        interaction = make_interaction()

        await view.roll_btn.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Add dice first!", ephemeral=True)
        cog._perform_roll.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_roll_with_expression_invokes_cog_perform_roll(self):
        cog = MagicMock()
        cog._perform_roll = AsyncMock()
        view = DiceTrayView(cog, MagicMock())
        view.expression = "1d20 + 5"
        interaction = make_interaction()
        interaction.response.defer = AsyncMock()
        interaction.delete_original_response = AsyncMock()

        await view.roll_btn.callback(interaction)

        cog._perform_roll.assert_awaited_once_with(interaction, "1d20 + 5", 0, 0, True, "Regular")

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_other_users(self):
        owner = MagicMock()
        view = DiceTrayView(MagicMock(), owner)
        interaction = make_interaction(user=MagicMock())

        result = await view.interaction_check(interaction)

        assert result is False
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_roll_views.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_roll_views.py
git commit -m "test: add coverage for commands/_roll_views.py"
```

---

### Task 29: Add tests for commands/_codex_views.py

**Files:**
- Create: `tests/test_commands_codex_views.py`

**Interfaces:**
- Consumes: `PaginatedListView.__init__`/`.update_select_options`/`.select_callback`/`.prev_button`/`.next_button`/`.close_button`/`.on_timeout`, `OptionsView.list_button`/`.random_button`/`.cancel_button`, `RenderView.__init__`/`.poster_button`/`.origin_poster_button`/`.add_to_inventory_button`, `CodexView._check_owner`/`.monsters_button`/`.talents_button`, `SelectionView.select_callback` (all from `commands/_codex_views.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._codex_views import (
    PaginatedListView,
    OptionsView,
    RenderView,
    CodexView,
    SelectionView,
)


def make_interaction(user=None):
    interaction = MagicMock()
    interaction.user = user or MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.data = {}
    return interaction


class TestPaginatedListView:
    def test_pagination_math_and_select_options_built(self):
        user = MagicMock()
        cog = MagicMock()
        items = [f"Item {i}" for i in range(45)]
        view = PaginatedListView(user, items, "Title", per_page=20, data={}, cog=cog, type_slug="monster")

        assert view.total_pages == 3
        assert view.select_menu is not None
        assert len(view.select_menu.options) == 20

    def test_no_items_on_page_adds_disabled_placeholder(self):
        user = MagicMock()
        cog = MagicMock()
        view = PaginatedListView(user, [], "Title", data={}, cog=cog, type_slug="monster")
        assert view.select_menu.options[0].value == "__none__"
        assert view.select_menu.disabled is True

    @pytest.mark.asyncio
    async def test_select_callback_rejects_non_owner(self):
        owner = MagicMock()
        cog = MagicMock()
        view = PaginatedListView(owner, ["Item A"], "Title", data={}, cog=cog, type_slug="monster")
        interaction = make_interaction(user=MagicMock())

        await view.select_callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("This isn't for you!", ephemeral=True)

    @pytest.mark.asyncio
    async def test_select_callback_displays_entry_when_found(self):
        owner = MagicMock()
        cog = MagicMock()
        cog._get_entry_data = MagicMock(return_value={"name": "Item A"})
        cog._display_entry = AsyncMock()
        view = PaginatedListView(owner, ["Item A"], "Title", data={"k": 1}, cog=cog, type_slug="monster")
        interaction = make_interaction(user=owner)
        interaction.data = {"values": ["Item A"]}

        await view.select_callback(interaction)

        cog._display_entry.assert_awaited_once_with(interaction, "Item A", "monster", {"name": "Item A"}, ephemeral=True)

    @pytest.mark.asyncio
    async def test_select_callback_falls_back_to_render_poster_when_missing(self):
        owner = MagicMock()
        cog = MagicMock()
        cog._get_entry_data = MagicMock(return_value=None)
        cog._render_poster = AsyncMock()
        view = PaginatedListView(owner, ["Item A"], "Title", data={}, cog=cog, type_slug="monster")
        interaction = make_interaction(user=owner)
        interaction.data = {"values": ["Item A"]}

        await view.select_callback(interaction)

        cog._render_poster.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_next_and_prev_buttons_update_page_and_embed(self):
        owner = MagicMock()
        items = [f"Item {i}" for i in range(25)]
        view = PaginatedListView(owner, items, "Title", per_page=20)
        interaction = make_interaction(user=owner)

        await view.next_button.callback(interaction)
        assert view.current_page == 1
        interaction.response.edit_message.assert_awaited_once()

        interaction2 = make_interaction(user=owner)
        await view.prev_button.callback(interaction2)
        assert view.current_page == 0

    @pytest.mark.asyncio
    async def test_close_button_clears_message_and_stops(self):
        owner = MagicMock()
        view = PaginatedListView(owner, ["Item A"], "Title")
        interaction = make_interaction(user=owner)

        await view.close_button.callback(interaction)

        interaction.response.edit_message.assert_awaited_once_with(content="List closed.", embed=None, view=None)
        assert view.is_finished()

    @pytest.mark.asyncio
    async def test_on_timeout_deletes_message(self):
        owner = MagicMock()
        view = PaginatedListView(owner, ["Item A"], "Title")
        view.message = MagicMock()
        view.message.delete = AsyncMock()

        await view.on_timeout()

        view.message.delete.assert_awaited_once()
        assert view.is_finished()


class TestOptionsView:
    @pytest.mark.asyncio
    async def test_list_button_loads_and_sorts_dict_keys(self):
        user = MagicMock()
        cog = MagicMock()
        loader = AsyncMock(return_value={"Zeta": {}, "Alpha": {}})
        view = OptionsView(user, loader, "monster", data_key=None, flatten_pulp=False, cog=cog, title="Monsters")
        interaction = make_interaction(user=user)

        await view.list_button.callback(interaction)

        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        sub_view = kwargs["view"]
        assert isinstance(sub_view, PaginatedListView)
        assert sub_view.items == ["Alpha", "Zeta"]

    @pytest.mark.asyncio
    async def test_list_button_rejects_non_owner(self):
        user = MagicMock()
        loader = AsyncMock(return_value={})
        view = OptionsView(user, loader, "monster", None, False, MagicMock(), "Monsters")
        interaction = make_interaction(user=MagicMock())

        await view.list_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("This isn't for you!", ephemeral=True)
        loader.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_random_button_shows_entry(self):
        user = MagicMock()
        cog = MagicMock()
        cog._get_entry_data = MagicMock(return_value={"name": "Nyarlathotep"})
        cog._display_entry = AsyncMock()
        loader = AsyncMock(return_value={"Nyarlathotep": {}})
        view = OptionsView(user, loader, "deity", None, False, cog, "Deities")
        interaction = make_interaction(user=user)

        await view.random_button.callback(interaction)

        cog._display_entry.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_random_button_no_entries_edits_error(self):
        user = MagicMock()
        loader = AsyncMock(return_value={})
        view = OptionsView(user, loader, "deity", None, False, MagicMock(), "Deities")
        interaction = make_interaction(user=user)

        await view.random_button.callback(interaction)

        interaction.edit_original_response.assert_awaited_once_with(content="No entries found.", embed=None, view=None)

    @pytest.mark.asyncio
    async def test_cancel_button_dismisses_and_stops(self):
        user = MagicMock()
        view = OptionsView(user, AsyncMock(), "deity", None, False, MagicMock(), "Deities")
        interaction = make_interaction(user=user)

        await view.cancel_button.callback(interaction)

        interaction.response.edit_message.assert_awaited_once_with(content="Dismissed.", embed=None, view=None)
        assert view.is_finished()


class TestRenderView:
    def test_weapon_type_adds_inventory_button(self):
        view = RenderView(MagicMock(), MagicMock(), "Revolver", "weapon")
        assert any(getattr(c, "label", None) == "Add to Inventory" for c in view.children)

    def test_monster_type_adds_origin_button(self):
        view = RenderView(MagicMock(), MagicMock(), "Nyarlathotep", "monster")
        assert any(getattr(c, "label", None) == "📜 View Origin" for c in view.children)

    def test_occupation_type_has_no_extra_buttons(self):
        view = RenderView(MagicMock(), MagicMock(), "Detective", "occupation")
        labels = {getattr(c, "label", None) for c in view.children}
        assert "Add to Inventory" not in labels
        assert "📜 View Origin" not in labels

    @pytest.mark.asyncio
    async def test_poster_button_calls_cog_render_poster(self):
        user = MagicMock()
        cog = MagicMock()
        cog._render_poster = AsyncMock()
        view = RenderView(user, cog, "Nyarlathotep", "monster")
        interaction = make_interaction(user=user)

        await view.poster_button.callback(interaction)

        cog._render_poster.assert_awaited_once()
        assert cog._render_poster.call_args.args[2] == "Nyarlathotep"

    @pytest.mark.asyncio
    async def test_add_to_inventory_requires_guild(self):
        view = RenderView(MagicMock(), MagicMock(), "Revolver", "weapon")
        interaction = make_interaction()
        interaction.guild = None

        await view.add_to_inventory_button(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "only be performed in a server" in interaction.response.send_message.call_args.args[0]

    @pytest.mark.asyncio
    async def test_add_to_inventory_appends_item_to_backstory(self):
        view = RenderView(MagicMock(), MagicMock(), "Revolver", "weapon")
        interaction = make_interaction()
        interaction.guild = MagicMock(id=111)
        interaction.user.id = 222

        player_stats = {"111": {"222": {"NAME": "Jane"}}}
        with patch("commands._codex_views.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._codex_views.save_player_stats", new=AsyncMock()) as mock_save:
            await view.add_to_inventory_button(interaction)

        assert "Revolver" in player_stats["111"]["222"]["Backstory"]["Gear and Possessions"]
        mock_save.assert_awaited_once_with(player_stats)
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_to_inventory_requires_existing_investigator(self):
        view = RenderView(MagicMock(), MagicMock(), "Revolver", "weapon")
        interaction = make_interaction()
        interaction.guild = MagicMock(id=111)
        interaction.user.id = 999

        with patch("commands._codex_views.load_player_stats", new=AsyncMock(return_value={})):
            await view.add_to_inventory_button(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "don't have an investigator" in interaction.response.send_message.call_args.args[0]


class TestCodexView:
    @pytest.mark.asyncio
    async def test_check_owner_rejects_non_owner(self):
        owner = MagicMock()
        view = CodexView(owner, MagicMock())
        interaction = make_interaction(user=MagicMock())

        result = await view._check_owner(interaction)

        assert result is False
        interaction.response.send_message.assert_awaited_once_with("This menu isn't for you.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_monsters_button_launches_list_with_loaded_data(self):
        owner = MagicMock()
        cog = MagicMock()
        view = CodexView(owner, cog)
        interaction = make_interaction(user=owner)

        monsters_data = {"monsters": [{"monster_entry": {"name": "Shoggoth"}}]}
        with patch("commands._codex_views.load_monsters_data", new=AsyncMock(return_value=monsters_data)):
            await view.monsters_button.callback(interaction)

        interaction.response.edit_message.assert_awaited_once()
        interaction.edit_original_response.assert_awaited_once()
        _, kwargs = interaction.edit_original_response.call_args
        assert kwargs["view"].items == ["Shoggoth"]

    @pytest.mark.asyncio
    async def test_talents_button_flattens_pulp_talent_names(self):
        owner = MagicMock()
        cog = MagicMock()
        view = CodexView(owner, cog)
        interaction = make_interaction(user=owner)

        talents_data = {"mundane": ["**Fast Talker**: desc"]}
        with patch("commands._codex_views.load_pulp_talents_data", new=AsyncMock(return_value=talents_data)):
            await view.talents_button.callback(interaction)

        _, kwargs = interaction.edit_original_response.call_args
        assert kwargs["view"].items == ["Fast Talker"]

    @pytest.mark.asyncio
    async def test_launch_list_no_choices_shows_error_embed(self):
        owner = MagicMock()
        cog = MagicMock()
        view = CodexView(owner, cog)
        interaction = make_interaction(user=owner)

        with patch("commands._codex_views.load_monsters_data", new=AsyncMock(return_value={"monsters": []})):
            await view.monsters_button.callback(interaction)

        interaction.edit_original_response.assert_awaited_once()
        _, kwargs = interaction.edit_original_response.call_args
        assert kwargs["embed"].title == "No entries found"

    @pytest.mark.asyncio
    async def test_on_timeout_deletes_message(self):
        view = CodexView(MagicMock(), MagicMock())
        view.message = MagicMock()
        view.message.delete = AsyncMock()

        await view.on_timeout()

        view.message.delete.assert_awaited_once()


class TestSelectionView:
    def test_options_indexed_by_position_to_avoid_length_limit(self):
        options = ["Alpha", "Beta"]
        view = SelectionView(MagicMock(), options, "monster", AsyncMock(), MagicMock())
        select = view.children[0]
        assert [o.value for o in select.options] == ["0", "1"]

    @pytest.mark.asyncio
    async def test_select_callback_resolves_index_and_displays_entry(self):
        user = MagicMock()
        cog = MagicMock()
        cog._get_entry_data = MagicMock(return_value={"name": "Beta"})
        cog._display_entry = AsyncMock()
        loader = AsyncMock(return_value={"k": 1})
        view = SelectionView(user, ["Alpha", "Beta"], "monster", loader, cog)
        interaction = make_interaction(user=user)
        interaction.data = {"values": ["1"]}

        await view.select_callback(interaction)

        cog._display_entry.assert_awaited_once_with(interaction, "Beta", "monster", {"name": "Beta"}, ephemeral=True)
        assert all(c.disabled for c in view.children)

    @pytest.mark.asyncio
    async def test_select_callback_rejects_non_owner(self):
        owner = MagicMock()
        view = SelectionView(owner, ["Alpha"], "monster", AsyncMock(), MagicMock())
        interaction = make_interaction(user=MagicMock())
        interaction.data = {"values": ["0"]}

        await view.select_callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("This selection is not for you.", ephemeral=True)
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_codex_views.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_codex_views.py
git commit -m "test: add coverage for commands/_codex_views.py"
```

---

### Task 30: Add tests for commands/_journal_views.py

**Files:**
- Create: `tests/test_commands_journal_views.py`

**Interfaces:**
- Consumes: `JournalEntryModal.on_submit`, `DeleteConfirmationView.confirm`/`.cancel`, `ImageManageView.select_callback`, `DeleteImageConfirmationView.confirm`, `JournalView.__init__`/`.load_entries`/`.get_embed`/`.prev_button`/`.next_button`/`.add_entry_button`/`.edit_button`/`.delete_button`/`._update_buttons`/`.switch_button`, `ClueTargetSelect.callback`, `ClueDestinationView.personal`/`.master`/`.give` (all from `commands/_journal_views.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._journal_views import (
    JournalEntryModal,
    DeleteConfirmationView,
    ImageManageView,
    DeleteImageConfirmationView,
    JournalView,
    ClueTargetSelect,
    ClueDestinationView,
)


def make_interaction(user=None, guild_id=111, admin=False):
    interaction = MagicMock()
    interaction.user = user or MagicMock(id=222)
    interaction.guild_id = guild_id
    interaction.permissions = MagicMock(administrator=admin)
    interaction.user.guild_permissions = MagicMock(administrator=admin)
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup.send = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


class TestJournalEntryModal:
    @pytest.mark.asyncio
    async def test_personal_new_entry_is_appended_and_parent_refreshed(self):
        parent_view = MagicMock()
        parent_view.external_refresh = AsyncMock()
        modal = JournalEntryModal(MagicMock(), mode="personal", parent_view=parent_view)
        modal.entry_title._value = "Day One"
        modal.entry_content._value = "We arrived in Arkham."

        interaction = make_interaction(guild_id=111)
        journal_data = {}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)), \
             patch("commands._journal_views.save_journal_data", new=AsyncMock()) as mock_save:
            await modal.on_submit(interaction)

        entries = journal_data["111"]["personal"]["222"]["entries"]
        assert len(entries) == 1
        assert entries[0]["title"] == "Day One"
        assert entries[0]["content"] == "We arrived in Arkham."
        mock_save.assert_awaited_once()
        parent_view.external_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_master_mode_requires_admin_permissions(self):
        modal = JournalEntryModal(MagicMock(), mode="master")
        modal.entry_title._value = "GM note"
        modal.entry_content._value = "Something lurks."

        interaction = make_interaction(admin=False)
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value={})):
            await modal.on_submit(interaction)

        interaction.followup.send.assert_awaited_once()
        assert "Only Game Masters" in interaction.followup.send.call_args.args[0]

    @pytest.mark.asyncio
    async def test_editing_existing_entry_preserves_timestamp_and_author(self):
        original_entry = {"title": "Old", "content": "Old content", "author_id": "999", "timestamp": 123.0, "images": []}
        modal = JournalEntryModal(MagicMock(), mode="personal", entry_index=0, original_entry=original_entry)
        modal.entry_title._value = "New Title"
        modal.entry_content._value = "New content"

        interaction = make_interaction(guild_id=111)
        journal_data = {"111": {"personal": {"222": {"entries": [dict(original_entry)]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)), \
             patch("commands._journal_views.save_journal_data", new=AsyncMock()):
            await modal.on_submit(interaction)

        updated = journal_data["111"]["personal"]["222"]["entries"][0]
        assert updated["title"] == "New Title"
        assert updated["author_id"] == "999"
        assert updated["timestamp"] == 123.0

    @pytest.mark.asyncio
    async def test_inspect_mode_requires_admin(self):
        modal = JournalEntryModal(MagicMock(), mode="inspect", target_user_id="555")
        modal.entry_title._value = "Clue"
        modal.entry_content._value = "A note"

        interaction = make_interaction(admin=False)
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value={})):
            await modal.on_submit(interaction)

        interaction.followup.send.assert_awaited_once()
        assert "Only Game Masters" in interaction.followup.send.call_args.args[0]


class TestDeleteConfirmationView:
    @pytest.mark.asyncio
    async def test_confirm_removes_personal_entry_and_refreshes(self):
        parent_view = MagicMock()
        parent_view.external_refresh = AsyncMock()
        view = DeleteConfirmationView("personal", "222", entry_index=0, parent_view=parent_view)
        interaction = make_interaction(guild_id=111)

        journal_data = {"111": {"personal": {"222": {"entries": [{"title": "A"}]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)), \
             patch("commands._journal_views.save_journal_data", new=AsyncMock()) as mock_save:
            await view.confirm.callback(interaction)

        assert journal_data["111"]["personal"]["222"]["entries"] == []
        mock_save.assert_awaited_once()
        parent_view.external_refresh.assert_awaited_once()
        assert view.is_finished()

    @pytest.mark.asyncio
    async def test_confirm_reports_error_when_entry_not_found(self):
        view = DeleteConfirmationView("master", None, entry_index=5, parent_view=MagicMock())
        interaction = make_interaction()

        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value={})):
            await view.confirm.callback(interaction)

        interaction.followup.send.assert_awaited_once()
        assert "Could not find entry" in interaction.followup.send.call_args.args[0]

    @pytest.mark.asyncio
    async def test_cancel_sends_message_and_stops(self):
        view = DeleteConfirmationView("personal", "222", 0, MagicMock())
        interaction = make_interaction()

        await view.cancel.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("❌ Deletion cancelled.", ephemeral=True)
        assert view.is_finished()


class TestImageManageView:
    @pytest.mark.asyncio
    async def test_select_callback_removes_chosen_image(self):
        parent_view = MagicMock()
        parent_view.external_refresh = AsyncMock()
        view = ImageManageView("personal", "222", entry_index=0, images=["a.png", "b.png"], parent_view=parent_view)
        view.select_menu._values = ["1"]
        interaction = make_interaction(guild_id=111)

        journal_data = {"111": {"personal": {"222": {"entries": [{"images": ["a.png", "b.png"]}]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)), \
             patch("commands._journal_views.save_journal_data", new=AsyncMock()) as mock_save, \
             patch("commands._journal_views.os.path.exists", return_value=False):
            await view.select_callback(interaction)

        assert journal_data["111"]["personal"]["222"]["entries"][0]["images"] == ["a.png"]
        mock_save.assert_awaited_once()
        parent_view.external_refresh.assert_awaited_once()


class TestDeleteImageConfirmationView:
    @pytest.mark.asyncio
    async def test_confirm_removes_named_image(self):
        parent_view = MagicMock()
        parent_view.external_refresh = AsyncMock()
        view = DeleteImageConfirmationView("master", None, entry_index=0, image_filename="a.png", parent_view=parent_view)
        interaction = make_interaction(guild_id=111)

        journal_data = {"111": {"master": {"entries": [{"images": ["a.png"]}]}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)), \
             patch("commands._journal_views.save_journal_data", new=AsyncMock()) as mock_save, \
             patch("commands._journal_views.os.path.exists", return_value=False):
            await view.confirm.callback(interaction)

        assert journal_data["111"]["master"]["entries"][0]["images"] == []
        mock_save.assert_awaited_once()
        parent_view.external_refresh.assert_awaited_once()


class TestJournalView:
    @pytest.mark.asyncio
    async def test_load_entries_personal_mode(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")

        journal_data = {"111": {"personal": {"222": {"entries": [{"title": "A"}]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)):
            entries = await view.load_entries()

        assert entries == [{"title": "A"}]

    @pytest.mark.asyncio
    async def test_get_embed_empty_journal(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")

        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value={})):
            embed = await view.get_embed()

        assert "empty" in embed.description

    @pytest.mark.asyncio
    async def test_prev_next_buttons_change_page(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")
        view.message = MagicMock()

        journal_data = {"111": {"personal": {"222": {"entries": [{"title": "A", "timestamp": 1}, {"title": "B", "timestamp": 2}]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)):
            await view.next_button.callback(interaction)
            assert view.current_page == 1
            await view.prev_button.callback(interaction)
            assert view.current_page == 0

    @pytest.mark.asyncio
    async def test_add_entry_button_opens_modal(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")

        await view.add_entry_button.callback(interaction)

        interaction.response.send_modal.assert_awaited_once() if hasattr(interaction.response, "send_modal") else None

    @pytest.mark.asyncio
    async def test_add_entry_button_blocked_for_inspect_non_admin(self):
        interaction = make_interaction(guild_id=111, admin=False)
        view = JournalView(MagicMock(), interaction, mode="inspect", target_user_id="999")
        interaction.response.send_modal = AsyncMock()

        await view.add_entry_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "cannot write" in interaction.response.send_message.call_args.args[0]
        interaction.response.send_modal.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_button_opens_confirmation_with_real_index(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")
        view.current_page = 0

        journal_data = {"111": {"personal": {"222": {"entries": [{"title": "A"}, {"title": "B"}]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)):
            await view.delete_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        confirm_view = kwargs["view"]
        assert isinstance(confirm_view, DeleteConfirmationView)
        # newest-first display means page 0 (newest = "B") maps to real_index 1
        assert confirm_view.entry_index == 1

    def test_update_buttons_switch_label_toggles_by_mode(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")
        view._update_buttons([])
        assert view.switch_button.label == "Switch to Master Journal"

        view.mode = "master"
        view._update_buttons([])
        assert view.switch_button.label == "Switch to Personal Journal"

    def test_update_buttons_disables_edit_delete_without_entries(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")
        view._update_buttons([])
        assert view.edit_button.disabled is True
        assert view.delete_button.disabled is True

    @pytest.mark.asyncio
    async def test_switch_button_denies_master_access_without_permission(self):
        interaction = make_interaction(guild_id=111, admin=False)
        view = JournalView(MagicMock(), interaction, mode="personal")

        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value={"111": {"master": {"access": []}}})):
            await view.switch_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "do not have access" in interaction.response.send_message.call_args.args[0]
        assert view.mode == "personal"


class TestClueTargetSelectAndDestinationView:
    @pytest.mark.asyncio
    async def test_clue_target_select_opens_inspect_modal_for_target(self):
        target_user = MagicMock(id=777)
        select = ClueTargetSelect(MagicMock(), original_entry={"title": "Clue"}, image_attachments=[])
        select._values = [target_user]
        interaction = make_interaction()

        await select.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.call_args.args[0]
        assert modal.mode == "inspect"
        assert modal.target_user_id == "777"

    @pytest.mark.asyncio
    async def test_give_button_swaps_view_to_user_select(self):
        view = ClueDestinationView(MagicMock(), original_entry={"title": "Clue"}, image_attachments=[])
        interaction = make_interaction()

        await view.give.callback(interaction)

        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        assert any(isinstance(c, ClueTargetSelect) for c in kwargs["view"].children)

    @pytest.mark.asyncio
    async def test_personal_button_opens_modal_and_stops(self):
        view = ClueDestinationView(MagicMock(), original_entry={"title": "Clue"}, image_attachments=[])
        interaction = make_interaction()

        await view.personal.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], JournalEntryModal)
        assert view.is_finished()
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_journal_views.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_journal_views.py
git commit -m "test: add coverage for commands/_journal_views.py"
```

---

### Task 31: Add tests for commands/_karma_views.py

**Files:**
- Create: `tests/test_commands_karma_views.py`

**Interfaces:**
- Consumes: `KarmaActionsView` (existence/shape only — known dead code), `KarmaRoleSetupMainView.add_role`/`.remove_role`/`.list_roles`, `KarmaRoleSelectView.select_role`, `KarmaThresholdModal.on_submit`, `KarmaRoleRemoveView`/`KarmaRoleRemoveSelect.callback`, `LeaderboardView.get_embed`/`.previous_page`/`.next_page`/`.interaction_check`, `KarmaSetupChannelView.select_channel`, `KarmaSetupEmojiModal.on_submit`, `KarmaSetupNotifyView.finish_setup`/`.skip` (all from `commands/_karma_views.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._karma_views import (
    KarmaActionsView,
    KarmaRoleSetupMainView,
    KarmaRoleSelectView,
    KarmaThresholdModal,
    KarmaRoleRemoveView,
    KarmaRoleRemoveSelect,
    LeaderboardView,
    KarmaSetupChannelView,
    KarmaSetupEmojiModal,
    KarmaSetupNotifyView,
)


def make_interaction(user=None, guild_id=111):
    interaction = MagicMock()
    interaction.user = user or MagicMock(id=222)
    interaction.guild_id = guild_id
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    return interaction


class TestKarmaActionsView:
    def test_dead_code_shape_only(self):
        # KarmaActionsView is confirmed dead code (never instantiated by production callers).
        # We only verify it still constructs and exposes its two documented buttons, so a
        # future accidental deletion/behavior change is caught without over-investing here.
        view = KarmaActionsView(MagicMock(), MagicMock())
        labels = {c.label for c in view.children}
        assert labels == {"Check Karma", "View Rank Card"}


class TestKarmaRoleSetupMainView:
    @pytest.mark.asyncio
    async def test_add_role_opens_role_select_view(self):
        user = MagicMock()
        view = KarmaRoleSetupMainView(MagicMock(), user)
        interaction = make_interaction(user=user)

        await view.add_role.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], KarmaRoleSelectView)

    @pytest.mark.asyncio
    async def test_remove_role_with_no_roles_configured(self):
        user = MagicMock()
        view = KarmaRoleSetupMainView(MagicMock(), user)
        interaction = make_interaction(user=user)

        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value={})):
            await view.remove_role.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("No roles configured yet.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_remove_role_shows_select_when_roles_exist(self):
        user = MagicMock()
        view = KarmaRoleSetupMainView(MagicMock(), user)
        interaction = make_interaction(user=user, guild_id=111)
        interaction.guild = MagicMock()
        interaction.guild.get_role = MagicMock(return_value=MagicMock(name="Cultist"))

        settings = {"111": {"roles": {"10": "555"}}}
        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value=settings)):
            await view.remove_role.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], KarmaRoleRemoveView)

    @pytest.mark.asyncio
    async def test_interaction_check_only_allows_owning_user(self):
        user = MagicMock(id=1)
        view = KarmaRoleSetupMainView(MagicMock(), user)
        interaction = make_interaction(user=MagicMock(id=2))

        assert await view.interaction_check(interaction) is False


class TestKarmaThresholdModal:
    @pytest.mark.asyncio
    async def test_valid_amount_saves_role_threshold(self):
        role = MagicMock(id=555, name="Cultist")
        bot = MagicMock()
        bot.get_cog = MagicMock(return_value=None)
        modal = KarmaThresholdModal(role, bot)
        modal.amount.component._value = "25"

        interaction = make_interaction(guild_id=111)
        settings = {}
        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value=settings)), \
             patch("commands._karma_views.save_karma_settings", new=AsyncMock()) as mock_save:
            await modal.on_submit(interaction)

        assert settings["111"]["roles"]["25"] == 555
        mock_save.assert_awaited_once_with(settings)
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_amount_rejected(self):
        role = MagicMock(id=555)
        modal = KarmaThresholdModal(role, MagicMock())
        modal.amount.component._value = "not-a-number"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "❌ Invalid number. Please enter a valid integer.", ephemeral=True
        )


class TestKarmaRoleRemoveSelect:
    @pytest.mark.asyncio
    async def test_callback_removes_threshold_from_settings(self):
        guild = MagicMock()
        guild.get_role = MagicMock(return_value=MagicMock(name="Cultist"))
        bot = MagicMock()
        bot.get_cog = MagicMock(return_value=None)
        view = KarmaRoleRemoveView(bot, MagicMock(), {"10": "555"}, guild)
        select = view.children[0]
        assert isinstance(select, KarmaRoleRemoveSelect)
        select._values = ["10"]

        interaction = make_interaction(guild_id=111)
        settings = {"111": {"roles": {"10": "555"}}}
        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value=settings)), \
             patch("commands._karma_views.save_karma_settings", new=AsyncMock()) as mock_save:
            await select.callback(interaction)

        assert "10" not in settings["111"]["roles"]
        mock_save.assert_awaited_once()
        interaction.response.send_message.assert_awaited_once()
        assert "Removed threshold" in interaction.response.send_message.call_args.args[0]

    @pytest.mark.asyncio
    async def test_callback_reports_error_if_threshold_missing(self):
        guild = MagicMock()
        view = KarmaRoleRemoveView(MagicMock(), MagicMock(), {"10": "555"}, guild)
        select = view.children[0]
        select._values = ["10"]

        interaction = make_interaction(guild_id=111)
        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value={})):
            await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("❌ Error finding threshold.", ephemeral=True)


class TestLeaderboardView:
    def test_pagination_bounds(self):
        interaction = make_interaction()
        users = [(str(i), 100 - i) for i in range(25)]
        view = LeaderboardView(interaction, users, items_per_page=10)

        assert view.total_pages == 3
        assert view.previous_page.disabled is True
        assert view.next_page.disabled is False

    @pytest.mark.asyncio
    async def test_next_page_advances_and_updates_buttons(self):
        interaction = make_interaction()
        interaction.guild = MagicMock()
        interaction.guild.get_member = MagicMock(return_value=MagicMock(display_name="Jane"))
        users = [(str(i), 100 - i) for i in range(15)]
        view = LeaderboardView(interaction, users, items_per_page=10)

        await view.next_page.callback(interaction)

        assert view.current_page == 2
        assert view.next_page.disabled is True
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_other_users(self):
        owner_interaction = make_interaction(user=MagicMock(id=1))
        view = LeaderboardView(owner_interaction, [("1", 10)])
        other = make_interaction(user=MagicMock(id=2))

        assert await view.interaction_check(other) is False
        other.response.send_message.assert_awaited_once_with("This isn't your leaderboard!", ephemeral=True)


class TestKarmaSetupFlow:
    @pytest.mark.asyncio
    async def test_channel_select_opens_emoji_modal(self):
        user = MagicMock()
        view = KarmaSetupChannelView(MagicMock(), user)
        channel = MagicMock(id=333)
        view.select_channel._values = [channel]
        interaction = make_interaction(user=user)

        await view.select_channel.callback(interaction)

        assert view.channel_id == 333
        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], KarmaSetupEmojiModal)

    @pytest.mark.asyncio
    async def test_emoji_modal_submits_to_notify_view(self):
        modal = KarmaSetupEmojiModal(MagicMock(), MagicMock(), channel_id=333)
        modal.upvote.component._value = "👍"
        modal.downvote.component._value = "👎"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        notify_view = kwargs["view"]
        assert isinstance(notify_view, KarmaSetupNotifyView)
        assert notify_view.data == {"channel_id": 333, "upvote_emoji": "👍", "downvote_emoji": "👎"}

    @pytest.mark.asyncio
    async def test_finish_setup_preserves_existing_roles(self):
        view = KarmaSetupNotifyView(MagicMock(), MagicMock(), channel_id=333, up="👍", down="👎")
        interaction = make_interaction(guild_id=111)

        settings = {"111": {"roles": {"10": "555"}}}
        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value=settings)), \
             patch("commands._karma_views.save_karma_settings", new=AsyncMock()) as mock_save:
            await view.finish_setup(interaction, notify_id=999)

        saved = mock_save.call_args.args[0]
        assert saved["111"]["roles"] == {"10": "555"}
        assert saved["111"]["notification_channel_id"] == 999
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_button_finishes_with_no_notification_channel(self):
        view = KarmaSetupNotifyView(MagicMock(), MagicMock(), channel_id=333, up="👍", down="👎")
        interaction = make_interaction(guild_id=111)

        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value={})), \
             patch("commands._karma_views.save_karma_settings", new=AsyncMock()) as mock_save:
            await view.skip.callback(interaction)

        saved = mock_save.call_args.args[0]
        assert saved["111"]["notification_channel_id"] is None
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_karma_views.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_karma_views.py
git commit -m "test: add coverage for commands/_karma_views.py"
```

---

### Task 32: Add tests for commands/_mychar_inventory.py

**Files:**
- Create: `tests/test_commands_mychar_inventory.py`

**Interfaces:**
- Consumes: `AddItemModal.on_submit`, `EditItemModal.on_submit`, `GiveUserSelect.callback`, `ItemActionsView.__init__`/`.show_item`/`.edit`/`.discard`/`.cancel`, `InventorySelect.__init__`/`.callback` (all from `commands/_mychar_inventory.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._mychar_inventory import (
    AddItemModal,
    EditItemModal,
    GiveUserSelect,
    ItemActionsView,
    InventorySelect,
)


def make_interaction(user=None, guild_id=111):
    interaction = MagicMock()
    interaction.user = user or MagicMock(id=222)
    interaction.guild_id = guild_id
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.delete_original_response = AsyncMock()
    return interaction


def make_dashboard_view(**overrides):
    view = MagicMock()
    view.server_id = overrides.get("server_id", "111")
    view.owner_id = overrides.get("owner_id", "222")
    view.char_data = overrides.get("char_data", {})
    view.can_edit = overrides.get("can_edit", True)
    view.refresh_dashboard = AsyncMock()
    view.user = overrides.get("user", MagicMock())
    view.inventory_page = 0
    view.update_components = MagicMock()
    view.launch_item_actions = AsyncMock()
    return view


class TestAddItemModal:
    @pytest.mark.asyncio
    async def test_adds_item_with_details_to_gear_and_possessions(self):
        view = make_dashboard_view(char_data={})
        modal = AddItemModal(view)
        modal.item_name._value = "Flashlight"
        modal.details._value = "1x"

        interaction = make_interaction()
        player_stats = {}
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._mychar_inventory.save_player_stats", new=AsyncMock()) as mock_save:
            await modal.on_submit(interaction)

        assert view.char_data["Backstory"]["Gear and Possessions"] == ["Flashlight 1x"]
        mock_save.assert_awaited_once()
        view.refresh_dashboard.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_creates_server_entry_if_missing(self):
        view = make_dashboard_view(char_data={})
        modal = AddItemModal(view)
        modal.item_name._value = "Revolver"
        modal.details._value = ""

        interaction = make_interaction()
        player_stats = {}
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._mychar_inventory.save_player_stats", new=AsyncMock()):
            await modal.on_submit(interaction)

        assert "111" in player_stats
        assert player_stats["111"]["222"] is view.char_data


class TestEditItemModal:
    @pytest.mark.asyncio
    async def test_updates_item_at_index(self):
        char_data = {"Backstory": {"Gear and Possessions": ["Old Item"]}}
        view = make_dashboard_view(char_data=char_data)
        modal = EditItemModal(view, "Gear and Possessions", 0, "Old Item")
        modal.item_input._value = "New Item"

        interaction = make_interaction()
        player_stats = {"111": {"222": {}}}
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._mychar_inventory.save_player_stats", new=AsyncMock()) as mock_save:
            await modal.on_submit(interaction)

        assert char_data["Backstory"]["Gear and Possessions"][0] == "New Item"
        mock_save.assert_awaited_once()
        view.refresh_dashboard.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_out_of_bounds_index_reports_error(self):
        char_data = {"Backstory": {"Gear and Possessions": ["Only Item"]}}
        view = make_dashboard_view(char_data=char_data)
        modal = EditItemModal(view, "Gear and Possessions", 5, "Only Item")
        modal.item_input._value = "New text"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once_with("Error: Item index out of bounds.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_missing_category_reports_error(self):
        char_data = {"Backstory": {}}
        view = make_dashboard_view(char_data=char_data)
        modal = EditItemModal(view, "Unknown Category", 0, "text")
        modal.item_input._value = "New text"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once_with("Error: Category not found.", ephemeral=True)


class TestGiveUserSelect:
    @pytest.mark.asyncio
    async def test_transfers_item_from_sender_to_target(self):
        dashboard_view = make_dashboard_view(server_id="111", owner_id="222", char_data={"Backstory": {"Gear and Possessions": ["Revolver"]}})
        action_view = MagicMock(dashboard_view=dashboard_view)
        action_view.stop = MagicMock()
        select = GiveUserSelect(action_view, "Gear and Possessions", "Revolver", 0)
        target_user = MagicMock(id=999, bot=False)
        target_user.display_name = "Bob"
        select._values = [target_user]

        interaction = make_interaction(guild_id=111)
        player_stats = {
            "111": {
                "222": {"Backstory": {"Gear and Possessions": ["Revolver"]}},
                "999": {},
            }
        }
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._mychar_inventory.save_player_stats", new=AsyncMock()) as mock_save:
            await select.callback(interaction)

        assert player_stats["111"]["222"]["Backstory"]["Gear and Possessions"] == []
        assert player_stats["111"]["999"]["Backstory"]["Gear and Possessions"] == ["Revolver"]
        assert dashboard_view.char_data["Backstory"]["Gear and Possessions"] == []
        mock_save.assert_awaited_once()
        dashboard_view.refresh_dashboard.assert_awaited_once_with(interaction)
        action_view.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_cannot_give_to_self(self):
        dashboard_view = make_dashboard_view(owner_id="222")
        action_view = MagicMock(dashboard_view=dashboard_view)
        select = GiveUserSelect(action_view, "Gear and Possessions", "Revolver", 0)
        target_user = MagicMock(id=222, bot=False)
        select._values = [target_user]

        interaction = make_interaction()
        await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("You cannot give items to yourself.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_cannot_give_to_bot(self):
        dashboard_view = make_dashboard_view(owner_id="222")
        action_view = MagicMock(dashboard_view=dashboard_view)
        select = GiveUserSelect(action_view, "Gear and Possessions", "Revolver", 0)
        target_user = MagicMock(id=999, bot=True)
        select._values = [target_user]

        interaction = make_interaction()
        await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("You cannot give items to bots.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_target_without_investigator_rejected(self):
        dashboard_view = make_dashboard_view(owner_id="222")
        action_view = MagicMock(dashboard_view=dashboard_view)
        select = GiveUserSelect(action_view, "Gear and Possessions", "Revolver", 0)
        target_user = MagicMock(id=999, bot=False)
        target_user.display_name = "Bob"
        select._values = [target_user]

        interaction = make_interaction(guild_id=111)
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value={"111": {}})):
            await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "does not have an active investigator" in interaction.response.send_message.call_args.args[0]


class TestItemActionsView:
    def test_give_select_only_added_when_can_edit(self):
        dashboard_view = make_dashboard_view(can_edit=True)
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        assert any(isinstance(c, GiveUserSelect) for c in view.children)

        dashboard_view2 = make_dashboard_view(can_edit=False)
        view2 = ItemActionsView(dashboard_view2, "Gear and Possessions", "Revolver", 0)
        assert not any(isinstance(c, GiveUserSelect) for c in view2.children)

    @pytest.mark.asyncio
    async def test_show_item_sends_to_channel(self):
        dashboard_view = make_dashboard_view()
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        interaction = make_interaction()
        interaction.channel.send = AsyncMock()

        await view.show_item.callback(interaction)

        interaction.channel.send.assert_awaited_once()
        interaction.response.send_message.assert_awaited_once_with("✅ Item shown to chat.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_edit_denied_without_permission(self):
        dashboard_view = make_dashboard_view(can_edit=False)
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        interaction = make_interaction()

        await view.edit.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("You cannot edit this.", ephemeral=True)
        interaction.response.send_modal.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_edit_opens_modal_and_stops(self):
        dashboard_view = make_dashboard_view(can_edit=True)
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        interaction = make_interaction()

        await view.edit.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert view.is_finished()

    @pytest.mark.asyncio
    async def test_discard_removes_item_from_both_stats_and_local_view(self):
        char_data = {"Backstory": {"Gear and Possessions": ["Revolver"]}}
        dashboard_view = make_dashboard_view(can_edit=True, char_data=char_data, owner_id="222")
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        interaction = make_interaction(guild_id=111)

        player_stats = {"111": {"222": {"Backstory": {"Gear and Possessions": ["Revolver"]}}}}
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._mychar_inventory.save_player_stats", new=AsyncMock()) as mock_save:
            await view.discard.callback(interaction)

        assert player_stats["111"]["222"]["Backstory"]["Gear and Possessions"] == []
        assert char_data["Backstory"]["Gear and Possessions"] == []
        mock_save.assert_awaited_once()
        dashboard_view.refresh_dashboard.assert_awaited_once_with(interaction)
        assert view.is_finished()

    @pytest.mark.asyncio
    async def test_cancel_deletes_ephemeral_message_and_stops(self):
        dashboard_view = make_dashboard_view()
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        interaction = make_interaction()

        await view.cancel.callback(interaction)

        interaction.response.defer.assert_awaited_once()
        interaction.delete_original_response.assert_awaited_once()
        assert view.is_finished()


class TestInventorySelect:
    def test_adds_pagination_options_when_more_items_exist(self):
        dashboard_view = make_dashboard_view()
        items = [("Gear and Possessions", f"Item {i}") for i in range(30)]
        select = InventorySelect(dashboard_view, items, page=0)

        values = [o.value for o in select.options]
        assert "next_page" in values
        assert "prev_page" not in values
        assert len(select.options) == 25  # 24 items + next_page marker

    @pytest.mark.asyncio
    async def test_selecting_next_page_advances_dashboard(self):
        dashboard_view = make_dashboard_view()
        items = [("Gear and Possessions", f"Item {i}") for i in range(30)]
        select = InventorySelect(dashboard_view, items, page=0)
        select._values = ["next_page"]
        interaction = make_interaction()
        interaction.user = dashboard_view.user

        await select.callback(interaction)

        assert dashboard_view.inventory_page == 1
        dashboard_view.update_components.assert_called_once()

    @pytest.mark.asyncio
    async def test_selecting_item_launches_item_actions(self):
        dashboard_view = make_dashboard_view()
        items = [("Gear and Possessions", "Revolver")]
        select = InventorySelect(dashboard_view, items, page=0)
        select._values = ["0"]
        interaction = make_interaction()
        interaction.user = dashboard_view.user

        await select.callback(interaction)

        dashboard_view.launch_item_actions.assert_awaited_once_with(interaction, "Gear and Possessions", "Revolver", 0)

    @pytest.mark.asyncio
    async def test_non_owner_rejected(self):
        dashboard_view = make_dashboard_view()
        items = [("Gear and Possessions", "Revolver")]
        select = InventorySelect(dashboard_view, items, page=0)
        select._values = ["0"]
        interaction = make_interaction(user=MagicMock())

        await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Not your dashboard!", ephemeral=True)
        dashboard_view.launch_item_actions.assert_not_awaited()
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_mychar_inventory.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_mychar_inventory.py
git commit -m "test: add coverage for commands/_mychar_inventory.py"
```

---

### Task 33: Add tests for commands/_mychar_roll.py (incl. back-navigation closures)

**Files:**
- Create: `tests/test_commands_mychar_roll.py`

**Interfaces:**
- Consumes: `SkillSearchModal.on_submit`, `SkillRollSelect.__init__`/`.callback` (all from `commands/_mychar_roll.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._mychar_roll import SkillSearchModal, SkillRollSelect
from commands._roll_views import RollResultView


def make_interaction(user=None):
    interaction = MagicMock()
    interaction.user = user or MagicMock(id=222)
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    return interaction


def make_dashboard_view(**overrides):
    view = MagicMock()
    view.server_id = overrides.get("server_id", "111")
    view.owner_id = overrides.get("owner_id", "222")
    view.char_data = overrides.get("char_data", {"Spot Hidden": 50, "Listen": 40})
    view.refresh_dashboard = AsyncMock()
    view._get_skill_list = MagicMock(return_value=list(view.char_data.items()))
    view._get_skill_emoji = MagicMock(return_value=None)
    return view


class TestSkillSearchModal:
    @pytest.mark.asyncio
    async def test_exact_substring_match_wins_over_fuzzy(self):
        view = make_dashboard_view(char_data={"Spot Hidden": 50, "Listen": 40})
        modal = SkillSearchModal(view)
        modal.skill_name._value = "spot"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        select = next(c for c in kwargs["view"].children if isinstance(c, SkillRollSelect))
        assert [o.value for o in select.options] == ["Spot Hidden"]

    @pytest.mark.asyncio
    async def test_no_matches_sends_ephemeral_failure(self):
        view = make_dashboard_view(char_data={"Spot Hidden": 50})
        modal = SkillSearchModal(view)
        modal.skill_name._value = "zzzznomatch"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "No skills found similar to" in interaction.response.send_message.call_args.args[0]
        interaction.response.edit_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_back_button_in_results_returns_to_dashboard(self):
        view = make_dashboard_view(char_data={"Spot Hidden": 50})
        modal = SkillSearchModal(view)
        modal.skill_name._value = "spot"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        _, kwargs = interaction.response.edit_message.call_args
        back_btn = next(c for c in kwargs["view"].children if getattr(c, "label", None) == "Back")

        back_interaction = make_interaction()
        await back_btn.callback(back_interaction)

        view.refresh_dashboard.assert_awaited_once_with(back_interaction)


class TestSkillRollSelect:
    @pytest.mark.asyncio
    async def test_callback_rolls_and_sends_result_publicly(self):
        char_data = {"Spot Hidden": 50}
        view = make_dashboard_view(char_data=char_data)
        select = SkillRollSelect(view, [("Spot Hidden", 50)])
        select._values = ["Spot Hidden"]

        roll_cog = MagicMock()
        roll_cog.calculate_roll_result = MagicMock(return_value=("Regular Success", 2))

        interaction = make_interaction()
        interaction.client.get_cog = MagicMock(return_value=roll_cog)
        sent_message = MagicMock()
        interaction.channel.send = AsyncMock(return_value=sent_message)

        with patch("loadnsave.load_luck_stats", new=AsyncMock(return_value={"111": 10})):
            await select.callback(interaction)

        interaction.channel.send.assert_awaited_once()
        _, kwargs = interaction.channel.send.call_args
        assert isinstance(kwargs["view"], RollResultView)
        assert kwargs["view"].message is sent_message
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_callback_reports_when_roll_system_unavailable(self):
        view = make_dashboard_view()
        select = SkillRollSelect(view, [("Spot Hidden", 50)])
        select._values = ["Spot Hidden"]

        interaction = make_interaction()
        interaction.client.get_cog = MagicMock(return_value=None)

        await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Roll system unavailable.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_back_to_sheet_button_after_roll_refreshes_dashboard(self):
        char_data = {"Spot Hidden": 50}
        view = make_dashboard_view(char_data=char_data)
        select = SkillRollSelect(view, [("Spot Hidden", 50)])
        select._values = ["Spot Hidden"]

        roll_cog = MagicMock()
        roll_cog.calculate_roll_result = MagicMock(return_value=("Regular Success", 2))
        interaction = make_interaction()
        interaction.client.get_cog = MagicMock(return_value=roll_cog)
        interaction.channel.send = AsyncMock(return_value=MagicMock())

        with patch("loadnsave.load_luck_stats", new=AsyncMock(return_value={"111": 10})):
            await select.callback(interaction)

        _, kwargs = interaction.response.edit_message.call_args
        back_btn = next(c for c in kwargs["view"].children if getattr(c, "label", None) == "Back to Sheet")

        back_interaction = make_interaction()
        await back_btn.callback(back_interaction)

        view.refresh_dashboard.assert_awaited_once_with(back_interaction)
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_mychar_roll.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_mychar_roll.py
git commit -m "test: add coverage for commands/_mychar_roll.py"
```

---

### Task 34: Add tests for commands/_newinvestigator_basicinfo.py

**Files:**
- Create: `tests/test_commands_newinvestigator_basicinfo.py`

**Interfaces:**
- Consumes: `BasicInfoModal.on_submit`, `RetireCharacterView.interaction_check`/`.retire`/`.cancel`, `BasicInfoStartView.enter_details` (all from `commands/_newinvestigator_basicinfo.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._newinvestigator_basicinfo import (
    BasicInfoModal,
    RetireCharacterView,
    BasicInfoStartView,
)


def make_interaction(user_id="222"):
    interaction = MagicMock()
    interaction.user = MagicMock(id=int(user_id))
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    return interaction


class TestBasicInfoModal:
    @pytest.mark.asyncio
    async def test_valid_submission_advances_to_gamemode_step(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        modal = BasicInfoModal(cog, MagicMock(), char_data, player_stats)
        modal.name.component._value = "Jane Doe"
        modal.residence.component._value = "Arkham"
        modal.age.component._value = "30"
        modal.language.component._value = "English"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert char_data["NAME"] == "Jane Doe"
        assert char_data["Residence"] == "Arkham"
        assert char_data["Age"] == 30
        assert char_data["First Language"] == "English"
        cog.step_gamemode.assert_awaited_once_with(interaction, char_data, player_stats)

    @pytest.mark.asyncio
    async def test_age_out_of_bounds_rejected(self):
        cog = AsyncMock()
        char_data = {}
        modal = BasicInfoModal(cog, MagicMock(), char_data, {})
        modal.name.component._value = "Jane"
        modal.residence.component._value = ""
        modal.age.component._value = "5"
        modal.language.component._value = "English"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "Age must be a number between 15 and 90.", ephemeral=True
        )
        cog.step_gamemode.assert_not_awaited()
        assert "NAME" not in char_data

    @pytest.mark.asyncio
    async def test_missing_residence_defaults_to_unknown(self):
        cog = AsyncMock()
        char_data = {}
        modal = BasicInfoModal(cog, MagicMock(), char_data, {})
        modal.name.component._value = "Jane"
        modal.residence.component._value = ""
        modal.age.component._value = "40"
        modal.language.component._value = ""

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert char_data["Residence"] == "Unknown"
        assert char_data["First Language"] == "Own"


class TestRetireCharacterView:
    @pytest.mark.asyncio
    async def test_interaction_check_rejects_other_users(self):
        view = RetireCharacterView(MagicMock(), user_id="222", server_id="111", player_stats={})
        interaction = make_interaction(user_id="999")

        result = await view.interaction_check(interaction)

        assert result is False
        interaction.response.send_message.assert_awaited_once_with("Not your session!", ephemeral=True)

    @pytest.mark.asyncio
    async def test_retire_moves_character_to_retired_and_restarts_wizard(self):
        cog = AsyncMock()
        player_stats = {"111": {"222": {"NAME": "Old Detective"}}}
        view = RetireCharacterView(cog, user_id="222", server_id="111", player_stats=player_stats)
        interaction = make_interaction()

        with patch("commands._newinvestigator_basicinfo.load_retired_characters_data", new=AsyncMock(return_value={})), \
             patch("commands._newinvestigator_basicinfo.save_retired_characters_data", new=AsyncMock()) as mock_save_retired, \
             patch("commands._newinvestigator_basicinfo.save_player_stats", new=AsyncMock()) as mock_save_stats:
            await view.retire.callback(interaction)

        assert view.value is True
        assert "222" not in player_stats["111"]
        mock_save_retired.assert_awaited_once()
        retired_arg = mock_save_retired.call_args.args[0]
        assert retired_arg["222"][0]["NAME"] == "Old Detective"
        mock_save_stats.assert_awaited_once_with(player_stats)
        cog.start_wizard.assert_awaited_once_with(interaction, player_stats)
        assert view.is_finished()

    @pytest.mark.asyncio
    async def test_cancel_sets_value_false_and_stops(self):
        view = RetireCharacterView(MagicMock(), user_id="222", server_id="111", player_stats={})
        interaction = make_interaction()

        await view.cancel.callback(interaction)

        assert view.value is False
        interaction.response.send_message.assert_awaited_once_with("Character creation cancelled.", ephemeral=True)
        assert view.is_finished()


class TestBasicInfoStartView:
    @pytest.mark.asyncio
    async def test_enter_details_opens_basic_info_modal(self):
        cog = MagicMock()
        char_data = {}
        player_stats = {}
        view = BasicInfoStartView(cog, char_data, player_stats)
        interaction = make_interaction()

        await view.enter_details.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.call_args.args[0]
        assert isinstance(modal, BasicInfoModal)
        assert modal.char_data is char_data
        assert modal.player_stats is player_stats
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_newinvestigator_basicinfo.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_newinvestigator_basicinfo.py
git commit -m "test: add coverage for commands/_newinvestigator_basicinfo.py"
```

---

### Task 35: Add tests for commands/_newinvestigator_gamemode.py

**Files:**
- Create: `tests/test_commands_newinvestigator_gamemode.py`

**Interfaces:**
- Consumes: `GameModeView.coc_button`/`.pulp_button`, `EraSelectView.select_era`/`.era_1920s`/`.era_gaslight`, `ArchetypeSelect.callback`, `ArchetypeSelectView.update_info`/`.confirm`, `CoreStatSelectView.__init__` (all from `commands/_newinvestigator_gamemode.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from commands._newinvestigator_gamemode import (
    GameModeView,
    EraSelectView,
    ArchetypeSelect,
    ArchetypeSelectView,
    CoreStatSelectView,
)
from commands._newinvestigator_data import ERA_SKILLS


def make_interaction():
    interaction = MagicMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_message = AsyncMock()
    return interaction


class TestGameModeView:
    @pytest.mark.asyncio
    async def test_coc_button_sets_mode_and_advances_to_era(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        view = GameModeView(cog, char_data, player_stats)
        interaction = make_interaction()

        await view.coc_button.callback(interaction)

        assert char_data["Game Mode"] == "Call of Cthulhu"
        interaction.response.edit_message.assert_awaited_once()
        cog.step_era.assert_awaited_once_with(interaction, char_data, player_stats)

    @pytest.mark.asyncio
    async def test_pulp_button_sets_mode_and_advances_to_era(self):
        cog = AsyncMock()
        char_data = {}
        view = GameModeView(cog, char_data, {})
        interaction = make_interaction()

        await view.pulp_button.callback(interaction)

        assert char_data["Game Mode"] == "Pulp of Cthulhu"
        cog.step_era.assert_awaited_once()


class TestEraSelectView:
    @pytest.mark.asyncio
    async def test_selecting_era_applies_skills_and_clears_previous_era_skills(self):
        cog = AsyncMock()
        char_data = {"Game Mode": "Call of Cthulhu", "Ride Horse": 5}  # stale Dark Ages skill
        player_stats = {}
        view = EraSelectView(cog, char_data, player_stats)
        interaction = make_interaction()

        await view.era_1920s.callback(interaction)

        assert char_data["Era"] == "1920s Era"
        assert char_data["Climb"] == ERA_SKILLS["1920s Era"]["Climb"]
        assert "Ride Horse" not in char_data
        cog.step_stats.assert_awaited_once_with(interaction, char_data, player_stats)

    @pytest.mark.asyncio
    async def test_pulp_game_mode_routes_to_archetype_selection_instead_of_stats(self):
        cog = AsyncMock()
        char_data = {"Game Mode": "Pulp of Cthulhu"}
        player_stats = {}
        view = EraSelectView(cog, char_data, player_stats)
        interaction = make_interaction()

        await view.era_gaslight.callback(interaction)

        assert char_data["Era"] == "Cthulhu by Gaslight"
        cog.select_pulp_archetype.assert_awaited_once_with(interaction, char_data, player_stats)
        cog.step_stats.assert_not_awaited()


class TestArchetypeSelectAndView:
    @pytest.mark.asyncio
    async def test_select_callback_stores_choice_and_updates_info(self):
        archetypes_data = {"Daredevil": {"description": "Fast and reckless.", "adjustments": ["+5 DEX"]}}
        cog = AsyncMock()
        view = ArchetypeSelectView(cog, {}, {}, archetypes_data)
        select = view.children[0]
        assert isinstance(select, ArchetypeSelect)
        select._values = ["Daredevil"]

        interaction = make_interaction()
        await select.callback(interaction)

        assert view.selected_archetype == "Daredevil"
        interaction.response.edit_message.assert_awaited_once()
        embed = interaction.response.edit_message.call_args.kwargs["embed"]
        assert embed.title == "Archetype: Daredevil"

    @pytest.mark.asyncio
    async def test_confirm_without_selection_is_rejected(self):
        cog = AsyncMock()
        view = ArchetypeSelectView(cog, {}, {}, {"Daredevil": {}})
        interaction = make_interaction()

        await view.confirm.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Please select an archetype first.", ephemeral=True)
        cog.step_stats.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_confirm_applies_archetype_and_advances_to_stats(self):
        archetypes_data = {"Daredevil": {"description": "Fast", "adjustments": []}}
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        view = ArchetypeSelectView(cog, char_data, player_stats, archetypes_data)
        view.selected_archetype = "Daredevil"
        interaction = make_interaction()

        await view.confirm.callback(interaction)

        assert char_data["Archetype"] == "Daredevil"
        assert char_data["Archetype Info"] == archetypes_data["Daredevil"]
        cog.step_stats.assert_awaited_once_with(interaction, char_data, player_stats)


class TestCoreStatSelectView:
    @pytest.mark.asyncio
    async def test_button_click_invokes_cog_apply_core_stat_logic(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        view = CoreStatSelectView(["STR", "DEX"], cog, char_data, player_stats)
        assert {c.label for c in view.children} == {"STR", "DEX"}

        str_btn = next(c for c in view.children if c.label == "STR")
        interaction = make_interaction()
        await str_btn.callback(interaction)

        cog.apply_core_stat_logic.assert_awaited_once_with(interaction, char_data, player_stats, "STR")
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_newinvestigator_gamemode.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_newinvestigator_gamemode.py
git commit -m "test: add coverage for commands/_newinvestigator_gamemode.py"
```

---

### Task 36: Add tests for commands/_newinvestigator_stats.py

**Files:**
- Create: `tests/test_commands_newinvestigator_stats.py`

**Interfaces:**
- Consumes: `StatGenerationView.auto`/`.quick`/`.assisted`/`.forced`, `StatsBulkEntryModal.on_submit`, `AssistedRollView.keep`/`.reroll`, `StatsDeductionView.deduct`/`.str_minus` (all from `commands/_newinvestigator_stats.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from commands._newinvestigator_stats import (
    StatGenerationView,
    StatsBulkEntryModal,
    AssistedRollView,
    StatsDeductionView,
)


def make_interaction():
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    return interaction


class TestStatGenerationView:
    @pytest.mark.asyncio
    async def test_each_mode_button_delegates_to_matching_cog_method(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        view = StatGenerationView(cog, char_data, player_stats)
        interaction = make_interaction()

        await view.auto.callback(interaction)
        cog.mode_full_auto.assert_awaited_once_with(interaction, char_data, player_stats)

        await view.quick.callback(interaction)
        cog.mode_quick_fire.assert_awaited_once_with(interaction, char_data, player_stats)

        await view.assisted.callback(interaction)
        cog.mode_assisted.assert_awaited_once_with(interaction, char_data, player_stats)

        await view.forced.callback(interaction)
        cog.mode_forced.assert_awaited_once_with(interaction, char_data, player_stats)


class TestStatsBulkEntryModal:
    @pytest.mark.asyncio
    async def test_parses_valid_stat_lines_and_ignores_invalid_ones(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        modal = StatsBulkEntryModal(cog, MagicMock(), char_data, player_stats, mode="bulk")
        modal.stats_input.component._value = "STR 60\nCON 70\nNOTASTAT 99\nSIZ abc\nDEX 55"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert char_data == {"STR": 60, "CON": 70, "DEX": 55}
        interaction.response.send_message.assert_awaited_once_with("Stats applied.", ephemeral=True)
        cog.display_stats_and_continue.assert_awaited_once_with(interaction, char_data, player_stats)


class TestAssistedRollView:
    @pytest.mark.asyncio
    async def test_keep_applies_value_and_continues_loop(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        queue = ["CON", "SIZ"]
        view = AssistedRollView(cog, char_data, player_stats, queue, "STR", "3D6 * 5", 65)
        interaction = make_interaction()

        await view.keep.callback(interaction)

        assert char_data["STR"] == 65
        cog.assisted_loop.assert_awaited_once_with(interaction, char_data, player_stats, queue)

    @pytest.mark.asyncio
    async def test_reroll_uses_formula_and_replaces_value(self):
        cog = AsyncMock()
        cog.roll_stat_formula = MagicMock(return_value=80)
        char_data = {}
        player_stats = {}
        queue = ["CON"]
        view = AssistedRollView(cog, char_data, player_stats, queue, "STR", "3D6 * 5", 65)
        interaction = make_interaction()

        await view.reroll.callback(interaction)

        cog.roll_stat_formula.assert_called_once_with("3D6 * 5")
        assert char_data["STR"] == 80
        interaction.response.edit_message.assert_awaited_once()
        cog.assisted_loop.assert_awaited_once_with(interaction, char_data, player_stats, queue)


class TestStatsDeductionView:
    @pytest.mark.asyncio
    async def test_deduct_reduces_stat_and_tracks_remaining(self):
        cog = AsyncMock()
        char_data = {"STR": 50}
        player_stats = {}
        view = StatsDeductionView(cog, char_data, player_stats, deduction_remaining=10)
        interaction = make_interaction()

        await view.str_minus.callback(interaction)

        assert char_data["STR"] == 45
        assert view.deduction_remaining == 5
        interaction.response.edit_message.assert_awaited_once()
        cog.finalize_age_modifiers.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deduct_completes_and_finalizes_when_remaining_hits_zero(self):
        cog = AsyncMock()
        char_data = {"STR": 50}
        player_stats = {}
        view = StatsDeductionView(cog, char_data, player_stats, deduction_remaining=5)
        interaction = make_interaction()

        await view.str_minus.callback(interaction)

        assert view.deduction_remaining == 0
        cog.finalize_age_modifiers.assert_awaited_once_with(interaction, char_data, player_stats)

    @pytest.mark.asyncio
    async def test_deduct_rejects_reduction_below_zero(self):
        cog = AsyncMock()
        char_data = {"STR": 2}
        view = StatsDeductionView(cog, char_data, {}, deduction_remaining=10)
        interaction = make_interaction()

        await view.str_minus.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Cannot reduce STR below 0.", ephemeral=True)
        assert char_data["STR"] == 2
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_newinvestigator_stats.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_newinvestigator_stats.py
git commit -m "test: add coverage for commands/_newinvestigator_stats.py"
```

---

### Task 37: Add tests for commands/_newinvestigator_occupation.py

**Files:**
- Create: `tests/test_commands_newinvestigator_occupation.py`

**Interfaces:**
- Consumes: `OccupationSearchModal.on_submit`, `OccupationSelect.callback`, `PaginatedOccupationListView.__init__`/`.update_view`/`.prev_page`/`.next_page`, `OccupationPageSelect.callback`, `OccupationSearchStartView.search`/`.browse`/`.browse_alpha` (all from `commands/_newinvestigator_occupation.py`)

- [ ] **Step 1: Write the test(s)**

```python
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from commands._newinvestigator_occupation import (
    OccupationSearchModal,
    OccupationSelectView,
    OccupationSelect,
    PaginatedOccupationListView,
    OccupationPageSelect,
    OccupationSearchStartView,
)


def make_interaction():
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    return interaction


OCCUPATIONS = {
    "Detective": {"skills": "Spot Hidden, Law"},
    "Doctor": {"skills": "Medicine, First Aid"},
    "Antiquarian": {"skills": "Appraise, History"},
}


class TestOccupationSearchModal:
    @pytest.mark.asyncio
    async def test_matching_search_shows_select_view(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        modal = OccupationSearchModal(cog, MagicMock(), char_data, player_stats, OCCUPATIONS)
        modal.search_term._value = "doc"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], OccupationSelectView)

    @pytest.mark.asyncio
    async def test_no_matches_reports_failure(self):
        cog = AsyncMock()
        modal = OccupationSearchModal(cog, MagicMock(), {}, {}, OCCUPATIONS)
        modal.search_term._value = "zzznomatch"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "No occupations found matching that term.", ephemeral=True
        )


class TestOccupationSelect:
    @pytest.mark.asyncio
    async def test_callback_assigns_occupation_skills_via_cog(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        view = OccupationSelectView(cog, char_data, player_stats, OCCUPATIONS, ["Detective", "Doctor"])
        select = view.children[0]
        assert isinstance(select, OccupationSelect)
        select._values = ["Detective"]

        interaction = make_interaction()
        await select.callback(interaction)

        cog.assign_occupation_skills.assert_awaited_once_with(
            interaction, char_data, player_stats, "Detective", OCCUPATIONS["Detective"]
        )


class TestPaginatedOccupationListView:
    def test_sorts_by_points_descending_by_default(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(side_effect=lambda char_data, info: {"Detective": 50, "Doctor": 70, "Antiquarian": 50}[[k for k, v in OCCUPATIONS.items() if v is info][0]])
        view = PaginatedOccupationListView(cog, {}, {}, OCCUPATIONS, sort_mode="points")

        names = [name for name, pts in view.sorted_list]
        assert names[0] == "Doctor"  # highest points first

    def test_alpha_sort_mode_orders_by_name(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(return_value=10)
        view = PaginatedOccupationListView(cog, {}, {}, OCCUPATIONS, sort_mode="alpha")

        names = [name for name, pts in view.sorted_list]
        assert names == sorted(OCCUPATIONS.keys())

    @pytest.mark.asyncio
    async def test_pagination_updates_page_and_embed(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(return_value=10)
        many_occupations = {f"Occ {i}": {"skills": ""} for i in range(30)}
        view = PaginatedOccupationListView(cog, {}, {}, many_occupations, sort_mode="alpha")
        interaction = make_interaction()

        next_btn = next(c for c in view.children if getattr(c, "label", None) == "Next")
        await next_btn.callback(interaction)

        assert view.page == 1
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_select_callback_assigns_occupation(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(return_value=10)
        cog.assign_occupation_skills = AsyncMock()
        char_data = {}
        player_stats = {}
        view = PaginatedOccupationListView(cog, char_data, player_stats, OCCUPATIONS, sort_mode="alpha")

        select = next(c for c in view.children if isinstance(c, OccupationPageSelect))
        select._values = ["Detective"]
        interaction = make_interaction()

        await select.callback(interaction)

        cog.assign_occupation_skills.assert_awaited_once_with(
            interaction, char_data, player_stats, "Detective", OCCUPATIONS["Detective"]
        )


class TestOccupationSearchStartView:
    @pytest.mark.asyncio
    async def test_search_button_opens_search_modal(self):
        cog = MagicMock()
        view = OccupationSearchStartView(cog, {}, {}, OCCUPATIONS)
        interaction = make_interaction()
        interaction.response.send_modal = AsyncMock()

        await view.search.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], OccupationSearchModal)

    @pytest.mark.asyncio
    async def test_browse_button_shows_points_sorted_list(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(return_value=10)
        view = OccupationSearchStartView(cog, {}, {}, OCCUPATIONS)
        interaction = make_interaction()

        await view.browse.callback(interaction)

        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        assert isinstance(kwargs["view"], PaginatedOccupationListView)
        assert kwargs["view"].sort_mode == "points"

    @pytest.mark.asyncio
    async def test_browse_alpha_button_shows_alpha_sorted_list(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(return_value=10)
        view = OccupationSearchStartView(cog, {}, {}, OCCUPATIONS)
        interaction = make_interaction()

        await view.browse_alpha.callback(interaction)

        _, kwargs = interaction.response.edit_message.call_args
        assert kwargs["view"].sort_mode == "alpha"
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_newinvestigator_occupation.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_newinvestigator_occupation.py
git commit -m "test: add coverage for commands/_newinvestigator_occupation.py"
```

---

### Task 38: Add schema test for commands/_newinvestigator_data.py

**Files:**
- Create: `tests/test_commands_newinvestigator_data.py`

**Interfaces:**
- Consumes: `ERA_SKILLS`, `BASE_SKILLS` (constants from `commands/_newinvestigator_data.py`)

- [ ] **Step 1: Write the test(s)**

```python
from commands._newinvestigator_data import ERA_SKILLS, BASE_SKILLS

EXPECTED_ERAS = {
    "1920s Era", "1930s Era", "Modern Era",
    "Cthulhu by Gaslight", "Down Darker Trails", "Dark Ages",
}


def test_all_expected_eras_present():
    assert set(ERA_SKILLS.keys()) == EXPECTED_ERAS


def test_base_skills_is_alias_for_1920s_era():
    assert BASE_SKILLS == ERA_SKILLS["1920s Era"]
    assert BASE_SKILLS is ERA_SKILLS["1920s Era"]


def test_every_era_skill_map_has_string_keys_and_int_values_in_range():
    for era_name, skills in ERA_SKILLS.items():
        assert isinstance(skills, dict) and skills, f"{era_name} has no skills"
        for skill_name, base_value in skills.items():
            assert isinstance(skill_name, str) and skill_name
            assert isinstance(base_value, int), f"{era_name}.{skill_name} base value is not an int"
            assert 0 <= base_value <= 99, f"{era_name}.{skill_name} base value {base_value} out of range"


def test_every_era_defines_core_universal_skills():
    universal_skills = {"Dodge", "Cthulhu Mythos", "Credit Rating", "Fighting (Brawl)", "First Aid", "Stealth"}
    for era_name, skills in ERA_SKILLS.items():
        missing = universal_skills - skills.keys()
        assert not missing, f"{era_name} is missing universal skills: {missing}"


def test_cthulhu_mythos_and_dodge_base_at_zero_in_every_era():
    for era_name, skills in ERA_SKILLS.items():
        assert skills["Cthulhu Mythos"] == 0, f"{era_name}.Cthulhu Mythos should base at 0"
        assert skills["Dodge"] == 0, f"{era_name}.Dodge should base at 0"
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_commands_newinvestigator_data.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_commands_newinvestigator_data.py
git commit -m "test: add schema coverage for commands/_newinvestigator_data.py"
```

---

### Task 39: Expand combat.py coverage — weapon-jam, reload, and malfunction-roll flow

**Files:**
- Create: `tests/test_combat_state_transitions.py`

**Interfaces:**
- Consumes: `commands.combat.CombatView` — specifically `_parse_damage_string`, `shoot_callback`, `reload_callback`, `fix_jam_callback`, and their private helpers (`_update_inventory_string`). Reuses the `CombatView.__new__(CombatView)` construction pattern already established in `tests/test_combat_weapon_parsing.py` (bypasses `__init__`/`update_components()`, sets only the attributes each test needs).
- `commands.combat.save_player_stats` is patched (by-name import: `from loadnsave import ... save_player_stats ...` at `commands/combat.py:7`, so the patch target is `commands.combat.save_player_stats`, not `loadnsave.save_player_stats`).
- `CombatView.perform_roll` is monkeypatched to an `AsyncMock` in the shoot/fix-jam tests, to isolate the state-transition logic in `on_shoot_done`/`on_repair_done` from the full roll-and-message-send flow (which needs a real Discord connection, `interaction.channel.send`, a real `Roll` cog, etc.) — this repo has no existing pattern for testing `perform_roll`'s full body, and building one is out of scope here; capturing and directly invoking the `on_complete` callback it's given is the correct, minimal way to test the state transition that callback performs.

- [ ] **Step 1: Write the tests**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.combat import CombatView


def make_view(**overrides):
    view = CombatView.__new__(CombatView)
    view.char_data = overrides.get("char_data", {
        "Backstory": {"Gear and Possessions": ["Shotgun [1/2]"]},
        "Rifle/Shotgun": 50,
    })
    view.weapon_db = overrides.get("weapon_db", {
        "Shotgun": {"capacity": "2", "damage": "4D6 (buckshot) or 2D6 (slug)", "malfunction": "96", "Skill": "Rifle/Shotgun"},
    })
    view.available_weapons = overrides.get("available_weapons", [
        {"key": "Shotgun", "display": "Shotgun [1/2]", "clean_name": "Shotgun",
         "ammo": 1, "cap": 2, "original": "Shotgun [1/2]", "is_jammed": False},
    ])
    view.weapon_states = overrides.get("weapon_states", {0: {"ammo": 1, "cap": 2, "jammed": False}})
    view.active_weapon_idx = overrides.get("active_weapon_idx", 0)
    view.player_stats = overrides.get("player_stats", {"1": {"2": view.char_data}})
    view.server_id = overrides.get("server_id", "1")
    view.user_id = overrides.get("user_id", "2")
    view.last_action = "Combat started."
    view.message = None
    return view


def make_interaction(response_done=False):
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=response_done)
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


# --- _parse_damage_string ---

def test_parse_damage_string_splits_or_alternatives_with_labels():
    view = CombatView.__new__(CombatView)
    options = view._parse_damage_string("1D10+5 (slug) or 4D6 (buckshot)", "Shotgun")
    assert options == [
        {"label": "slug", "value": "1D10+5"},
        {"label": "buckshot", "value": "4D6"},
    ]


def test_parse_damage_string_no_label_uses_weapon_name():
    view = CombatView.__new__(CombatView)
    options = view._parse_damage_string("1D8", "Knife")
    assert options == [{"label": "Knife", "value": "1D8"}]


def test_parse_damage_string_unknown_returns_empty():
    view = CombatView.__new__(CombatView)
    assert view._parse_damage_string("Unknown", "Fists") == []
    assert view._parse_damage_string("", "Fists") == []


# --- shoot_callback: ammo depletion + malfunction (jam) transition ---

@pytest.mark.asyncio
async def test_shoot_callback_out_of_ammo_sends_ephemeral_message_and_does_not_roll():
    view = make_view(weapon_states={0: {"ammo": 0, "cap": 2, "jammed": False}})
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    await view.shoot_callback(interaction)

    interaction.response.send_message.assert_awaited_once_with("Click... (Out of Ammo!)", ephemeral=True)
    view.perform_roll.assert_not_awaited()


@pytest.mark.asyncio
async def test_shoot_callback_decrements_ammo_and_persists_inventory_string():
    view = make_view()
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock) as mock_save:
        await view.shoot_callback(interaction)

    assert view.weapon_states[0]["ammo"] == 0
    mock_save.assert_awaited_once()
    updated_str = view.char_data["Backstory"]["Gear and Possessions"][0]
    assert updated_str == "Shotgun [0/2]"
    view.perform_roll.assert_awaited_once()


@pytest.mark.asyncio
async def test_shoot_callback_malfunction_jams_weapon_via_on_complete_callback():
    view = make_view()
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock):
        await view.shoot_callback(interaction)

    on_complete = view.perform_roll.await_args.kwargs["on_complete"]
    assert view.weapon_states[0]["jammed"] is False

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock):
        await on_complete(roll=97, tier=0, is_malf=True)

    assert view.weapon_states[0]["jammed"] is True
    assert "(JAMMED!)" in view.last_action


@pytest.mark.asyncio
async def test_shoot_callback_non_malfunction_does_not_jam_weapon():
    view = make_view()
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock):
        await view.shoot_callback(interaction)

    on_complete = view.perform_roll.await_args.kwargs["on_complete"]
    await on_complete(roll=40, tier=2, is_malf=False)

    assert view.weapon_states[0]["jammed"] is False


# --- reload_callback: refills ammo, clears jam, persists ---

@pytest.mark.asyncio
async def test_reload_callback_refills_ammo_and_clears_jam():
    view = make_view(
        weapon_states={0: {"ammo": 0, "cap": 2, "jammed": True}},
        available_weapons=[{"key": "Shotgun", "display": "🔴 Shotgun [0/2] (JAMMED)", "clean_name": "Shotgun",
                             "ammo": 0, "cap": 2, "original": "🔴 Shotgun [0/2] (JAMMED)", "is_jammed": True}],
        char_data={"Backstory": {"Gear and Possessions": ["🔴 Shotgun [0/2] (JAMMED)"]}, "Rifle/Shotgun": 50},
    )
    view.player_stats = {"1": {"2": view.char_data}}
    interaction = make_interaction(response_done=False)

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock) as mock_save:
        await view.reload_callback(interaction)

    assert view.weapon_states[0]["ammo"] == 2
    assert view.weapon_states[0]["jammed"] is False
    mock_save.assert_awaited_once()
    assert view.char_data["Backstory"]["Gear and Possessions"][0] == "Shotgun [2/2]"
    interaction.response.edit_message.assert_awaited_once()


# --- fix_jam_callback: malfunction-roll boundary for clearing a jam ---

@pytest.mark.asyncio
async def test_fix_jam_callback_regular_success_or_better_clears_jam():
    view = make_view(weapon_states={0: {"ammo": 1, "cap": 2, "jammed": True}})
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock):
        await view.fix_jam_callback(interaction)

    on_complete = view.perform_roll.await_args.kwargs["on_complete"]

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock):
        await on_complete(roll=40, tier=2, is_malf=False)  # tier 2 == Regular Success

    assert view.weapon_states[0]["jammed"] is False
    assert "Cleared jam" in view.last_action


@pytest.mark.asyncio
async def test_fix_jam_callback_failure_leaves_weapon_jammed():
    view = make_view(weapon_states={0: {"ammo": 1, "cap": 2, "jammed": True}})
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    await view.fix_jam_callback(interaction)
    on_complete = view.perform_roll.await_args.kwargs["on_complete"]

    await on_complete(roll=90, tier=1, is_malf=False)  # tier 1 == Fail

    assert view.weapon_states[0]["jammed"] is True
    assert "Failed to clear jam" in view.last_action
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_combat_state_transitions.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures, including `tests/test_combat_weapon_parsing.py` (confirms the shared `CombatView.__new__` construction pattern is unaffected).

- [ ] **Step 4: Commit**

```bash
git add tests/test_combat_state_transitions.py
git commit -m "test: add combat.py weapon-jam/reload/malfunction state-transition coverage"
```

---

### Task 40: Expand chase.py coverage — hazard pass/fail branch and dashboard action-economy handlers

**Files:**
- Create: `tests/test_chase_actions.py`

**Interfaces:**
- Consumes: `commands.chase.ChaseActionsView` (`move_button`, `dash_button`, `attack_button`), `commands.chase.ChaseSession`, `commands.chase.ChaseParticipant`, `commands.chase.ChaseLocation` (all already exercised as plain dataclasses in `tests/test_chase_session.py` — reuse those construction patterns).
- `commands.chase.random.randint` is patched (module-level `import random` at `commands/chase.py:2`, so `random.randint` is looked up via that module object at call time — patch at `commands.chase.random.randint`) to make the hazard skill-check roll deterministic for both the pass and fail branches.
- `ChaseActionsView.update_dashboard` (which calls `self.cog.save_and_update`) is monkeypatched to an `AsyncMock` so these tests don't need a real Discord channel/message — this isolates the state-transition logic (position, actions_remaining, session.log) from the dashboard-rendering side effect, matching this repo's established pattern of mocking side-effecting bot calls (`tests/test_dashboard_routes.py`'s `mock_dependencies` fixture) rather than skipping the test.

- [ ] **Step 1: Write the tests**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.chase import ChaseActionsView, ChaseSession, ChaseParticipant


def make_session_with_hazard_at(index, check="DEX"):
    session = ChaseSession(guild_id=1, channel_id=2, environment="Urban", mode="Foot")
    session.ensure_track_length(index)
    session.track[index].hazard = {"name": "Test Hazard", "check": check, "difficulty": "Regular", "desc": "..."}
    session.track[index].description = f"⚠️ Test Hazard ({check} Check)"
    return session


def make_participant(position=0, dex=50, move_actions=1, actions=1):
    p = ChaseParticipant(user_id="99", name="Investigator")
    p.position = position
    p.dex = dex
    p.move_actions_remaining = move_actions
    p.actions_remaining = actions
    return p


def make_interaction():
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    return interaction


def make_view(session, participant):
    cog = MagicMock()
    view = ChaseActionsView(cog, session, participant)
    view.update_dashboard = AsyncMock()
    return view


# --- move_button: hazard pass/fail branch ---

@pytest.mark.asyncio
async def test_move_button_passes_hazard_check_advances_position():
    session = make_session_with_hazard_at(1, check="DEX")
    participant = make_participant(position=0, dex=80, move_actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    with patch("commands.chase.random.randint", return_value=10):  # 10 <= 80 dex -> pass
        await view.move_button(interaction, MagicMock())

    assert participant.position == 1
    assert participant.move_actions_remaining == 0
    assert "Passed" in session.log[-1]
    view.update_dashboard.assert_awaited_once()


@pytest.mark.asyncio
async def test_move_button_fails_hazard_check_stays_but_still_consumes_move_action():
    session = make_session_with_hazard_at(1, check="DEX")
    participant = make_participant(position=0, dex=20, move_actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    with patch("commands.chase.random.randint", return_value=95):  # 95 > 20 dex -> fail
        await view.move_button(interaction, MagicMock())

    assert participant.position == 0  # unchanged, stuck at hazard
    assert participant.move_actions_remaining == 0  # still consumed on failure
    assert "stumbled" in session.log[-1].lower()
    view.update_dashboard.assert_awaited_once()


@pytest.mark.asyncio
async def test_move_button_no_hazard_at_next_location_always_advances():
    session = ChaseSession(guild_id=1, channel_id=2, environment="Urban", mode="Foot")
    session.ensure_track_length(1)
    session.track[1].hazard = None
    participant = make_participant(position=0, move_actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.move_button(interaction, MagicMock())

    assert participant.position == 1
    assert participant.move_actions_remaining == 0


@pytest.mark.asyncio
async def test_move_button_no_move_actions_remaining_rejects_without_consuming_state():
    session = ChaseSession(guild_id=1, channel_id=2)
    participant = make_participant(position=0, move_actions=0)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.move_button(interaction, MagicMock())

    interaction.response.send_message.assert_awaited_once_with(
        "❌ No Movement Actions remaining!", ephemeral=True
    )
    assert participant.position == 0
    view.update_dashboard.assert_not_awaited()


# --- dash_button: converts a standard action into +1 move action ---

@pytest.mark.asyncio
async def test_dash_button_converts_standard_action_to_move_action():
    session = ChaseSession(guild_id=1, channel_id=2)
    participant = make_participant(actions=1, move_actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.dash_button(interaction, MagicMock())

    assert participant.actions_remaining == 0
    assert participant.move_actions_remaining == 2
    view.update_dashboard.assert_awaited_once()


@pytest.mark.asyncio
async def test_dash_button_no_actions_remaining_rejects():
    session = ChaseSession(guild_id=1, channel_id=2)
    participant = make_participant(actions=0, move_actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.dash_button(interaction, MagicMock())

    interaction.response.send_message.assert_awaited_once_with(
        "❌ No Standard Actions remaining!", ephemeral=True
    )
    assert participant.move_actions_remaining == 1  # unchanged
    view.update_dashboard.assert_not_awaited()


# --- attack_button: consumes a standard action ---

@pytest.mark.asyncio
async def test_attack_button_consumes_standard_action():
    session = ChaseSession(guild_id=1, channel_id=2)
    participant = make_participant(actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.attack_button(interaction, MagicMock())

    assert participant.actions_remaining == 0
    assert "attacks" in session.log[-1].lower()
    view.update_dashboard.assert_awaited_once()


@pytest.mark.asyncio
async def test_attack_button_no_actions_remaining_rejects():
    session = ChaseSession(guild_id=1, channel_id=2)
    participant = make_participant(actions=0)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.attack_button(interaction, MagicMock())

    interaction.response.send_message.assert_awaited_once_with(
        "❌ No Actions remaining!", ephemeral=True
    )
    view.update_dashboard.assert_not_awaited()
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_chase_actions.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures, including `tests/test_chase_session.py` (confirms `ChaseSession`/`ChaseParticipant`/`ChaseLocation` construction is unaffected).

- [ ] **Step 4: Commit**

```bash
git add tests/test_chase_actions.py
git commit -m "test: add chase.py hazard pass/fail and action-economy state-transition coverage"
```

---

### Task 41: Expand newinvestigator.py coverage — wizard step-to-step transition chain

**Files:**
- Create: `tests/test_newinvestigator_wizard_flow.py`

**Interfaces:**
- Consumes: `commands.newinvestigator.newinvestigator` Cog's `step_gamemode`, `step_era`, `step_stats` methods (the start of the wizard's step chain: game mode → era selection → stat-generation method choice). Constructs the Cog directly with a `MagicMock()` bot (matching the existing `tests/test_newinvestigator_logic.py` pattern for testing Cog methods without a real bot).
- Asserts each step method sends the correct next-step View class (`commands._newinvestigator_gamemode.GameModeView`, `EraSelectView`, `commands._newinvestigator_stats.StatGenerationView`) via the correct interaction method (`response.send_message` vs `followup.send`, matching each method's `interaction.response.is_done()` branching) — this is what "beyond smoke level" wizard coverage means here: proving the chain actually wires each step to the right next view, not just that individual view classes construct correctly in isolation (which the companion-file-level tests cover separately).

- [ ] **Step 1: Write the tests**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from commands.newinvestigator import newinvestigator
from commands._newinvestigator_gamemode import GameModeView, EraSelectView
from commands._newinvestigator_stats import StatGenerationView


def make_cog():
    return newinvestigator(MagicMock())


def make_interaction(response_done=False):
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=response_done)
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_step_gamemode_sends_game_mode_view():
    cog = make_cog()
    interaction = make_interaction(response_done=False)
    char_data = {}
    player_stats = {}

    await cog.step_gamemode(interaction, char_data, player_stats)

    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.await_args
    assert isinstance(kwargs["view"], GameModeView)


@pytest.mark.asyncio
async def test_step_era_sends_era_select_view_via_followup():
    cog = make_cog()
    interaction = make_interaction(response_done=True)
    char_data = {}
    player_stats = {}

    await cog.step_era(interaction, char_data, player_stats)

    interaction.followup.send.assert_awaited_once()
    _, kwargs = interaction.followup.send.await_args
    assert isinstance(kwargs["view"], EraSelectView)


@pytest.mark.asyncio
async def test_step_stats_uses_followup_when_response_already_done():
    cog = make_cog()
    interaction = make_interaction(response_done=True)
    char_data = {}
    player_stats = {}

    await cog.step_stats(interaction, char_data, player_stats)

    interaction.followup.send.assert_awaited_once()
    interaction.response.send_message.assert_not_awaited()
    _, kwargs = interaction.followup.send.await_args
    assert isinstance(kwargs["view"], StatGenerationView)


@pytest.mark.asyncio
async def test_step_stats_uses_response_send_message_when_response_not_done():
    cog = make_cog()
    interaction = make_interaction(response_done=False)
    char_data = {}
    player_stats = {}

    await cog.step_stats(interaction, char_data, player_stats)

    interaction.response.send_message.assert_awaited_once()
    interaction.followup.send.assert_not_awaited()
    _, kwargs = interaction.response.send_message.await_args
    assert isinstance(kwargs["view"], StatGenerationView)


@pytest.mark.asyncio
async def test_gamemode_to_era_to_stats_chain_each_hands_off_to_the_next_view():
    """Simulates the real transition chain by directly invoking each step in
    sequence (as the prior step's button callback would), confirming each
    stage produces the view the next stage depends on -- not just that each
    step method works in isolation."""
    cog = make_cog()
    char_data = {}
    player_stats = {}

    interaction_1 = make_interaction(response_done=False)
    await cog.step_gamemode(interaction_1, char_data, player_stats)
    _, kwargs_1 = interaction_1.response.send_message.await_args
    assert isinstance(kwargs_1["view"], GameModeView)

    # GameModeView's own selection callback would normally call step_era next;
    # simulate that hand-off directly since this task's scope is the Cog-level
    # step chain, not GameModeView's own button-callback internals.
    interaction_2 = make_interaction(response_done=True)
    await cog.step_era(interaction_2, char_data, player_stats)
    _, kwargs_2 = interaction_2.followup.send.await_args
    assert isinstance(kwargs_2["view"], EraSelectView)

    interaction_3 = make_interaction(response_done=True)
    await cog.step_stats(interaction_3, char_data, player_stats)
    _, kwargs_3 = interaction_3.followup.send.await_args
    assert isinstance(kwargs_3["view"], StatGenerationView)
```

- [ ] **Step 2: Run the tests, confirm they pass**

Run: `pytest tests/test_newinvestigator_wizard_flow.py -v`
Expected: all cases PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: 0 failures, including `tests/test_newinvestigator_logic.py` and `tests/test_data_schema.py` (confirms no interference with the existing Cog-level tests).

- [ ] **Step 4: Commit**

```bash
git add tests/test_newinvestigator_wizard_flow.py
git commit -m "test: add newinvestigator wizard step-to-step transition chain coverage"
```

---

### Task 42: Final verification pass

**Files:**
- None modified — this task is verification only.

**Interfaces:**
- Consumes: everything from every prior task in this phase.

- [ ] **Step 1: Confirm no production code was touched**

Run:
```bash
git diff --stat f74a2bb..HEAD -- . ':!tests/*'
```
Expected: empty output — every change in this phase lives under `tests/`. If anything outside `tests/` shows up, investigate before declaring the phase done (per this plan's Global Constraint: zero production code changes).

- [ ] **Step 2: Run the full test suite**

Run: `pytest -v` (or `.venv/bin/python -m pytest -v`)
Expected: 0 failures, including every pre-existing test from Phases 0-3 and every new test file added in this phase.

- [ ] **Step 3: Confirm test file count and naming**

Run: `ls tests/ | sort`
Expected: one new test file per task in this plan (or an extended existing file, per each task's brief), all following the `test_<module>_<aspect>.py` naming convention — no stray `phaseN_*`-named files added by this phase.

- [ ] **Step 4: Spot-check coverage breadth**

Run:
```bash
grep -rl "^import discord\|^from discord" tests/ | wc -l
```
Sanity-check this count against the number of blueprint/companion-file test files added — every blueprint and companion-file test should import either `discord`-related mocks or the target module itself; a suspiciously low count could indicate a task produced trivial/no-op tests. Manually skim any file that looks unusually short.

- [ ] **Step 5: Commit** (only if any of the above steps required a fix; otherwise this task produces no commit of its own, just a clean verification pass)

## Definition of Done for Phase 4

- Every one of the 24 `dashboard/blueprints/*.py` files has real, content-asserting test coverage (not just the generic route-inventory smoke sweep) for its genuinely-missing routes — 17 files get fresh coverage (Tasks 1-8, 16-25), 7 already-partially-covered files get their remaining gaps filled (Tasks 9-15).
- Every one of the 12 `commands/_foo.py` UI-class companion files has at least one test directly exercising its View/Modal/Select classes (not just the parent Cog's cog-load import/registration check), plus a light schema test for the 13th, pure-data `_newinvestigator_data.py` file (Tasks 26-38).
- Combat's weapon-jam/reload/malfunction-roll flow, chase's hazard pass/fail branch and dashboard action-economy handlers, and the newinvestigator wizard's step chain and back-navigation handlers all have dedicated regression tests (Tasks 39-41).
- `pytest -v` passes with 0 failures.
- Zero production code was modified anywhere in this phase (purely additive test coverage).
- 41 test-writing tasks (Tasks 1-41) plus 1 final verification pass (Task 42) — the largest phase in this refactor by task count.
