# CthulhuBotV2

**CthulhuBotV2** is a feature-rich, unofficial Discord bot designed to assist Keepers and Investigators in playing the **Call of Cthulhu** Tabletop RPG. Built with a modern, service-oriented architecture, it provides an immersive experience with a high-performance web dashboard and robust data management.

> **Disclaimer:** This is an **UNOFFICIAL** bot! It is **not** associated with Chaosium Inc. To play **Call of Cthulhu**, you will need the [Call of Cthulhu Keeper Rulebook](https://www.chaosium.com/call-of-cthulhu-keeper-rulebook-hardcover/), [Call of Cthulhu Starter Set](https://www.chaosium.com/call-of-cthulhu-starter-set/), or [Pulp Cthulhu](https://www.chaosium.com/pulp-cthulhu-hardcover/) published by [Chaosium Inc.](https://www.chaosium.com/)

## 🚀 Key Architectural Overhaul (New!)

The bot has recently undergone a major architectural transformation to improve performance, maintainability, and user experience:

*   **🗄️ Database-Backed (SQL)**: Replaced 30+ fragmented JSON files with a centralized **SQLite** database managed via **SQLAlchemy**.
*   **⚙️ Service-Oriented Logic**: Core game logic (Combat, Codex, Characters, Music) is now decoupled into a **Service Layer**, ensuring 100% logic parity between Discord commands and the Web Dashboard.
*   **✨ Glassmorphism Frontend**: The Web Dashboard has been completely refactored using **Tailwind CSS** with a modern, immersive **Glassmorphism** design ("Eldritch Glass").
*   **🛠️ Lightweight Commands**: All Discord commands have been reduced to lightweight entry points (< 100 lines), delegating all business logic to reusable services.
*   **🔄 Robust Persistence**: Game states, voice connections, and music queues (metadata) now survive bot restarts.

## Features

*   🛠️ **Slash Commands**: Fully integrated with Discord's Slash Commands (`/`) for a modern and intuitive user experience.
*   🕵️‍♂️ **Character Management**: Create, update, and manage investigator sheets with strict **Pydantic** validation.
*   🎲 **Advanced Dice Rolling**: Interactive rolls with deterministic parity verification and support for Bonus/Penalty dice, Luck spending, and Pushing.
*   🐙 **The Grimoire (Codex)**: A searchable, SQL-backed library of 3,300+ entries including monsters, spells, weapons, and historical events.
*   👊 **Pulp Cthulhu Support**: Comprehensive support for Pulp Archetypes, Talents, and modified game rules.
*   📜 **Session Management**: Real-time combat tracking and session logging persisted in the database.
*   🎵 **Music & Audio**: High-quality audio mixing with idle timeouts, auto-rejoin, and shared control between Discord and the Web Dashboard.
*   💻 **Eldritch Glass Dashboard**: An immersive web interface to manage your campaign:
    *   **Live Combat Tracker**: Monitor initiative and HP in real-time from the web.
    *   **Interactive Character Sheets**: Edit stats and backstories with instant database sync.
    *   **Searchable Codex**: Fast, indexed rule lookup.
    *   **Server Admin**: Manage RSS feeds, auto-rooms, karma, and more.

## Commands

The bot uses **Slash Commands** (`/`). 

### 🐙 Investigator Tools
*   `/newinvestigator`: 🕵️‍♂️ Multi-step character creation wizard.
*   `/mycharacter`: 📜 Interactive character card with tabbed stats, skills, and backstory.
*   `/rename`: 🏷️ Rename your investigator.
*   `/addbackstory`, `/updatebackstory`, `/removebackstory`: 📖 Comprehensive identity management.
*   `/retire`: 👴 Manage character lifecycle and retirement.

### 🎲 Dice Rolling & Session
*   `/roll`: 🎲 Interactive dice roll or skill check.
*   `/combat`: ⚔️ Start/Manage a combat session with an interactive tracker.
*   `/session`: 🎬 Start and log game sessions.

### 📚 The Grimoire (Codex)
*   `/codex`: 📖 Unified searchable rules reference.
*   `/randomnpc`: 👤 Generate random NPCs using the Codex database.
*   `/macguffin` / `/loot`: 🏺/💰 Generate plot devices and rewards.

### 🎵 Music & Sound
*   `/play` `[query/URL]`: 🎵 Immersive audio playback.
*   `/volume` / `/stop` / `/skip`: 🎼 Complete playback control.

## Installation

### Prerequisites

*   **Python 3.11** or higher.
*   **FFmpeg**: Required for audio playback.
*   **Playwright**: Required for dashboard features (`python -m playwright install --with-deps`).

### Quick Start

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/SenpaiCZ/CthulhuBotV2.git
    cd CthulhuBotV2
    ```
2.  **Run Setup**:
    *   **Windows**: `setup.bat`
    *   **Linux/Ubuntu**: `chmod +x setup.sh && ./setup.sh`
3.  **Configure**:
    *   Create a `.env` file or edit `config.json` with your `DISCORD_TOKEN`.
4.  **Sync Commands**:
    *   Start the bot (`python bot.py`) and run `!sync guild` in your Discord server.

## Migration Tools

If you are upgrading from a legacy version, use the provided migration utilities in the `tools/` directory:
*   `migrate_json_to_sql.py`: Port investigator data.
*   `migrate_settings_to_sql.py`: Port server configurations.
*   `migrate_campaign_to_sql.py`: Port journals and karma.
*   `migrate_game_to_sql.py`: Port the Codex and active games.

---

> **Note:** The `data/database.sqlite` included in this repository contains the sanitized **Codex (Rules)** data. User-specific data (players, settings) is cleared for the public release.
