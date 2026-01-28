# CthulhuBotV2

**CthulhuBotV2** is a feature-rich, unofficial Discord bot designed to assist Keepers and Investigators in playing the **Call of Cthulhu** Tabletop RPG. It provides tools for character management, dice rolling, rule lookups, and session management.

> **Disclaimer:** This is an **UNOFFICIAL** bot! It is **not** associated with Chaosium Inc. To play **Call of Cthulhu**, you will need the [Call of Cthulhu Keeper Rulebook](https://www.chaosium.com/call-of-cthulhu-keeper-rulebook-hardcover/), [Call of Cthulhu Starter Set](https://www.chaosium.com/call-of-cthulhu-starter-set/), or [Pulp Cthulhu](https://www.chaosium.com/pulp-cthulhu-hardcover/) published by [Chaosium Inc.](https://www.chaosium.com/)

## Features

*   **Character Management:** Create, update, and manage investigator sheets, including stats, skills, and backstories.
*   **Dice Rolling:** Advanced dice rolling capabilities, including standard rolls, bonus/penalty dice, luck rolls, and skill checks.
*   **Keeper Tools:** Extensive library of game information including firearms, inventions, madness tables, phobias/manias, and NPC generation.
*   **Session Management:** Tools to start, track, and log game sessions.
*   **Utility & Admin:** YouTube feed integration, auto-rooms, RSS feeds, and server administration tools.

## Installation

### Prerequisites

*   Python 3.8 or higher
*   Git

### Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd CthulhuBotV2
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Settings:**
    The bot prioritizes configuration in the following order:
    1.  **Environment Variables** (Recommended for cloud deployment like Replit)
    2.  `data/settings.json` (Recommended for local development, this file is git-ignored)
    3.  `config.json` (Default values)

    **Local Development:**
    Create a folder named `data` in the root directory. Inside `data`, create a file named `settings.json`.

    ```bash
    mkdir data
    touch data/settings.json
    ```

    Open `data/settings.json` and add your configuration:
    ```json
    {
        "token": "YOUR_DISCORD_BOT_TOKEN",
        "youtubetoken": "YOUR_YOUTUBE_API_KEY"
    }
    ```
    *   `token`: Your Discord Bot Token (Required).
    *   `youtubetoken`: Your YouTube Data API Key (Optional, for YouTube feed features).

    **Deployment on Replit:**
    1.  Fork the repository to your Replit account.
    2.  Go to the **Tools** pane and select **Secrets**.
    3.  Add the following secrets (Environment Variables):
        *   `DISCORD_TOKEN`: Your Discord Bot Token.
        *   `YOUTUBE_API_KEY`: Your YouTube Data API Key (Optional).
    4.  Run the bot. The `config.json` file serves as a template with default values.

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
