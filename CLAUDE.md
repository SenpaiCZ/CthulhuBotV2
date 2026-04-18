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
- `_foo.py` prefix = shared View/UI helpers imported by other commands (not standalone Cogs)
- Uses `app_commands` (slash) + legacy `commands` (prefix) mixed

Key shared modules:
- `emojis.py` — stat emoji helpers, health bar rendering
- `descriptions.py` — stat value → flavor text lookup
- `occupation_emoji.py` — occupation → emoji map
- `support_functions.py` — `session_success()` (records skill use in session), `MockContext` (wraps interaction as ctx-like object)
- `rss_utils.py` — YouTube channel URL → RSS feed URL resolver (uses yt-dlp)

### Dashboard: `dashboard/`
- `app.py` — Quart app; all web routes + API endpoints. Imports heavily from `loadnsave`. Shares `guild_mixers` and `server_volumes` dicts with the music cog.
- `audio_mixer.py` — `MixingAudioSource`: FFmpeg-based audio source that mixes music + soundboard streams
- `file_utils.py` — sync file ops for dashboard use (upload, extract zip, rename, delete)

### Music: `commands/music.py`
- yt-dlp for audio extraction, FFmpeg for playback via discord.py voice
- Per-guild queue (`self.queue[guild_id]`), current track, volume
- Shares mixer state with dashboard via `dashboard.app.guild_mixers`
- Linux/Pi: voice reconnect handled carefully (recent fix: `dcd8252`)

### Character System
- `commands/newinvestigator.py` — multi-step modal wizard; handles eras (1920s/1930s/Modern), occupations, stat rolling, skill allocation
- `commands/roll.py` — dice + skill checks; uses `rapidfuzz` for fuzzy skill name matching
- `descriptions.py` — maps stat values to flavor descriptions (thresholds, not exact match)
- Era skill base values defined in `newinvestigator.py` as `ERA_SKILLS` dict

### Auto-Restart
- `restarter.py` — spawned by `/updatebot` and `/restart` commands; waits for old PID to exit (psutil), then re-launches `bot.py`

## Adding a New Command

1. Create `commands/mycommand.py` with a Cog class + `async def setup(bot)` at bottom
2. Bot auto-loads all `.py` in `commands/` — no registration needed
3. Use `load_X` / `save_X` from `loadnsave` for persistence; never write JSON directly
4. For UI components (buttons/selects/modals), follow the `_foo.py` naming if shared across cogs

## Static Game Data

Reference data lives in `infodata/` as JSON: monsters, spells, deities, weapons, occupations, skills, phobias, manias, inventions, years, archetypes, pulp talents. These load once and are cached forever. Modify these files to change game content without touching code.
