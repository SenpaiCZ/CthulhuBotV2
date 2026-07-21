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
    monkeypatch.setattr(loadnsave, "_POLLS_DATA_CACHE", None)
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
    channel_by_id = {c.id: c for c in (channels or [])}
    guild.get_channel.side_effect = lambda cid: channel_by_id.get(cid)
    return guild


@pytest.mark.asyncio
async def test_admin_polls_redirects_if_not_logged_in(client):
    response = await client.get('/admin/polls')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_polls_data_unauthorized_without_session(client):
    response = await client.get('/api/polls/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_polls_data_no_bot_returns_empty_guilds(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.get('/api/polls/data')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"guilds": []}


@pytest.mark.asyncio
async def test_polls_data_filters_by_guild_and_resolves_channel_and_votes(client, isolated_data_dir):
    await login(client)

    channel = make_channel(555, "polls-channel")
    guild = make_guild(guild_id=123, channels=[channel])
    other_guild = make_guild(guild_id=999, name="Other Guild")

    await loadnsave.save_polls_data({
        "1": {
            "guild_id": "123", "channel_id": 555,
            "question": "Best Mythos?", "votes": {"1": 0, "2": 1},
        },
        "2": {
            "guild_id": "999", "channel_id": 1,
            "question": "Other guild poll", "votes": {},
        },
    })

    mock_bot = MagicMock()
    mock_bot.guilds = [guild, other_guild]
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/api/polls/data')

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))

    guild_123 = next(g for g in data["guilds"] if g["id"] == "123")
    assert len(guild_123["polls"]) == 1
    poll = guild_123["polls"][0]
    assert poll["message_id"] == "1"
    assert poll["channel_name"] == "polls-channel"
    assert poll["vote_count"] == 2

    guild_999 = next(g for g in data["guilds"] if g["id"] == "999")
    assert len(guild_999["polls"]) == 1
    assert guild_999["polls"][0]["channel_name"] == "Unknown"


@pytest.mark.asyncio
async def test_polls_create_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/polls/create', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_polls_create_bot_not_ready_returns_500(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.post(
            '/api/polls/create',
            json={
                "guild_id": "1", "channel_id": "2",
                "question": "Q?", "options": "a,b",
            },
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_polls_create_cog_not_loaded_returns_500(client):
    await login(client)
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = None
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/create',
            json={
                "guild_id": "1", "channel_id": "2",
                "question": "Q?", "options": "a,b",
            },
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_polls_create_splits_comma_separated_options_string(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.create_poll_api = AsyncMock(return_value=(True, "poll-42"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/create',
            json={
                "guild_id": "1", "channel_id": "2",
                "question": "Best?", "options": "Cats,Dogs,Fish",
            },
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success", "poll_id": "poll-42"}
    mock_cog.create_poll_api.assert_awaited_once_with("1", "2", "Best?", ["Cats", "Dogs", "Fish"])


@pytest.mark.asyncio
async def test_polls_create_passes_list_options_unchanged(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.create_poll_api = AsyncMock(return_value=(True, "poll-1"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/create',
            json={
                "guild_id": "1", "channel_id": "2",
                "question": "Best?", "options": ["Cats", "Dogs"],
            },
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    mock_cog.create_poll_api.assert_awaited_once_with("1", "2", "Best?", ["Cats", "Dogs"])


@pytest.mark.asyncio
async def test_polls_create_failure_returns_500_with_message(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.create_poll_api = AsyncMock(return_value=(False, "Could not send poll"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/create',
            json={
                "guild_id": "1", "channel_id": "2",
                "question": "Best?", "options": "a,b",
            },
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 500
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "error", "message": "Could not send poll"}


@pytest.mark.asyncio
async def test_polls_end_missing_poll_id_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/polls/end', json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_polls_end_bot_not_ready_returns_500(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.post(
            '/api/polls/end', json={"poll_id": "1"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_polls_end_cog_not_loaded_returns_500(client):
    await login(client)
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = None
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/end', json={"poll_id": "1"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_polls_end_success(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.end_poll_api = AsyncMock(return_value=(True, None))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/polls/end', json={"poll_id": "1"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}
    mock_cog.end_poll_api.assert_awaited_once_with("1")
