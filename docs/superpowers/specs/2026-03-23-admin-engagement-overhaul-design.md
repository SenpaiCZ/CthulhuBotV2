# Spec: Administration & Engagement Architectural Overhaul (Phase 7)

## Goal
Finalize the architectural transition by refactoring all administrative and social engagement commands into a service-oriented, database-backed structure. Achieve zero JSON dependency for all bot features and shared administrative state with the Web Dashboard.

## Architecture
- **Data Layer:** New relational tables for Polls, Giveaways, RSS Feeds, Reminders, and Role Panels.
- **Service Layer:** 
    - `EngagementService`: Logic for social features (Polls, Giveaways, RSS).
    - `AdminService`: Centralized bot lifecycle management (Backups, Restarts, Updates).
- **View Layer:** Interactive Discord Views (`views/admin_hub.py`, `views/poll_view.py`) for management.
- **Command Layer:** Final 21 commands refactored to < 100 line entry points.

## Components
1. **Database Tables**:
    - `polls`: `message_id`, `guild_id`, `question`, `options` (JSON), `votes` (JSON).
    - `giveaways`: `message_id`, `guild_id`, `title`, `prize`, `end_time`, `participants` (JSON).
    - `reminders`: `id`, `user_id`, `guild_id`, `channel_id`, `message`, `due_at`.
    - `rss_feeds`: `id`, `guild_id`, `channel_id`, `url`, `last_item_id`.
    - `autorooms`: `id`, `guild_id`, `creator_id`, `channel_id`, `name_format`.
    - `pogo_events`: `id`, `guild_id`, `name`, `timestamp`, `location`.
    - `gameroles`: `id`, `guild_id`, `role_id`, `category`.
    - `deleter_jobs`: `id`, `guild_id`, `channel_id`, `user_id`, `status`.
2. `services/engagement_service.py`: Centralized logic for social mechanics and automated feed polling.
3. `services/admin_service.py`: Logic for bot maintenance and system-level operations.
4. `views/poll_view.py`: Reusable interactive voting component.
5. `commands/`: 21 final commands refactored to use new services.

## Phase 7 Commands List
- `polls.py`, `giveaway.py`, `rss.py`, `autoroom.py`, `reminders.py`, `botstatus.py`, `backup.py`, `reportbug.py`, `pogo.py`, `enroll.py`, `deleter.py`, `gameroles.py`, `rolepanel.py`, `reactionroles.py`, `smartreaction.py`, `help.py`, `ping.py`, `uptime.py`, `restart.py`, `updatebot.py`, `admin_slash.py`.

## Success Criteria
- Zero remaining `.json` files in the `data/` directory used for state persistence.
- All 21 Phase 7 command files reduced to < 100 lines of code.
- Administrative tasks (Backups, Restarts) can be triggered and monitored from the Web Dashboard.
- Automated tasks (Reminders, Giveaways) survive bot restarts via database persistence.
