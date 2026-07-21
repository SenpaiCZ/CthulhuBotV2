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
    assert 'value="?"' in html


@pytest.mark.asyncio
async def test_admin_bot_config_defaults_prefix_when_unset(client, isolated_data_dir):
    await login(client)
    guild = make_guild(guild_id=456, name="Other Guild")
    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/admin/bot_config')

    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'value="!"' in html


@pytest.mark.asyncio
async def test_save_status_unauthorized_without_session(client):
    response = await client.post(
        '/api/save_status', json={"type": "playing", "text": "a game"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


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
async def test_save_status_supports_all_activity_types(client, isolated_data_dir):
    await login(client)

    import discord

    expected_types = {
        "playing": None,
        "watching": discord.ActivityType.watching,
        "listening": discord.ActivityType.listening,
        "competing": discord.ActivityType.competing,
    }

    for status_type, activity_type in expected_types.items():
        mock_bot = MagicMock()
        mock_bot.is_ready.return_value = True
        mock_bot.change_presence = AsyncMock()

        with patch('dashboard.app.app.bot', mock_bot):
            response = await client.post(
                '/api/save_status',
                json={"type": status_type, "text": "flavor"},
                headers={"Origin": "http://localhost"},
            )

        assert response.status_code == 200
        mock_bot.change_presence.assert_awaited_once()
        _, kwargs = mock_bot.change_presence.call_args
        activity = kwargs["activity"]
        if status_type == "playing":
            assert isinstance(activity, discord.Game)
        else:
            assert activity.type == activity_type


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
async def test_save_status_skips_presence_update_when_bot_none(client, isolated_data_dir):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.post(
            '/api/save_status',
            json={"type": "playing", "text": "a game"},
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    saved = await loadnsave.load_bot_status()
    assert saved == {"type": "playing", "text": "a game"}


@pytest.mark.asyncio
async def test_save_prefix_unauthorized_without_session(client):
    response = await client.post(
        '/api/save_prefix', json={"guild_id": "1", "prefix": "?"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


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


@pytest.mark.asyncio
async def test_save_prefix_updates_existing_guild_and_keeps_others(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_server_stats({"123": "!", "999": "$"})

    response = await client.post(
        '/api/save_prefix',
        json={"guild_id": "123", "prefix": "?"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200

    saved = await loadnsave.load_server_stats()
    assert saved["123"] == "?"
    assert saved["999"] == "$"
