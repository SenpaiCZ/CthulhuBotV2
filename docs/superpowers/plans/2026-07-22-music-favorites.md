# Music Favorites via Reaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user react ❤️ on the music "now playing" panel to save the current song to a
personal, per-server favorites list, un-react to remove it, and manage/play that list via a new
`/favorites` command group (`play`, `list`, `remove`, `clear`).

**Architecture:** A new `loadnsave.py` data pair (`load_music_favorites`/`save_music_favorites`,
uncached, matching `karma_stats`) backs everything. Two new `Music` cog listeners
(`on_raw_reaction_add`/`on_raw_reaction_remove`) recognize reactions on the guild's dashboard
message and delegate to two new helper methods (`_add_favorite`/`_remove_favorite`). `_play_song`
gets one new line clearing stale reactions whenever a genuinely new track starts, so add/remove
stays unambiguous across song changes. `/favorites play` is pure composition of the already-shipped
`_queue_playlist_entries`/`_finalize_play` — no new queueing logic.

**Tech Stack:** discord.py 2.7.1 (`app_commands.Group`, raw reaction events), pytest + pytest-asyncio.

## Global Constraints

- Favorites are scoped per guild — data shape is `{guild_id: {user_id: [{"url", "title",
  "thumbnail", "duration"}, ...]}}`, matching every other per-user store in this codebase
  (`player_stats.json`, `karma_stats.json`).
- `load_music_favorites`/`save_music_favorites` have **no module-level cache** — matches
  `load_karma_stats`/`save_karma_stats` exactly, the closest existing precedent for
  reaction-triggered per-user data.
- The reaction listeners only ever act on `❤️` reacted on the guild's current
  `dashboard_messages[guild_id]`, and only when a track is actively playing (`current_track` set,
  not finished) — everything else is ignored, no side effects.
- `_play_song` clears all reactions on the dashboard message every time a genuinely new track
  starts (the single choke point every "a song starts playing" path already funnels through) —
  best-effort, wrapped so a permissions failure there never blocks playback.
- `/favorites play` does **not** go through `PlaylistChoiceView` — there is no link-shape
  ambiguity to resolve, it unconditionally queues the whole list, matching how a playlist link
  that resolves to a single track is already queued directly today.
