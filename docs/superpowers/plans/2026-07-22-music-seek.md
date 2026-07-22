# Music Playback Seek Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user jump the currently playing track to a specific timestamp, or skip forward/backward by some number of seconds, from both a new Discord `/seek` slash command and the web dashboard's music panel (clickable progress bar + ±10s buttons).

**Architecture:** A `Track.seek()` primitive in `dashboard/audio_mixer.py` restarts the FFmpeg source with `-ss` injected into `before_options` and re-bases the elapsed-time bookkeeping; `MixingAudioSource.seek_track()` locks and delegates to it. A `Music._seek()` cog method (guild lookup + mixer dispatch + dashboard refresh) is the single implementation both the new `/seek` command and the dashboard's `/api/music/control` `seek` action call — the command layer parses/validates position text and resolves relative-vs-absolute, the dashboard layer already has an absolute float from the click/button JS.

**Tech Stack:** discord.py 2.7.1, `discord.FFmpegPCMAudio`, Quart (dashboard blueprint), vanilla JS (dashboard template), pytest + pytest-asyncio.

## Global Constraints

- Python 3.11+ union syntax (`X | None`) — matches the rest of the touched files.
- Seeking only ever applies to `current_track[guild_id]` — no changes to queueing, resolution, or how tracks start.
- No Discord UI buttons for seek — `/seek <position>` is the only Discord-side surface.
- Absolute `/seek` positions are rejected when `track.metadata.get('duration')` is falsy ("duration unknown, use +/- instead"); relative seeks remain allowed regardless.
- Overshoot past the end of a track clamps to `duration - 3` seconds (not exactly `duration`) so at least one real audio chunk plays before the track naturally finishes and the queue advances. Undershoot (negative target) clamps to `0`.
- `MixingAudioSource.seek_track()` must take `self.lock` for the swap — `read()` (the mixing thread) and a seek (the asyncio-loop thread) touch `self.source` concurrently otherwise.
- discord.py 2.7.1 UI-test conventions from `CLAUDE.md`'s Testing section apply where relevant (this plan's tests are mostly plain async method / dashboard-route tests, not View/Modal/Select construction, so most of those conventions don't apply here — the ones that do: mock only what a test exercises, `mock.patch()`/`monkeypatch.setattr()` targets the module that looks the name up).
- Dashboard route tests use Quart's test client against the real blueprint-registered `app` from `dashboard.app`, with `login(client)` + an `Origin` header matching the test client's host, per `CLAUDE.md`'s Testing section.
- No JS test harness exists in this repo for dashboard templates — Task 5 (dashboard UI) has no automated test step; it's a structural/manual-verification task, called out explicitly in that task.

---

### Task 1: `Track.seek()` + `MixingAudioSource.seek_track()`

**Files:**
- Modify: `dashboard/audio_mixer.py`
- Create: `tests/test_dashboard_audio_mixer.py`

**Interfaces:**
- Consumes: nothing from other tasks — this is the foundation layer.
- Produces: `Track.seek(seconds: float) -> None` and `MixingAudioSource.seek_track(track_id: str, seconds: float) -> bool`. Consumed by Task 3's `Music._seek()`.

No test file exists yet for `dashboard/audio_mixer.py`. `Track.__init__` calls `discord.FFmpegPCMAudio(...)` directly, which spawns a real `ffmpeg` subprocess — every test in the new file must mock that out via an autouse fixture, never construct a real `Track` without it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dashboard_audio_mixer.py`:

```python
from unittest.mock import MagicMock

import pytest

from dashboard.audio_mixer import Track, MixingAudioSource


@pytest.fixture(autouse=True)
def mock_ffmpeg(monkeypatch):
    """Replace discord.FFmpegPCMAudio with a factory returning a fresh MagicMock per call,
    so tests can construct real Track/MixingAudioSource objects without spawning ffmpeg."""
    def _factory(*args, **kwargs):
        source = MagicMock()
        source.read.return_value = b""
        return source
    mock = MagicMock(side_effect=_factory)
    monkeypatch.setattr("dashboard.audio_mixer.discord.FFmpegPCMAudio", mock)
    return mock


