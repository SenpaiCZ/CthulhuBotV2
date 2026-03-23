# Spec: Music & Audio Architectural Overhaul (Phase 3)

## Goal
Refactor the music and audio subsystems (`music.py`, `audio_mixer.py`, `app.py`) to improve maintainability, architectural separation, and state persistence.

## Architecture
- **Data Layer:** `GuildSettings` table in SQLite via SQLAlchemy ORM (for voice state).
- **Service Layer:** 
    - `services/audio_service.py`: Manages voice connections, `MixingAudioSource` lifecycle, and master volume.
    - `services/music_service.py`: In-memory music queue management, track resolution (yt-dlp), and playback control.
- **View Layer:** Decoupled Discord UI components (`views/music_player.py`) that consume services.
- **Task Layer:** `tasks/voice_monitor.py` for auto-rejoining voice channels on bot startup.
- **Dashboard Integration:** Shared audio and music services between the Discord bot and the Quart web app.

## Components
1. `models/guild_settings.py`: Updated with `last_voice_channel_id` (String) and `music_auto_resume` (Boolean).
2. `services/audio_service.py`: Centralized management of `guild_mixers` and voice connections.
3. `services/music_service.py`: Business logic for music queues and track history.
4. `views/music_player.py`: Refactored Discord UI components for music control (Play, Pause, Skip, Queue).
5. `tasks/voice_monitor.py`: Background task to rejoin last active voice channel on bot start.
6. `commands/music.py`: Lightweight command entry point.

## Data Flow
1. User triggers `/music play [URL]`.
2. Bot calls `MusicService.add_to_queue(guild_id, URL)`.
3. `MusicService` calls `AudioService.connect_to_voice(guild_id, channel_id)` if not connected.
4. `MusicService` starts playback via `AudioService` using the shared `MixingAudioSource`.
5. `AudioService` updates `GuildSettings.last_voice_channel_id` in the database.

## Trade-off Analysis
- **In-Memory Queue:** The music queue is kept in memory for performance and simplicity. **Trade-off:** All queued tracks are lost on bot restart, though the bot will automatically rejoin the last voice channel and can optionally resume the last played song if its URL is persisted.
- **Service Layer Overhead:** Moving audio logic to `AudioService` adds complexity but ensures that the Web Dashboard and Discord commands share the same voice state and mixer.

## Lifecycle & Resource Management
- **Idle Timeout:** `AudioService` will implement a configurable idle timeout (default 10 minutes). If no audio is playing (music or soundboard), the bot will automatically disconnect from the voice channel to save resources.
- **Cleanup Lifecycle:** `AudioService` is responsible for calling `MixingAudioSource.cleanup()` on every disconnection (manual or automatic) to ensure underlying FFmpeg processes are terminated.
- **Error Handling:** The service will monitor for unexpected disconnections (e.g., bot kicked) and update the `GuildSettings` accordingly.

## Staggered Rejoin Strategy
- **Voice Monitor Task:** `tasks/voice_monitor.py` will use a staggered approach (e.g., 5-second delay between guilds) to avoid hitting Discord rate limits when rejoining voice channels on bot startup.

## Verification Plan
1. **Service Tests:** Unit tests for `MusicService` (queue logic) and `AudioService` (mixer initialization).
2. **Resource Leak Check:** Verify that FFmpeg processes are correctly terminated after an idle timeout or manual stop.
3. **Startup Verification:** Restart the bot and verify it automatically rejoins active voice channels with a staggered delay.

## Success Criteria
- Audio logic is independent of Discord commands and can be controlled via the Web Dashboard.
- Voice channel state is persisted in the database across bot restarts.
- `guild_mixers` global state is safely encapsulated within the `AudioService`.
