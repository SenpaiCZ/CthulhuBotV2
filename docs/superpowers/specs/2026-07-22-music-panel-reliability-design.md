# Music Panel Reliability & Auto-Delete Exemption — Design

Date: 2026-07-22
Status: Approved by user, ready for implementation planning

## Goal

Fix two reported problems with the music system and three related bugs found during
investigation:

1. The bot's own auto-delete/purge system deletes the persistent music dashboard panel along
   with everything else, since it has no exemption mechanism at all.
2. After a long play session, the music panel sometimes stops visibly responding to button
   clicks.

## Why

A user reported both symptoms directly. Investigation (see Current Behavior below) found the
auto-delete system has literally no message exemptions of any kind, and found a concrete root
cause for the "stops responding" symptom: `Music._finalize_play()` silently orphans the old
dashboard message when an edit fails with anything other than `discord.NotFound`, leaving a
second, dead-looking panel behind while all future updates go to a different message the user
isn't looking at. Two related robustness gaps (an interaction-response bug in
`refresh_dashboard`, and two background loops with no error handler) surfaced in the same
investigation and match the same failure shape ("works fine, then permanently breaks after
running a while"), so they're included here rather than filed separately. A fifth, more minor
gap (`CookieView` has no `on_timeout`) was also found and is included as low-risk polish.

## Non-Goals

- No general "protect all pinned messages" auto-delete exemption — scoped narrowly to the
  tracked music dashboard message only, per explicit choice.
- No change to `/purge`'s or the dashboard bulk-delete's core deletion semantics beyond adding
  the same exemption — they still delete by count/age exactly as before.
- No auto-restart supervisor for the bot process itself (unrelated to this investigation — see
  the separate rollback-system design if that's still wanted).
- `CookieView` instances built by `_format_download_error()` (used in `/play`'s error path and
  `PlaylistChoiceView.just_one`'s error path) are **not** wired up with `on_timeout` — only the
  `/setytcookie` command's direct `CookieView` gets it. See Design section 5 for why.

## Current Behavior (for reference)

- `commands/deleter.py`'s `autodelete_task` (a `tasks.loop(minutes=5)`) calls
  `channel.purge(limit=None, before=threshold_time)` with no `check=` predicate — deletes
  everything older than the configured age, unconditionally. The manual `/purge` command and the
  dashboard's `api_bulk_delete` do the same with no predicate, just a different `limit=`/`before=`
  combination.
- `Music._finalize_play()` (`commands/music.py:406-429`) tries `old_msg.edit(...)`; on
  `discord.NotFound` it correctly forgets the old message; on any other exception it just drops
  the local reference (`old_msg = None`) without deleting the old message, then sends a brand-new
  one. The old message stays in the channel, its buttons still routing to real handlers
  (`toggle_pause`, `skip_track`, etc. — they're bound to `guild_id`, not the specific message), but
  its embed never updates again since only the new message is tracked in
  `self.dashboard_messages[guild_id]` from that point on.
- `Music.refresh_dashboard()` (`commands/music.py:647-671`) wraps both `msg.edit(...)` and the
  subsequent `interaction.response.defer()` in one `try/except discord.NotFound`. A `defer()`
  failure (e.g. an expired interaction token from a slow edit) is indistinguishable in that except
  block from "the message is gone," incorrectly clearing `dashboard_messages[guild_id]` and
  falling through to a second, also-doomed `interaction.response.send_message(...)`.
- `_idle_disconnect` and `_refresh_dashboards` (`commands/music.py:308-364`) have no
  `@loop.error` handler. `_refresh_dashboards`'s loop body already catches `Exception` broadly
  inside its per-guild loop, so it's fairly well protected; `_idle_disconnect` only wraps the
  `vc.disconnect()` call narrowly (`commands/music.py:327-330`) — an exception from
  `self._cleanup_guild()` or `self._update_dashboard_for_guild()` (lines 326, 331) would escape
  uncaught. Per discord.py's default behavior, an unhandled exception permanently stops a
  `tasks.Loop` with no restart and no notification.
- `CookieView` (`commands/music.py:160-168`, `timeout=300`) has no `on_timeout`. Once its
  5-minute window elapses, discord.py's internal view store drops it; a click after that point
  fails at the Discord-client level ("this interaction failed") rather than being silently eaten
  — annoying but not silent. Still worth a visible, proactive disabled state for the common case.

## Design

### 1. Auto-delete exemption for the music dashboard (`commands/deleter.py`)

A new helper method on `Deleter`:

```python
def _is_protected_message(self, message: discord.Message) -> bool:
    """True if this message is the guild's currently-tracked music dashboard panel."""
    music_cog = getattr(self.bot, 'music_cog', None)
    if not music_cog or not message.guild:
        return False
    dashboard_msg = music_cog.dashboard_messages.get(str(message.guild.id))
    return dashboard_msg is not None and dashboard_msg.id == message.id
```

Applied uniformly at all three `purge()` call sites via a `check=` predicate (messages for which
`check()` returns `True` are the ones deleted, so the predicate is the *inverse* of "protected"):

- `autodelete_task` (`commands/deleter.py:112`):
  `await channel.purge(limit=None, before=threshold_time, check=lambda m: not self._is_protected_message(m))`
- `/purge` command (`commands/deleter.py:94`):
  `deleted = await interaction.channel.purge(limit=amount, check=lambda m: not self._is_protected_message(m))`
- `api_bulk_delete` (`commands/deleter.py:129`):
  `deleted = await channel.purge(limit=int(amount), check=lambda m: not self._is_protected_message(m))`

This mirrors the defensive `getattr`/`hasattr` pattern `dashboard/blueprints/music.py` already
uses to reach the music cog, so it degrades cleanly (no exemption, no crash) if the music cog
isn't loaded.

### 2. Stop orphaning the old dashboard message (`commands/music.py`, `_finalize_play`)

Replace the generic-exception branch so it best-effort deletes the old message before falling
through to sending a replacement — guaranteeing at most one live panel per guild at any time:

```python
        if old_msg:
            try:
                await old_msg.edit(embed=embed, view=view)
            except discord.NotFound:
                self.dashboard_messages.pop(guild_id, None)
                old_msg = None
            except Exception:
                try:
                    await old_msg.delete()
                except Exception:
                    pass
                old_msg = None
```

`_update_dashboard_for_guild()` (`commands/music.py:614-626`) is **not** touched — it only ever
edits an existing message and never creates a new one on failure, so it has no duplication risk
to fix; its current "give up silently, try again next tick" behavior is an acceptable contract
for a pure best-effort refresh.

### 3. Separate the edit and defer failure paths (`commands/music.py`, `refresh_dashboard`)

```python
        if msg:
            try:
                await msg.edit(embed=embed, view=view)
            except discord.NotFound:
                self.dashboard_messages.pop(guild_id, None)
                msg = None
            else:
                if interaction and not interaction.response.is_done():
                    await interaction.response.defer()
                return
```

A `defer()` failure now propagates as itself instead of being caught and misinterpreted as "the
message is gone." This matches the function's pre-existing behavior for non-`NotFound` edit
failures too (already uncaught/propagating before this change) — no new exception surface is
introduced, only the incorrect one is removed.

### 4. Error handlers on the two background loops (`commands/music.py`)

```python
    @_idle_disconnect.error
    async def _idle_disconnect_error(self, error: Exception):
        print(f"[Music] _idle_disconnect loop crashed, restarting: {error}")
        self._idle_disconnect.restart()

    @_refresh_dashboards.error
    async def _refresh_dashboards_error(self, error: Exception):
        print(f"[Music] _refresh_dashboards loop crashed, restarting: {error}")
        self._refresh_dashboards.restart()
```

Placed directly after each loop's existing `@_idle_disconnect.before_loop` /
`@_refresh_dashboards.before_loop` handler. `Loop.error()` + `Loop.restart()` from inside the
handler is a standard discord.py idiom — restarting is safe here since both loops run on
20-30 second intervals (not a tight retry loop) and their bodies are otherwise already
well-guarded, so a restart-after-crash converts "silently dead forever" into "logs once, keeps
running" rather than risking a fast crash loop.

### 5. `CookieView.on_timeout` — scoped to the direct-send case only

```python
class CookieView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.message: discord.Message | None = None

    @discord.ui.button(label="Set YouTube Cookie", emoji="🍪", style=discord.ButtonStyle.primary)
    async def set_cookie_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Admins only.", ephemeral=True)
        await interaction.response.send_modal(CookieModal())

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
            except Exception:
                pass
```

`self.message` is only ever set at the `/setytcookie` command site
(`commands/music.py:824-837`):

```python
        view = CookieView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()
```

The two other `CookieView` construction sites — inside `_format_download_error()` (used by
`/play`'s `DownloadError` branch and `PlaylistChoiceView.just_one`'s `DownloadError` branch) —
are deliberately left with `self.message` unset (`None`), so their `on_timeout` becomes a no-op
disable-only (no visible effect, but also no risk). Wiring `.message` there too would require
different code at three separate call sites (an ephemeral `followup.send`, and an
`interaction.message.edit` on someone else's existing prompt message) for a rarer, already
recoverable path — Discord's own "this interaction failed" client-side message already gives the
user a clear signal once one of *those* CookieViews expires. Scoping to the one common,
easily-fixed path avoids that complexity for a proportionally small benefit.

## Testing

- `tests/test_commands_deleter.py` (new file — confirm it doesn't already exist before creating):
  `_is_protected_message()` returns `True` only for the exact tracked dashboard message of the
  message's own guild (not a dashboard message from a *different* guild, not a non-dashboard
  message); returns `False` gracefully when no music cog is loaded (`bot.music_cog` absent) or the
  message has no guild. Each of the three purge call sites passes a `check=` that correctly
  excludes a protected message from a fake channel's `purge()` call (mock `channel.purge` and
  assert the `check` kwarg's behavior against a protected vs. unprotected `discord.Message` stub).
- `tests/test_commands_music.py` (existing file, extend): `_finalize_play` — on a non-`NotFound`
  edit exception, the old message's `.delete()` is called and a new message is sent (extends the
  existing `TestFinalizePlay` class). `refresh_dashboard` — a `defer()` failure after a successful
  edit propagates instead of clearing `dashboard_messages`; a `NotFound` edit failure still falls
  through to sending a new message as before. The two new `.error` handlers call `.restart()` on
  their respective loop (mock the loop object, invoke the error handler directly with a synthetic
  exception, assert `restart()` was called). `CookieView.on_timeout` disables its button and edits
  `self.message` when set; is a no-op when `self.message` is `None`. The `/setytcookie` command
  sets `view.message` after sending.

## Rollout / Risk

- Two independent-but-related fix groups (deleter exemption; music-panel resilience) —
  implementable as separate tasks/commits within one plan, same pattern as prior work in this
  repo.
- No data-layer changes. No behavior change to any command's happy path — every fix only changes
  what happens on an already-failing/edge-case branch (a purge that would have hit the panel, an
  edit that would have orphaned a message, a defer that would have been misattributed, a loop that
  would have died silently, a cookie prompt that would have kept looking clickable after expiring).