def make_track(**overrides):
    kwargs = dict(
        file_path="http://example.com/stream",
        is_url=True,
        metadata={},
        before_options="-reconnect 1",
        options="-vn",
    )
    kwargs.update(overrides)
    return Track(**kwargs)


class TestTrackSeek:
    def test_seek_clamps_negative_to_zero(self):
        track = make_track(metadata={"duration": 200})
        track.seek(-50)
        assert track.elapsed == pytest.approx(0, abs=0.05)

    def test_seek_clamps_overshoot_to_duration_minus_3(self):
        track = make_track(metadata={"duration": 200})
        track.seek(9999)
        assert track.elapsed == pytest.approx(197, abs=0.05)

    def test_seek_unclamped_when_duration_unknown(self):
        track = make_track(metadata={})
        track.seek(500)
        assert track.elapsed == pytest.approx(500, abs=0.05)

    def test_seek_rebuilds_source_and_cleans_up_old_one(self, mock_ffmpeg):
        track = make_track(metadata={"duration": 200})
        old_source = track.source

        track.seek(30)

        assert track.source is not old_source
        old_source.cleanup.assert_called_once()

    def test_seek_injects_ss_into_before_options(self, mock_ffmpeg):
        track = make_track(metadata={"duration": 200}, before_options="-reconnect 1")
        mock_ffmpeg.reset_mock()

        track.seek(30)

        _, kwargs = mock_ffmpeg.call_args
        assert kwargs["before_options"] == "-ss 30.00 -reconnect 1"

    def test_seek_preserves_paused_state(self):
        track = make_track(metadata={"duration": 200})
        track.paused = True

        track.seek(50)

        assert track.paused is True
        assert track.elapsed == pytest.approx(50, abs=0.05)

    def test_seek_resumes_normal_elapsed_tracking_when_not_paused(self):
        track = make_track(metadata={"duration": 200})
        track.seek(50)
        assert track.elapsed == pytest.approx(50, abs=0.1)


class TestMixingAudioSourceSeekTrack:
    def test_seek_track_returns_false_for_unknown_id(self):
        mixer = MixingAudioSource()
        assert mixer.seek_track("nonexistent", 30) is False

    def test_seek_track_delegates_to_track_seek_and_returns_true(self):
        mixer = MixingAudioSource()
        track = mixer.add_track(file_path="http://x", is_url=True, metadata={"duration": 200})

        result = mixer.seek_track(track.id, 50)

        assert result is True
        assert track.elapsed == pytest.approx(50, abs=0.05)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dashboard_audio_mixer.py -v`
Expected: every test fails with `AttributeError: 'Track' object has no attribute 'seek'` (or the equivalent for `MixingAudioSource.seek_track`).

- [ ] **Step 3: Write minimal implementation**

In `dashboard/audio_mixer.py`, replace the existing `_create_source` method:

```python
    def _create_source(self) -> discord.FFmpegPCMAudio:
        if not self.is_url and not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        return discord.FFmpegPCMAudio(
            self.file_path,
            before_options=self.before_options,
            options=self.options
        )
```

with:

```python
    def _create_source(self, seek_seconds: float = 0) -> discord.FFmpegPCMAudio:
        if not self.is_url and not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        before_options = self.before_options or ''
        if seek_seconds:
            before_options = f"-ss {seek_seconds:.2f} {before_options}".rstrip()
        return discord.FFmpegPCMAudio(
            self.file_path,
            before_options=before_options,
            options=self.options
        )
```

Then add a new `seek` method to `Track`, placed right after `_create_source` and before `read`:

```python
    def seek(self, seconds: float):
        """Restart the FFmpeg source at `seconds` into the track, preserving play/pause state."""
        seconds = max(0.0, seconds)
        duration = self.metadata.get('duration')
        if duration:
            seconds = min(seconds, max(0.0, duration - 3))

        old_source = self.source
        self.source = self._create_source(seek_seconds=seconds)
        try:
            old_source.cleanup()
        except Exception:
            pass

        now = time.monotonic()
        self.started_at = now - seconds
        self._paused_duration = 0.0
        self._paused_since = now if self._paused else None
