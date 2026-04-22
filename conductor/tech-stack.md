# CthulhuBotV2 Tech Stack

## Core Technologies
*   **Language:** Python 3.11+
*   **Discord Library:** `discord.py` (with Slash Commands)
*   **Web Framework:** Quart (Async Flask-like)

## Data & Persistence
*   **Persistence:** JSON-based flat files with in-memory caching for runtime data.
*   **Game Reference Data:** Static JSON files in `infodata/` directory.

## Multimedia
*   **Audio Streaming:** `yt-dlp` for on-the-fly streaming from various platforms.
*   **Audio Processing:** FFmpeg for mixing background music and sound effects.

## UI & UX
*   **Discord Interface:** Discord UI Components (Buttons, Modals, Selects) and Embeds.
*   **Web Dashboard:** HTML/CSS with JavaScript, integrated with the Quart backend.