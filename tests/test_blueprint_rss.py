import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import loadnsave
from dashboard.app import app
import dashboard.blueprints.rss as rss


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
    monkeypatch.setattr(loadnsave, "_RSS_DATA_CACHE", None)
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


def make_feed(entries, feed_title="A Feed"):
    feed = MagicMock()
    feed.entries = entries
    feed.feed = {"title": feed_title}
    return feed


def make_entry(title, link, entry_id=None):
    entry = MagicMock()
    entry.title = title
    entry.link = link
    entry.id = entry_id or link
    return entry


@pytest.mark.asyncio
async def test_admin_rss_redirects_if_not_logged_in(client):
    response = await client.get('/admin/rss')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_rss_data_unauthorized_without_session(client):
    response = await client.get('/api/rss/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rss_data_no_bot_returns_empty_guilds_but_lists_feeds(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_rss_data({
        "999": [{"channel_id": 1, "link": "http://unknown.com/feed"}],
    })
    with patch('dashboard.app.app.bot', None):
        response = await client.get('/api/rss/data')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data["guilds"] == []
    assert data["feeds"][0]["guild_name"] == "Unknown Guild (999)"
    assert data["feeds"][0]["channel_name"] == "Unknown Channel (1)"


@pytest.mark.asyncio
async def test_rss_data_resolves_guild_and_channel_names(client, isolated_data_dir):
    await login(client)

    channel = make_channel(555, "news-channel")
    guild = make_guild(guild_id=123, channels=[channel])

    await loadnsave.save_rss_data({
        "123": [
            {"channel_id": 555, "link": "http://example.com/feed", "last_message": "Latest", "color": "#ABCDEF"},
        ],
        "999": [
            {"channel_id": 1, "link": "http://unknown.com/feed"},
        ],
    })

    mock_bot = MagicMock()
    mock_bot.guilds = [guild]
    mock_bot.get_guild.side_effect = lambda gid: guild if gid == 123 else None
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/api/rss/data')

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    feeds = {f["link"]: f for f in data["feeds"]}

    known = feeds["http://example.com/feed"]
    assert known["guild_name"] == "Test Guild"
    assert known["channel_name"] == "news-channel"
    assert known["color"] == "#ABCDEF"

    unknown = feeds["http://unknown.com/feed"]
    assert unknown["guild_name"] == "Unknown Guild (999)"
    assert unknown["channel_name"] == "Unknown Channel (1)"
    assert unknown["color"] == "#2E8B57"

    guilds_data = data["guilds"][0]
    assert guilds_data["id"] == "123"
    assert guilds_data["channels"] == [{"id": "555", "name": "news-channel"}]


