import pytest
from unittest.mock import AsyncMock, patch

import loadnsave
from dashboard.app import app
import dashboard.blueprints.music as music


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
    monkeypatch.setattr(loadnsave, "_SERVER_VOLUMES_CACHE", None)
    monkeypatch.setattr(loadnsave, "_MUSIC_BLACKLIST_CACHE", None)
    # music.py does `from dashboard.state import server_volumes` -- a dict
    # object, imported by reference, so mutating it in the route mutates the
    # same dict everywhere. We swap the blueprint's own binding for a fresh
    # dict so tests don't leak state into each other or into dashboard.state.
    monkeypatch.setattr(music, "server_volumes", {})
    return tmp_path


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


class FakeTrack:
    def __init__(self, title="Song", url="http://example.com/song", thumbnail="thumb.png",
                 volume=1.0, loop=False, paused=False, finished=False, duration=100, elapsed=1.5):
        self.metadata = {"title": title, "original_url": url, "thumbnail": thumbnail, "duration": duration}
        self.volume = volume
        self.loop = loop
        self.paused = paused
        self.finished = finished
        self.elapsed = elapsed


class FakeMusicCog:
    def __init__(self):
        self.current_track = {}
        self.queue = {}
        self.loop_mode = {}
        self.blacklist = []
        self.process_queue_calls = []

    async def _process_queue(self, guild_id):
        self.process_queue_calls.append(guild_id)


class FakeVoiceClient:
    def __init__(self):
        self.paused = False
        self.resumed = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.resumed = True


class FakeGuild:
    def __init__(self, id, voice_client=None):
        self.id = id
        self.name = f"Guild{id}"
        self.voice_client = voice_client


class FakeBot:
    def __init__(self, music_cog, guilds=None):
        self.music_cog = music_cog
        self.guilds = guilds or []

    def get_guild(self, guild_id):
        return next((g for g in self.guilds if g.id == guild_id), None)


@pytest.mark.asyncio
async def test_music_data_no_bot_returns_empty_guilds(client):
    await login(client)
    response = await client.get('/api/music/data')
    assert response.status_code == 200
    assert await response.get_json() == {"guilds": {}}


@pytest.mark.asyncio
async def test_music_data_reports_current_track_and_queue(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    cog.current_track["555"] = FakeTrack(title="Ia Ia", volume=0.75, loop=True)
    cog.loop_mode["555"] = "track"
    cog.queue["555"] = [{"title": "Next", "original_url": "u", "thumbnail": "t", "duration": 50}]
    cog.blacklist = ["http://banned"]
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.get('/api/music/data')
    assert response.status_code == 200
    data = await response.get_json()
    assert data["guilds"]["555"]["current_track"]["title"] == "Ia Ia"
    assert data["guilds"]["555"]["current_track"]["volume"] == 75
    assert data["guilds"]["555"]["current_track"]["loop_mode"] == "track"
    assert data["guilds"]["555"]["queue"][0]["title"] == "Next"
    assert data["blacklist"] == ["http://banned"]


@pytest.mark.asyncio
async def test_music_data_hides_finished_track(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    cog.current_track["555"] = FakeTrack(finished=True)
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.get('/api/music/data')
    data = await response.get_json()
    assert data["guilds"]["555"]["current_track"] is None


@pytest.mark.asyncio
async def test_music_control_pause_pauses_track_and_voice_client(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    track = FakeTrack(paused=False)
    cog.current_track["555"] = track
    vc = FakeVoiceClient()
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555, voice_client=vc)]))

    response = await client.post(
        '/api/music/control',
        json={"action": "pause", "guild_id": "555"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert track.paused is True
    assert vc.paused is True


@pytest.mark.asyncio
async def test_music_control_skip_marks_finished_and_processes_queue(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    track = FakeTrack(finished=False)
    cog.current_track["555"] = track
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/control',
        json={"action": "skip", "guild_id": "555"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert track.finished is True
    assert cog.process_queue_calls == ["555"]


@pytest.mark.asyncio
async def test_music_control_loop_cycles_off_to_track_to_queue_to_off(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    track = FakeTrack(finished=False)
    cog.current_track["555"] = track
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    async def cycle():
        return await client.post(
            '/api/music/control',
            json={"action": "loop", "guild_id": "555"},
            headers={"Origin": "http://localhost"}
        )

    await cycle()
    assert cog.loop_mode["555"] == "track"
    assert track.loop is True

    await cycle()
    assert cog.loop_mode["555"] == "queue"
    assert track.loop is False

    await cycle()
    assert cog.loop_mode["555"] == "off"
    assert track.loop is False


@pytest.mark.asyncio
async def test_music_control_volume_clamps_and_persists(client, isolated_data_dir, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    track = FakeTrack()
    cog.current_track["555"] = track
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/control',
        json={"action": "volume", "guild_id": "555", "volume": 150},  # out of range
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert music.server_volumes["555"]["music"] == 1.0  # clamped to 100 -> 1.0
    assert track.volume == 1.0 ** 2

    reloaded = await loadnsave.load_server_volumes()
    assert reloaded["555"]["music"] == 1.0


@pytest.mark.asyncio
async def test_music_control_remove_pops_queue_index(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    cog.queue["555"] = [{"title": "A"}, {"title": "B"}]
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/control',
        json={"action": "remove", "guild_id": "555", "index": 0},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.queue["555"] == [{"title": "B"}]


@pytest.mark.asyncio
async def test_music_ban_missing_url_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/music/ban', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_music_ban_adds_url_persists_and_skips_playing_track(client, isolated_data_dir, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    track = FakeTrack(url="http://example.com/banned", finished=False)
    cog.current_track["555"] = track
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/ban',
        json={"url": "http://example.com/banned"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.blacklist == ["http://example.com/banned"]
    assert track.finished is True

    reloaded = await loadnsave.load_music_blacklist()
    assert reloaded == ["http://example.com/banned"]


@pytest.mark.asyncio
async def test_music_ban_does_not_duplicate_existing_entry(client, isolated_data_dir, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    cog.blacklist = ["http://example.com/banned"]
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/ban',
        json={"url": "http://example.com/banned"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.blacklist == ["http://example.com/banned"]
