# CthulhuBotV2

**CthulhuBotV2** is a feature-rich, unofficial Discord bot designed to assist Keepers and Investigators in playing the **Call of Cthulhu** Tabletop RPG. It provides tools for character management, dice rolling, rule lookups, and session management.

> **Disclaimer:** This is an **UNOFFICIAL** bot! It is **not** associated with Chaosium Inc. To play **Call of Cthulhu**, you will need the [Call of Cthulhu Keeper Rulebook](https://www.chaosium.com/call-of-cthulhu-keeper-rulebook-hardcover/), [Call of Cthulhu Starter Set](https://www.chaosium.com/call-of-cthulhu-starter-set/), or [Pulp Cthulhu](https://www.chaosium.com/pulp-cthulhu-hardcover/) published by [Chaosium Inc.](https://www.chaosium.com/)

## Features

*   🛠️ **Slash Commands**: Fully integrated with Discord's Slash Commands (`/`) for a modern and intuitive user experience.
*   🕵️‍♂️ **Character Management**: Create, update, and manage investigator sheets, including stats, skills, inventory, and rich backstory elements (Description, Beliefs, Connections, etc.).
*   🎲 **Advanced Dice Rolling**: Interactive rolls with support for Bonus/Penalty dice, Luck spending, and Pushing rolls.
*   🐙 **The Grimoire (Codex)**: Extensive library of game information including firearms, inventions, monsters, deities, spells, madness tables, phobias/manias, and historical events.
*   👊 **Pulp Cthulhu Support**: Includes Pulp Archetypes, Talents, Insane Talents, and modified character creation rules.
*   📜 **Session Management**: Tools to start, track, and log game sessions.
*   🎵 **Music Bot**: High-quality music playback from YouTube with queue management, looping, and volume control.
*   📱 **Pokemon GO**: Track and notify your community about upcoming Pokemon GO events (powered by LeekDuck).
*   💻 **Web Dashboard**: A powerful web interface to manage the bot and server:
    *   **Codex Browser**: View Monsters, Spells, Deities, Weapons, and more in a browser-friendly format.
    *   **Karma System**: Configure roles, emojis, and notifications.
    *   **Auto Rooms**: Easy setup for voice channel generation.
    *   **RSS Feeds**: Manage subscriptions (RSS & YouTube).
    *   **Soundboard**: Upload and play audio clips in voice channels.
    *   **Music Control**: Manage the music queue and blacklist songs.
    *   **Reaction Roles**: Easily configure self-assignable roles.
    *   **Auto Deleter**: Manage auto-deletion rules for channels.
    *   **Polls**: Create and manage interactive polls.
    *   **Reminders**: View and delete pending reminders.
    *   **Enrollment Wizard**: Configure a multi-step role assignment wizard for new members.
    *   **Backups**: Manage automated and manual system backups.
*   📈 **Karma System**: Track user reputation with custom upvote/downvote emojis.
*   📊 **Polls & Reminders**: Native support for creating polls and setting reminders.

## Commands

The bot uses **Slash Commands** (`/`). Legacy prefix commands have been removed, with the exception of `!sync`.

### 🐙 Investigator Tools
*   `/character backstory`: 📜 View or edit your character's backstory with dedicated fields for Description, Beliefs, and more.
*   `/character connections`: 🤝 Manage relationships between investigators.
*   `/newinvestigator`: 🕵️‍♂️ Start the character creation wizard.
*   `/mycharacter`: 📜 View your character sheet.
*   `/stat`: 📊 View or edit specific stats on your sheet.
*   `/rename`: 🏷️ Rename your character.
*   `/renameskill`: ✏️ Rename a skill on your sheet.
*   `/deleteinvestigator`: 🗑️ Delete a character.
*   `/addbackstory`, `/updatebackstory`, `/removebackstory`: 📖 Manage backstory elements.
*   `/generatebackstory`: 🎲 Generate a random backstory.
*   `/retire`: 👴 Retire an active character.
*   `/unretire`: 👶 Bring a retired character back to active duty.
*   `/printcharacter`: 🖼️ Generate an image of your character sheet.

### 🎲 Dice Rolling & Session
*   `/roll`: 🎲 Perform a dice roll or skill check. Interactive interface allows for Bonus/Penalty dice and Luck spending.
*   `/showluck`: 🍀 Show the luck threshold for the server.
*   `/session start`: 🎬 Start a new game session.
*   `/session show`: 📝 Show current session details.
*   `/session wipe`: 🧹 Clear session data.

### 📚 The Grimoire (Codex)
*   `/codex`: 📖 Open the main Codex menu to browse all categories.
*   `/monster` `[name]`: 👹 Lookup a Cthulhu Mythos monster.
*   `/deity` `[name]`: 👁️ Lookup a Great Old One or Outer God.
*   `/spell` `[name]`: ✨ Lookup a spell.
*   `/weapon` `[name]`: 🔫 Lookup weapon statistics.
*   `/occupation` `[name]`: 💼 Lookup occupation details.
*   `/skill` `[name]`: 📚 Lookup skill descriptions.
*   `/archetype` `[name]`: 🦸‍♂️ Lookup Pulp Cthulhu Archetypes.
*   `/talent` `[name]`: 🌟 Lookup Pulp Talents.
*   `/insane` `[name]`: 🩸 Lookup Insane Talents.
*   `/mania` `[name]`, `/phobia` `[name]`: 🤪 Random or specific madness.
*   `/poison` `[name]`: 🧪 Lookup poison info.
*   `/invention` `[decade]`: 💡 Lookup inventions by decade (e.g., "1920s").
*   `/year` `[year]`: 📅 Historical events for a specific year.
*   `/randomnpc`: 👤 Generate a random NPC with region selection.
*   `/randomname`: 🏷️ Generate a random name (1920s era).
*   `/macguffin`: 🏺 Generate a plot device.
*   `/loot`: 💰 Generate random loot.

### 🎵 Music & Sound
*   `/play` `[query]`: 🎵 Play a song from YouTube.
*   `/skip`: ⏭️ Skip the current song.
*   `/stop`: 🛑 Stop music, clear queue, and disconnect.
*   `/volume` `[0-100]`: 🔊 Set playback volume.
*   `/loop`: 🔁 Toggle song looping.
*   `/queue`: 🎼 View the current music queue.
*   `/nowplaying`: 💿 Show the currently playing song.

### 🛠️ Utilities & Community
*   `/enroll`: 🧙 Start the enrollment wizard to get roles (if configured).
*   `/poll`: 📊 Create an interactive poll.
*   `/remind`: ⏰ Set a reminder for yourself or a channel.
*   `/reportbug`: 🐛 Report a bug to the developer.
*   `/ping`: 🏓 Check bot latency.
*   `/uptime`: ⏱️ Check bot uptime.
*   `/leaderboard`: 🏆 Show the Karma leaderboard.
*   `/karma`: 🌟 Check karma for a user.

### ⚙️ Admin & Configuration
*   `!sync`: 🔄 **Essential!** Sync slash commands to Discord. This is the only prefix command.
    *   `!sync`: Sync global commands (takes up to 1 hour to propagate).
    *   `!sync guild`: Sync to current guild (instant).
    *   `!sync clear`: Clear global commands.
    *   `!sync clearguild`: Clear guild-specific commands (use to fix duplicates).
*   `/setupkarma`: ⚙️ Interactive setup wizard for the karma system.
*   `/setupkarmaroles`: 🧙 Interactive wizard to manage karma rank roles.
*   `/reactionrole`: 🎭 Setup a reaction role on a message.
*   `/autoroom setup`: ⚙️ Interactive setup wizard for Auto Rooms.
*   `/rsssetup`: 📰 Interactive setup wizard for RSS/YouTube feeds.
*   `/autodeleter set`: 🤖 Set auto-deletion rules for a channel.
*   `/autodeleter stop`: 🛑 Stop auto-deletion for a channel.
*   `/purge`: 🗑️ Bulk delete messages.
*   `/pogo setchannel`, `/pogo setrole`: 📱 Configure Pokemon GO notifications.
*   `/backup`: 💾 Trigger a manual backup.
*   `/updatebot`: 🔄 Update the bot (if installed via git).

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

### Syncing Slash Commands
**Important:** After starting the bot for the first time, you must sync the slash commands to your server or globally.
1.  Ensure you are in a server where the bot is present.
2.  Run the command `!sync guild` to instantly sync commands to that specific server.
3.  Run `!sync` to sync commands globally (this can take up to an hour to propagate to all servers).

**Troubleshooting:**
*   `!sync clear`: Clear global commands.
*   `!sync clearguild`: Clear guild-specific commands (use to fix duplicates).

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
6.  Install Playwright browsers (for Dashboard rendering):
    ```bash
    playwright install chromium
    ```

**B. Configuration**

1.  The bot uses `config.json` in the root directory.
2.  Create `config.json` and add your configuration (see [Configuration Details](#configuration-details)):
    ```json
    {
        "token": "YOUR_DISCORD_BOT_TOKEN",
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

The bot includes a comprehensive web dashboard to help manage character data, edit configuration files, and control server settings.

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

### Dashboard Features
*   **Investigator/Keeper Tools**: View and manage active and retired character sheets.
*   **Codex Browser**: Browse the entire library of Monsters, Spells, Deities, Weapons, and more.
*   **Soundboard**: Upload audio files, organize them into folders, and play them directly into your voice channel.
*   **Music Control**: Manage the music queue, skip tracks, and blacklist specific URLs.
*   **Pokemon GO**: Configure event notifications, role pings, and view upcoming events.
*   **Enrollment Wizard**: Configure a step-by-step role assignment process for new members.
*   **Polls & Reminders**: Manage active polls and view scheduled reminders.
*   **Backup Manager**: Download or delete system backups, and trigger manual backups.
*   **File Editor**: (Advanced) Edit internal JSON data files directly from the browser.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
