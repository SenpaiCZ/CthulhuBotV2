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

## 🌐 Hosting as a Discord Activity (New!)

CthulhuBotV2 can now be hosted as a **Discord Activity**, allowing players to interact with their character sheets and roll dice directly within the Discord interface.

### Prerequisites for Activities
*   A **publicly accessible HTTPS URL** (required by Discord).
*   A registered Discord Application in the [Developer Portal](https://discord.com/developers/applications).

### 🚀 Turnkey Setup with Cloudflare Tunnel (Recommended for RPi)

The easiest way to host your bot from a local device (like a Raspberry Pi) is using **Cloudflare Tunnel**. This provides a secure HTTPS URL without port-forwarding.

1.  **Run the Tunnel Setup Script**:
    ```bash
    chmod +x tools/setup_tunnel.sh
    ./tools/setup_tunnel.sh
    ```
2.  **Follow the Authentication Prompt**: The script will provide a link to log in to your Cloudflare account and authorize the tunnel.
3.  **Configure your Domain**: If you have a custom domain on Cloudflare, the script can automatically create a CNAME record (e.g., `cthulhubot.yourdomain.com`).
4.  **Update Config**: Add your new tunnel URL to `config.json` under the `"tunnel_url"` key.

### 🛠️ Discord Developer Portal Configuration

Once your tunnel is live:
1.  Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2.  Select your App and go to the **Activities** section.
3.  Set the **URL Mapping**:
    *   **Root URL**: Paste your Tunnel URL (e.g., `https://cthulhubot.yourdomain.com`).
    *   **Mapping**: Map `/` to your root URL.
4.  Copy your **Client ID** and put it in `config.json` as `"activity_client_id"`.
5.  Launch the bot and try starting the Activity in any voice channel!

### 📱 Mobile-Optimized Experience

The Discord Activity is designed with a **mobile-first approach**. Whether you're on a desktop or using the Discord app on your phone, the UI automatically adjusts to provide:
*   **Touch-Friendly Controls**: Large, accessible buttons for dice rolls and stat edits.
*   **Responsive Layouts**: Character sheets that stack elegantly on narrow screens.
*   **Immersive Visuals**: The "Eldritch Glass" design remains consistent across all devices.

### ❓ Troubleshooting Tunnel & Activity Issues

*   **`cloudflared` not found**: The setup script works best on Debian/Ubuntu (including Raspberry Pi OS). For other systems, install it manually from the [Cloudflare docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/).
*   **"Invalid Origin" or Connection Errors**: 
    *   Ensure `tunnel_url` in `config.json` exactly matches the URL in the Discord Developer Portal.
    *   Verify that the `cloudflared` service is running (`systemctl status cloudflared`).
*   **Activity stuck on "Loading"**: Check the bot console for any errors. Ensure the `activity_client_id` is correct.
*   **Port 5000 Conflicts**: If another service is using port 5000, change the dashboard port in `config.json` and update your tunnel's `config.yml` accordingly.

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