```

Then add a new `seek_track` method to `MixingAudioSource`, placed right after `get_track` and before `read`:

```python
    def seek_track(self, track_id: str, seconds: float) -> bool:
        with self.lock:
            track = next((t for t in self.tracks if t.id == track_id), None)
            if not track:
                return False
            track.seek(seconds)
            return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dashboard_audio_mixer.py -v`
Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add dashboard/audio_mixer.py tests/test_dashboard_audio_mixer.py
git commit -m "feat: add Track.seek() and MixingAudioSource.seek_track()"
```

---

### Task 2: `_parse_seek_position()` helper

**Files:**
- Modify: `commands/music.py`
- Test: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `_parse_seek_position(position: str) -> tuple[float, bool]` (seconds, is_relative), raising `ValueError` on unparseable input. Consumed by Task 3's `/seek` command.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands_music.py`:

```python
from commands.music import _parse_seek_position


class TestParseSeekPosition:
    def test_plain_seconds_is_absolute(self):
        assert _parse_seek_position("90") == (90.0, False)

    def test_mm_ss_is_absolute(self):
        assert _parse_seek_position("1:30") == (90.0, False)

    def test_h_mm_ss_is_absolute(self):
        assert _parse_seek_position("1:02:03") == (3723.0, False)

    def test_relative_forward_plain_seconds(self):
        assert _parse_seek_position("+30") == (30.0, True)

    def test_relative_backward_plain_seconds(self):
        assert _parse_seek_position("-15") == (-15.0, True)

    def test_relative_forward_mm_ss(self):
        assert _parse_seek_position("+1:30") == (90.0, True)

    def test_relative_backward_mm_ss(self):
        assert _parse_seek_position("-1:30") == (-90.0, True)

    def test_invalid_text_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_seek_position("not-a-time")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_seek_position("")

    def test_too_many_colon_segments_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_seek_position("1:2:3:4")

    def test_bare_sign_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_seek_position("+")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k ParseSeekPosition`
Expected: `ImportError: cannot import name '_parse_seek_position' from 'commands.music'`

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, immediately after `_query_has_explicit_video` (right before `_delete_after`):

```python
def _parse_seek_position(position: str) -> tuple[float, bool]:
    """Parse a /seek argument. Returns (seconds, is_relative).
    '+30' / '-15' / '+1:30' -> relative, signed seconds.
    '90' / '1:30' / '1:02:03' -> absolute, unsigned.
    Raises ValueError with a user-facing message on unparseable input."""
    position = position.strip()
    error = ValueError(
        f"❌ Couldn't parse a time from '{position}' — try a number of seconds, MM:SS, or +/-30."
    )
    if not position:
        raise error

    is_relative = position[0] in ('+', '-')
    sign = -1.0 if position[0] == '-' else 1.0
    body = position[1:] if is_relative else position

    parts = body.split(':')
    if not (1 <= len(parts) <= 3):
        raise error

    try:
        nums = [float(p) for p in parts]
    except ValueError:
        raise error

    seconds = 0.0
    for n in nums:
        seconds = seconds * 60 + n

    if is_relative:
        seconds *= sign

    return seconds, is_relative
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k ParseSeekPosition`
Expected: all 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "feat: add _parse_seek_position helper for /seek argument parsing"
```

---

### Task 3: `Music._seek()` + `/seek` slash command

**Files:**
- Modify: `commands/music.py`
- Test: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: `Track.seek`/`MixingAudioSource.seek_track` (Task 1, via `guild_mixers[guild_id].seek_track(...)`), `_parse_seek_position` (Task 2), `MusicLookupError` (pre-existing in this file), `_fmt_duration` (pre-existing import from `commands._music_view`).
- Produces: `Music._seek(self, guild_id: str, target_seconds: float) -> discord.Embed`, raising `MusicLookupError`. Consumed by the `/seek` command (this task) and by Task 4's dashboard route.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_commands_music.py`:

```python
class TestMusicSeek:
    @pytest.mark.asyncio
    async def test_seek_raises_lookup_error_when_nothing_playing(self):
        cog = make_music_cog()
        with pytest.raises(MusicLookupError, match="Nothing is playing"):
            await cog._seek("g1", 30.0)

    @pytest.mark.asyncio
    async def test_seek_raises_lookup_error_when_track_finished(self):
        cog = make_music_cog()
        cog.current_track["g1"] = MagicMock(finished=True)
        with pytest.raises(MusicLookupError, match="Nothing is playing"):
            await cog._seek("g1", 30.0)

    @pytest.mark.asyncio
    async def test_seek_raises_lookup_error_when_no_mixer(self, monkeypatch):
        monkeypatch.setattr("commands.music.guild_mixers", {})
        cog = make_music_cog()
        track = MagicMock(finished=False, id="t1")
        cog.current_track["g1"] = track
        with pytest.raises(MusicLookupError, match="Could not seek"):
            await cog._seek("g1", 30.0)

    @pytest.mark.asyncio
    async def test_seek_raises_lookup_error_when_mixer_reports_track_gone(self, monkeypatch):
        mixer = MagicMock()
        mixer.seek_track.return_value = False
        monkeypatch.setattr("commands.music.guild_mixers", {"g1": mixer})
        cog = make_music_cog()
        track = MagicMock(finished=False, id="t1")
        cog.current_track["g1"] = track
        with pytest.raises(MusicLookupError, match="Could not seek"):
            await cog._seek("g1", 30.0)

    @pytest.mark.asyncio
    async def test_seek_success_calls_mixer_and_updates_dashboard(self, monkeypatch):
        mixer = MagicMock()
        mixer.seek_track.return_value = True
        monkeypatch.setattr("commands.music.guild_mixers", {"g1": mixer})
        cog = make_music_cog()
        cog._update_dashboard_for_guild = AsyncMock()
        track = MagicMock(finished=False, id="t1", elapsed=30.0, metadata={"duration": 200})
        cog.current_track["g1"] = track

        embed = await cog._seek("g1", 30.0)

        mixer.seek_track.assert_called_once_with("t1", 30.0)
        cog._update_dashboard_for_guild.assert_awaited_once_with("g1")
        # _fmt_duration zero-pads minutes (e.g. 30s -> "00:30", 200s -> "03:20") -- assert
        # the exact strings, not a substring, so this doesn't silently pass on a format change.
        assert "00:30" in embed.description
        assert "03:20" in embed.description

    @pytest.mark.asyncio
    async def test_seek_success_omits_total_duration_when_unknown(self, monkeypatch):
        mixer = MagicMock()
        mixer.seek_track.return_value = True
        monkeypatch.setattr("commands.music.guild_mixers", {"g1": mixer})
        cog = make_music_cog()
        cog._update_dashboard_for_guild = AsyncMock()
        track = MagicMock(finished=False, id="t1", elapsed=30.0, metadata={})
        cog.current_track["g1"] = track

        embed = await cog._seek("g1", 30.0)

        assert "00:30" in embed.description
        assert "/" not in embed.description


class TestSeekCommand:
    @pytest.mark.asyncio
    async def test_relative_seek_adds_to_elapsed(self, monkeypatch):
        cog = make_music_cog()
        cog._seek = AsyncMock(return_value=discord.Embed(description="ok"))
        track = MagicMock(finished=False, elapsed=40.0, metadata={"duration": 200})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "+30")

        cog._seek.assert_awaited_once_with("123", 70.0)
        interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_absolute_seek_uses_position_directly(self, monkeypatch):
        cog = make_music_cog()
        cog._seek = AsyncMock(return_value=discord.Embed(description="ok"))
        track = MagicMock(finished=False, elapsed=40.0, metadata={"duration": 200})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "1:30")

        cog._seek.assert_awaited_once_with("123", 90.0)

    @pytest.mark.asyncio
    async def test_absolute_seek_rejected_when_duration_unknown(self):
        cog = make_music_cog()
        cog._seek = AsyncMock()
        track = MagicMock(finished=False, elapsed=40.0, metadata={})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "1:30")

        cog._seek.assert_not_called()
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.call_args
        assert "duration is unknown" in args[0]

    @pytest.mark.asyncio
    async def test_relative_seek_allowed_when_duration_unknown(self):
        cog = make_music_cog()
        cog._seek = AsyncMock(return_value=discord.Embed(description="ok"))
        track = MagicMock(finished=False, elapsed=40.0, metadata={})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "+10")

        cog._seek.assert_awaited_once_with("123", 50.0)

    @pytest.mark.asyncio
    async def test_nothing_playing_rejected(self):
        cog = make_music_cog()
        cog._seek = AsyncMock()
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "+10")

        cog._seek.assert_not_called()
        interaction.response.send_message.assert_awaited_once_with("❌ Nothing is playing.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_unparseable_position_rejected(self):
        cog = make_music_cog()
        cog._seek = AsyncMock()
        track = MagicMock(finished=False, elapsed=40.0, metadata={"duration": 200})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "garbage")

        cog._seek.assert_not_called()
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lookup_error_from_seek_sent_as_followup(self):
        cog = make_music_cog()
        cog._seek = AsyncMock(side_effect=MusicLookupError("❌ Could not seek — track is no longer active."))
        track = MagicMock(finished=False, elapsed=40.0, metadata={"duration": 200})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "+10")

        interaction.followup.send.assert_awaited_once_with("❌ Could not seek — track is no longer active.")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k "MusicSeek or SeekCommand"`
