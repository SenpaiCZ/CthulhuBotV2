# CthulhuBotV2 - Technical Context

This document provides architectural overview, development guidelines, and operational procedures for CthulhuBotV2.

## Project Overview
CthulhuBotV2 is a specialized Discord bot for the **Call of Cthulhu TTRPG**. It features a comprehensive character sheet system, interactive dice rolling with Luck spending, a searchable game codex (The Grimoire), music playback, and a concurrent web dashboard for administrative management.

### Tech Stack
- **Language:** Python 3.11+
- **Discord Library:** `discord.py` (with Slash Commands)
- **Web Framework:** Quart (Async Flask-like)
- **Persistence:** JSON-based flat files with in-memory caching
- **Audio:** `yt-dlp` for streaming, FFmpeg for mixing and playback
- **UI:** Discord UI Components (Modals, Views, Selects) + HTML/CSS Dashboard

---

## Architecture & Directory Structure

### Core Components
- `bot.py`: Main entry point. Initializes the Discord bot, loads extensions, and starts the Quart dashboard concurrently.
- `loadnsave.py`: Central data access layer. Implements async loading/saving with in-memory caching and corrupted file recovery.
- `commands/`: Contains discord.py Cogs. Any `.py` file not starting with `_` is auto-loaded as an extension.
- `dashboard/`: The web interface (Quart app). Shares state with the bot via shared objects (e.g., `guild_mixers`).
- `data/`: Mutable runtime data (player stats, server settings).
- `infodata/`: Static game reference data (monsters, spells, weapons). Cached indefinitely once loaded.
- `gamedata/`: Supplementary game content (quiz questions, etc.).

### Shared Utilities
- `emojis.py`: Helpers for stat-specific emojis and health bar rendering.
- `descriptions.py`: Flavor text mappings for stat values.
- `support_functions.py`: Common helpers like `session_success()` for skill progression.
- `occupation_emoji.py`: Mapping of TTRPG occupations to visual emojis.

---

## Development Guidelines

### 1. Adding New Commands
- Create a new file in `commands/`.
- Use `app_commands` for Slash commands.
- Use the `_filename.py` convention for files containing shared UI components (Views/Modals) that should **not** be loaded as standalone Cogs.
- **Registration:** Bot auto-loads files. After adding/modifying commands, use `!sync guild` (prefix command) in Discord for instant development testing.

### 2. Data Persistence
- **Rule:** Never interact with JSON files directly.
- **Workflow:** Use `loadnsave.py`.
    - Use `await load_X()` to get data (usually returns a dict).
    - Use `await save_X(data)` to persist changes.
- `infodata/` is for **read-only** game content. Changes here require a bot restart or cache clearing (if implemented).

### 3. Asynchronous Programming
- Use `async/await` for all I/O operations (network, disk).
- Avoid blocking calls in command handlers.
- The Dashboard runs on the same event loop as the Bot; be mindful of shared state thread-safety (though largely handled by `asyncio` single-threaded loop).

### 4. Audio Processing
- Custom `MixingAudioSource` (`dashboard/audio_mixer.py`) allows simultaneous playback of music and soundboard effects.
- Music state is managed per-guild in `commands/music.py`.

---

## Building and Running

### Prerequisites
- Python 3.11+
- FFmpeg (added to PATH)
- `pip install -r requirements.txt`
- `playwright install chromium`

### Key Commands
- **Run Bot:** `python bot.py`
- **Sync Commands:** Use `!sync guild` (instant) or `!sync` (global, up to 1hr) inside Discord.
- **Update Bot:** `/updatebot` (triggers `updater.py` and `restarter.py`).

### Configuration
Configuration is handled via `config.json` with environment variable overrides.
- `token` / `DISCORD_TOKEN`: Required bot token.
- `enable_dashboard`: Boolean to toggle the Quart app.
- `admin_password`: Used for Dashboard authentication.

---

## Common Workflows for AI Agents

- **Modifying Character Stats:** Edit `data/player_stats.json` via `load_player_stats` / `save_player_stats`.
- **Expanding the Codex:** Add new entries to the relevant file in `infodata/` (e.g., `monsters.json`).
- **Fixing Music Issues:** Check `commands/music.py` and ensure FFmpeg parameters are correct for the host OS (Linux/Pi vs Windows).
- **UI Tweaks:** Shared UI logic is often in `commands/_foo_view.py`. Emojis are managed in `emojis.py`.
