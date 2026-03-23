# Music & Audio Architectural Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the music and audio subsystems to a service-oriented architecture with voice state persistence, idle timeout, and staggered rejoin.

**Architecture:**
- **Data Layer:** `GuildSettings` (SQLite) for voice channel persistence.
- **Service Layer:** `services/audio_service.py` (voice/mixer) and `services/music_service.py` (queue/logic).
- **Lifecycle:** Idle timeout for automatic disconnection and FFmpeg cleanup.
- **Task:** Staggered rejoin of voice channels on bot start.

**Tech Stack:** Python, SQLAlchemy, Discord.py, yt-dlp, FFmpeg.

---

### Task 1: Data Modeling (Voice State)

**Files:**
- Modify: `models/guild_settings.py`

- [ ] **Step 1: Add voice-related fields to GuildSettings model**
Add `last_voice_channel_id` (String) and `music_auto_resume` (Boolean).
- [ ] **Step 2: Commit**
```bash
git add models/guild_settings.py
git commit -m "feat: add voice state fields to GuildSettings model"
```

### Task 2: Audio Service Implementation

**Files:**
- Create: `services/audio_service.py`

- [ ] **Step 1: Implement AudioService with mixer management**
Encapsulate `guild_mixers` and `server_volumes`.
- [ ] **Step 2: Implement voice connection and cleanup logic**
Ensure `MixingAudioSource.cleanup()` is called on disconnect.
- [ ] **Step 3: Implement idle timeout logic**
- [ ] **Step 4: Commit**
```bash
git add services/audio_service.py
git commit -m "feat: implement audio service for mixer and voice management"
```

### Task 3: Music Service Implementation

**Files:**
- Create: `services/music_service.py`

- [ ] **Step 1: Implement MusicService with in-memory queue**
- [ ] **Step 2: Port track resolution (yt-dlp) and playback logic**
- [ ] **Step 3: Commit**
```bash
git add services/music_service.py
git commit -m "feat: implement music service for queue and playback control"
```

### Task 4: Voice Monitor Task (Staggered Rejoin)

**Files:**
- Create: `tasks/voice_monitor.py`

- [ ] **Step 1: Implement background task for auto-rejoin**
Use a 5-second delay between guilds to avoid rate limits.
- [ ] **Step 2: Integrate task into bot startup**
- [ ] **Step 3: Commit**
```bash
git add tasks/voice_monitor.py
git commit -m "feat: implement staggered voice rejoin task"
```

### Task 5: Integration & Dashboard Update

**Files:**
- Modify: `loadnsave.py`
- Modify: `dashboard/app.py`

- [ ] **Step 1: Update loadnsave.py to bridge to new services**
- [ ] **Step 2: Refactor dashboard routes for music control**
- [ ] **Step 3: Commit**
```bash
git add loadnsave.py dashboard/app.py
git commit -m "refactor: integrate audio and music services into dashboard"
```

### Task 6: Discord UI Refactor (Music Player)

**Files:**
- Create: `views/music_player.py`
- Modify: `commands/music.py`

- [ ] **Step 1: Move music UI logic to specialized Views**
- [ ] **Step 2: Update /music command to use services**
- [ ] **Step 3: Final verification**
- [ ] **Step 4: Commit**
```bash
git add views/music_player.py commands/music.py
git commit -m "refactor: decouple music UI and logic"
```
