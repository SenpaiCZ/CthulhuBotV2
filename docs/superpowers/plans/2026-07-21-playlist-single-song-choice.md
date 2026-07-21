# Playlist vs. Single-Song Choice on `/play` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `/play` resolves an ambiguous link (a playlist link, or a `watch?v=...&list=...` link) to more than one track, show the user a button prompt to choose "just this song" vs. "the whole playlist," instead of always queueing the entire playlist as today.

**Architecture:** Extract three cog methods (`_queue_playlist_entries`, `_queue_single_track`, `_finalize_play`) from the current linear body of `Music.play()` in `commands/music.py`, behavior-preserving. Then add a `PlaylistChoiceView` (same file, alongside the existing `CookieView`) whose two button callbacks call those same extracted helpers, so the direct path and the button-driven path share identical queueing/error logic.

**Tech Stack:** discord.py 2.7.1 (`discord.ui.View`/button), yt-dlp, pytest + pytest-asyncio.

## Global Constraints

- **Zero behavior change** for a plain video URL, a search query, or a playlist link that resolves to exactly one track, through Task 5 — these are the same code paths as today, just moved into methods, not rewritten. The only new observable behavior (the button prompt) is introduced in Task 6, wired to real queueing in Task 7.
- Python 3.11+ union syntax (`X | None`) — matches the rest of `commands/music.py` (e.g. `discord.VoiceClient | None` at music.py:230).
- No new companion `_foo.py` file — `PlaylistChoiceView` goes in `commands/music.py` next to the existing `CookieView`, per the approved design (`docs/superpowers/specs/2026-07-21-playlist-single-song-choice-design.md`).
- discord.py 2.7.1 UI-test conventions from `CLAUDE.md`'s Testing section apply: mock only the `interaction.response`/`.followup`/`.message` methods a test actually exercises; construct `discord.NotFound` the way `tests/test_blueprint_reaction_roles.py:78` already does: `discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "Unknown Message")`.
- All new tests live in one new file, `tests/test_commands_music.py` — it does not exist yet (confirmed: `ls tests/ | grep -i music` only finds `test_blueprint_music.py`, a dashboard-route test file).
- `Music.__init__` starts two `discord.ext.tasks.Loop`s (`_idle_disconnect`, `_refresh_dashboards`). Every test that constructs a real `Music` cog must cancel these immediately after construction — same pattern `tests/test_commands_cog_load.py:56-63` already uses — or they'll try to run against a `MagicMock` bot in the background.

---

### Task 1: `_query_has_explicit_video()` helper + test file scaffolding

**Files:**
- Modify: `commands/music.py` (add function after `_is_playlist_url`, music.py:60-61)
- Create: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `_query_has_explicit_video(query: str) -> bool`, used by Task 6 to pick the `PlaylistChoiceView` button label and by `play()` to decide what "just this song" resolves to. Also produces the shared test-file scaffolding (`make_interaction`, `make_music_cog`, the autouse `_delete_after` patch) that every later task's tests import/reuse.

- [ ] **Step 1: Write the failing test**

Create `tests/test_commands_music.py`:

```python
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
import yt_dlp
from discord.ext import tasks

from commands.music import Music, _query_has_explicit_video


def make_interaction(user=None):
    interaction = MagicMock()
    interaction.guild = MagicMock(id=123)
    interaction.user = user or MagicMock(id=999, display_name="Tester")
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.message = MagicMock()
    interaction.message.edit = AsyncMock()
    return interaction


def make_music_cog():
    bot = MagicMock()
    bot.loop.run_in_executor = AsyncMock()
    cog = Music(bot)
    # Music.__init__ starts two tasks.Loop instances (idle-disconnect, dashboard-refresh) --
    # cancel them immediately so they never run against this MagicMock bot in the background,
    # same as tests/test_commands_cog_load.py already does for every cog.
    for attr_name in dir(cog):
        attr = getattr(cog, attr_name, None)
        if isinstance(attr, tasks.Loop):
            attr.cancel()
    return cog


@pytest.fixture(autouse=True)
def _no_delete_after(monkeypatch):
    # play()/helpers schedule asyncio.create_task(_delete_after(msg, N)) after sending a
    # confirmation message. Patch it to a no-op so tests don't leave a real N-second sleep
    # task pending when the test (and its event loop) ends.
    monkeypatch.setattr("commands.music._delete_after", AsyncMock())


class TestQueryHasExplicitVideo:
    def test_watch_url_with_list_has_explicit_video(self):
        url = "https://www.youtube.com/watch?v=abc123&list=PLxyz"
        assert _query_has_explicit_video(url) is True

    def test_bare_playlist_url_has_no_explicit_video(self):
        url = "https://www.youtube.com/playlist?list=PLxyz"
        assert _query_has_explicit_video(url) is False

    def test_youtu_be_short_link_has_explicit_video(self):
        url = "https://youtu.be/abc123?list=PLxyz"
        assert _query_has_explicit_video(url) is True

    def test_search_query_has_no_explicit_video(self):
        assert _query_has_explicit_video("some random search terms") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v`
Expected: `ImportError: cannot import name '_query_has_explicit_video' from 'commands.music'`

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, immediately after the existing `_is_playlist_url` function (music.py:60-61):

