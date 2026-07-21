# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

CthulhuBotV2 — Discord bot for Call of Cthulhu TTRPG. Python 3.11+, discord.py with slash commands. Runs bot process + optional Quart web dashboard concurrently via asyncio.

## Running

```bash
# Setup (first time)
pip install -r requirements.txt
playwright install chromium

# Run bot
python bot.py

# Config: config.json in root
# Required field: "token" (or set DISCORD_TOKEN env var)
# Optional: "enable_dashboard": true, "admin_password": "...", "dashboard_port": 5000
```

Bot token loads from `config.json` → `settings["token"]`, with `DISCORD_TOKEN` env var as override.

Dashboard accessible at `http://localhost:5000` when enabled.

## Sync Slash Commands

After adding/modifying commands, sync via Discord prefix commands:
- `!sync` — sync global
- `!sync guild` — sync to current guild (faster, dev use)
- `!sync clear` / `!sync clearguild` — clear commands

## Architecture

### Entry Point: `bot.py`
- Creates `commands.Bot` with dynamic prefix (per-guild, default `!`)
- Loads all `.py` files in `commands/` as extensions (Cogs)
- If `enable_dashboard: true`, starts Quart app (`dashboard/app.py`) as concurrent asyncio task via hypercorn

### Data Layer: `loadnsave.py`
All persistence goes through here. Pattern:
- JSON files in `data/` (mutable runtime data), `infodata/` (static game reference, cached in-memory), `gamedata/` (game content like questions)
- Every entity has `load_X()` / `save_X()` functions with in-memory cache (`_X_CACHE`)
- `infodata/` files are read-once and never evicted — reference data like monsters, spells, occupations, skills
- `data/` files are read-through cached; cache invalidated on save
- Async IO via `aiofiles`; sync variants exist for some (used in dashboard thread contexts)
- On JSON decode error: backs up `.bak`, returns `None` (callers must handle)

Key data files:
- `data/player_stats.json` — character sheets keyed by `user_id`
- `data/server_stats.json` — per-guild settings/prefixes
- `data/session_data.json` — active game session skill usage
- `data/retired_characters_data.json` — retired investigators
- `config.json` — bot config (token, dashboard toggle, etc.)

### Commands: `commands/`
Each file is a discord.py Cog loaded as an extension. Naming conventions:
- `_foo.py` prefix = a companion module holding `discord.ui.View`/`Modal`/`Select` classes split out of an oversized parent Cog file, or other shared helpers imported by other commands — **not** a standalone Cog. `bot.py` still tries to load every `.py` file in `commands/` as an extension, so a companion file must never define its own `async def setup(bot)`.
- Classes a companion file's parent Cog constructs directly are imported *by name* into the Cog module (`from commands._newinvestigator_stats import CoreStatSelectView`); classes only ever constructed by another class *within the same companion file* don't need a Cog-level import.
- A Cog occasionally imports a UI class from a companion file that isn't its own — e.g. `commands/combat.py` and `commands/_mychar_roll.py` both import `RollResultView` from `commands/_roll_views.py`, not from `commands/roll.py`'s own file. Grep the whole repo, not just the file you're editing, before assuming a class's only consumer is its original parent.
- Uses `app_commands` (slash) + legacy `commands` (prefix) mixed

Companion-file clusters as of this writing: `commands/newinvestigator.py`'s wizard splits across `_newinvestigator_data.py` (era/skill constants), `_newinvestigator_basicinfo.py`, `_newinvestigator_gamemode.py`, `_newinvestigator_stats.py`, `_newinvestigator_talents.py`, `_newinvestigator_skills.py`, `_newinvestigator_occupation.py`; `commands/roll.py` → `_roll_views.py`; `commands/codex.py` → `_codex_views.py`; `commands/karma.py` → `_karma_views.py`; `commands/journal.py` → `_journal_views.py`; `commands/mycharacter.py`'s `_mychar_view.py` hub further splits into `_mychar_inventory.py` and `_mychar_roll.py`.

