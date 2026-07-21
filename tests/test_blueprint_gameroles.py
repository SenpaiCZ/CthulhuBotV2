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
