# CthulhuBotV2

**CthulhuBotV2** is a feature-rich, unofficial Discord bot designed to assist Keepers and Investigators in playing the **Call of Cthulhu** Tabletop RPG. It provides tools for character management, dice rolling, rule lookups, and session management.

> **Disclaimer:** This is an **UNOFFICIAL** bot! It is **not** associated with Chaosium Inc. To play **Call of Cthulhu**, you will need the [Call of Cthulhu Keeper Rulebook](https://www.chaosium.com/call-of-cthulhu-keeper-rulebook-hardcover/), [Call of Cthulhu Starter Set](https://www.chaosium.com/call-of-cthulhu-starter-set/), or [Pulp Cthulhu](https://www.chaosium.com/pulp-cthulhu-hardcover/) published by [Chaosium Inc.](https://www.chaosium.com/)

## Features

*   **Character Management:** Create, update, and manage investigator sheets, including stats, skills, and backstories.
*   **Dice Rolling:** Advanced dice rolling capabilities, including standard rolls, bonus/penalty dice, luck rolls, and skill checks.
*   **Keeper Tools:** Extensive library of game information including firearms, inventions, madness tables, phobias/manias, and NPC generation.
*   **Session Management:** Tools to start, track, and log game sessions.
*   **Utility & Admin:** YouTube feed integration, auto-rooms, RSS feeds, and server administration tools.
*   **Web Dashboard:** An optional web interface for easier management of data files and characters.

## Installation

### Prerequisites

*   **Python 3.8** or higher: [Download Python](https://www.python.org/downloads/)
*   **Git**: [Download Git](https://git-scm.com/downloads)

### 1. Installation on Linux

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

**B. Configuration**

1.  Create the `data` directory and `settings.json` file:
    ```bash
    mkdir -p data
    touch data/settings.json
    ```
2.  Edit `data/settings.json` using nano or your preferred editor:
    ```bash
    nano data/settings.json
    ```
3.  Add your configuration (see [Configuration Details](#configuration-details) below for more info):
    ```json
    {
        "token": "YOUR_DISCORD_BOT_TOKEN",
        "youtubetoken": "YOUR_YOUTUBE_API_KEY"
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

### 2. Installation on Windows

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

**B. Configuration**

1.  Create a new folder named `data` inside the project folder.
2.  Inside `data`, create a text file named `settings.json`.
3.  Open it with Notepad and add your configuration (see [Configuration Details](#configuration-details)):
    ```json
    {
        "token": "YOUR_DISCORD_BOT_TOKEN",
        "youtubetoken": "YOUR_YOUTUBE_API_KEY"
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
2.  `data/settings.json` (Local overrides)
3.  `config.json` (Default values)

**Common Settings (`data/settings.json`):**
```json
{
    "token": "YOUR_DISCORD_BOT_TOKEN",
    "youtubetoken": "YOUR_YOUTUBE_API_KEY",
    "enable_dashboard": true,
    "admin_password": "your_secure_password"
}
```

## Web Dashboard

The bot includes a web dashboard to help manage character data and edit configuration files easily.

### Setup
1.  Open your `data/settings.json` file.
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

### Features
*   **Character Viewer:** View details of active and retired investigators.
*   **File Editor:** Browse and edit JSON files in the `data` and `infodata` directories directly from the browser (Admin only).

## Usage

To start the bot, run the `bot.py` script:

```bash
python bot.py
```

The bot should now be online and ready to use in your Discord server.

## Commands

The bot uses a dynamic prefix (default is `!`). Here is a list of available commands categorized by function:

### Character Creation
*   `newinvestigator`: Create a new investigator (Wizard).
*   `mychar`: View your character sheet.
*   `autochar`: Generate stats for your investigator (Standard CoC 7e rules).
*   `stat`: View or edit specific stats.
*   `rename`: Rename your character.
*   `renameskill`: Rename a skill on your sheet.
*   `deleteinvestigator`: Delete a character.
*   `addbackstory`: Add backstory elements.
*   `updatebackstory`: Update backstory elements.
*   `removebackstory`: Remove backstory elements.
*   `generatebackstory`: Generate a random backstory.
*   `retire`: Retire an active character.
*   `unretire`: Bring a retired character back.

### Rolling Die and Session Management
*   `newroll` (aliases: `roll`, `d`, `nd`, `s`): Perform a dice roll or skill check. Interactive interface allows for Bonus/Penalty dice and Luck spending.
*   `showluck`: Display current luck.
*   `startsession`: Start a new game session.
*   `showsession`: Show current session details.
*   `wipesession`: Clear session data.

### For Keeper
*   `changeluck`: Modify an investigator's luck.
*   `occupationinfo`: Lookup occupation details.
*   `skillinfo`: Lookup skill details.
*   `createnpc`: Generate an NPC.
*   `randomname`: Generate a random name (1920s).
*   `macguffin`: Generate a MacGuffin.
*   `loot`: Generate random loot.
*   `archetypeinfo`: Lookup archetype info (Pulp).
*   `firearms`: Lookup firearm statistics.
*   `inventions`: Lookup invention details.
*   `talents`: Lookup talent info.
*   `years`: Historical info for different years.
*   `madness`: Consult madness rules.
*   `madnessAlone`: Madness tables for solo investigators.
*   `insaneTalents`: Lookup insane talents.
*   `phobia`: Random phobia.
*   `mania`: Random mania.
*   `poisons`: Lookup poison info.

### Bot Functions
*   `autoroomkick`: Kick user from auto-room.
*   `autoroomlock`: Lock auto-room.
*   `autoroomunlock`: Unlock auto-room.
*   `reportbug`: Report a bug to the developer.
*   `repeatafterme`: Make the bot repeat a message.
*   `uptime`: Check bot uptime.

### Admin
*   `autoroomset`: Configure auto-rooms.
*   `changeprefix`: Change the bot's command prefix for the server.
*   `ping`: Check latency.
*   `addreaction`: Add a smart reaction.
*   `removereaction`: Remove a smart reaction.
*   `listreactions`: List all smart reactions.
*   `youtube`: Setup YouTube channel notifications.
*   `unsubscribe`: Unsubscribe from YouTube notifications.
*   `deleter`: Setup auto-deletion for channels.
*   `autodeleter`: Configure auto-deleter.
*   `stopdeleter`: Stop auto-deletion.
*   `rss`: Manage RSS feeds.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
