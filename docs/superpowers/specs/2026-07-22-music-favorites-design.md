# Music Favorites via Reaction — Design

Date: 2026-07-22
Status: Approved by user, ready for implementation planning

## Goal

Let a user react ❤️ on the music "now playing" panel to save the current song to a personal,
per-server favorites list, un-react to remove it, and run `/favorites play` to queue their whole
favorites list — plus `/favorites list`, `/favorites remove`, and `/favorites clear` for managing
it.

## Why

Users want an easy way to build a personal playlist out of songs they hear the bot play, without
re-searching for them later.

## Non-Goals

- No cross-server favorites — scoped per guild, matching every other per-user data store in this
  bot (`player_stats.json`, `karma_stats.json` are both keyed `guild_id → user_id`; there is no
  existing precedent for global-per-user data, and introducing one wasn't wanted).
- No Discord UI buttons for favorites — reaction (❤️) is the only add/remove surface; `/favorites`
  is a plain command group, not a View.
- No changes to the queueing/playback engine — `/favorites play` reuses the existing
  `_queue_playlist_entries`/`_finalize_play` methods unchanged; no new queueing code path.

## Current Behavior (for reference)

- `Music.dashboard_messages: dict[str, discord.Message]` (`commands/music.py:289`) holds one
  persistent "now playing" panel message per guild, edited in place as songs change (via
  `_finalize_play`, `_update_dashboard_for_guild`, `refresh_dashboard`) — never deleted and
  resent for an in-progress session.
- `Music.current_track: dict[str, Track]` (`commands/music.py:287`) holds the actively-playing
  `Track` per guild; `Track.metadata` (`dashboard/audio_mixer.py:40`) contains
  `title`/`url`/`original_url`/`thumbnail`/`duration`/`requested_by`/`needs_resolve` — `url` is a
  short-lived resolved stream URL, `original_url` is the stable YouTube link and the one that
  matters for saving a favorite.
- `_play_song` (`commands/music.py:563-612`) is the single choke point every "a new song starts
  playing" path funnels through (`_finalize_play` when idle, `_process_queue` when a track
  finishes and the next one starts) — it sets `self.current_track[guild_id] = track` at line 611.
- `_queue_playlist_entries(guild_id, entries: list[dict], playlist_title, requester)`
  (`commands/music.py:431-460`) already does everything `/favorites play` needs: it iterates
  `entries`, reading `entry.get('url')`/`'title'`/`'thumbnail'`/`'duration'` per item, checks the
  blacklist, and appends to `self.queue[guild_id]`.
- `commands/reactionroles.py:136-165` is the established pattern for a reaction-driven feature in
  this codebase: `@commands.Cog.listener() async def on_raw_reaction_add(self, payload)`, ignoring
  the bot's own reactions, keying persisted JSON data by `str(payload.guild_id)`/`str(...)`.
- `commands/deleter.py`'s `autodeleter_group = app_commands.Group(...)` class attribute plus
  `@autodeleter_group.command(...)`-decorated methods is the established pattern for a slash
  command group on a Cog.
- `loadnsave.py`'s `load_karma_stats`/`save_karma_stats` (`loadnsave.py:467-471`) is the closest
  existing precedent for reaction-triggered per-user JSON data: no module-level cache (unlike
  `reaction_roles`, which does cache) — read fresh, mutate, write back, every time.

## Design

### 1. Data layer (`loadnsave.py`)

```python
async def load_music_favorites():
    return await _load_json_file(DATA_FOLDER, 'music_favorites.json')

async def save_music_favorites(favorites):
    await _save_json_file(DATA_FOLDER, 'music_favorites.json', favorites)
```

No cache, matching `karma_stats` — favorites are written on every reaction event, and a stale
cache across concurrent guilds/users is a correctness risk not worth trading for the read
savings. Shape: `{guild_id: {user_id: [{"url", "title", "thumbnail", "duration"}, ...]}}`.

### 2. Reaction listeners (`commands/music.py`, on the `Music` cog)

