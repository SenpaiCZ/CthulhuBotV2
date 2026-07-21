# Playlist vs. Single-Song Choice on `/play` — Design

Date: 2026-07-21
Status: Approved by user, ready for implementation planning

## Goal

When a user runs `/play` with a link that resolves to more than one track (a playlist link, or a
`watch?v=...&list=...` link that references both a specific video and a playlist), let the user
choose whether to queue just the one song or the entire playlist, instead of always loading the
whole playlist as today.

## Why

`commands/music.py`'s `_is_playlist_url()` (music.py:60) currently treats any URL containing
`list=` or `/playlist` as "load the whole playlist," with no way to say "I just wanted that one
song." This is a common false positive: a user pasting a video link copied while browsing a
playlist (`watch?v=XXXX&list=YYYY`) gets the entire playlist queued instead of the single video
they meant to share.

## Non-Goals

- No change to non-ambiguous cases: a plain video URL, a search query, or a playlist link that
  resolves to exactly one track all behave exactly as today (no prompt).
- No support for choosing an arbitrary track from the middle of a playlist — the "just one song"
  choice is either the video explicitly referenced in the URL, or (for a bare playlist link with
  no video reference) the playlist's first track.
- No changes to non-YouTube sources, blacklist logic, streaming/FFmpeg playback, or the dashboard
  `MusicView` rendering.

## Current Behavior (for reference)

In `play()` (music.py:456-625):
1. `_is_playlist_url(query)` decides playlist vs. single-track extraction.
2. Playlist branch: flat extraction (`YTDL_PLAYLIST` opts) → filters entries with a `url` → appends
   every entry to `self.queue[guild_id]` → sends a "📥 Playlist Added" embed.
3. Single-track branch: full extraction (`YTDL_BASE` opts, `noplaylist: True`) → blacklist check →
   appends one `song_info` dict to the queue → sends either an "Added to Queue" embed (if something
   is already playing) or falls through to the shared trailing block.
4. Trailing block (music.py:603-625, shared by both branches unless the single-track "already
   playing" case returned early): updates/sends the dashboard `MusicView` message, and starts
   playback if nothing is currently playing.

## Design

### 1. Branch point in `play()`

The playlist branch's flat extraction happens exactly as it does today, unconditionally (needed
either way to know the track count). After filtering entries:

- `len(entries) <= 1` → **unchanged**: proceed directly to queueing that single entry via the
  existing playlist-append logic (now factored into `_queue_playlist_entries`, see below), no
  prompt. There is no real choice when the "playlist" only has one track.
- `len(entries) > 1` → **new**: instead of queueing anything yet, send a confirmation embed with a
  `PlaylistChoiceView` and return. The queueing happens in the view's button callbacks.

### 2. Link-shape detection

A small helper, `_query_has_explicit_video(query: str) -> bool`, returns `True` if the query
contains `v=` (as a URL parameter — check for `v=` preceded by `?` or `&`) or `youtu.be/`. This
decides:
- Button label: `"🎵 Just this song"` (explicit video) vs. `"🎵 Just the first song"` (bare
  playlist link).
- What "just this song" resolves to: the *original query string* (explicit-video case — the
  existing single-track extraction already sets `noplaylist: True` in `YTDL_BASE`, which makes
  yt-dlp isolate that one video even though the URL also carries a `list=` param) vs. `entries[0]`'s
  URL (bare-playlist case, already available from the flat extraction — no extra yt-dlp call).

### 3. `PlaylistChoiceView` (new class, `commands/music.py`, placed next to the existing
`CookieView` — same file, same pattern, no new companion file needed for one small View class)

```python
class PlaylistChoiceView(discord.ui.View):
    def __init__(self, cog, guild_id, requester_id, single_query, entries, playlist_title):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.requester_id = requester_id
        self.single_query = single_query    # original query or entries[0]'s URL
        self.entries = entries              # already-fetched flat entries
        self.playlist_title = playlist_title
        self.message = None                 # set after send, used by on_timeout

    async def interaction_check(self, interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("This choice isn't for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="...", style=discord.ButtonStyle.primary)
    async def just_one(self, interaction, button): ...

    @discord.ui.button(label="Whole playlist (N)", style=discord.ButtonStyle.secondary)
    async def whole_playlist(self, interaction, button): ...

    async def on_timeout(self):
        # disable buttons, edit self.message to say the choice expired
        ...
```

Button labels are set at construction time (not hardcoded in the decorator) since they depend on
the link shape and track count — set via `self.just_one.label = ...` etc. in `__init__`.