Expected: `AttributeError: 'Music' object has no attribute '_seek'` (and `AttributeError: type object 'Music' has no attribute 'seek'` for the command tests).

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, add this method to the `Music` class, right after `_update_dashboard_for_guild` and before `refresh_dashboard`:

```python
    async def _seek(self, guild_id: str, target_seconds: float) -> discord.Embed:
        """Seek the currently playing track to target_seconds (already resolved to absolute
        seconds by the caller — this method does no relative-vs-absolute interpretation).
        Raises MusicLookupError if nothing is playing or the track is no longer active."""
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            raise MusicLookupError("❌ Nothing is playing.")

        mixer = guild_mixers.get(guild_id)
        if not mixer or not mixer.seek_track(track.id, target_seconds):
            raise MusicLookupError("❌ Could not seek — track is no longer active.")

        await self._update_dashboard_for_guild(guild_id)
        dur = track.metadata.get('duration')
        return discord.Embed(
            description=f"⏩ Seeked to **{_fmt_duration(track.elapsed)}**" + (f" / {_fmt_duration(dur)}" if dur else ""),
            color=discord.Color.blurple(),
        )
```

Then add this slash command, right after `/volume` (which ends with `await self._update_dashboard_for_guild(guild_id)`) and before `/loop`:

```python
    @app_commands.command(name="seek", description="⏩ Jump to a time in the current track, or skip +/- seconds.")
    @app_commands.describe(position="Absolute: 90, 1:30, 1:02:03 — Relative: +30, -15")
    async def seek(self, interaction: discord.Interaction, position: str):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            return await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

        try:
            seconds, is_relative = _parse_seek_position(position)
        except ValueError as e:
            return await interaction.response.send_message(str(e), ephemeral=True)

        if is_relative:
            target = track.elapsed + seconds
        else:
            if not track.metadata.get('duration'):
                return await interaction.response.send_message(
                    "❌ This track's duration is unknown (likely a livestream) — use a relative "
                    "skip like `+30` or `-15` instead.", ephemeral=True
                )
            target = seconds

        await interaction.response.defer()
        try:
            embed = await self._seek(guild_id, target)
        except MusicLookupError as e:
            return await interaction.followup.send(str(e))
        await interaction.followup.send(embed=embed)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "feat: add Music._seek() and /seek slash command"
```