See `docs/CONTRIBUTING.md` for the step-by-step process to add a new command or split a growing Cog.

Key shared modules:
- `emojis.py` — stat emoji helpers, health bar rendering
- `descriptions.py` — stat value → flavor text lookup
- `occupation_emoji.py` — occupation → emoji map
- `support_functions.py` — `session_success()` (records skill use in session), `MockContext` (wraps interaction as ctx-like object)
- `rss_utils.py` — YouTube channel URL → RSS feed URL resolver (uses yt-dlp)

### Dashboard: `dashboard/`
- `app.py` — composition root only (~300 lines): Quart app instance, security/CSRF/auth `before_request`/`after_request` hooks, template filters, context processors, and blueprint registration. It never defines a route directly.
- `blueprints/` — one file per feature area (24 files), each a Quart `Blueprint` registered in `app.py` near the bottom of the file. Every dashboard route lives in exactly one of these files, grouped by feature (e.g. all `/admin/karma` + `/api/karma/*` routes are in `karma.py`). Blueprints import `app` and other shared helpers back from `dashboard.app` — this circular-looking import is intentional and safe as long as `dashboard.app` (not a blueprint module) is always imported first, which is how `bot.py` and every test in this repo already does it.
- `state.py` — shared mutable state that must keep single, consistent object identity across `dashboard/app.py`, every blueprint that touches it, and the `commands/` cogs that also read/write it: `guild_mixers` and `server_volumes` (both shared with `commands/music.py`; `server_volumes` also with `commands/roll.py`), plus folder-path/constant globals (`IMAGES_FOLDER`, `FONTS_FOLDER`, `OLD_FONTS_FOLDER`, `BACKUP_FOLDER`, `SOUNDBOARD_FOLDER`, `BASIC_FONTS`, `MORSE_CODE_MAP`, `_PUBLIC_API`). Import these by reference (`from dashboard.state import server_volumes`, then mutate in place with `.update()`/`[key] = value`) — never rebind the name (`server_volumes = {...}` inside a consuming module breaks the shared identity every other importer relies on).
- `audio_mixer.py` — `MixingAudioSource`: FFmpeg-based audio source that mixes music + soundboard streams
- `file_utils.py` — sync file ops for dashboard use (upload, extract zip, rename, delete)

See `docs/CONTRIBUTING.md` for the step-by-step process to add a new dashboard route.

### Music: `commands/music.py`
- yt-dlp for audio extraction, FFmpeg for playback via discord.py voice
- Per-guild queue (`self.queue[guild_id]`), current track, volume
- Shares mixer state with dashboard via `dashboard.state.guild_mixers` (imported by reference, not `dashboard.app`)
- Linux/Pi: voice reconnect handled carefully (recent fix: `dcd8252`)

### Character System
- `commands/newinvestigator.py` — multi-step modal wizard hub Cog; handles eras (1920s/1930s/Modern), occupations, stat rolling, skill allocation. Wizard-stage View/Modal classes live in the sibling `commands/_newinvestigator_*.py` companion files (see Commands section above), not in this file.
- `commands/roll.py` — dice + skill checks; uses `rapidfuzz` for fuzzy skill name matching. UI classes (roll-result view, dice tray, disambiguation) live in `commands/_roll_views.py`.
- `descriptions.py` — maps stat values to flavor descriptions (thresholds, not exact match)
- Era skill base values live in `commands/_newinvestigator_data.py` as `ERA_SKILLS` (per-era dict) and `BASE_SKILLS` (the 1920s era, aliased as the default baseline). This is game-balance-sensitive static data — treat changes to it as game-content changes, not refactors, and keep it byte-identical across any future file move.

### Auto-Restart
- `restarter.py` — spawned by `/updatebot` and `/restart` commands; waits for old PID to exit (psutil), then re-launches `bot.py`