```python
def _is_playlist_url(query: str) -> bool:
    return 'list=' in query or '/playlist' in query


def _query_has_explicit_video(query: str) -> bool:
    """True if the query references a specific video (watch?v=... or youtu.be/...), as
    opposed to a bare playlist link with no video reference."""
    return '?v=' in query or '&v=' in query or 'youtu.be/' in query
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v`
Expected: 4 passed (all in `TestQueryHasExplicitVideo`; the autouse fixture doesn't count as a test).

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "feat: add _query_has_explicit_video helper for playlist-link detection"
```

---

### Task 2: `MusicLookupError` + `_format_download_error()`, rewire `play()`'s `DownloadError` handling

**Files:**
- Modify: `commands/music.py` (add exception class + function near `COOKIE_INSTRUCTIONS`/`CookieView`, music.py:90-127; modify `play()`'s `except yt_dlp.utils.DownloadError` block, music.py:579-599)
- Test: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: `CookieView`, `COOKIES_FILE`, `COOKIE_INSTRUCTIONS` (all already defined above this point in `commands/music.py`).
- Produces: `MusicLookupError(Exception)` and `_format_download_error(e: yt_dlp.utils.DownloadError) -> tuple[str | None, discord.Embed | None, discord.ui.View | None, bool]` (content, embed, view, ephemeral). `MusicLookupError` is raised by `_queue_single_track` in Task 5. `_format_download_error` is called by `play()` (this task) and by `PlaylistChoiceView.just_one` in Task 7.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands_music.py`:

```python
from commands.music import MusicLookupError, _format_download_error, CookieView


class TestFormatDownloadError:
    def test_age_restricted_returns_cookie_embed_and_view_ephemeral(self):
        e = yt_dlp.utils.DownloadError("Sign in to confirm your age")
        content, embed, view, ephemeral = _format_download_error(e)
        assert content is None
        assert embed.title == "🔞 Age-Restricted Content"
        assert isinstance(view, CookieView)
        assert ephemeral is True

    def test_private_video_returns_plain_message(self):
        e = yt_dlp.utils.DownloadError("Private video")
        content, embed, view, ephemeral = _format_download_error(e)
        assert content == "❌ That video is private."
        assert embed is None and view is None and ephemeral is False

    def test_unavailable_video_returns_plain_message(self):
        e = yt_dlp.utils.DownloadError("Video unavailable")
        content, embed, view, ephemeral = _format_download_error(e)
        assert content == "❌ Video is unavailable."
        assert embed is None and view is None and ephemeral is False

    def test_generic_download_error_truncated_to_200_chars(self):
        e = yt_dlp.utils.DownloadError("x" * 300)
        content, embed, view, ephemeral = _format_download_error(e)
        assert content == f"❌ Download error: {'x' * 200}"
        assert embed is None and view is None and ephemeral is False


class TestPlayDownloadErrorHandling:
    @pytest.mark.asyncio
    async def test_play_sends_cookie_prompt_on_age_restricted_download_error(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog.bot.loop.run_in_executor = AsyncMock(
            side_effect=yt_dlp.utils.DownloadError("Sign in to confirm your age")
        )
        interaction = make_interaction()

        await Music.play.callback(cog, interaction, "https://youtu.be/abc123")

        interaction.followup.send.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert kwargs["embed"].title == "🔞 Age-Restricted Content"
        assert isinstance(kwargs["view"], CookieView)
        assert kwargs["ephemeral"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v`
Expected: `ImportError: cannot import name 'MusicLookupError' from 'commands.music'`

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, immediately after the `CookieView` class (music.py:119-127), add:

```python
class MusicLookupError(Exception):
    """Raised by queue helpers for an expected 'no results / blacklisted' condition — the
    caller sends str(exc) to the user unmodified, with no '❌ Unexpected error' prefix."""


def _format_download_error(e: yt_dlp.utils.DownloadError) -> tuple:
    """Map a yt-dlp DownloadError to (content, embed, view, ephemeral) for an interaction
    response/followup/message-edit — matches /play's DownloadError branches exactly."""
    err = str(e)
    if 'Sign in' in err or 'age' in err.lower() or 'login' in err.lower():
        cookie_exists = os.path.exists(COOKIES_FILE)
        embed = discord.Embed(
            title="🔞 Age-Restricted Content",
            description=(
                "This video requires a YouTube login to play.\n\n"
                + ("⚠️ Cookies are set but may be expired — try refreshing them.\n\n" if cookie_exists else "")
                + COOKIE_INSTRUCTIONS
            ),
            color=discord.Color.orange()
        )
        return None, embed, CookieView(), True
    elif 'Private' in err or 'private' in err:
        return "❌ That video is private.", None, None, False
    elif 'unavailable' in err.lower():
        return "❌ Video is unavailable.", None, None, False
    else:
        return f"❌ Download error: {err[:200]}", None, None, False
```

Then in `play()`, replace the `except yt_dlp.utils.DownloadError` block (music.py:579-592, the block that builds the age/private/unavailable/generic messages) with:

```python
        except yt_dlp.utils.DownloadError as e:
            content, embed, view, ephemeral = _format_download_error(e)
            return await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
```

This removes the old inline `if 'Sign in' in err...` chain from `play()` (music.py:580-599) — everything from `err = str(e)` through the final `return await interaction.followup.send(msg)` — replacing it with the two lines above. The subsequent `except Exception as e:` block (music.py:600-601) is unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v`
Expected: all tests pass (9 total so far).

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "refactor: extract _format_download_error from play(), add MusicLookupError"
```

---

### Task 3: Extract `_finalize_play()`

**Files:**
- Modify: `commands/music.py` (new `Music._finalize_play` method; rewire `play()`'s trailing block, music.py:603-625)
- Test: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: `self.dashboard_messages`, `self.current_track`, `self.queue`, `MusicView`, `self._play_song` (all pre-existing).
- Produces: `Music._finalize_play(self, interaction: discord.Interaction, guild_id: str) -> None`. Called by `play()` (this task), and by both `PlaylistChoiceView` button callbacks in Task 7.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands_music.py`:

```python
class TestFinalizePlay:
    @pytest.mark.asyncio
    async def test_sends_new_dashboard_and_starts_playback_when_idle(self):
        cog = make_music_cog()
        guild_id = "123"
        cog.queue[guild_id] = [{"title": "Next Song"}]
        cog._play_song = AsyncMock()
        interaction = make_interaction()
        sent_msg = MagicMock()
        interaction.followup.send = AsyncMock(return_value=sent_msg)

        await cog._finalize_play(interaction, guild_id)

        interaction.followup.send.assert_awaited_once()
        assert cog.dashboard_messages[guild_id] is sent_msg
        cog._play_song.assert_awaited_once_with(guild_id, {"title": "Next Song"})
        assert cog.queue[guild_id] == []

    @pytest.mark.asyncio
    async def test_edits_existing_dashboard_and_does_not_start_playback_when_already_playing(self):
        cog = make_music_cog()
        guild_id = "123"
        old_msg = MagicMock()
        old_msg.edit = AsyncMock()
        cog.dashboard_messages[guild_id] = old_msg
        cog.current_track[guild_id] = MagicMock(finished=False)
        cog.queue[guild_id] = [{"title": "Waiting Song"}]
        cog._play_song = AsyncMock()
        interaction = make_interaction()

        await cog._finalize_play(interaction, guild_id)

        old_msg.edit.assert_awaited_once()
        interaction.followup.send.assert_not_called()
        cog._play_song.assert_not_called()
        assert cog.queue[guild_id] == [{"title": "Waiting Song"}]  # untouched

    @pytest.mark.asyncio
    async def test_falls_back_to_new_message_when_old_dashboard_message_not_found(self):
        cog = make_music_cog()
        guild_id = "123"
        old_msg = MagicMock()
        old_msg.edit = AsyncMock(
            side_effect=discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "Unknown Message")
        )
        cog.dashboard_messages[guild_id] = old_msg
        cog.queue[guild_id] = []
        interaction = make_interaction()
        sent_msg = MagicMock()
        interaction.followup.send = AsyncMock(return_value=sent_msg)

        await cog._finalize_play(interaction, guild_id)

        assert cog.dashboard_messages[guild_id] is sent_msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k FinalizePlay`
Expected: `AttributeError: 'Music' object has no attribute '_finalize_play'`

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, add this method to the `Music` class — place it right after `_ensure_voice` (music.py:230-257) and before `_get_volume`:

```python
    async def _finalize_play(self, interaction: discord.Interaction, guild_id: str):
        """Update the existing dashboard message or send a new one (avoid delete+send to
        keep the panel stable); start playback if nothing is currently playing."""
        old_msg = self.dashboard_messages.get(guild_id)
        view = MusicView(self, guild_id)
        embed = view.get_embed()

        if old_msg:
            try:
                await old_msg.edit(embed=embed, view=view)
            except discord.NotFound:
                self.dashboard_messages.pop(guild_id, None)
                old_msg = None
            except Exception:
                old_msg = None

        if not old_msg:
            new_msg = await interaction.followup.send(embed=embed, view=view)
            self.dashboard_messages[guild_id] = new_msg

        current = self.current_track.get(guild_id)
        if (not current or current.finished) and self.queue.get(guild_id):
            next_song = self.queue[guild_id].pop(0)
            await self._play_song(guild_id, next_song)
```

Then in `play()`, replace the trailing block (music.py:603-625 — from `# Update existing dashboard or send new one` through the final `await self._play_song(guild_id, next_song)`) with:

```python
        await self._finalize_play(interaction, guild_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v`
Expected: all tests pass (12 total so far).

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "refactor: extract _finalize_play from play()'s trailing dashboard/playback block"
```

---

### Task 4: Extract `_queue_playlist_entries()`

**Files:**
- Modify: `commands/music.py` (new `Music._queue_playlist_entries` method; rewire `play()`'s playlist branch, music.py:479-521)
- Test: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: `self.blacklist`, `self.queue`, `_finalize_play` (Task 3).
- Produces: `Music._queue_playlist_entries(self, guild_id: str, entries: list[dict], playlist_title: str, requester) -> tuple[discord.Embed, bool]`. Called by `play()` (this task, for the `len(entries) <= 1` case) and by `PlaylistChoiceView.whole_playlist` in Task 7.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands_music.py`:

```python
class TestQueuePlaylistEntries:
    @pytest.mark.asyncio
    async def test_appends_all_non_blacklisted_entries_and_returns_embed(self):
        cog = make_music_cog()
        cog.queue["g1"] = []
        cog.blacklist = ["blocked-url"]
        entries = [
            {"title": "Song A", "url": "url-a", "thumbnail": "thumb-a", "duration": 100},
            {"title": "Song B", "url": "blocked-url", "thumbnail": "", "duration": 50},
            {"title": "Song C", "url": "url-c", "thumbnail": "", "duration": 200},
        ]
        requester = MagicMock(display_name="Alice")

        embed, already_playing = await cog._queue_playlist_entries("g1", entries, "My Playlist", requester)

        assert already_playing is False
        assert len(cog.queue["g1"]) == 2
        assert cog.queue["g1"][0] == {
            "title": "Song A", "url": None, "webpage_url": "url-a", "original_url": "url-a",
            "thumbnail": "thumb-a", "duration": 100, "requested_by": "Alice", "needs_resolve": True,
        }
        assert cog.queue["g1"][1]["title"] == "Song C"
        assert "My Playlist" in embed.description
        assert "2 tracks queued" in embed.description
        assert embed.title == "📥 Playlist Added"

    @pytest.mark.asyncio
    async def test_play_command_single_entry_playlist_queues_directly_no_prompt(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog._finalize_play = AsyncMock()
        flat_info = {
            "title": "My Playlist",
            "entries": [{"title": "Song A", "url": "url-a", "thumbnail": "", "duration": 100}],
        }
        cog.bot.loop.run_in_executor = AsyncMock(return_value=flat_info)
        interaction = make_interaction()

        await Music.play.callback(cog, interaction, "https://www.youtube.com/playlist?list=PL1")

        assert len(cog.queue["123"]) == 1
        assert cog.queue["123"][0]["title"] == "Song A"
        cog._finalize_play.assert_awaited_once()
        # followup.send called once for the "Playlist Added" embed, no view kwarg (no prompt)
        interaction.followup.send.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert "view" not in kwargs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k QueuePlaylistEntries`
Expected: `AttributeError: 'Music' object has no attribute '_queue_playlist_entries'`

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, add this method to the `Music` class, right after `_finalize_play` (added in Task 3):

```python
    async def _queue_playlist_entries(self, guild_id: str, entries: list, playlist_title: str,
                                       requester) -> tuple:
        """Append flat playlist entries to the guild queue, skipping blacklisted URLs.
        Returns (embed, already_playing) — already_playing is always False; queueing a
        playlist never short-circuits the dashboard/playback-start step the way a
        single-track 'something's already playing' add does."""
        added = 0
        for entry in entries:
            orig = entry.get('url', '')
            if orig in self.blacklist:
                continue
            self.queue[guild_id].append({
                'title': entry.get('title', 'Unknown'),
                'url': None,
                'webpage_url': orig,
                'original_url': orig,
                'thumbnail': entry.get('thumbnail', ''),
                'duration': entry.get('duration'),
                'requested_by': requester.display_name,
                'needs_resolve': True,
            })
            added += 1

        embed = discord.Embed(
            title="📥 Playlist Added",
            description=f"**{playlist_title}**\n{added} tracks queued",
            color=discord.Color.blurple(),
        )
        return embed, False
```

Then in `play()`, replace the playlist-queueing block (music.py:497-521 — from `added = 0` through `asyncio.create_task(_delete_after(msg, 10))`) with:

```python
                playlist_title = info.get('title', 'Playlist')
                embed, _already_playing = await self._queue_playlist_entries(
                    guild_id, entries, playlist_title, interaction.user
                )
                msg = await interaction.followup.send(embed=embed)
                asyncio.create_task(_delete_after(msg, 10))
```

(This moves the `playlist_title = info.get('title', 'Playlist')` line, previously at music.py:514, up above the new call — it's needed as an argument now instead of only for the embed.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v`
Expected: all tests pass (14 total so far).

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "refactor: extract _queue_playlist_entries from play()'s playlist branch"
```

---

### Task 5: Extract `_queue_single_track()`

**Files:**
- Modify: `commands/music.py` (new `Music._queue_single_track` method; rewire `play()`'s single-track branch, music.py:523-577; add `except MusicLookupError` clause)
- Test: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: `self.blacklist`, `self.queue`, `self.current_track`, `_fmt_duration` (imported from `commands._music_view`), `MusicLookupError` (Task 2), `_finalize_play` (Task 3).
- Produces: `Music._queue_single_track(self, guild_id: str, query: str, requester) -> tuple[discord.Embed | None, bool]`, raising `MusicLookupError` on no-results/blacklisted. Called by `play()` (this task) and by `PlaylistChoiceView.just_one` in Task 7.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands_music.py`:

```python
class TestQueueSingleTrack:
    @pytest.mark.asyncio
    async def test_queues_track_and_returns_none_embed_when_nothing_playing(self):
        cog = make_music_cog()
        cog.queue["g1"] = []
        cog.bot.loop.run_in_executor = AsyncMock(return_value={
            "title": "Song A", "webpage_url": "url-a", "url": "stream-a",
            "thumbnail": "thumb-a", "duration": 120,
        })
        requester = MagicMock(display_name="Alice")

        embed, already_playing = await cog._queue_single_track("g1", "url-a", requester)

        assert embed is None
        assert already_playing is False
        assert len(cog.queue["g1"]) == 1
        assert cog.queue["g1"][0]["title"] == "Song A"
        assert cog.queue["g1"][0]["requested_by"] == "Alice"
        assert cog.queue["g1"][0]["needs_resolve"] is False

    @pytest.mark.asyncio
    async def test_returns_added_to_queue_embed_when_something_already_playing(self):
        cog = make_music_cog()
        cog.queue["g1"] = []
        cog.current_track["g1"] = MagicMock(finished=False)
        cog.bot.loop.run_in_executor = AsyncMock(return_value={
            "title": "Song A", "webpage_url": "url-a", "url": "stream-a",
            "thumbnail": "", "duration": 120,
        })
        requester = MagicMock(display_name="Alice")

        embed, already_playing = await cog._queue_single_track("g1", "url-a", requester)

        assert already_playing is True
        assert embed.title == "📥 Added to Queue"
        assert len(cog.queue["g1"]) == 1

    @pytest.mark.asyncio
    async def test_raises_lookup_error_when_no_results(self):
        cog = make_music_cog()
        cog.queue["g1"] = []
        cog.bot.loop.run_in_executor = AsyncMock(return_value=None)

        with pytest.raises(MusicLookupError, match="No results found"):
            await cog._queue_single_track("g1", "nonsense query", MagicMock(display_name="Alice"))

    @pytest.mark.asyncio
    async def test_raises_lookup_error_when_blacklisted(self):
        cog = make_music_cog()
        cog.queue["g1"] = []
        cog.blacklist = ["url-a"]
        cog.bot.loop.run_in_executor = AsyncMock(return_value={
            "title": "Song A", "webpage_url": "url-a", "url": "stream-a",
        })

        with pytest.raises(MusicLookupError, match="is blacklisted"):
            await cog._queue_single_track("g1", "url-a", MagicMock(display_name="Alice"))


class TestPlaySingleTrackBranch:
    @pytest.mark.asyncio
    async def test_play_queues_and_finalizes_when_nothing_playing(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog._finalize_play = AsyncMock()
        cog.bot.loop.run_in_executor = AsyncMock(return_value={
            "title": "Song A", "webpage_url": "url-a", "url": "stream-a", "duration": 100,
        })
        interaction = make_interaction()

        await Music.play.callback(cog, interaction, "url-a")

        assert len(cog.queue["123"]) == 1
        cog._finalize_play.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_play_sends_added_to_queue_and_updates_dashboard_when_already_playing(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog._finalize_play = AsyncMock()
        cog._update_dashboard_for_guild = AsyncMock()
        cog.current_track["123"] = MagicMock(finished=False)
        cog.bot.loop.run_in_executor = AsyncMock(return_value={
            "title": "Song A", "webpage_url": "url-a", "url": "stream-a", "duration": 100,
        })
        interaction = make_interaction()

        await Music.play.callback(cog, interaction, "url-a")

        interaction.followup.send.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert kwargs["embed"].title == "📥 Added to Queue"
        cog._update_dashboard_for_guild.assert_awaited_once_with("123")
        cog._finalize_play.assert_not_called()

    @pytest.mark.asyncio
    async def test_play_sends_lookup_error_message_on_no_results(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog.bot.loop.run_in_executor = AsyncMock(return_value=None)
        interaction = make_interaction()

        await Music.play.callback(cog, interaction, "nonsense query")

        interaction.followup.send.assert_awaited_once_with("❌ No results found.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k "QueueSingleTrack or PlaySingleTrackBranch"`
Expected: `AttributeError: 'Music' object has no attribute '_queue_single_track'`

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, add this method to the `Music` class, right after `_queue_playlist_entries` (added in Task 4):

```python
    async def _queue_single_track(self, guild_id: str, query: str, requester) -> tuple:
        """Full yt-dlp extraction + blacklist check + queue append for one track.
        Returns (embed, already_playing). If something is already playing, embed is the
        'Added to Queue' embed and already_playing is True — the caller must send/edit it
        and call _update_dashboard_for_guild, and must NOT call _finalize_play. If nothing
        is playing, embed is None and already_playing is False — the caller must call
        _finalize_play. Raises MusicLookupError (an expected condition, not an unexpected
        failure) if extraction finds nothing playable or the track is blacklisted."""
        opts = _ytdl_opts_with_cookies(YTDL_BASE)
        def _extract_single():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(query, download=False)

        info = await self.bot.loop.run_in_executor(None, _extract_single)

        if not info:
            raise MusicLookupError("❌ No results found.")

        if 'entries' in info:
            entry = next((e for e in info['entries'] if e), None)
            if not entry:
                raise MusicLookupError("❌ No playable result found.")
            info = entry

        original_url = info.get('webpage_url', info.get('url', ''))
        if original_url in self.blacklist:
            raise MusicLookupError(f"❌ **{info.get('title', 'That track')}** is blacklisted.")

        song_info = {
            'title': info.get('title', 'Unknown'),
            'url': info.get('url', ''),
            'original_url': original_url,
            'thumbnail': info.get('thumbnail', ''),
            'duration': info.get('duration'),
            'requested_by': requester.display_name,
            'needs_resolve': False,
        }
        self.queue[guild_id].append(song_info)

        current = self.current_track.get(guild_id)
        if current and not current.finished:
            pos = len(self.queue[guild_id])
            dur = song_info['duration']
            embed = discord.Embed(
                title="📥 Added to Queue",
                description=f"[{song_info['title']}]({original_url})",
                color=discord.Color.blurple(),
            )
            if dur:
                embed.add_field(name="Duration", value=_fmt_duration(dur), inline=True)
            embed.add_field(name="Position", value=f"#{pos}", inline=True)
            embed.set_footer(text=f"Requested by {requester.display_name}")
            if song_info['thumbnail']:
                embed.set_thumbnail(url=song_info['thumbnail'])
            return embed, True

        return None, False
```

Then in `play()`, replace the entire single-track `else` branch (music.py:523-577 — from `# Single track — full extraction` through the `return  # Don't replace dashboard; just update queue section` line) with:

```python
            else:
                embed, already_playing = await self._queue_single_track(guild_id, query, interaction.user)
                if already_playing:
                    msg = await interaction.followup.send(embed=embed)
                    asyncio.create_task(_delete_after(msg, 15))
                    await self._update_dashboard_for_guild(guild_id)
                    return  # Don't replace dashboard; just update queue section
```

Finally, add a new `except MusicLookupError` clause to `play()`'s exception handling, immediately before the `except yt_dlp.utils.DownloadError` clause (from Task 2):

```python
        except MusicLookupError as e:
            return await interaction.followup.send(str(e))
        except yt_dlp.utils.DownloadError as e:
            ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v`
Expected: all tests pass (21 total so far).

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "refactor: extract _queue_single_track from play()'s single-track branch"
```

---

### Task 6: `PlaylistChoiceView` skeleton + wire the ambiguous branch in `play()`

**Files:**
- Modify: `commands/music.py` (new `PlaylistChoiceView` class, placed after `CookieView`/`MusicLookupError`/`_format_download_error`, before the `Music` cog class; rewire `play()`'s playlist branch to send it when `len(entries) > 1`)
- Test: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: `_query_has_explicit_video` (Task 1), `discord.ui.View`.
- Produces: `PlaylistChoiceView(cog, guild_id, requester_id, single_query, has_explicit_video, entries, playlist_title)` with `.just_one` / `.whole_playlist` buttons (bodies added in Task 7), `.interaction_check`, `.on_timeout`, `.message`. `play()` sends this view instead of queueing directly when `len(entries) > 1`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands_music.py`:

```python
from commands.music import PlaylistChoiceView


class TestPlaylistChoiceViewConstruction:
    def test_explicit_video_link_labels_just_one_as_this_song(self):
        entries = [{"title": "A", "url": "a"}, {"title": "B", "url": "b"}]
        view = PlaylistChoiceView(
            cog=MagicMock(), guild_id="123", requester_id=999,
            single_query="https://www.youtube.com/watch?v=abc&list=PL1",
            has_explicit_video=True, entries=entries, playlist_title="My Playlist",
        )
        assert view.just_one.label == "🎵 Just this song"
        assert view.whole_playlist.label == "📥 Whole playlist (2)"

    def test_bare_playlist_link_labels_just_one_as_first_song(self):
        entries = [{"title": "A", "url": "a"}, {"title": "B", "url": "b"}, {"title": "C", "url": "c"}]
        view = PlaylistChoiceView(
            cog=MagicMock(), guild_id="123", requester_id=999,
            single_query="a", has_explicit_video=False,
            entries=entries, playlist_title="My Playlist",
        )
        assert view.just_one.label == "🎵 Just the first song"
        assert view.whole_playlist.label == "📥 Whole playlist (3)"

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_non_requester(self):
        view = PlaylistChoiceView(
            cog=MagicMock(), guild_id="123", requester_id=999,
            single_query="a", has_explicit_video=False,
            entries=[{"title": "A", "url": "a"}, {"title": "B", "url": "b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=111))

        result = await view.interaction_check(interaction)

        assert result is False
        interaction.response.send_message.assert_awaited_once_with(
            "This choice isn't for you.", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_interaction_check_accepts_requester(self):
        view = PlaylistChoiceView(
            cog=MagicMock(), guild_id="123", requester_id=999,
            single_query="a", has_explicit_video=False,
            entries=[{"title": "A", "url": "a"}, {"title": "B", "url": "b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        result = await view.interaction_check(interaction)

        assert result is True
        interaction.response.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_timeout_disables_buttons_and_edits_message(self):
        view = PlaylistChoiceView(
            cog=MagicMock(), guild_id="123", requester_id=999,
            single_query="a", has_explicit_video=False,
            entries=[{"title": "A", "url": "a"}, {"title": "B", "url": "b"}],
            playlist_title="P",
        )
        view.message = MagicMock()
        view.message.edit = AsyncMock()

        await view.on_timeout()

        assert all(c.disabled for c in view.children)
        view.message.edit.assert_awaited_once()


class TestPlayAmbiguousPlaylistBranch:
    @pytest.mark.asyncio
    async def test_play_sends_choice_view_when_entries_exceed_one(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        flat_info = {
            "title": "My Playlist",
            "entries": [
                {"title": "Song A", "url": "url-a"},
                {"title": "Song B", "url": "url-b"},
            ],
        }
        cog.bot.loop.run_in_executor = AsyncMock(return_value=flat_info)
        interaction = make_interaction()

        await Music.play.callback(
            cog, interaction, "https://www.youtube.com/watch?v=url-a&list=PL1"
        )

        assert cog.queue["123"] == []  # nothing queued yet -- waiting on the button click
        interaction.followup.send.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert isinstance(kwargs["view"], PlaylistChoiceView)
        assert kwargs["view"].just_one.label == "🎵 Just this song"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k "PlaylistChoiceViewConstruction or PlayAmbiguousPlaylistBranch"`
Expected: `ImportError: cannot import name 'PlaylistChoiceView' from 'commands.music'`

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, add this class after `_format_download_error` (added in Task 2) and before the `# ── Cog ──` comment (music.py:130):

```python
class PlaylistChoiceView(discord.ui.View):
    def __init__(self, cog, guild_id: str, requester_id: int, single_query: str,
                 has_explicit_video: bool, entries: list, playlist_title: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.requester_id = requester_id
        self.single_query = single_query
        self.entries = entries
        self.playlist_title = playlist_title
        self.message: discord.Message | None = None

        self.just_one.label = "🎵 Just this song" if has_explicit_video else "🎵 Just the first song"
        self.whole_playlist.label = f"📥 Whole playlist ({len(entries)})"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("This choice isn't for you.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="⌛ Choice timed out — run `/play` again.", embed=None, view=self)
            except discord.NotFound:
                pass
            except Exception:
                pass

    @discord.ui.button(label="Just one song", style=discord.ButtonStyle.primary)
    async def just_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass  # implemented in Task 7

    @discord.ui.button(label="Whole playlist", style=discord.ButtonStyle.secondary)
    async def whole_playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass  # implemented in Task 7
```

Then in `play()`, in the playlist branch, replace the direct queueing call added in Task 4:

```python
                playlist_title = info.get('title', 'Playlist')
                embed, _already_playing = await self._queue_playlist_entries(
                    guild_id, entries, playlist_title, interaction.user
                )
                msg = await interaction.followup.send(embed=embed)
                asyncio.create_task(_delete_after(msg, 10))
```

with:

```python
                playlist_title = info.get('title', 'Playlist')

                if len(entries) <= 1:
                    embed, _already_playing = await self._queue_playlist_entries(
                        guild_id, entries, playlist_title, interaction.user
                    )
                    msg = await interaction.followup.send(embed=embed)
                    asyncio.create_task(_delete_after(msg, 10))
                else:
                    has_explicit_video = _query_has_explicit_video(query)
                    single_query = query if has_explicit_video else entries[0]['url']
                    view = PlaylistChoiceView(
                        cog=self, guild_id=guild_id, requester_id=interaction.user.id,
                        single_query=single_query, has_explicit_video=has_explicit_video,
                        entries=entries, playlist_title=playlist_title,
                    )
                    prompt_embed = discord.Embed(
                        title="📀 Playlist link detected",
                        description=(
                            f"**{playlist_title}** — {len(entries)} tracks\n"
                            f"First track: **{entries[0].get('title', 'Unknown')}**\n\n"
                            "Queue the whole playlist, or just one song?"
                        ),
                        color=discord.Color.blurple(),
                    )
                    view.message = await interaction.followup.send(embed=prompt_embed, view=view)
                    return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v`
Expected: all tests pass (27 total so far).

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "feat: add PlaylistChoiceView skeleton, prompt on ambiguous playlist links"
```

---

### Task 7: Implement `just_one` and `whole_playlist` button callbacks

**Files:**
- Modify: `commands/music.py` (`PlaylistChoiceView.just_one` / `.whole_playlist` bodies)
- Test: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: `Music._queue_single_track` (Task 5), `Music._queue_playlist_entries` (Task 4), `Music._finalize_play` (Task 3), `Music._update_dashboard_for_guild` (pre-existing), `MusicLookupError` (Task 2), `_format_download_error` (Task 2).
- Produces: nothing consumed by a later task — this is the last functional task.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands_music.py`:

```python
class TestJustOneButton:
    @pytest.mark.asyncio
    async def test_explicit_video_case_queues_via_original_query_and_finalizes(self):
        cog = make_music_cog()
        cog._queue_single_track = AsyncMock(return_value=(None, False))
        cog._finalize_play = AsyncMock()
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="https://www.youtube.com/watch?v=abc&list=PL1",
            has_explicit_video=True,
            entries=[{"title": "A", "url": "a"}, {"title": "B", "url": "b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.just_one.callback(interaction)

        cog._queue_single_track.assert_awaited_once_with(
            "123", "https://www.youtube.com/watch?v=abc&list=PL1", interaction.user
        )
        interaction.message.edit.assert_awaited_once()
        _, kwargs = interaction.message.edit.call_args
        assert kwargs["view"] is None
        cog._finalize_play.assert_awaited_once_with(interaction, "123")

    @pytest.mark.asyncio
    async def test_bare_playlist_case_queues_via_first_entry_url(self):
        cog = make_music_cog()
        cog._queue_single_track = AsyncMock(return_value=(None, False))
        cog._finalize_play = AsyncMock()
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="url-a", has_explicit_video=False,
            entries=[{"title": "A", "url": "url-a"}, {"title": "B", "url": "url-b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.just_one.callback(interaction)

        cog._queue_single_track.assert_awaited_once_with("123", "url-a", interaction.user)

    @pytest.mark.asyncio
    async def test_already_playing_edits_added_to_queue_embed_and_updates_dashboard_only(self):
        cog = make_music_cog()
        added_embed = discord.Embed(title="📥 Added to Queue")
        cog._queue_single_track = AsyncMock(return_value=(added_embed, True))
        cog._finalize_play = AsyncMock()
        cog._update_dashboard_for_guild = AsyncMock()
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="url-a", has_explicit_video=False,
            entries=[{"title": "A", "url": "url-a"}, {"title": "B", "url": "url-b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.just_one.callback(interaction)

        interaction.message.edit.assert_awaited_once_with(embed=added_embed, view=None)
        cog._update_dashboard_for_guild.assert_awaited_once_with("123")
        cog._finalize_play.assert_not_called()

    @pytest.mark.asyncio
    async def test_lookup_error_edits_message_with_error_and_does_not_finalize(self):
        cog = make_music_cog()
        cog._queue_single_track = AsyncMock(side_effect=MusicLookupError("❌ No results found."))
        cog._finalize_play = AsyncMock()
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="url-a", has_explicit_video=False,
            entries=[{"title": "A", "url": "url-a"}, {"title": "B", "url": "url-b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.just_one.callback(interaction)

        interaction.message.edit.assert_awaited_once_with(
            content="❌ No results found.", embed=None, view=None
        )
        cog._finalize_play.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_error_edits_message_via_format_download_error(self):
        cog = make_music_cog()
        cog._queue_single_track = AsyncMock(
            side_effect=yt_dlp.utils.DownloadError("Private video")
        )
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="url-a", has_explicit_video=False,
            entries=[{"title": "A", "url": "url-a"}, {"title": "B", "url": "url-b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.just_one.callback(interaction)

        interaction.message.edit.assert_awaited_once_with(
            content="❌ That video is private.", embed=None, view=None
        )


class TestWholePlaylistButton:
    @pytest.mark.asyncio
    async def test_queues_all_entries_and_finalizes(self):
        cog = make_music_cog()
        playlist_embed = discord.Embed(title="📥 Playlist Added")
        cog._queue_playlist_entries = AsyncMock(return_value=(playlist_embed, False))
        cog._finalize_play = AsyncMock()
        entries = [{"title": "A", "url": "url-a"}, {"title": "B", "url": "url-b"}]
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="url-a", has_explicit_video=False,
            entries=entries, playlist_title="My Playlist",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.whole_playlist.callback(interaction)

        cog._queue_playlist_entries.assert_awaited_once_with(
            "123", entries, "My Playlist", interaction.user
        )
        interaction.message.edit.assert_awaited_once_with(embed=playlist_embed, view=None)
        cog._finalize_play.assert_awaited_once_with(interaction, "123")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k "JustOneButton or WholePlaylistButton"`
Expected: failures — the button callbacks currently `pass`, so e.g. `cog._queue_single_track.assert_awaited_once_with(...)` fails with "Expected ... to have been called once. Called 0 times."

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, replace the two placeholder button methods added in Task 6:

```python
    @discord.ui.button(label="Just one song", style=discord.ButtonStyle.primary)
    async def just_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            embed, already_playing = await self.cog._queue_single_track(
                self.guild_id, self.single_query, interaction.user
            )
        except MusicLookupError as e:
            await interaction.message.edit(content=str(e), embed=None, view=None)
            self.stop()
            return
        except yt_dlp.utils.DownloadError as e:
            content, err_embed, err_view, _ephemeral = _format_download_error(e)
            await interaction.message.edit(content=content, embed=err_embed, view=err_view)
            self.stop()
            return
        except Exception as e:
            await interaction.message.edit(
                content=f"❌ Unexpected error: {type(e).__name__}: {str(e)[:200]}", embed=None, view=None
            )
            self.stop()
            return

        if already_playing:
            await interaction.message.edit(embed=embed, view=None)
            await self.cog._update_dashboard_for_guild(self.guild_id)
        else:
            queued_embed = discord.Embed(
                description="▶️ Queued — starting playback.", color=discord.Color.blurple()
            )
            await interaction.message.edit(embed=queued_embed, view=None)
            await self.cog._finalize_play(interaction, self.guild_id)
        self.stop()

    @discord.ui.button(label="Whole playlist", style=discord.ButtonStyle.secondary)
    async def whole_playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed, _already_playing = await self.cog._queue_playlist_entries(
            self.guild_id, self.entries, self.playlist_title, interaction.user
        )
        await interaction.message.edit(embed=embed, view=None)
        await self.cog._finalize_play(interaction, self.guild_id)
        self.stop()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v`
Expected: all tests pass (33 total).

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "feat: implement PlaylistChoiceView button callbacks"
```

---

### Task 8: Full regression pass

**Files:**
- Verify only — no source changes expected unless this step uncovers a regression.

**Interfaces:**
- Consumes: everything from Tasks 1-7.
- Produces: nothing — this is the last task in the plan.

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass, including the pre-existing suite (1002 tests as of this plan's writing) plus the 33 new tests in `tests/test_commands_music.py` — no regressions in any other module. If anything fails, fix it in `commands/music.py` before proceeding (do not edit the failing test to make it pass unless the test itself is wrong).

- [ ] **Step 2: Manually re-read the final `play()` command for the three preserved-behavior cases**

Run:
```bash
grep -n "async def play" commands/music.py
```
Read the method and confirm by inspection: a plain video URL and a search query still go through `_queue_single_track` → conditionally `_finalize_play`, unchanged from Task 5; a playlist URL resolving to exactly one entry still goes through `_queue_playlist_entries` → `_finalize_play` directly, unchanged from Task 6, with no `PlaylistChoiceView` involved.

- [ ] **Step 3: Commit (only if Step 1 required a fix)**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "fix: address regression found in playlist-choice full-suite pass"
```

If Step 1 found no regressions, skip this step — there is nothing to commit.

---

## Self-Review Notes

- **Spec coverage:** design spec sections 1 (branch point) → Tasks 4/6; 2 (link-shape detection) → Task 1 + Task 6; 3 (`PlaylistChoiceView`) → Tasks 6-7; 4 (cog helpers) → Tasks 3-5; 5 (error handling) → Task 2 + Task 7; 6 (testing) → every task's test steps. All six spec sections have a corresponding task.
- **Placeholder scan:** no TBD/TODO; Task 6's `pass  # implemented in Task 7` is an explicit, intentional placeholder that Task 7 replaces in the same file before the plan ends — not a plan-completion placeholder.
- **Type consistency:** `_queue_playlist_entries` and `_queue_single_track` both return `(embed, already_playing)` tuples in every task that defines or calls them (Tasks 3-7) — verified consistent. `PlaylistChoiceView.__init__`'s parameter names (`single_query`, `has_explicit_video`, `entries`, `playlist_title`) match exactly between Task 6 (construction site in `play()`) and Task 7 (usage inside the button callbacks).
