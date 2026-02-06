# CthulhuBotV2

**CthulhuBotV2** is a feature-rich, unofficial Discord bot designed to assist Keepers and Investigators in playing the **Call of Cthulhu** Tabletop RPG. It provides tools for character management, dice rolling, rule lookups, and session management.

> **Disclaimer:** This is an **UNOFFICIAL** bot! It is **not** associated with Chaosium Inc. To play **Call of Cthulhu**, you will need the [Call of Cthulhu Keeper Rulebook](https://www.chaosium.com/call-of-cthulhu-keeper-rulebook-hardcover/), [Call of Cthulhu Starter Set](https://www.chaosium.com/call-of-cthulhu-starter-set/), or [Pulp Cthulhu](https://www.chaosium.com/pulp-cthulhu-hardcover/) published by [Chaosium Inc.](https://www.chaosium.com/)

## Features

*   🕵️‍♂️ **Character Management**: Create, update, and manage investigator sheets, including stats, skills, and backstories.
*   🎲 **Advanced Dice Rolling**: Interactive rolls with support for Bonus/Penalty dice, Luck spending, and Pushing rolls.
*   🐙 **Keeper Tools**: Extensive library of game information including firearms, inventions, madness tables, phobias/manias, and NPC generation.
*   👊 **Pulp Cthulhu Support**: Includes Pulp Archetypes, Talents, and modified character creation rules.
*   📜 **Session Management**: Tools to start, track, and log game sessions.
*   🎵 **Music Bot**: High-quality music playback from YouTube with queue management, looping, and volume control.
*   💻 **Web Dashboard**: A powerful web interface to manage the bot:
    *   **Karma System**: Configure roles, emojis, and notifications.
    *   **Auto Rooms**: Easy setup for voice channel generation.
    *   **RSS Feeds**: Manage subscriptions and settings.
    *   **Server Prefixes**: Manage bot prefixes.
    *   **File Editor**: Edit configuration and data files directly.
    *   **Soundboard**: Upload and play audio clips in voice channels.
    *   **Music Control**: Manage the music queue and blacklist songs.
    *   **Game Settings**: Configure gameplay rules like Luck Threshold.
    *   **Reaction Roles**: easily configure self-assignable roles.
*   📈 **Karma System**: Track user reputation with custom upvote/downvote emojis.
*   🎭 **Reaction Roles**: Allow users to assign roles to themselves by reacting to messages.
*   🔊 **Soundboard**: Admin-controlled soundboard to play audio clips in voice channels.
*   🛠️ **Utility & Admin**: Auto-rooms, auto-moderation, YouTube feed integration, and RSS feeds.

## Commands

The bot uses a dynamic prefix (default is `!`). Here is a list of available commands categorized by function:

### 🐙 Cthulhu & Investigator Tools
*   `newinvestigator` (alias: `newinv`): 🕵️‍♂️ Start the character creation wizard.
*   `mychar`: 📜 View your character sheet.
*   `autochar`: 🤖 Generate random stats for your investigator (Standard CoC 7e rules).
*   `stat`: 📊 View or edit specific stats.
*   `rename`: 🏷️ Rename your character.
*   `renameskill`: ✏️ Rename a skill on your sheet.
*   `deleteinvestigator`: 🗑️ Delete a character.
*   `addbackstory`: 📖 Add backstory elements.
*   `updatebackstory`: 🔄 Update backstory elements.
*   `removebackstory`: ❌ Remove backstory elements.
*   `generatebackstory`: 🎲 Generate a random backstory.
*   `retire`: 👴 Retire an active character.
*   `unretire`: 👶 Bring a retired character back.
*   `printcharacter` (aliases: `pchar`, `printchar`): 🖼️ Generate an image of your character sheet.

### 🎲 Dice Rolling & Session
*   `newroll` (aliases: `roll`, `d`, `nd`): 🎲 Perform a dice roll or skill check. Interactive interface allows for Bonus/Penalty dice and Luck spending.
*   `showluck`: 🍀 Display current luck.
*   `startsession`: 🎬 Start a new game session.
*   `showsession`: 📝 Show current session details.
*   `wipesession`: 🧹 Clear session data.

### 🎵 Music & Sound
*   `play` (alias: `p`): 🎵 Play a song from YouTube.
*   `skip` (alias: `s`): ⏭️ Skip the current song.
*   `stop` (aliases: `leave`, `disconnect`): 🛑 Stop music, clear queue, and disconnect.
*   `volume` (alias: `vol`): 🔊 Set playback volume (0-100).
*   `loop`: 🔁 Toggle song looping.
*   `queue` (alias: `q`): 🎼 View the current music queue.
*   `nowplaying` (alias: `np`): 💿 Show the currently playing song.

### 📈 Karma System
*   `setupkarma`: ⚙️ Interactive setup wizard for the karma system.
*   `setupkarmaroles`: 🧙 Interactive wizard to manage rank roles.
*   `karma` (alias: `k`): 🌟 Check karma for yourself or another user.
*   `leaderboard` (aliases: `top`): 🏆 Show the Karma leaderboard.

### 🎭 Reaction Roles
*   `reactionrole` (alias: `rr`): 🎭 Setup a reaction role on a message (Admin).

### 🧠 Keeper Resources
*   `changeluck`: 🍀 Modify the server's maximum luck spend threshold (Default: 10).
*   `occupationinfo`: 💼 Lookup occupation details.
*   `skillinfo`: 📚 Lookup skill details.
*   `createnpc`: 👤 Generate an NPC.
*   `randomname`: 🏷️ Generate a random name (1920s).
*   `macguffin`: 🏺 Generate a MacGuffin.
*   `loot`: 💰 Generate random loot.
*   `archetypeinfo`: 🦸‍♂️ Lookup archetype info (Pulp).
*   `firearms`: 🔫 Lookup firearm statistics.
*   `inventions`: 💡 Lookup invention details.
*   `talents`: 🌟 Lookup talent info.
*   `years`: 📅 Historical info for different years.
*   `madness`: 🤪 Consult madness rules.
*   `madnessAlone`: 🌑 Madness tables for solo investigators.
*   `insaneTalents`: 🩸 Lookup insane talents.
*   `phobia`: 😨 Random phobia.
*   `mania`: 🤩 Random mania.
*   `poisons`: 🧪 Lookup poison info.

### 🛠️ General & Admin
*   `autoroomkick`: 👢 Kick user from auto-room.
*   `autoroomlock`: 🔒 Lock auto-room.
*   `autoroomunlock`: 🔓 Unlock auto-room.
*   `reportbug`: 🐛 Report a bug to the developer.
*   `repeatafterme`: 🦜 Make the bot repeat a message.
*   `uptime`: ⏱️ Check bot uptime.
*   `autoroomsetup`: ⚙️ Interactive setup wizard for Auto Rooms.
*   `autoroomset`: ⚙️ Configure auto-rooms (Legacy).
*   `changeprefix`: ❗ Change the bot's command prefix for the server.
*   `ping`: 🏓 Check latency.
*   `addreaction`: ➕ Add a smart reaction.
*   `removereaction`: ➖ Remove a smart reaction.
*   `listreactions`: 📋 List all smart reactions.
*   `youtube`: 📺 Setup YouTube channel notifications.
*   `unsubscribe`: 🔕 Unsubscribe from YouTube notifications.
*   `deleter`: 🗑️ Setup auto-deletion for channels.
*   `autodeleter`: 🤖 Configure auto-deleter.
*   `stopdeleter`: 🛑 Stop auto-deletion.
*   `rss`: 📰 Add a specific RSS feed manually.
*   `rsssetup`: 📰 Interactive setup wizard for RSS feeds.

## Installation

### Prerequisites

*   **Python 3.11** or higher: [Download Python](https://www.python.org/downloads/)
*   **Git**: [Download Git](https://git-scm.com/downloads)
*   **FFmpeg**: Required for audio playback.
    *   **Windows**: [Download FFmpeg](https://ffmpeg.org/download.html). Extract the archive and add the `bin` folder to your System PATH environment variable.
    *   **Linux**: Install via your package manager (e.g., `sudo apt install ffmpeg`).

#### Discord Developer Portal Setup

When creating your bot application in the [Discord Developer Portal](https://discord.com/developers/applications), please ensure the following:

1.  **Permissions Integer**: Use the integer `288746576` to automatically select the required permissions.
    *   *Includes*: Manage Channels, Add Reactions, View Channels, Send Messages, Manage Messages, Embed Links, Attach Files, Read Message History, Use External Emojis, Connect, Speak, Move Members, Manage Roles.
2.  **Privileged Gateway Intents**: You **must** enable the following intents under the "Bot" tab for the bot to function correctly:
    *   **Presence Intent**
    *   **Server Members Intent**
    *   **Message Content Intent**

### Quick Start (Auto-Install)

The repository comes with automated setup scripts for both Linux/macOS and Windows. These scripts handle virtual environment creation, dependency installation, and initial configuration.

**Linux/macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```batch
setup.bat
```

After running the setup script, edit the `config.json` file in the root directory to add your bot token and API keys.

---

### Manual Installation

If you prefer to install manually, follow these steps.

#### 1. Installation on Linux

**A. Clone and Setup**

1.  Open your terminal.
2.  Clone the repository:
    ```bash
    git clone https://github.com/YourUsername/CthulhuBotV2.git
    cd CthulhuBotV2
    ```
3.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    ```
4.  Activate the virtual environment:
    ```bash
    source venv/bin/activate
    ```
5.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
6.  Install Playwright browsers:
    ```bash
    playwright install chromium
    ```

**B. Configuration**

1.  The bot uses `config.json` in the root directory.
2.  Create `config.json` and add your configuration (see [Configuration Details](#configuration-details)):
    ```json
    {
        "token": "YOUR_DISCORD_BOT_TOKEN",
        "youtubetoken": "YOUR_YOUTUBE_API_KEY",
        "enable_dashboard": true,
        "admin_password": "SetAStrongPasswordHere"
    }
    ```

**C. Running the Bot**

To run the bot manually:
```bash
python bot.py
```

**D. Auto-Start with Systemd**

To keep the bot running in the background and start automatically on boot:

1.  Create a service file:
    ```bash
    sudo nano /etc/systemd/system/cthulhubot.service
    ```
2.  Paste the following content (update paths and user accordingly):
    ```ini
    [Unit]
    Description=CthulhuBotV2 Discord Bot
    After=network.target

    [Service]
    User=your_linux_username
    WorkingDirectory=/path/to/CthulhuBotV2
    ExecStart=/path/to/CthulhuBotV2/venv/bin/python bot.py
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```
    *Replace `/path/to/CthulhuBotV2` with the actual path to your cloned directory.*
    *Replace `your_linux_username` with your actual username.*

3.  Enable and start the service:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable cthulhubot.service
    sudo systemctl start cthulhubot.service
    ```
4.  Check status:
    ```bash
    sudo systemctl status cthulhubot.service
    ```

---

#### 2. Installation on Windows

**A. Clone and Setup**

1.  Open Command Prompt (cmd) or PowerShell.
2.  Clone the repository:
    ```bash
    git clone https://github.com/YourUsername/CthulhuBotV2.git
    cd CthulhuBotV2
    ```
3.  Create a virtual environment:
    ```bash
    python -m venv venv
    ```
4.  Activate the virtual environment:
    ```cmd
    venv\Scripts\activate
    ```
5.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
6.  Install Playwright browsers:
    ```bash
    playwright install chromium
    ```

**B. Configuration**

1.  The bot uses `config.json` in the root directory.
2.  Create `config.json` and add your configuration (see [Configuration Details](#configuration-details)):
    ```json
    {
        "token": "YOUR_DISCORD_BOT_TOKEN",
        "youtubetoken": "YOUR_YOUTUBE_API_KEY",
        "enable_dashboard": true,
        "admin_password": "SetAStrongPasswordHere"
    }
    ```

**C. Running the Bot**

To run the bot manually, make sure the virtual environment is activated, then run:
```bash
python bot.py
```

**D. Auto-Start on Windows**

To make the bot start automatically when you log in:

1.  Create a new file named `start_bot.bat` in the project folder.
2.  Edit it and add the following lines (adjust paths as necessary):
    ```batch
    @echo off
    cd /d "C:\path\to\CthulhuBotV2"
    call venv\Scripts\activate.bat
    python bot.py
    pause
    ```
3.  Press `Win + R`, type `shell:startup`, and press Enter. This opens the Startup folder.
4.  Create a shortcut to your `start_bot.bat` file and place it in this Startup folder.
    *   *Alternatively, you can use Windows Task Scheduler for more advanced control (e.g., running regardless of user login).*

---

### 3. Deployment on Replit

1.  Fork the repository to your Replit account.
2.  Go to the **Tools** pane and select **Secrets**.
3.  Add the following secrets (Environment Variables):
    *   `DISCORD_TOKEN`: Your Discord Bot Token.
    *   `YOUTUBE_API_KEY`: Your YouTube Data API Key (Optional).
4.  Run the bot. The `config.json` file serves as a template with default values.

---

### Configuration Details

The bot prioritizes configuration in the following order:
1.  **Environment Variables** (Highest priority)
2.  `config.json`

**Common Settings (`config.json`):**
```json
{
    "token": "YOUR_DISCORD_BOT_TOKEN",
    "youtubetoken": "YOUR_YOUTUBE_API_KEY",
    "enable_dashboard": true,
    "admin_password": "your_secure_password"
}
```

### Updating the Bot

You can easily update the bot using the included `update.bat` script (Windows only). This script will back up your data, download the latest version from GitHub, and apply updates while preserving your `config.json`.

### YouTube Cookies Support

To support age-restricted content or avoid rate limits, you can provide a cookies file for `yt-dlp`.

1.  **Create Directory:** Create a folder named `cookies` in the root directory.
2.  **Get Cookies:** Use a browser extension (like "Get cookies.txt LOCALLY") to export your YouTube cookies.
3.  **Save File:** Save the exported cookies as `cookies.txt` inside the `cookies` folder.
    *   Path: `cookies/cookies.txt`
4.  **Restart:** Restart the bot if it's already running.

## Web Dashboard & Soundboard

The bot includes a web dashboard to help manage character data, edit configuration files, and control the soundboard.

### Setup
1.  Open your `config.json` file.
2.  Add or update the following keys:
    ```json
    {
        ...
        "enable_dashboard": true,
        "admin_password": "SetAStrongPasswordHere"
    }
    ```
    *   `enable_dashboard`: Set to `true` to turn it on.
    *   `admin_password`: The password required to log in to the dashboard.

### Accessing the Dashboard
1.  Start the bot.
2.  Open your web browser and navigate to: `http://localhost:5000`
    *   If running on a remote server, replace `localhost` with the server's IP address. You may need to open port 5000 in your firewall.
3.  Log in using the `admin_password` you set.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