---

### Task 4: Dashboard `/api/music/control` `seek` action

**Files:**
- Modify: `dashboard/blueprints/music.py`
- Test: `tests/test_blueprint_music.py`

**Interfaces:**
- Consumes: `Music._seek` (Task 3), `MusicLookupError` (pre-existing in `commands/music.py`, newly imported here).
- Produces: nothing consumed by a later task.

- [ ] **Step 1: Write the failing tests**

In `tests/test_blueprint_music.py`, modify `FakeMusicCog` (replace the existing class):

```python
class FakeMusicCog:
    def __init__(self):
        self.current_track = {}
        self.queue = {}
        self.loop_mode = {}
        self.blacklist = []
        self.process_queue_calls = []
        self.seek_calls = []
        self.seek_error = None

    async def _process_queue(self, guild_id):
        self.process_queue_calls.append(guild_id)

    async def _seek(self, guild_id, target_seconds):
        self.seek_calls.append((guild_id, target_seconds))
        if self.seek_error:
            raise self.seek_error
```

Then append these tests at the end of the file:

```python
@pytest.mark.asyncio
async def test_music_control_seek_calls_cog_seek_with_float_seconds(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/control',
        json={"action": "seek", "guild_id": "555", "seconds": 42.5},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.seek_calls == [("555", 42.5)]


@pytest.mark.asyncio
async def test_music_control_seek_missing_seconds_is_noop(client, monkeypatch):
    await login(client)
    cog = FakeMusicCog()
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/control',
        json={"action": "seek", "guild_id": "555"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.seek_calls == []


@pytest.mark.asyncio
async def test_music_control_seek_swallows_music_lookup_error(client, monkeypatch):
    await login(client)
    from commands.music import MusicLookupError
    cog = FakeMusicCog()
    cog.seek_error = MusicLookupError("❌ Nothing is playing.")
    monkeypatch.setattr(app, "bot", FakeBot(cog, guilds=[FakeGuild(555)]))

    response = await client.post(
        '/api/music/control',
        json={"action": "seek", "guild_id": "555", "seconds": 10},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert cog.seek_calls == [("555", 10.0)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_blueprint_music.py -v -k seek`
Expected: all 3 new tests fail — the `music_control` view function has no `'seek'` branch, so `cog.seek_calls` stays empty for the first and third tests (assertion failure), and the second test may pass vacuously; re-run after Step 3 to confirm real coverage either way.

- [ ] **Step 3: Write minimal implementation**

In `dashboard/blueprints/music.py`, add the import at the top of the file (after the existing `loadnsave` import):

```python
from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from dashboard.state import server_volumes
from loadnsave import save_server_volumes, save_music_blacklist
from commands.music import MusicLookupError
```

Then add a new branch to `music_control()`, right after the existing `elif action == 'volume':` block (which ends with `track.volume = (clamped / 100.0) ** 2  # log-scale amplitude for PCM`) and before `elif action == 'remove':`:

```python
    elif action == 'seek':
        seconds = data.get('seconds')
        if seconds is not None:
            try:
                await music_cog._seek(guild_id, float(seconds))
            except MusicLookupError:
                pass  # track ended between page render and click; silently ignore like other stale-state actions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_blueprint_music.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add dashboard/blueprints/music.py tests/test_blueprint_music.py
git commit -m "feat: add seek action to /api/music/control"
```

---

### Task 5: Dashboard UI (progress bar click + ±10s buttons)

**Files:**
- Modify: `dashboard/templates/music_dashboard.html`

**Interfaces:**
- Consumes: the `seek` action from Task 4's `/api/music/control`.
- Produces: nothing consumed by a later task.

