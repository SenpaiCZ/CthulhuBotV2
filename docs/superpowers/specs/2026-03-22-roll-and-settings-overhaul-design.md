# Spec: Dice Rolling & Settings Architectural Overhaul (Phase 2)

## Goal
Refactor the dice rolling (`roll.py`) and server settings (`gamesettings.py`) to improve maintainability, architectural separation, and scalability.

## Architecture
- **Data Layer:** `GuildSettings` table in SQLite via SQLAlchemy ORM.
- **Validation Layer:** Pydantic models for roll results and settings validation.
- **Service Layer:** 
    - `services/roll_service.py`: Dice parsing, skill check logic, and luck spending math.
    - `services/settings_service.py`: Server-wide configuration management.
- **View Layer:** Decoupled Discord UI components (`views/roll_view.py`) that consume services.
- **Dashboard Integration:** Shared settings and roll services between the Discord bot and the Quart web app.

## Components
1. `models/guild_settings.py`: SQLAlchemy database models for server configurations.
2. `schemas/roll.py`: Pydantic schemas for structured roll results.
3. `services/roll_service.py`: Business logic for CoC skill checks and dice rolling.
4. `services/settings_service.py`: Business logic for getting/setting guild-level configurations.
5. `views/roll_view.py`: Refactored Discord UI components for roll results (Push, Luck spending).
6. `commands/roll.py`: Lightweight command entry point.

## Data Flow
1. User triggers `/roll [stat]`.
2. Bot calls `RollService.calculate_roll(guild_id, user_id, stat)`.
3. `RollService` fetches character data (from `CharacterService`) and guild settings (from `SettingsService`).
4. `RollService` returns a `RollResult` Pydantic model.
5. Bot initializes `RollView(roll_result)` and sends the response.

## Migration Plan
1. **Settings Migration Utility:** Create `tools/migrate_settings_to_sql.py` to move existing JSON configurations (`luck_stats.json`, `skill_settings.json`, `gamemode.json`) into the new `guild_settings` table.
2. **Backward Compatibility:** Update `loadnsave.py` to bridge to the new services if `USE_DATABASE` is enabled.

## Trade-off Analysis
- **Database vs. JSON:** Centralizing into a database improves data integrity and allows the Web Dashboard to query settings efficiently. The trade-off is higher initial complexity and the need for a migration script.
- **Service Layer Overhead:** Introducing `RollService` and `SettingsService` adds more files but enables unit testing of core game logic without a Discord client or active bot session.

## Cache Safety & Data Integrity
- **LoadNSave Bridge:** `loadnsave.py` will serve as the primary bridge. When `USE_DATABASE` is enabled, the JSON cache in `loadnsave.py` must be kept in sync with the database to prevent desynchronization.
- **Atomic Operations:** All database updates for settings and roll results will use SQLAlchemy's session management to ensure atomicity.

## Expanded Migration Scope
Beyond luck and skill settings, the following files will be migrated to the `guild_settings` table (or specialized tables):
- `karma_settings.json`
- `loot_settings.json`
- `pogo_settings.json`
- `autorooms.json`
- `rss_data.json`

## Verification Plan
1. **Parallel Testing:** Compare roll results from `RollService` against the legacy `_perform_roll` logic in a controlled test environment.
2. **Settings Parity:** A script will verify that every configuration in the legacy JSON files is correctly reflected in the database.

## Success Criteria
- Dice logic is independent of Discord and can be tested or called from the Web Dashboard.
- Server settings are centralized in the database instead of multiple JSON files.
- The web dashboard can trigger rolls or edit server settings through shared services.
- Zero data loss during the migration of 5+ settings files.
