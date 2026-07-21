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