@pytest.mark.asyncio
async def test_rss_add_unauthorized_without_session(client, isolated_data_dir):
    response = await client.post(
        '/api/rss/add',
        json={"guild_id": "1", "channel_id": "2", "link": "http://example.com/feed"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rss_add_missing_arguments_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/rss/add', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_rss_add_feed_with_no_entries_returns_400(client, isolated_data_dir):
    await login(client)
    empty_feed = make_feed(entries=[])
    with patch.object(rss, 'get_youtube_rss_url', new=AsyncMock(return_value=None)), \
         patch.object(rss.feedparser, 'parse', return_value=empty_feed):
        response = await client.post(
            '/api/rss/add',
            json={"guild_id": "1", "channel_id": "2", "link": "http://example.com/feed"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "No items found in RSS feed"


@pytest.mark.asyncio
async def test_rss_add_feed_parse_failure_returns_400(client, isolated_data_dir):
    await login(client)
    with patch.object(rss, 'get_youtube_rss_url', new=AsyncMock(return_value=None)), \
         patch.object(rss.feedparser, 'parse', side_effect=ValueError("boom")):
        response = await client.post(
            '/api/rss/add',
            json={"guild_id": "1", "channel_id": "2", "link": "http://example.com/feed"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert "Failed to parse RSS" in data["message"]


@pytest.mark.asyncio
async def test_rss_add_persists_new_subscription(client, isolated_data_dir):
    await login(client)
    entry = make_entry("Episode 1", "http://example.com/ep1")
    feed = make_feed(entries=[entry])
    with patch.object(rss, 'get_youtube_rss_url', new=AsyncMock(return_value=None)), \
         patch.object(rss.feedparser, 'parse', return_value=feed):
        response = await client.post(
            '/api/rss/add',
            json={"guild_id": "1", "channel_id": "2", "link": "http://example.com/feed", "color": "#123456"},
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    saved = await loadnsave.load_rss_data()
    entries = saved["1"]
    assert len(entries) == 1
    assert entries[0]["link"] == "http://example.com/feed"
    assert entries[0]["channel_id"] == 2
    assert entries[0]["last_message"] == "Episode 1"
    assert entries[0]["color"] == "#123456"


@pytest.mark.asyncio
async def test_rss_add_rejects_duplicate_subscription(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_rss_data({
        "1": [{"link": "http://example.com/feed", "channel_id": 2, "last_message": "x", "color": "#fff"}]
    })

    entry = make_entry("Episode 2", "http://example.com/ep2")
    feed = make_feed(entries=[entry])
    with patch.object(rss, 'get_youtube_rss_url', new=AsyncMock(return_value=None)), \
         patch.object(rss.feedparser, 'parse', return_value=feed):
        response = await client.post(
            '/api/rss/add',
            json={"guild_id": "1", "channel_id": "2", "link": "http://example.com/feed"},
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Feed already subscribed in this channel"


@pytest.mark.asyncio
async def test_rss_add_resolves_youtube_channel_url_to_rss(client, isolated_data_dir):
    await login(client)
    entry = make_entry("YT Video", "http://youtube.com/watch?v=abc")
    feed = make_feed(entries=[entry])
    with patch.object(rss, 'get_youtube_rss_url', new=AsyncMock(return_value="http://youtube.com/feeds/videos.xml?channel_id=xyz")) as mock_yt, \
         patch.object(rss.feedparser, 'parse', return_value=feed):
        response = await client.post(
            '/api/rss/add',
            json={"guild_id": "1", "channel_id": "2", "link": "http://youtube.com/channel/xyz"},
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    mock_yt.assert_awaited_once_with("http://youtube.com/channel/xyz")

    saved = await loadnsave.load_rss_data()
    assert saved["1"][0]["link"] == "http://youtube.com/feeds/videos.xml?channel_id=xyz"


@pytest.mark.asyncio
async def test_rss_add_notifies_channel_when_bot_and_channel_present(client, isolated_data_dir):
    await login(client)
    entry = make_entry("Episode 1", "http://example.com/ep1")
    feed = make_feed(entries=[entry], feed_title="My Feed")

    channel = make_channel(2, "announcements")
    channel.send = AsyncMock()
    guild = make_guild(guild_id=1, channels=[channel])
    mock_bot = MagicMock()
    mock_bot.get_guild.side_effect = lambda gid: guild if gid == 1 else None
    mock_bot.get_cog.return_value = None

    with patch.object(rss, 'get_youtube_rss_url', new=AsyncMock(return_value=None)), \
         patch.object(rss.feedparser, 'parse', return_value=feed), \
         patch('dashboard.app.app.bot', mock_bot):
        response = await client.post(
            '/api/rss/add',
            json={"guild_id": "1", "channel_id": "2", "link": "http://example.com/feed"},
            headers={"Origin": "http://localhost"},
        )

    assert response.status_code == 200
    channel.send.assert_awaited_once()
    sent_text = channel.send.call_args.args[0]
    assert "My Feed" in sent_text


@pytest.mark.asyncio
async def test_rss_update_color_unauthorized_without_session(client, isolated_data_dir):
    response = await client.post(
        '/api/rss/update_color',
        json={"guild_id": "1", "link": "http://example.com/feed", "color": "#abcabc"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rss_update_color_missing_arguments_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/rss/update_color', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_rss_update_color_feed_not_found_returns_404(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/rss/update_color',
        json={"guild_id": "1", "link": "http://missing.com/feed", "color": "#000"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rss_update_color_persists_new_color(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_rss_data({
        "1": [{"link": "http://example.com/feed", "channel_id": 2, "last_message": "x", "color": "#fff"}]
    })

    response = await client.post(
        '/api/rss/update_color',
        json={"guild_id": "1", "link": "http://example.com/feed", "color": "#abcabc"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    saved = await loadnsave.load_rss_data()
    assert saved["1"][0]["color"] == "#abcabc"


@pytest.mark.asyncio
async def test_rss_delete_unauthorized_without_session(client, isolated_data_dir):
    response = await client.post(
        '/api/rss/delete',
        json={"guild_id": "1", "link": "http://example.com/feed"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rss_delete_missing_arguments_returns_400(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/rss/delete', json={"guild_id": "1"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_rss_delete_no_feeds_for_guild_returns_404(client, isolated_data_dir):
    await login(client)
    response = await client.post(
        '/api/rss/delete',
        json={"guild_id": "1", "link": "http://example.com/feed"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rss_delete_removes_feed_and_cleans_empty_guild_entry(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_rss_data({
        "1": [{"link": "http://example.com/feed", "channel_id": 2, "last_message": "x", "color": "#fff"}]
    })

    response = await client.post(
        '/api/rss/delete',
        json={"guild_id": "1", "link": "http://example.com/feed"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    saved = await loadnsave.load_rss_data()
    assert "1" not in saved


@pytest.mark.asyncio
async def test_rss_delete_unknown_link_returns_404(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_rss_data({
        "1": [{"link": "http://example.com/feed", "channel_id": 2, "last_message": "x", "color": "#fff"}]
    })

    response = await client.post(
        '/api/rss/delete',
        json={"guild_id": "1", "link": "http://other.com/feed"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404