This task has no automated test — this repo has no JS test harness for dashboard templates (no `.js` test files reference `music_dashboard.html`, and the existing `ctrl()`/`progressBar()` functions are untested today). Verification is structural (grep-based, shown below) plus a note that a human should manually spot-check in a browser before considering this shipped, per `CLAUDE.md`'s "test the golden path in a browser for UI changes" guidance — an implementer without a running bot/dashboard cannot do that part itself and should say so rather than claim it.

- [ ] **Step 1: Update `ctrl()` to carry a `seconds` parameter**

In `dashboard/templates/music_dashboard.html`, replace:

```javascript
async function ctrl(guildId, action, volume = null, index = null) {
    await fetch('/api/music/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guild_id: guildId, action, volume, index })
    });
    await updateMusicData();
}
```

with:

```javascript
async function ctrl(guildId, action, volume = null, index = null, seconds = null) {
    await fetch('/api/music/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guild_id: guildId, action, volume, index, seconds })
    });
    await updateMusicData();
}
```

- [ ] **Step 2: Make the progress bar clickable**

Replace the `progressBar` function:

```javascript
function progressBar(elapsed, duration) {
    if (!duration || duration <= 0) return '';
    const pct = Math.min(100, Math.max(0, (elapsed / duration) * 100)).toFixed(1);
    const elStr = fmtDur(elapsed) || '0:00';
    const durStr = fmtDur(duration) || '?:??';
    return `
        <div class="progress-row">
            <div class="progress-bar-wrapper">
                <div class="progress-bar-fill" style="width:${pct}%"></div>
            </div>
            <div class="progress-times"><span>${elStr}</span><span>${durStr}</span></div>
        </div>`;
}
```

with:

```javascript
function progressBar(elapsed, duration, guildId) {
    if (!duration || duration <= 0) return '';
    const pct = Math.min(100, Math.max(0, (elapsed / duration) * 100)).toFixed(1);
    const elStr = fmtDur(elapsed) || '0:00';
    const durStr = fmtDur(duration) || '?:??';
    return `
        <div class="progress-row">
            <div class="progress-bar-wrapper" onclick="seekClick(event, '${guildId}', ${duration})">
                <div class="progress-bar-fill" style="width:${pct}%"></div>
            </div>
            <div class="progress-times"><span>${elStr}</span><span>${durStr}</span></div>
        </div>`;
}

function seekClick(evt, guildId, duration) {
    const rect = evt.currentTarget.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (evt.clientX - rect.left) / rect.width));
    ctrl(guildId, 'seek', null, null, frac * duration);
}
```

- [ ] **Step 3: Thread `guildId` into the `progressBar` call site**

In `renderGuild`, replace:

```javascript
        const progHtml = progressBar(track.elapsed, track.duration);
```

with:

```javascript
        const progHtml = progressBar(track.elapsed, track.duration, guildId);
```

- [ ] **Step 4: Add ±10s buttons to the controls row**

Replace:

```javascript
            <div class="controls-row">
                ${pauseBtn}
                <button class="btn-eld" onclick="ctrl('${guildId}', 'skip')">⌁ SKIP</button>
                <button class="btn-eld ${loopClass}" onclick="ctrl('${guildId}', 'loop')">◎ LOOP MODE</button>
                <button class="btn-eld rust" onclick="banTrack('${guildId}', '${url}')">⌫ BAN SONG</button>
            </div>`;
```

with:

```javascript
            <div class="controls-row">
                ${pauseBtn}
                <button class="btn-eld" onclick="ctrl('${guildId}', 'seek', null, null, ${Math.max(0, track.elapsed - 10)})">⏪ 10s</button>
                <button class="btn-eld" onclick="ctrl('${guildId}', 'seek', null, null, ${track.elapsed + 10})">10s ⏩</button>
                <button class="btn-eld" onclick="ctrl('${guildId}', 'skip')">⌁ SKIP</button>
                <button class="btn-eld ${loopClass}" onclick="ctrl('${guildId}', 'loop')">◎ LOOP MODE</button>
                <button class="btn-eld rust" onclick="banTrack('${guildId}', '${url}')">⌫ BAN SONG</button>
            </div>`;
```

