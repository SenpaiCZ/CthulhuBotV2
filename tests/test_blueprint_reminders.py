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
