# Spec: Global Emoji & Metadata Architectural Overhaul (Phase 9)

## Goal
Centralize all emoji mappings and system metadata (currently hardcoded in `emojis.py` and `occupation_emoji.py`) into the SQLite database. This enables real-time updates via the Web Dashboard without code changes and improves architectural consistency.

## Architecture
- **Data Layer:** New `global_emojis` table in SQLite via SQLAlchemy.
- **Service Layer:** `MetadataService` for high-performance retrieval with in-memory caching.
- **Bridge Layer:** Refactored `emojis.py` and `occupation_emoji.py` to act as backward-compatible bridges to the service layer.
- **Management:** New administrative interface on the Web Dashboard for real-time asset management.

## Components
1. **Database Table (`global_emojis`)**:
    - `id` (Integer, PK)
    - `category` (String: 'Stat', 'Skill', 'Occupation', 'Language', 'Item', 'System')
    - `key` (String, Indexed: e.g., 'STR', 'Archaeologist')
    - `value` (String: The emoji character or Discord emoji ID)
2. `services/metadata_service.py`: 
    - `get_emoji(key, category)`
    - `get_all_emojis()`
    - `sync_cache()`: Background task or on-demand cache refresh.
3. `emojis.py` & `occupation_emoji.py`: Refactored to delegate to `MetadataService` while maintaining existing function signatures.
4. `tools/migrate_emojis_to_sql.py`: Migration utility to ingest current Python dictionaries.

## Data Flow
1. Bot/Dashboard requests an emoji: `get_stat_emoji("STR")`.
2. Bridge function calls `MetadataService.get_emoji("STR", "Stat")`.
3. Service checks in-memory cache (populated from SQL).
4. Returns the emoji string.

## Migration Plan
1. **Model Creation**: Add `Metadata` model to the project.
2. **Ingestion**: Run migration script to move ~300+ mappings from `.py` files to SQL.
3. **Bridge Implementation**: Update the legacy files to use the service.
4. **Verification**: Confirm character sheets, codex, and rolls still display correct emojis.

## Success Criteria
- `emojis.py` and `occupation_emoji.py` no longer contain large static dictionaries.
- Emoji changes in the database are reflected in the bot without a restart.
- Zero breakage in existing UI/Commands that rely on emoji functions.