Each button callback:
1. `await interaction.response.defer()` (extraction takes a network round-trip).
2. Calls `_queue_single_track(...)` or `_queue_playlist_entries(...)` (see below) to do the actual
   queueing. Both return `(embed, already_playing)` — see helper signatures below.
3. Edits the original choice message (`self.message`) to that `embed`, removing the view
   (`view=None`).
4. If `already_playing` is `True`, also calls `_update_dashboard_for_guild(guild_id)` (matching
   today's single-track "already playing" branch) and stops there. If `False`, calls
   `_finalize_play(interaction, guild_id)` next, which sends/updates the separate dashboard
   `MusicView` panel message — a different message from the choice prompt just edited in step 3.
5. Same `try`/`except yt_dlp.utils.DownloadError` / generic `Exception` handling as the direct
   path, edited into the choice message on failure (age-restriction, private, unavailable, generic
   — same branches and messages as today).

### 4. Cog helper methods (extracted from today's linear `play()` body — behavior-preserving)

Both helpers return `(embed: discord.Embed, already_playing: bool)` so callers can decide how to
deliver the embed (send a new followup vs. edit an existing choice message) without the helper
needing to know which context it's called from:

- `_queue_playlist_entries(self, guild_id, entries, playlist_title, requester) -> (discord.Embed,
  bool)`: today's playlist-append loop (blacklist filtering, appending each entry with
  `needs_resolve: True`, building the "📥 Playlist Added" embed). `already_playing` is always
  `False` here — queueing a playlist never short-circuits the dashboard/playback-start step, exactly
  like today.
- `_queue_single_track(self, guild_id, query, requester) -> (discord.Embed | None, bool)`: today's
  single-track full extraction, blacklist check, and queue append. Preserves today's branch
  exactly: if something is already playing, returns the "Added to Queue" embed with
  `already_playing=True`; otherwise queues the track and returns `(None, False)`.
- `_finalize_play(self, interaction, guild_id)`: today's trailing block — update-or-send the
  dashboard `MusicView` message, start playback if idle. Called only when `already_playing` is
  `False`.

`play()`'s body becomes: ensure voice → defer → determine playlist vs. single via
`_is_playlist_url` → for the single-track path: call `_queue_single_track`; if `already_playing`,
send its embed as a followup (`_delete_after(..., 15)` as today) and call
`_update_dashboard_for_guild`; otherwise call `_finalize_play`. For the playlist path: do the flat
extraction, and either call `_queue_playlist_entries` (send its embed as a followup with
`_delete_after(..., 10)`, then `_finalize_play`, exactly as today) when `len(entries) <= 1`, or send
the `PlaylistChoiceView` and return when `len(entries) > 1`. The `just_one` and `whole_playlist`
button callbacks follow the same "call helper → branch on `already_playing`" sequence as the direct
path, but edit the existing choice message instead of sending a new followup.

### 5. Error handling

Identical error categories and messages to today (age-restricted/cookie prompt, private,
unavailable, generic download error, unexpected exception) — just triggered from three call sites
now (the direct single-track path, and the two button callbacks) instead of one. No new error
categories are introduced.

### 6. Testing

New `tests/test_commands_music.py`:
- `_query_has_explicit_video()` — explicit-video vs. bare-playlist URL shapes.
- `play()` with a playlist link resolving to 1 entry → queues directly, no view sent (mocking
  `yt_dlp.YoutubeDL.extract_info` to return a single-entry flat result).
- `play()` with a playlist link resolving to >1 entries → sends a message with a
  `PlaylistChoiceView`, queue is untouched until a button fires.
- `PlaylistChoiceView.just_one` callback (explicit-video case) queues via the original query,
  editing the message to an "Added to Queue"/single-track embed.
- `PlaylistChoiceView.just_one` callback (bare-playlist case) queues via `entries[0]`'s URL.
- `PlaylistChoiceView.whole_playlist` callback queues all filtered entries via
  `_queue_playlist_entries`.
- `interaction_check` rejects a non-requester click (ephemeral message, no queue mutation).
- `on_timeout` disables both buttons and edits the message.

Existing discord.py 2.7.1 UI-test conventions from `CLAUDE.md`'s Testing section apply (mock only
the `interaction.response`/`.followup` methods actually called; `children` ordering caveat doesn't
apply here since there are only two decorated buttons and both are addressed by attribute name, not
index).

## Rollout / Risk

- Single commit (or a small stack) touching only `commands/music.py` + the new test file — no
  dashboard, no data-layer, no other cog changes.
- Behavior-preserving for every case except the new ambiguous-link prompt: a plain video URL, a
  search query, and a playlist link that resolves to one track are byte-for-byte the same code path
  as before the refactor (helpers are extracted, not rewritten).
