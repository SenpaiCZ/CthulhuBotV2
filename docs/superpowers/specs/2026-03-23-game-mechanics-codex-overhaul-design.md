# Spec: Game Mechanics & The Codex Architectural Overhaul (Phase 6)

## Goal
Refactor core game mechanics (Combat, Chases, Session Tracking) and the rule reference library (Codex) to a service-oriented architecture. Move all static and active game data from fragmented JSON files to a unified SQLite database.

## Architecture
- **Data Layer:**
    - `codex_entries`: Unified table for all reference data (Monsters, Spells, Items).
    - `combat_sessions` & `combat_participants`: Relational tables for active combat state.
    - `session_logs`: Persistence for session history and events.
- **Service Layer:**
    - `CodexService`: Centralized search and data retrieval for rule references.
    - `CombatService`: State-machine for managing combat turns and participants.
    - `SessionService`: Logic for tracking session duration and event logging.
- **View Layer:** Modular Discord Views (`views/combat_tracker.py`, `views/codex_renderer.py`) for complex rendering and interaction.
- **Command Layer:** Massive command files (`codex.py`, `combat.py`) reduced to < 100 line entry points.

## Components
1. `models/codex.py`: SQLAlchemy model for rules and references.
2. `models/game_state.py`: SQLAlchemy models for combat and active sessions.
3. `services/codex_service.py`: Searching, autocomplete, and data-fetching logic.
4. `services/combat_service.py`: Initiatives, turns, HP tracking, and state management.
5. `views/combat_tracker.py`: Interactive Discord View for real-time combat monitoring.
6. `commands/`: 10 commands refactored to use new services.

## Phase 6 Commands List
- `combat.py`, `chase.py`, `versus.py`, `madness.py`, `session.py`, `stat.py`, `changeluck.py`, `codex.py`, `randomname.py`, `randomnpc.py`.

## Data Flow
1. User triggers `/codex search name:Ghoul`.
2. Bot calls `CodexService.get_entry("Ghoul")`.
3. `CodexService` queries `codex_entries` table.
4. Bot initializes `CodexRendererView` and sends the formatted embed.

## Migration Plan
1. **The Codex Migration**: `tools/migrate_codex_to_sql.py` to parse all `infodata/*.json` files.
2. **Active State Migration**: Transition any currently active combats from `session_data.json` to SQL.
3. **Verification**: Parallel search validation between JSON and SQL datasets.

## Success Criteria
- `commands/codex.py` (1000+ lines) is reduced to < 100 lines.
- All core game data (Monsters, Spells, Combat state) is SQL-backed.
- Zero JSON dependency for active gameplay mechanics.
- Web Dashboard can display live combat initiative and search the full Codex.
