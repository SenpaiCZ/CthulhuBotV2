import time
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
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "error", "message": "No participants"}
