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
    def __init__(self, id, name, is_default=False, managed=False):
        self.id = id
        self.name = name
        self._is_default = is_default
        self.managed = managed

    def is_default(self):
        return self._is_default


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
