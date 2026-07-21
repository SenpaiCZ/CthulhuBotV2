import os

import pytest
import discord
from unittest.mock import AsyncMock, patch

import loadnsave
from dashboard.app import app
import dashboard.blueprints.soundboard as soundboard


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
def isolated_soundboard_env(tmp_path, monkeypatch):
    # soundboard.py does `from dashboard.state import SOUNDBOARD_FOLDER, server_volumes,
    # guild_mixers` -- SOUNDBOARD_FOLDER is a plain string, imported BY VALUE, so
    # patching dashboard.state.SOUNDBOARD_FOLDER would NOT affect this blueprint's
    # own copy. It must be patched on the blueprint module directly.
    # server_volumes/guild_mixers are dicts (mutable, imported by reference) but we
    # still swap in fresh ones per-test to avoid cross-test leakage.
    soundboard_dir = tmp_path / "soundboard"
    soundboard_dir.mkdir()
    monkeypatch.setattr(soundboard, "SOUNDBOARD_FOLDER", str(soundboard_dir))
    monkeypatch.setattr(soundboard, "server_volumes", {})
    monkeypatch.setattr(soundboard, "guild_mixers", {})

    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path / "data"))
    monkeypatch.setattr(loadnsave, "_SOUNDBOARD_SETTINGS_CACHE", None)
    monkeypatch.setattr(loadnsave, "_SERVER_VOLUMES_CACHE", None)
    return soundboard_dir


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


class FakeMixer(discord.AudioSource):
    """
    Stands in for audio_mixer.MixingAudioSource. Subclassing discord.AudioSource
    lets it pass through discord.PCMVolumeTransformer's real isinstance/is_opus
    checks unmodified, while add_track/get_track/remove_track/cleanup are
    lightweight and never spawn ffmpeg (unlike the real Track class).
    """
    def __init__(self):
        self._tracks = {}
        self._next_id = 1
        self.cleaned_up = False

    def read(self):
        return b""

    def add_track(self, file_path, volume=0.5, loop=False, metadata=None):
        track_id = str(self._next_id)
        self._next_id += 1
        track = type("FakeTrack", (), {})()
        track.id = track_id
        track.file_path = file_path
        track.volume = volume
        track.loop = loop
        track.paused = False
        track.finished = False
        track.metadata = metadata or {}
        self._tracks[track_id] = track
        return track

    def get_track(self, track_id):
        return self._tracks.get(track_id)

    def remove_track(self, track_id):
        return self._tracks.pop(track_id, None) is not None

    def cleanup(self):
        self.cleaned_up = True
        self._tracks.clear()

    @property
    def tracks(self):
        return list(self._tracks.values())

    @property
    def lock(self):
        import threading
        return threading.Lock()


class FakeVoiceClient:
    def __init__(self, connected=True, playing=False, channel=None):
        self._connected = connected
        self._playing = playing
        self.channel = channel
        self.source = None
        self.stopped = False
        self.disconnected = False

    def is_connected(self):
        return self._connected

    def is_playing(self):
        return self._playing

    def play(self, source):
        self.source = source
        self._playing = True

    def stop(self):
        self.stopped = True
        self._playing = False

    async def disconnect(self, force=False):
        self.disconnected = True


class FakeGuild:
    def __init__(self, id, voice_client=None):
        self.id = id
        self.name = f"Guild{id}"
        self.voice_channels = []
        self.voice_client = voice_client


class FakeBot:
    def __init__(self, guilds=None):
        self.guilds = guilds or []

    def get_guild(self, guild_id):
        return next((g for g in self.guilds if g.id == guild_id), None)


def make_audio_file(soundboard_dir, name="sound.mp3"):
    path = soundboard_dir / name
    path.write_bytes(b"fake-audio-bytes")
    return name


# --- /api/soundboard/data ---

@pytest.mark.asyncio
async def test_soundboard_data_no_bot_returns_empty(client):
    await login(client)
    response = await client.get('/api/soundboard/data')
    assert response.status_code == 200
    data = await response.get_json()
    assert data == {"guilds": [], "files": {}, "status": {}, "settings": {}}


# --- /api/soundboard/play ---