- discord.py 2.7.1 UI-test conventions from `CLAUDE.md`'s Testing section apply where relevant
  (mock only what a test exercises; `discord.NotFound`/`discord.Forbidden` constructed as
  `ExceptionType(SimpleNamespace(status=..., reason=...), "message")`, matching
  `tests/test_blueprint_reaction_roles.py:78`'s established pattern).
- `mock.patch()`/`monkeypatch.setattr()` targets the module that looks the name up:
  `commands.music.load_music_favorites`/`commands.music.save_music_favorites` (imported by name
  into `commands/music.py`), not `loadnsave.load_music_favorites`.

---

### Task 1: Data layer (`loadnsave.py`)

**Files:**
- Modify: `loadnsave.py`
- Modify: `tests/test_loadnsave_roundtrip.py`

**Interfaces:**
- Consumes: nothing from other tasks — this is the foundation layer.
- Produces: `load_music_favorites() -> dict`, `save_music_favorites(favorites: dict) -> None`.
  Consumed by Task 2 (`_add_favorite`/`_remove_favorite`) and Task 4/5 (`/favorites` commands).

- [ ] **Step 1: Write the failing test**

In `tests/test_loadnsave_roundtrip.py`, add one new entry to the existing `ENTITY_CASES` list
(`tests/test_loadnsave_roundtrip.py:6-57`), right after the `retired_characters_data` entry and
before the closing `]`:

```python
    pytest.param(
        loadnsave.load_music_favorites, loadnsave.save_music_favorites,
        "music_favorites.json", None,
        {"123": {"456": [{"url": "u", "title": "t", "thumbnail": "", "duration": 100}]}},
        id="music_favorites",
    ),
]
```

(Replace the existing closing `]` on its own line — this new entry goes immediately before it.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_loadnsave_roundtrip.py -v -k music_favorites`
Expected: `AttributeError: module 'loadnsave' has no attribute 'load_music_favorites'`

- [ ] **Step 3: Write minimal implementation**

In `loadnsave.py`, immediately after the Karma System block (`loadnsave.py:461-472`, ending with
`save_karma_stats`) and before `# --- Reaction Roles ---` (`loadnsave.py:474`), add:

```python
# --- Music Favorites ---
async def load_music_favorites():
    return await _load_json_file(DATA_FOLDER, 'music_favorites.json')

async def save_music_favorites(favorites):
    await _save_json_file(DATA_FOLDER, 'music_favorites.json', favorites)

```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_loadnsave_roundtrip.py -v -k music_favorites`
Expected: both parametrized sub-tests for `music_favorites` pass (round-trip + no-cache-reset-needed).

Run: `.venv/bin/python -m pytest tests/test_loadnsave_roundtrip.py -v`
Expected: all tests in the file still pass (no regression to the other 5 entity cases).

- [ ] **Step 5: Commit**

```bash
git add loadnsave.py tests/test_loadnsave_roundtrip.py
git commit -m "feat: add load_music_favorites/save_music_favorites data layer"
```

---

### Task 2: `_add_favorite`/`_remove_favorite` + reaction listeners

**Files:**
- Modify: `commands/music.py`
- Modify: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: `load_music_favorites`/`save_music_favorites` (Task 1).
- Produces: `Music._add_favorite(self, guild_id: str, user_id: str, metadata: dict) -> None`,
  `Music._remove_favorite(self, guild_id: str, user_id: str, url: str) -> None`, and the two
  `on_raw_reaction_add`/`on_raw_reaction_remove` listeners. Not consumed by any later task in this
  plan (the listeners are the only callers) — a self-contained feature slice.

- [ ] **Step 1: Write the failing tests**

`tests/test_commands_music.py`'s existing import block (`tests/test_commands_music.py:1-10`) needs
no changes for this task — `load_music_favorites`/`save_music_favorites` are patched by dotted
string path (`"commands.music.load_music_favorites"`), not imported by name, and no new name is
needed from `commands.music` itself.

Append to `tests/test_commands_music.py`:

```python
def make_reaction_payload(user_id=999, guild_id=123, message_id=555, emoji="❤️"):
    return SimpleNamespace(user_id=user_id, guild_id=guild_id, message_id=message_id, emoji=emoji)


class TestAddRemoveFavorite:
    @pytest.mark.asyncio
    async def test_add_favorite_saves_new_entry(self, monkeypatch):
        cog = make_music_cog()
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._add_favorite("g1", "u1", {
            "original_url": "url-a", "title": "Song A", "thumbnail": "thumb-a", "duration": 100,
        })

        save_mock.assert_awaited_once()
        saved = save_mock.call_args[0][0]
        assert saved["g1"]["u1"] == [{"url": "url-a", "title": "Song A", "thumbnail": "thumb-a", "duration": 100}]

    @pytest.mark.asyncio
    async def test_add_favorite_is_noop_when_url_missing(self, monkeypatch):
        cog = make_music_cog()
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._add_favorite("g1", "u1", {"title": "No URL"})

        save_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_favorite_dedupes_by_url(self, monkeypatch):
        cog = make_music_cog()
        existing = {"g1": {"u1": [{"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100}]}}
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=existing))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._add_favorite("g1", "u1", {"original_url": "url-a", "title": "Song A (dup)"})

        save_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_favorite_removes_matching_url(self, monkeypatch):
        cog = make_music_cog()
        existing = {"g1": {"u1": [
            {"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100},
            {"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50},
        ]}}
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=existing))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._remove_favorite("g1", "u1", "url-a")

        save_mock.assert_awaited_once()
        saved = save_mock.call_args[0][0]
        assert saved["g1"]["u1"] == [{"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50}]

    @pytest.mark.asyncio
    async def test_remove_favorite_is_noop_when_url_absent(self, monkeypatch):
        cog = make_music_cog()
        existing = {"g1": {"u1": [{"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100}]}}
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=existing))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._remove_favorite("g1", "u1", "url-does-not-exist")

        save_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_favorite_is_noop_for_unknown_guild_or_user(self, monkeypatch):
        cog = make_music_cog()
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._remove_favorite("g1", "u1", "url-a")

        save_mock.assert_not_called()


class TestReactionListeners:
    @pytest.mark.asyncio
    async def test_add_ignores_bot_own_reaction(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=999)
        cog._add_favorite = AsyncMock()
        payload = make_reaction_payload(user_id=999)

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_ignores_non_heart_emoji(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._add_favorite = AsyncMock()
        payload = make_reaction_payload(user_id=999, emoji="👍")

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_ignores_reaction_on_non_dashboard_message(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._add_favorite = AsyncMock()
        cog.dashboard_messages["123"] = MagicMock(id=555)
        payload = make_reaction_payload(guild_id=123, message_id=999)  # different message id

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_ignores_when_nothing_playing(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._add_favorite = AsyncMock()
        cog.dashboard_messages["123"] = MagicMock(id=555)
        payload = make_reaction_payload(guild_id=123, message_id=555)

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_ignores_finished_track(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._add_favorite = AsyncMock()
        cog.dashboard_messages["123"] = MagicMock(id=555)
        cog.current_track["123"] = MagicMock(finished=True)
        payload = make_reaction_payload(guild_id=123, message_id=555)

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_calls_add_favorite_with_current_track_metadata(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._add_favorite = AsyncMock()
        cog.dashboard_messages["123"] = MagicMock(id=555)
        track = MagicMock(finished=False, metadata={"original_url": "url-a", "title": "Song A"})
        cog.current_track["123"] = track
        payload = make_reaction_payload(user_id=999, guild_id=123, message_id=555)

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_awaited_once_with("123", "999", track.metadata)

    @pytest.mark.asyncio
    async def test_remove_calls_remove_favorite_with_current_track_original_url(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._remove_favorite = AsyncMock()
        cog.dashboard_messages["123"] = MagicMock(id=555)
        track = MagicMock(finished=False, metadata={"original_url": "url-a", "title": "Song A"})
        cog.current_track["123"] = track
        payload = make_reaction_payload(user_id=999, guild_id=123, message_id=555)

        await cog.on_raw_reaction_remove(payload)

        cog._remove_favorite.assert_awaited_once_with("123", "999", "url-a")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k "AddRemoveFavorite or ReactionListeners"`
Expected: `AttributeError: 'Music' object has no attribute '_add_favorite'` (and similarly for the
other new names).

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, add `load_music_favorites, save_music_favorites` to the existing
`loadnsave` import block (`commands/music.py:13-16`):

```python
from loadnsave import (
    load_music_blacklist, save_music_blacklist,
    load_server_volumes, save_server_volumes,
    load_music_favorites, save_music_favorites,
)
```

Add this new section to the `Music` class, right after `on_voice_state_update`'s body
(`commands/music.py:1094-1122`) and before `async def setup(bot):`:

```python
    # ── Favorites ────────────────────────────────────────────────────────────

    FAVORITE_EMOJI = "❤️"

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != self.FAVORITE_EMOJI:
            return
        guild_id = str(payload.guild_id) if payload.guild_id else None
        if not guild_id:
            return

        dashboard_msg = self.dashboard_messages.get(guild_id)
        if not dashboard_msg or dashboard_msg.id != payload.message_id:
            return

        track = self.current_track.get(guild_id)
        if not track or track.finished:
            return

        await self._add_favorite(guild_id, str(payload.user_id), track.metadata)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != self.FAVORITE_EMOJI:
            return
        guild_id = str(payload.guild_id) if payload.guild_id else None
        if not guild_id:
            return

        dashboard_msg = self.dashboard_messages.get(guild_id)
        if not dashboard_msg or dashboard_msg.id != payload.message_id:
            return

        track = self.current_track.get(guild_id)
        if not track or track.finished:
            return

        await self._remove_favorite(guild_id, str(payload.user_id), track.metadata.get('original_url', ''))

    async def _add_favorite(self, guild_id: str, user_id: str, metadata: dict):
        url = metadata.get('original_url', '')
        if not url:
            return
        favorites = await load_music_favorites()
        favorites.setdefault(guild_id, {}).setdefault(user_id, [])
        user_favs = favorites[guild_id][user_id]
        if any(f['url'] == url for f in user_favs):
            return
        user_favs.append({
            'url': url,
            'title': metadata.get('title', 'Unknown'),
            'thumbnail': metadata.get('thumbnail', ''),
            'duration': metadata.get('duration'),
        })
        await save_music_favorites(favorites)

    async def _remove_favorite(self, guild_id: str, user_id: str, url: str):
        if not url:
            return
        favorites = await load_music_favorites()
        user_favs = favorites.get(guild_id, {}).get(user_id)
        if not user_favs:
            return
        new_favs = [f for f in user_favs if f['url'] != url]
        if len(new_favs) == len(user_favs):
            return
        favorites[guild_id][user_id] = new_favs
        await save_music_favorites(favorites)

```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k "AddRemoveFavorite or ReactionListeners"`
Expected: all 13 tests pass (6 in `TestAddRemoveFavorite` + 7 in `TestReactionListeners`).

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "feat: add favorite add/remove helpers and heart-reaction listeners"
```

---

### Task 3: Clear reactions when a new track starts (`_play_song`)

**Files:**
- Modify: `commands/music.py`
- Test: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: nothing new from other tasks — this is an independent hardening of `_play_song`
  (pre-existing method) that keeps Task 2's listeners unambiguous across song changes.
- Produces: nothing consumed by a later task.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_commands_music.py`:

```python
from dashboard.audio_mixer import MixingAudioSource


def make_playable_guild(cog, guild_id, mixer):
    """Wire up cog.bot.get_guild(...) and guild_mixers so _play_song's existing setup path
    (mixer lookup, voice-client-already-playing-this-mixer check) is satisfied without
    constructing any real discord.py audio objects or spawning FFmpeg."""
    fake_source = MagicMock(spec=discord.PCMVolumeTransformer)
    fake_source.original = mixer
    fake_vc = MagicMock()
    fake_vc.is_connected.return_value = True
    fake_vc.is_playing.return_value = True
    fake_vc.source = fake_source

    fake_guild = MagicMock()
    fake_guild.voice_client = fake_vc
    cog.bot.get_guild = MagicMock(return_value=fake_guild)


class TestPlaySongClearsReactions:
    @pytest.mark.asyncio
    async def test_clears_reactions_on_dashboard_message_when_new_track_starts(self, monkeypatch):
        cog = make_music_cog()
        dashboard_msg = MagicMock()
        dashboard_msg.clear_reactions = AsyncMock()
        cog.dashboard_messages["123"] = dashboard_msg
        cog._update_dashboard_for_guild = AsyncMock()

        fake_mixer = MagicMock(spec=MixingAudioSource)
        fake_track = MagicMock(id="track-1")
        fake_mixer.add_track = MagicMock(return_value=fake_track)
        monkeypatch.setattr("commands.music.guild_mixers", {"123": fake_mixer})
        make_playable_guild(cog, "123", fake_mixer)

        await cog._play_song("123", {"url": "stream-a", "needs_resolve": False, "title": "Song A"})

        dashboard_msg.clear_reactions.assert_awaited_once()
        assert cog.current_track["123"] is fake_track

    @pytest.mark.asyncio
    async def test_no_dashboard_message_is_noop_no_error(self, monkeypatch):
        cog = make_music_cog()
        cog._update_dashboard_for_guild = AsyncMock()

        fake_mixer = MagicMock(spec=MixingAudioSource)
        fake_mixer.add_track = MagicMock(return_value=MagicMock(id="track-1"))
        monkeypatch.setattr("commands.music.guild_mixers", {"123": fake_mixer})
        make_playable_guild(cog, "123", fake_mixer)

        await cog._play_song("123", {"url": "stream-a", "needs_resolve": False, "title": "Song A"})
        # No dashboard message registered for this guild -- must not raise.

    @pytest.mark.asyncio
    async def test_clear_reactions_failure_does_not_prevent_playback(self, monkeypatch):
        cog = make_music_cog()
        dashboard_msg = MagicMock()
        dashboard_msg.clear_reactions = AsyncMock(
            side_effect=discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Missing Permissions")
        )
        cog.dashboard_messages["123"] = dashboard_msg
        cog._update_dashboard_for_guild = AsyncMock()

        fake_mixer = MagicMock(spec=MixingAudioSource)
        fake_track = MagicMock(id="track-1")
        fake_mixer.add_track = MagicMock(return_value=fake_track)
        monkeypatch.setattr("commands.music.guild_mixers", {"123": fake_mixer})
        make_playable_guild(cog, "123", fake_mixer)

        await cog._play_song("123", {"url": "stream-a", "needs_resolve": False, "title": "Song A"})

        assert cog.current_track["123"] is fake_track  # playback still proceeded
        cog._update_dashboard_for_guild.assert_awaited_once_with("123")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k PlaySongClearsReactions`
Expected: `test_clears_reactions_on_dashboard_message_when_new_track_starts` and
`test_clear_reactions_failure_does_not_prevent_playback` fail because `dashboard_msg.clear_reactions`
is never called (`_play_song` doesn't do this yet); `test_no_dashboard_message_is_noop_no_error`
already passes vacuously (nothing to assert) — that's expected, it exists to guard against a future
regression, not to currently prove anything new.

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`'s `_play_song` method, replace:

```python
        self.current_track[guild_id] = track
        await self._update_dashboard_for_guild(guild_id)
```

with:

```python
        self.current_track[guild_id] = track
        dashboard_msg = self.dashboard_messages.get(guild_id)
        if dashboard_msg:
            try:
                await dashboard_msg.clear_reactions()
            except Exception:
                pass
        await self._update_dashboard_for_guild(guild_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k PlaySongClearsReactions`
Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "feat: clear dashboard reactions when a new track starts playing"
```

---

### Task 4: `/favorites play`

**Files:**
- Modify: `commands/music.py`
- Test: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: `load_music_favorites` (Task 1), `_ensure_voice`/`_queue_playlist_entries`/
  `_finalize_play` (all pre-existing).
- Produces: `favorites_group = app_commands.Group(...)` (the class attribute later tasks in this
  plan add more commands to) and the `favorites_play` command.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_commands_music.py`:

```python
class TestFavoritesPlay:
    @pytest.mark.asyncio
    async def test_no_favorites_sends_message(self, monkeypatch):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        interaction = make_interaction()

        await Music.favorites_play.callback(cog, interaction)

        interaction.followup.send.assert_awaited_once()
        args, kwargs = interaction.followup.send.call_args
        assert "don't have any favorited" in args[0]

    @pytest.mark.asyncio
    async def test_queues_all_favorites_and_finalizes(self, monkeypatch):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog._finalize_play = AsyncMock()
        favorites = {"123": {"999": [
            {"url": "url-a", "title": "Song A", "thumbnail": "thumb-a", "duration": 100},
            {"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50},
        ]}}
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=favorites))
        embed = discord.Embed(title="📥 Playlist Added")
        cog._queue_playlist_entries = AsyncMock(return_value=(embed, False))
        interaction = make_interaction()

        await Music.favorites_play.callback(cog, interaction)

        cog._queue_playlist_entries.assert_awaited_once()
        call_args = cog._queue_playlist_entries.call_args[0]
        assert call_args[0] == "123"
        assert call_args[1] == [
            {"url": "url-a", "title": "Song A", "thumbnail": "thumb-a", "duration": 100},
            {"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50},
        ]
        cog._finalize_play.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_voice_channel_aborts_early(self, monkeypatch):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=None)
        cog._queue_playlist_entries = AsyncMock()
        interaction = make_interaction()

        await Music.favorites_play.callback(cog, interaction)

        cog._queue_playlist_entries.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k FavoritesPlay`
Expected: `AttributeError: type object 'Music' has no attribute 'favorites_play'`

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, inside the `# ── Favorites ──` section added in Task 2 (right after
`_remove_favorite`'s body, before the section ends), add:

```python
    favorites_group = app_commands.Group(name="favorites", description="❤️ Manage your favorite songs")

    @favorites_group.command(name="play", description="▶️ Queue all of your favorited songs.")
    async def favorites_play(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Servers only.", ephemeral=True)

        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        await interaction.response.defer()

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        favorites = await load_music_favorites()
        user_favs = favorites.get(guild_id, {}).get(user_id, [])

        if not user_favs:
            return await interaction.followup.send(
                "❌ You don't have any favorited songs yet. React ❤️ on the now-playing panel to save one."
            )

        if not self.blacklist:
            self.blacklist = await load_music_blacklist() or []

        entries = [
            {'url': f['url'], 'title': f['title'], 'thumbnail': f['thumbnail'], 'duration': f['duration']}
            for f in user_favs
        ]
        embed, _already_playing = await self._queue_playlist_entries(
            guild_id, entries, f"❤️ {interaction.user.display_name}'s Favorites", interaction.user
        )
        msg = await interaction.followup.send(embed=embed)
        asyncio.create_task(_delete_after(msg, 10))
        await self._finalize_play(interaction, guild_id)

```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k FavoritesPlay`
Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "feat: add /favorites play command"
```

---

### Task 5: `/favorites list`, `/favorites remove`, `/favorites clear`

**Files:**
- Modify: `commands/music.py`
- Test: `tests/test_commands_music.py`

**Interfaces:**
- Consumes: `load_music_favorites`/`save_music_favorites` (Task 1), `favorites_group` (Task 4),
  `_fmt_duration` (pre-existing import).
- Produces: nothing consumed by a later task — these are terminal, user-facing commands.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_commands_music.py`:

```python
class TestFavoritesList:
    @pytest.mark.asyncio
    async def test_empty_favorites_shows_message(self, monkeypatch):
        cog = make_music_cog()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        interaction = make_interaction()

        await Music.favorites_list.callback(cog, interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert "No favorited songs yet" in kwargs["embed"].description

    @pytest.mark.asyncio
    async def test_lists_favorites_with_truncation(self, monkeypatch):
        cog = make_music_cog()
        favs = [{"url": f"url-{i}", "title": f"Song {i}", "thumbnail": "", "duration": 60} for i in range(12)]
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={"123": {"999": favs}}))
        interaction = make_interaction()

        await Music.favorites_list.callback(cog, interaction)

        _, kwargs = interaction.response.send_message.call_args
        desc = kwargs["embed"].description
        assert "Song 0" in desc
        assert "Song 9" in desc
        assert "Song 10" not in desc
        assert "and 2 more" in desc


class TestFavoritesRemove:
    @pytest.mark.asyncio
    async def test_no_favorites_shows_message(self, monkeypatch):
        cog = make_music_cog()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        interaction = make_interaction()

        await Music.favorites_remove.callback(cog, interaction, 1)

        interaction.response.send_message.assert_awaited_once_with(
            "You don't have any favorited songs.", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_out_of_range_position_rejected(self, monkeypatch):
        cog = make_music_cog()
        favs = [{"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100}]
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={"123": {"999": favs}}))
        interaction = make_interaction()

        await Music.favorites_remove.callback(cog, interaction, 5)

        interaction.response.send_message.assert_awaited_once_with("Position must be 1–1.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_removes_correct_entry_and_saves(self, monkeypatch):
        cog = make_music_cog()
        favs = [
            {"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100},
            {"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50},
        ]
        data = {"123": {"999": favs}}
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=data))
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)
        interaction = make_interaction()

        await Music.favorites_remove.callback(cog, interaction, 1)

        save_mock.assert_awaited_once()
        saved = save_mock.call_args[0][0]
        assert saved["123"]["999"] == [{"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50}]
        interaction.response.send_message.assert_awaited_once_with(
            "🗑️ Removed **Song A** from your favorites.", ephemeral=True
        )


class TestFavoritesClear:
    @pytest.mark.asyncio
    async def test_clears_existing_favorites(self, monkeypatch):
        cog = make_music_cog()
        data = {"123": {"999": [{"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100}]}}
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=data))
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)
        interaction = make_interaction()

        await Music.favorites_clear.callback(cog, interaction)

        save_mock.assert_awaited_once()
        saved = save_mock.call_args[0][0]
        assert saved["123"]["999"] == []
        interaction.response.send_message.assert_awaited_once_with(
            "🧹 Your favorites have been cleared.", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_clearing_when_no_favorites_exist_does_not_raise(self, monkeypatch):
        cog = make_music_cog()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)
        interaction = make_interaction()

        await Music.favorites_clear.callback(cog, interaction)

        save_mock.assert_not_called()
        interaction.response.send_message.assert_awaited_once_with(
            "🧹 Your favorites have been cleared.", ephemeral=True
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k "FavoritesList or FavoritesRemove or FavoritesClear"`
Expected: `AttributeError: type object 'Music' has no attribute 'favorites_list'` (and similarly for
`favorites_remove`/`favorites_clear`).

- [ ] **Step 3: Write minimal implementation**

In `commands/music.py`, right after `favorites_play` (added in Task 4), add:

```python
    @favorites_group.command(name="list", description="📋 Show your favorited songs.")
    async def favorites_list(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Servers only.", ephemeral=True)

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        favorites = await load_music_favorites()
        user_favs = favorites.get(guild_id, {}).get(user_id, [])

        embed = discord.Embed(title="❤️ Your Favorites", color=discord.Color.red())
        if not user_favs:
            embed.description = "No favorited songs yet. React ❤️ on the now-playing panel to save one."
        else:
            lines = []
            for i, f in enumerate(user_favs[:10], 1):
                dur = f" `{_fmt_duration(f['duration'])}`" if f.get('duration') else ""
                lines.append(f"`{i}.` [{f['title']}]({f['url']}){dur}")
            if len(user_favs) > 10:
                lines.append(f"*…and {len(user_favs) - 10} more*")
            embed.description = "\n".join(lines)
            embed.set_footer(text=f"Total: {len(user_favs)} songs")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @favorites_group.command(name="remove", description="🗑️ Remove a favorited song by its number in /favorites list.")
    @app_commands.describe(position="Position from /favorites list (1 = first)")
    async def favorites_remove(self, interaction: discord.Interaction, position: int):
        if not interaction.guild:
            return await interaction.response.send_message("Servers only.", ephemeral=True)

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        favorites = await load_music_favorites()
        user_favs = favorites.get(guild_id, {}).get(user_id, [])

        if not user_favs:
            return await interaction.response.send_message("You don't have any favorited songs.", ephemeral=True)
        if position < 1 or position > len(user_favs):
            return await interaction.response.send_message(f"Position must be 1–{len(user_favs)}.", ephemeral=True)

        removed = user_favs.pop(position - 1)
        favorites[guild_id][user_id] = user_favs
        await save_music_favorites(favorites)
        await interaction.response.send_message(f"🗑️ Removed **{removed['title']}** from your favorites.", ephemeral=True)

    @favorites_group.command(name="clear", description="🧹 Clear all of your favorited songs.")
    async def favorites_clear(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Servers only.", ephemeral=True)

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        favorites = await load_music_favorites()
        if guild_id in favorites and user_id in favorites[guild_id]:
            favorites[guild_id][user_id] = []
            await save_music_favorites(favorites)

        await interaction.response.send_message("🧹 Your favorites have been cleared.", ephemeral=True)

```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_commands_music.py -v -k "FavoritesList or FavoritesRemove or FavoritesClear"`
Expected: all 7 tests pass (2 in `TestFavoritesList` + 3 in `TestFavoritesRemove` + 2 in
`TestFavoritesClear`).

- [ ] **Step 5: Commit**

```bash
git add commands/music.py tests/test_commands_music.py
git commit -m "feat: add /favorites list, remove, and clear commands"
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
Expected: all tests pass, including the pre-existing suite plus every test added in Tasks 1-5 —
no regressions in any other module (in particular: `commands/reactionroles.py`'s existing
`on_raw_reaction_add`/`on_raw_reaction_remove` listeners must be unaffected — they're on a
different Cog and only ever act on messages tracked in their own `reaction_roles.json` data, never
on the music dashboard message).

- [ ] **Step 2: Manually re-verify the reaction-scoping guard**

Run:
```bash
grep -n "dashboard_msg.id != payload.message_id\|str(payload.emoji) != self.FAVORITE_EMOJI" commands/music.py
```
Confirm by inspection: both listeners check the reacted emoji AND the exact dashboard message id
before touching any favorites data — a reaction on any other message, or with any other emoji, is
a guaranteed no-op.

- [ ] **Step 3: Commit (only if Step 1 required a fix)**

```bash
git add -A
git commit -m "fix: address regression found in music-favorites full-suite pass"
```

If Step 1 found no regressions, skip this step — there is nothing to commit.

---

## Self-Review Notes

- **Spec coverage:** design spec section 1 (data layer) → Task 1; section 2 (reaction listeners +
  add/remove helpers) → Task 2; section 3 (reaction-staleness fix) → Task 3; section 4
  (`/favorites` command group) → Tasks 4-5; section 5 (help menu) → already automatic, no task
  needed (confirmed in the spec itself — `Music.help_category` already covers new commands on this
  cog).
- **Placeholder scan:** no TBD/TODO; every step has literal code or literal shell commands with a
  stated expected output.
- **Type consistency:** `_add_favorite(guild_id: str, user_id: str, metadata: dict)` and
  `_remove_favorite(guild_id: str, user_id: str, url: str)` signatures are consistent between
  Task 2's definition and both the listener call sites (same task) — no other task calls them
  directly. `load_music_favorites`/`save_music_favorites` signatures are consistent across Task 1's
  definition and every consumer (Task 2, 4, 5). The favorites-entry dict shape (`url`, `title`,
  `thumbnail`, `duration`) is identical everywhere it's constructed or read: `_add_favorite`
  (Task 2), `favorites_play`'s `entries` list comprehension (Task 4), `favorites_list`/
  `favorites_remove` (Task 5).
