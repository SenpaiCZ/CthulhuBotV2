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
async def test_save_general_settings_unauthorized_without_session(client):
    response = await client.post(
        '/api/game/settings/save_general', json={"guild_id": "123"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


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
async def test_save_general_settings_max_skill_below_range_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/game/settings/save_general',
        json={"guild_id": "123", "max_skill_value": 0},
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
async def test_save_general_settings_luck_only_leaves_skill_untouched(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_skill_settings({"123": {"max_starting_skill": 55}})

    response = await client.post(
        '/api/game/settings/save_general',
        json={"guild_id": "123", "luck_value": 5},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200

    luck = await loadnsave.load_luck_stats()
    skill = await loadnsave.load_skill_settings()
    assert luck["123"] == 5
    assert skill["123"]["max_starting_skill"] == 55


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
async def test_game_loot_save_unauthorized_without_session(client):
    response = await client.post(
        '/api/game/loot/save', json={"items": []},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


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
async def test_game_loot_save_persists_all_provided_fields(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/game/loot/save',
        json={
            "items": ["Rope", "Torch"],
            "money_chance": 40,
            "money_min": 1.5,
            "money_max": 20.0,
            "currency_symbol": "£",
            "num_items_min": 2,
            "num_items_max": 4,
        },
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200

    saved = await loadnsave.load_loot_settings()
    assert saved["items"] == ["Rope", "Torch"]
    assert saved["money_chance"] == 40
    assert saved["money_min"] == 1.5
    assert saved["money_max"] == 20.0
    assert saved["currency_symbol"] == "£"
    assert saved["num_items_min"] == 2
    assert saved["num_items_max"] == 4


@pytest.mark.asyncio
async def test_game_sounds_data_unauthorized_without_session(client):
    response = await client.get('/api/game/sounds/data')
    assert response.status_code == 401


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
async def test_game_sounds_data_returns_saved_settings(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_skill_sound_settings({"123": {"default": {"critical": "yay.mp3"}, "skills": {}}})

    with patch.object(game_settings, 'sync_get_soundboard_files', return_value={}):
        response = await client.get('/api/game/sounds/data')

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data["settings"] == {"123": {"default": {"critical": "yay.mp3"}, "skills": {}}}
    assert data["files"] == []


@pytest.mark.asyncio
async def test_game_sounds_save_unauthorized_without_session(client):
    response = await client.post(
        '/api/game/sounds/save', json={"guild_id": "123"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


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


@pytest.mark.asyncio
async def test_game_sounds_save_overwrites_existing_guild_entry(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_skill_sound_settings({"123": {"default": {"critical": "old.mp3"}, "skills": {}}})

    response = await client.post(
        '/api/game/sounds/save',
        json={"guild_id": "123", "default": {}, "skills": {}},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200

    saved = await loadnsave.load_skill_sound_settings()
    assert saved["123"] == {"default": {}, "skills": {}}