@pytest.mark.asyncio
async def test_soundboard_play_missing_arguments_returns_400(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/play', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_soundboard_play_blocks_path_traversal(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/play',
        json={"guild_id": "555", "channel_id": "1", "file_path": "../../etc/passwd"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400
    data = await response.get_json()
    assert "Invalid file path" in data["message"]


@pytest.mark.asyncio
async def test_soundboard_play_file_not_found_returns_404(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/play',
        json={"guild_id": "555", "channel_id": "1", "file_path": "missing.mp3"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_soundboard_play_voice_join_failure_returns_500(client, isolated_soundboard_env):
    await login(client)
    filename = make_audio_file(isolated_soundboard_env)
    with patch('dashboard.blueprints.soundboard.get_or_join_voice_channel',
               new_callable=AsyncMock) as mock_join:
        mock_join.return_value = (None, "Connection timed out.")
        response = await client.post(
            '/api/soundboard/play',
            json={"guild_id": "555", "channel_id": "1", "file_path": filename},
            headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 500
        data = await response.get_json()
        assert data["message"] == "Connection timed out."


@pytest.mark.asyncio
async def test_soundboard_play_creates_mixer_and_adds_track_with_computed_volume(client, isolated_soundboard_env):
    await login(client)
    filename = make_audio_file(isolated_soundboard_env)
    vc = FakeVoiceClient(connected=True, playing=False)

    soundboard.server_volumes["555"] = {"music": 1.0, "soundboard": 0.5}

    # `_soundboard_play_inner` instantiates `MixingAudioSource()` directly when no
    # mixer exists yet for the guild. The real class builds a `Track`, whose
    # `_create_source()` shells out to a real `ffmpeg` binary -- not available in
    # this sandbox (no ffmpeg on PATH). Substitute `FakeMixer` at the blueprint's
    # own by-name import site so the route's mixer-creation/add_track/volume-math
    # logic is still exercised for real, without spawning a subprocess.
    with patch('dashboard.blueprints.soundboard.MixingAudioSource', FakeMixer), \
         patch('dashboard.blueprints.soundboard.get_or_join_voice_channel',
               new_callable=AsyncMock) as mock_join:
        mock_join.return_value = (vc, None)
        response = await client.post(
            '/api/soundboard/play',
            json={"guild_id": "555", "channel_id": "1", "file_path": filename, "volume_modifier": 0.5},
            headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 200

        mixer = soundboard.guild_mixers["555"]
        assert isinstance(mixer, discord.AudioSource)
        assert len(mixer.tracks) == 1
        track = mixer.tracks[0]
        assert track.volume == pytest.approx(0.5 * 0.5)  # sb_vol(0.5) * volume_modifier(0.5)
        assert vc.source is not None  # voice_client.play() was called


@pytest.mark.asyncio
async def test_soundboard_play_reuses_existing_mixer_object(client, isolated_soundboard_env):
    await login(client)
    filename = make_audio_file(isolated_soundboard_env)
    existing_mixer = FakeMixer()
    soundboard.guild_mixers["555"] = existing_mixer
    vc = FakeVoiceClient(connected=True, playing=False)

    with patch('dashboard.blueprints.soundboard.get_or_join_voice_channel',
               new_callable=AsyncMock) as mock_join:
        mock_join.return_value = (vc, None)
        response = await client.post(
            '/api/soundboard/play',
            json={"guild_id": "555", "channel_id": "1", "file_path": filename},
            headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 200
        assert soundboard.guild_mixers["555"] is existing_mixer
        assert len(existing_mixer.tracks) == 1


# --- /api/soundboard/join, /leave, /stop ---

@pytest.mark.asyncio
async def test_soundboard_join_missing_arguments_returns_400(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/join', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_soundboard_leave_disconnects_and_cleans_mixer(client, isolated_soundboard_env, monkeypatch):
    await login(client)
    vc = FakeVoiceClient()
    guild = FakeGuild(555, voice_client=vc)
    monkeypatch.setattr(app, "bot", FakeBot(guilds=[guild]))

    mixer = FakeMixer()
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/leave', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert vc.disconnected is True
    assert mixer.cleaned_up is True
    assert "555" not in soundboard.guild_mixers


@pytest.mark.asyncio
async def test_soundboard_stop_clears_mixer_tracks_without_disconnecting(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    mixer.add_track("x.mp3")
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/stop', json={"guild_id": "555"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert mixer.cleaned_up is True


# --- /api/soundboard/volume (master) ---

@pytest.mark.asyncio
async def test_soundboard_volume_clamps_and_updates_active_soundboard_tracks(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    track = mixer.add_track("x.mp3", volume=0.1, metadata={"type": "soundboard", "volume_modifier": 0.5})
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/volume',
        json={"guild_id": "555", "volume": 200},  # out of range, clamps to 100
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert soundboard.server_volumes["555"]["soundboard"] == 1.0
    assert track.volume == pytest.approx(1.0 * 0.5)

    reloaded = await loadnsave.load_server_volumes()
    assert reloaded["555"]["soundboard"] == 1.0


@pytest.mark.asyncio
async def test_soundboard_volume_invalid_value_returns_400(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/volume',
        json={"guild_id": "555", "volume": "not-a-number"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


# --- /api/soundboard/track/* ---

@pytest.mark.asyncio
async def test_track_volume_no_active_mixer_returns_404(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/track/volume',
        json={"guild_id": "555", "track_id": "1", "volume": 50},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_track_volume_updates_clamped_value(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    track = mixer.add_track("x.mp3")
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/track/volume',
        json={"guild_id": "555", "track_id": track.id, "volume": 150},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert track.volume == 1.0


@pytest.mark.asyncio
async def test_track_loop_toggles_flag(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    track = mixer.add_track("x.mp3", loop=False)
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/track/loop',
        json={"guild_id": "555", "track_id": track.id, "loop": True},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert track.loop is True


@pytest.mark.asyncio
async def test_track_pause_sets_flag(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    track = mixer.add_track("x.mp3")
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/track/pause',
        json={"guild_id": "555", "track_id": track.id, "paused": True},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert track.paused is True


@pytest.mark.asyncio
async def test_track_remove_not_found_returns_404(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/track/remove',
        json={"guild_id": "555", "track_id": "nonexistent"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_track_remove_success(client, isolated_soundboard_env):
    await login(client)
    mixer = FakeMixer()
    track = mixer.add_track("x.mp3")
    soundboard.guild_mixers["555"] = mixer

    response = await client.post(
        '/api/soundboard/track/remove',
        json={"guild_id": "555", "track_id": track.id},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert mixer.get_track(track.id) is None