- [ ] **Step 5: Structural verification**

Run:
```bash
grep -n "function seekClick\|function ctrl\|function progressBar\|progressBar(track.elapsed" dashboard/templates/music_dashboard.html
grep -c "onclick=\"ctrl(" dashboard/templates/music_dashboard.html
```
Expected: `seekClick`, `ctrl`, and `progressBar` function definitions are all present; `progressBar(track.elapsed, track.duration, guildId)` is found (three args, not two); the `onclick="ctrl(` count is `7` (5 before this task — the `resume`/`pause` ternary's two branches, `skip`, `loop`, `remove` — plus the 2 new ±10s buttons this task adds; `volume`'s handler uses `onchange`, not `onclick`, so it was never in this count).

Note in your report that a human should open `/admin/music` in a browser with a track playing and confirm: clicking partway across the progress bar seeks there, the ⏪10s/10s⏩ buttons nudge playback, and existing controls (pause/skip/loop/ban/volume) still work — this wasn't run as part of this task since it requires a live bot + browser.

- [ ] **Step 6: Commit**

```bash
git add dashboard/templates/music_dashboard.html
git commit -m "feat: add clickable progress bar and +/-10s buttons to music dashboard"
```

---

### Task 6: Full regression pass

**Files:**
- Verify only — no source changes expected unless this step uncovers a regression.

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: nothing — this is the last task in the plan.

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass, including the pre-existing suite plus every test added in Tasks 1-4 — no regressions in any other module (in particular: `/pause`, `/resume`, `/volume`, and the dashboard's existing `pause`/`resume`/`skip`/`loop`/`volume`/`remove` actions, none of which this plan's code changes touch, but all of which share `commands/music.py` and `dashboard/blueprints/music.py` with this feature's new code).

- [ ] **Step 2: Manually re-read `Track.seek()` and `MixingAudioSource.seek_track()` against the design's locking requirement**

Run:
```bash
grep -n "def read\|def seek_track\|with self.lock" dashboard/audio_mixer.py
```
Confirm by inspection: `MixingAudioSource.read()` and `MixingAudioSource.seek_track()` both acquire `self.lock` before touching `self.tracks`/a track's `self.source` — the concurrency guard the design called out (mixing thread vs. asyncio-loop-thread seek) is actually in place, not just described.

- [ ] **Step 3: Commit (only if Step 1 required a fix)**

```bash
git add -A
git commit -m "fix: address regression found in music-seek full-suite pass"
```

If Step 1 found no regressions, skip this step — there is nothing to commit.

---

## Self-Review Notes

- **Spec coverage:** design spec section 1 (`Track.seek()`/`MixingAudioSource.seek_track()`) → Task 1; section 2 (position parsing + `Music._seek()`/`/seek` command) → Tasks 2-3; section 3 (dashboard control endpoint) → Task 4; section 4 (dashboard UI) → Task 5; section 5 (error handling) → covered across Tasks 3-4's tests; section 6 (testing) → each task's own test steps, including the explicit no-JS-harness carve-out for Task 5 that the spec itself calls for.
- **Placeholder scan:** no TBD/TODO; every step has literal code or literal shell commands with a stated expected output.
- **Type consistency:** `Music._seek(guild_id: str, target_seconds: float) -> discord.Embed` matches between its Task 3 definition and Task 4's dashboard-route call site (`await music_cog._seek(guild_id, float(seconds))`) and Task 3's own `/seek` command call site (`await self._seek(guild_id, target)`). `Track.seek(seconds: float)` and `MixingAudioSource.seek_track(track_id: str, seconds: float) -> bool` are consistent between Task 1's definition and Task 3's `_seek()` usage (`mixer.seek_track(track.id, target_seconds)`). `_parse_seek_position(position: str) -> tuple[float, bool]` is consistent between Task 2's definition and Task 3's `/seek` command usage.