```python
FAVORITE_EMOJI = "❤️"

@commands.Cog.listener()
async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
    if payload.user_id == self.bot.user.id:
        return
    if str(payload.emoji) != FAVORITE_EMOJI:
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
    if str(payload.emoji) != FAVORITE_EMOJI:
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

Both listeners only need `payload.user_id` (not a resolved `Member`) since favorites don't
involve roles/permissions — simpler than `reactionroles.py`'s flow.

### 3. Reaction-staleness fix: clear reactions when a new song starts

The dashboard message is one message reused across songs — a ❤️ left on it from three songs ago
is still "on" the message. Without clearing it, a late un-react could be misread as un-favoriting
whatever's playing *now* rather than what was playing *then*. Fix: clear all reactions on the
dashboard message every time `_play_song` starts a genuinely new track — this is the single choke
point every "a new song starts" path already funnels through, so one change here covers all of
them (`_finalize_play`'s idle-start path and `_process_queue`'s natural-track-end path both call
into `_play_song`):

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

(Inserted right after `commands/music.py:611`, before the existing
`await self._update_dashboard_for_guild(guild_id)` at line 612.) Best-effort, matching this
file's established style for non-critical Discord API calls (`_finalize_play`'s message-edit
try/except, etc.) — `clear_reactions()` needs Manage Messages permission; if the bot lacks it,
this silently no-ops rather than breaking playback.

### 4. `/favorites` command group (`commands/music.py`, on the `Music` cog)

Same `app_commands.Group` pattern `commands/deleter.py`'s `autodeleter_group` already
establishes:

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

`favorites_play` deliberately does **not** go through `PlaylistChoiceView` (the "just one song vs.
whole playlist" prompt from a prior feature) — that prompt exists to resolve ambiguity in a
*link*; a favorites list has no such ambiguity, it's unconditionally "queue everything," matching
how `/play` already handles a playlist link that resolves to a single track (direct queue, no
prompt).

### 5. Help menu

`Music` cog already sets `self.help_category = "Music"` (`commands/music.py:282`) — since
`/favorites` lives on the same cog, its commands are automatically picked up and correctly
categorized by the dynamic help system (`commands/help.py`) with no further changes needed, the
same way `/seek` already was.

## Testing

- `tests/test_loadnsave_roundtrip.py` (existing parametrized file — extend, don't create a new
  file): add one `pytest.param(loadnsave.load_music_favorites, loadnsave.save_music_favorites,
  "music_favorites.json", None, {"123": {"456": [{"url": "u", "title": "t", "thumbnail": "",
  "duration": 100}]}}, id="music_favorites")` entry to the existing `ENTITY_CASES` list, matching
  `karma_stats`'s `None` cache-name convention.
- `tests/test_commands_music.py` (existing file — extend): `_add_favorite`/`_remove_favorite`
  cover — new favorite added; duplicate URL is a no-op; removing a present URL removes it;
  removing an absent URL is a no-op; removing from a guild/user with no favorites at all doesn't
  raise. The two reaction listeners cover — ignores the bot's own reaction; ignores a non-❤️
  emoji; ignores a reaction on a message that isn't the dashboard message; ignores a reaction when
  nothing is playing or the track is finished; add listener calls `_add_favorite` with the current
  track's metadata; remove listener calls `_remove_favorite` with the current track's
  `original_url`. `favorites_play`/`favorites_list`/`favorites_remove`/`favorites_clear` cover —
  empty-favorites messaging for play/list; `favorites_play` builds the correct `entries` list and
  calls `_queue_playlist_entries`/`_finalize_play` (mock both, assert call args); `favorites_list`
  truncates at 10 with a "…and N more" line; `favorites_remove` rejects an out-of-range position
  and correctly pops the right entry; `favorites_clear` empties the list without raising when the
  user already has no favorites recorded. `_play_song`'s new reaction-clearing — dashboard
  message's `clear_reactions()` is called when a new track starts; a `discord.Forbidden`/generic
  exception from it doesn't propagate and doesn't prevent playback from continuing.

## Rollout / Risk

- No changes to the queueing/playback engine — `/favorites play` is pure composition of two
  already-tested, already-shipped methods (`_queue_playlist_entries`, `_finalize_play`).
- New reaction listeners only ever act on the one message they recognize
  (`dashboard_messages[guild_id]`) and only for the ❤️ emoji — no interaction with any other
  reaction-based feature in the bot (`reactionroles.py`'s listeners are on different messages
  entirely, so no collision).
- `clear_reactions()` requires Manage Messages permission; degrades to a silent no-op (stale ❤️
  reactions may linger, no functional breakage) if the bot lacks it in a given server — not a
  blocker, consistent with how this file already treats non-critical Discord API failures.
