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
    # pokemon_data() filters roles via `role.is_default()` / `role.managed`
    # before it ever reaches the role-name-resolution logic being tested here,
    # so both must be present (matches the FakeRole convention already used in
    # tests/test_blueprint_reaction_roles.py).
    def __init__(self, id, name, is_default=False, managed=False):
        self.id = id
        self.name = name
        self._is_default = is_default
        self.managed = managed

    def is_default(self):
        return self._is_default


class FakeGuild:
    # pokemon_data() also iterates `guild.text_channels` unconditionally, so
    # that attribute must exist even when a test doesn't care about channels.
    def __init__(self, id, name, roles=None, text_channels=None):
        self.id = id
        self.name = name
        self.roles = roles or []
        self.text_channels = text_channels or []

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
