# Spec: Campaign & Social Engagement Architectural Overhaul (Phase 5)

## Goal
Refactor collaborative world-building and social reward commands (`journal.py`, `loot.py`, `karma.py`, etc.) to a service-oriented, database-backed architecture to improve data integrity, searching capabilities, and cross-platform consistency.

## Architecture
- **Data Layer:** New relational tables in SQLite for Journals, Inventory, Handouts, and Karma.
- **Service Layer:** `CampaignService` to centralize world-building logic and rewards.
- **View Layer:** Modular Discord Views (`views/campaign_dashboard.py`) for player interaction.
- **Command Layer:** Refactored Phase 5 commands into lightweight (< 100 lines) entry points.

## Components
1. **Database Tables**:
    - `journal_entries`: `id`, `guild_id`, `type`, `author_id`, `title`, `content`, `timestamp`.
    - `inventory_items`: `id`, `investigator_id` (FK), `name`, `description`, `is_macguffin`.
    - `karma_stats`: `guild_id`, `user_id`, `score`.
    - `handouts`: `id`, `guild_id`, `title`, `content`, `image_url`.
2. `services/campaign_service.py`: Logic for entry management, loot generation, and karma rewards.
3. `views/campaign_dashboard.py`: Unified tabbed view for Inventory, Handouts, and Journals.
4. `commands/`: 5 commands refactored to use `CampaignService`.

## Phase 5 Commands List
- `journal.py`, `handout.py`, `macguffin.py`, `loot.py`, `karma.py`.

## Data Flow
1. User triggers `/journal add`.
2. Bot calls `CampaignService.add_journal_entry(guild_id, author_id, content)`.
3. `CampaignService` saves to `journal_entries` table.
4. Bot triggers a "Dashboard Refresh" for the Web Dashboard to show the new entry.

## Migration Plan
1. **JSON Migration Utility**: `tools/migrate_campaign_to_sql.py` to transition data from:
    - `journal_data.json` -> `journal_entries`
    - `karma_stats.json` -> `karma_stats`
    - Investigator `gear` field -> `inventory_items`
2. **Verification**: Count-based parity and random field spot-checks.

## Success Criteria
- All Phase 5 command files are reduced to < 100 lines of code.
- Campaign data is fully searchable via SQL (enabling full-text search on the Web Dashboard).
- Inventory management is moved from flat strings to a structured table.
- Zero data loss during the migration of world-building files.
