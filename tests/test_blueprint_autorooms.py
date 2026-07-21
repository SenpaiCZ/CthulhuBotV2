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
    assert guild_data["id"] == "123"
    assert guild_data["name"] == "Test Guild"
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
async def test_autorooms_save_unauthorized_without_session(client, isolated_data_dir):
    response = await client.post(
        '/api/autorooms/save',
        json={"guild_id": "123", "channel_id": "10", "category_id": "20"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


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


@pytest.mark.asyncio
async def test_autorooms_save_clears_category_id_when_omitted(client, isolated_data_dir):
    await login(client)
    await loadnsave.autoroom_save({"123": {"channel_id": 10, "category_id": 20}})

    response = await client.post(
        '/api/autorooms/save',
        json={"guild_id": "123", "channel_id": "10", "category_id": ""},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200

    saved = await loadnsave.autoroom_load()
    assert saved["123"]["channel_id"] == 10
    assert "category_id" not in saved["123"]


@pytest.mark.asyncio
async def test_autorooms_save_creates_new_guild_entry(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/autorooms/save',
        json={"guild_id": "999", "channel_id": "5", "category_id": "6"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200

    saved = await loadnsave.autoroom_load()
    assert saved["999"] == {"channel_id": 5, "category_id": 6}
