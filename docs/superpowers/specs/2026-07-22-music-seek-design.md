# Music Playback Seek — Design

Date: 2026-07-22
Status: Approved by user, ready for implementation planning

## Goal

Let a user jump the currently playing track to a specific timestamp, or skip forward/backward by
some number of seconds, from both Discord (a new `/seek` slash command) and the web dashboard's
music panel (clickable progress bar + ±10s buttons).

## Why

Playback currently has no way to change position within a track — only pause/resume/skip/loop.
Users who mis-click into the wrong part of a long track, or want to skip an intro, have no option
but to let it play or skip the whole track.

## Non-Goals

- No seeking within the `/playnext` insert-at-front flow, or on queued-but-not-yet-playing tracks
  — seeking only ever applies to `current_track[guild_id]`, the track actively feeding the mixer.
- No Discord UI buttons for seek (no fixed-offset buttons on the Discord embed) — `/seek <position>`
  is the only Discord-side surface. Arbitrary numeric/time input doesn't fit a button well, and
  this wasn't requested.
- No seeking on a livestream or any track whose `duration` metadata is falsy, for **absolute**
  positions — relative seeks (`+30`/`-15`) remain allowed since they don't need a known duration.
- No changes to how tracks are queued, resolved, or started — this only affects an already-playing
  `Track`'s in-flight FFmpeg source.

## Current Behavior (for reference)

- `dashboard/audio_mixer.py`'s `Track` wraps a `discord.FFmpegPCMAudio` source created once in
  `_create_source()` from `song_info['url']` (a direct, already-resolved stream URL) plus fixed
  `before_options`/`options` (reconnect flags, `-vn`). `Track.elapsed` is computed from
  `started_at` monotonic time minus accumulated paused duration — there is no concept of a seek
  offset.