## Testing

- `pytest` (+ `pytest-asyncio`) — run `python -m pytest -q` from repo root (use the project's `.venv` if one exists: `.venv/bin/python -m pytest -q`).
- One test file per source module, named after it: `dashboard/blueprints/karma.py` → `tests/test_blueprint_karma.py`; `commands/_karma_views.py` → `tests/test_commands_karma_views.py`. A `_gaps` suffix (e.g. `test_render_blueprint_gaps.py`) marks a file that supplements — not replaces — coverage already present in an earlier same-module test file; check for an existing non-`_gaps` file before creating a new one.
- **Dashboard route tests** use Quart's test client against the real blueprint-registered `app` from `dashboard.app`. Any mutating route needs two things to pass the app's `before_request` hooks: a `login(client)` helper (sets `session['logged_in'] = True` via `session_transaction()`) for `check_api_auth`, and an `Origin` header matching the test client's host for `check_csrf`.
- **discord.py UI-class tests** (Views/Modals/Selects) construct the real class directly — never go through `dashboard.app` or a Cog's slash-command entry point for this. Mock only `discord.Interaction` and the specific `.response`/`.followup` methods the code under test actually calls (grep the source for every `interaction.response.*`/`interaction.followup.*` call site first — a shared fixture that mocks only the method one test happens to need will `TypeError` on a sibling test that hits an unmocked one). Installed discord.py is **2.7.1**: `BaseView.__init__` swallows the `asyncio.get_running_loop()` `RuntimeError` when called outside a running loop rather than raising it, so both sync and `@pytest.mark.asyncio` test functions can construct a View/Modal — but any test that `await`s a callback still needs `@pytest.mark.asyncio`. A `View`'s decorated buttons/selects (`@discord.ui.button`, `@discord.ui.select`) are added to `.children` during `super().__init__()`, *before* the constructor body's own `self.add_item(...)` calls run — don't assume `view.children[0]` is the item you `add_item`'d; use `next(c for c in view.children if isinstance(c, TargetClass))` when order isn't guaranteed. Simulate a Select choice with `select._values = [...]`. For a Modal field wrapped in `discord.ui.Label`, set `modal.field_name.component._value`, not `modal.field_name._value` (the Label itself has no `_value`).
- `mock.patch()` / `monkeypatch.setattr()` must target the module where the code under test *looks the name up*, not where the name is defined — e.g. a value imported into `dashboard/blueprints/karma.py` gets patched at `dashboard.blueprints.karma.<name>`, not at `loadnsave.<name>` where it's originally defined.
- Any test that writes through `loadnsave`'s `data/` folder must isolate via a `DATA_FOLDER` monkeypatch fixture pointed at `tmp_path` — patch **both** `loadnsave.DATA_FOLDER` **and** any blueprint/module that separately imports `DATA_FOLDER` by value (some do; check with `grep -n "^from loadnsave import.*DATA_FOLDER\|^DATA_FOLDER" <module>.py` before assuming one patch site covers it), or a test can silently write into the repository's real `data/` folder.
- Never use `MagicMock(name="Something")` expecting `mock.name == "Something"` — `name=` is a reserved `Mock` constructor kwarg (controls `repr()`, not a real attribute). Set it after construction instead: `mock.name = "Something"`.

## Adding a New Command

1. Create `commands/mycommand.py` with a Cog class + `async def setup(bot)` at bottom
2. Bot auto-loads all `.py` in `commands/` — no registration needed
3. Use `load_X` / `save_X` from `loadnsave` for persistence; never write JSON directly
4. For UI components (buttons/selects/modals), follow the `_foo.py` naming if shared across cogs

## Static Game Data

Reference data lives in `infodata/` as JSON: monsters, spells, deities, weapons, occupations, skills, phobias, manias, inventions, years, archetypes, pulp talents. These load once and are cached forever. Modify these files to change game content without touching code.
