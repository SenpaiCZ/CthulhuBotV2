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
    # karma_settings.html does not actually render the `guilds` context server-side
    # (it fetches its own data client-side via JS, from endpoints that don't even
    # match this blueprint's routes -- see report). So we verify the route's real
    # role-resolution/filtering logic by capturing what it passes to render_template,
    # rather than asserting on rendered HTML content.
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

    captured = {}

    async def fake_render_template(name, **context):
        captured.update(context)
        return "OK"

    with patch('dashboard.blueprints.karma.render_template', side_effect=fake_render_template):
        response = await client.get('/admin/karma')

    assert response.status_code == 200
    guild_entry = captured["guilds"][0]

    role_names = {r["id"]: r["name"] for r in guild_entry["roles_list"]}
    # @everyone / managed roles must be filtered out of the dropdown list.
    assert role_names == {"111": "Investigator"}

    resolved = {r["threshold"]: r["role_name"] for r in guild_entry["resolved_roles"]}
    assert resolved["10"] == "Investigator"
    assert resolved["50"] == "Unknown Role (999)"


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