- `MixingAudioSource` holds `tracks: list[Track]` behind `self.lock` (a `threading.Lock`, since
  `read()` is called from FFmpeg's mixing thread) and mixes their PCM output every 20ms chunk.
- `commands/music.py`'s `Music` cog exposes `/pause`, `/resume`, `/skip`, `/volume`, `/loop`, etc.,
  each looking up `self.current_track.get(guild_id)` and mutating it or the voice client directly.
- `dashboard/blueprints/music.py`'s `/api/music/control` POST endpoint accepts an `action` field
  (`pause`/`resume`/`skip`/`loop`/`volume`/`remove`) and does the same lookups/mutations
  server-side, mirroring the Discord commands' effects so both surfaces stay in sync.
- `dashboard/templates/music_dashboard.html` renders a non-interactive progress bar
  (`progressBar(elapsed, duration)`, only rendered when `duration` is truthy) and a `controls-row`
  of buttons that all call a shared `ctrl(guildId, action, volume, index)` JS function POSTing to
  `/api/music/control`.

## Design

### 1. `Track.seek()` and `MixingAudioSource.seek_track()` (`dashboard/audio_mixer.py`)

`Track._create_source()` gains an optional `seek_seconds: float = 0` parameter: when nonzero, it
prepends `-ss {seek_seconds} ` to `self.before_options or ''` before constructing the
`discord.FFmpegPCMAudio` (an FFmpeg **input** seek — placed before `-i`, so FFmpeg seeks in the
demuxer rather than decoding-and-discarding from the start; fast for the network stream URLs this
bot plays). The `or ''` guards the (currently unreached in practice, since `_play_song` always
passes real reconnect flags) case where `before_options` is `None`.

`Track` gains:

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

(The `duration - 3` clamp implements "clamp to a few seconds before the end" — landing exactly on
`duration` risks FFmpeg immediately hitting EOF with zero audio read, which could be mistaken for a
read error; 3 seconds of margin guarantees at least one real chunk plays before the track finishes
and the queue advances normally.)

`MixingAudioSource` gains:

```python
def seek_track(self, track_id: str, seconds: float) -> bool:
    with self.lock:
        track = next((t for t in self.tracks if t.id == track_id), None)
        if not track:
            return False
        track.seek(seconds)
        return True
```

The lock matters here for the same reason it already guards `add_track`/`remove_track`: `read()`
runs on FFmpeg's mixing thread and calls `track.source.read()` concurrently with any
command-triggered seek from the asyncio event loop thread. Swapping `self.source` outside the lock
could let the mixing thread read from a source mid-`cleanup()`.

### 2. Position parsing + `Music._seek()` (`commands/music.py`)

A module-level parser, next to the existing `_fmt_duration` import (it lives in
`commands/_music_view.py`, this new function stays in `music.py` since it's seek-specific, not a
general display helper):

```python
def _parse_seek_position(position: str) -> tuple[float, bool]:
    """Parse a /seek argument. Returns (seconds, is_relative).
    '+30' / '-15'  -> relative, signed seconds (also accepts '+1:30' style).
    '90' / '1:30' / '1:02:03' -> absolute, unsigned.
    Raises ValueError with a user-facing message on unparseable input.
    """
```

Leading `+`/`-` decides `is_relative`; the remainder (or the whole string, for absolute) is parsed
as either a bare number of seconds or `MM:SS`/`H:MM:SS` (splitting on `:`, each part an int,
reassembled as `h*3600 + m*60 + s`). Invalid input (empty, non-numeric parts, too many `:`-segments)
raises `ValueError("❌ Couldn't parse a time from '...' — try a number of seconds, MM:SS, or +/-30.")`.

`Music` gains:

```python
async def _seek(self, guild_id: str, target_seconds: float) -> discord.Embed:
    """Seek the currently playing track to target_seconds (already resolved to absolute).
    Raises MusicLookupError if nothing is playing."""
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

Resolving the parsed `(seconds, is_relative)` into `target_seconds` — and the "reject absolute
seek on unknown duration" rule — happens in the `/seek` command itself (music.py:456-area, next to
`/play`), since that's where both the parsed position *and* the live `track` (for `track.elapsed`
and `track.metadata['duration']`) are available together:

```python
@app_commands.command(name="seek", description="⏩ Jump to a time in the current track, or skip +/- seconds.")
@app_commands.describe(position="Absolute: 90, 1:30, 1:02:03 — Relative: +30, -15")
async def seek(self, interaction: discord.Interaction, position: str):
    if not interaction.guild:
        return await interaction.response.send_message("Servers only.", ephemeral=True)
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

(`target < 0` from a large negative relative skip is handled by `Track.seek()`'s own
`max(0.0, seconds)` clamp — no separate check needed here.)

### 3. Dashboard control endpoint (`dashboard/blueprints/music.py`)

`/api/music/control` gains a new branch alongside the existing `pause`/`resume`/`skip`/etc., reusing
`Music._seek()` (not reimplementing the clamp/lookup logic):

```python
elif action == 'seek':
    seconds = data.get('seconds')
    if seconds is not None:
        try:
            await music_cog._seek(guild_id, float(seconds))
        except MusicLookupError:
            pass  # track ended between page render and click; silently ignore like other stale-state actions
```

This matches the existing endpoint's style — other actions (`pause`, `skip`, ...) also don't
surface errors to the dashboard beyond the blanket `{"status": "success"}` response; a stale click
racing a track ending is treated the same way `pause` on an already-finished track is today (silent
no-op).

### 4. Dashboard UI (`dashboard/templates/music_dashboard.html`)

- `ctrl()` gains a `seconds` parameter: `async function ctrl(guildId, action, volume = null, index = null, seconds = null)`, added to the POST body.
- Two new buttons in `.controls-row`, next to the existing Pause/Skip/Loop/Ban buttons:
  ```html
  <button class="btn-eld" onclick="ctrl('${guildId}', 'seek', null, null, ${Math.max(0, track.elapsed - 10)})">⏪ 10s</button>
  <button class="btn-eld" onclick="ctrl('${guildId}', 'seek', null, null, ${track.elapsed + 10})">10s ⏩</button>
  ```
  Only rendered inside the existing `if (isActive)` block (same guard as the other controls) — no
  new visibility logic needed.
- `progressBar(elapsed, duration)` gains an `onclick` on `.progress-bar-wrapper` that computes the
  click fraction and calls `ctrl`:
  ```js
  return `
      <div class="progress-row">
          <div class="progress-bar-wrapper" onclick="seekClick(event, '${guildId}', ${duration})">
              <div class="progress-bar-fill" style="width:${pct}%"></div>
          </div>
          <div class="progress-times"><span>${elStr}</span><span>${durStr}</span></div>
      </div>`;
  ```
  (`progressBar` needs `guildId` threaded in as a new parameter — currently called as
  `progressBar(track.elapsed, track.duration)` with no guild context.) A new helper:
  ```js
  function seekClick(evt, guildId, duration) {
      const rect = evt.currentTarget.getBoundingClientRect();
      const frac = Math.min(1, Math.max(0, (evt.clientX - rect.left) / rect.width));
      ctrl(guildId, 'seek', null, null, frac * duration);
  }
  ```
  Since `progressBar()` is only invoked when `duration` is truthy (existing early-return), this
  click handler always has a real duration to scale against — no unknown-duration case to guard
  here (that case never renders a progress bar at all, both today and after this change).

### 5. Error handling

- Unparseable `/seek` argument → ephemeral error naming the accepted formats (no state change).
- Nothing playing → ephemeral "❌ Nothing is playing." (no state change).
- Absolute seek with unknown duration → ephemeral error suggesting relative seek instead (no state
  change).
- Track finishes/mixer torn down between the `/seek` command's initial checks and the actual
  `mixer.seek_track()` call (a genuine, if narrow, race — e.g. track ends mid-command) →
  `MusicLookupError` from `_seek()`, surfaced as a followup message on the Discord side, silently
  ignored on the dashboard side (matching that endpoint's existing no-feedback style for stale
  actions).
- Dashboard seek requests with a missing/non-numeric `seconds` field are ignored (mirrors the
  existing `volume` branch's use of `data.get(...)`).

### 6. Testing

- `tests/test_dashboard_audio_mixer.py` (new file — no test file exists yet for
  `dashboard/audio_mixer.py`): `Track.seek()` clamps negative input to 0; clamps overshoot to
  `duration - 3` when duration is known; leaves target unclamped when duration is unknown; rebuilds
  `self.source` (old source's `cleanup()` called, new source is a different object) with `-ss`
  injected into `before_options`; resets `started_at` so `elapsed` reflects the new position
  immediately; preserves `paused` state (a paused track seeked mid-pause is still paused
  afterward, and `elapsed` still excludes further paused time). `MixingAudioSource.seek_track()`
  returns `False` for an unknown `track_id` without raising, `True` and delegates to `Track.seek()`
  for a known one.
- `tests/test_commands_music.py` (existing file from the prior playlist-choice feature — extend it,
  don't create a new one): `_parse_seek_position()` covers plain seconds, `MM:SS`, `H:MM:SS`,
  `+30`, `-15`, `+1:30`, and invalid input (raises `ValueError`); the `/seek` command covers
  relative seek (uses `track.elapsed + seconds`), absolute seek with known duration, absolute seek
  rejected on unknown duration, nothing-playing rejection, and unparseable input — all via
  `Music.seek.callback(cog, interaction, position)` per this repo's established pattern for testing
  slash-command bodies directly, mocking `guild_mixers[guild_id].seek_track` rather than exercising
  real FFmpeg.
- `tests/test_blueprint_music.py` (existing file — extend): `/api/music/control` with
  `action: 'seek'` calls `music_cog._seek` with the float-converted `seconds`; a missing `seconds`
  field is a no-op; a `MusicLookupError` from `_seek` doesn't propagate as a 500 (endpoint still
  returns its standard success response, per the "silent no-op" decision above). Follows this
  file's existing `login(client)` + `Origin` header conventions per `CLAUDE.md`'s Testing section.
- No new test file for `music_dashboard.html`'s JS (`seekClick`, `ctrl` changes) — this repo has no
  existing JS test harness for dashboard templates (confirmed: no `.js` test files reference
  `music_dashboard.html`), consistent with how the existing `ctrl()`/`progressBar()` functions are
  untested today. Manual dashboard spot-check covers this per `CLAUDE.md`'s "test the golden path
  in a browser for UI changes" guidance.

## Rollout / Risk

- Three independent-but-related pieces (mixer/Track seek primitive, Discord command, dashboard
  route+UI) — implementable and testable as separate commits/tasks, in the order listed above
  (each layer depends only on the one below it).
- No data-layer changes, no changes to existing commands' behavior — purely additive (`seek`
  action, `/seek` command, two new dashboard buttons + click handler).
- The `duration - 3` clamp and `-ss`-based input seeking are the two judgment calls most likely to
  need real-world tuning (e.g. if some stream URLs don't support fast input seeking and end up
  reading-and-discarding instead, seeking near the end of a long track could be slow) — acceptable
  to ship and revisit if observed, not a blocker.
