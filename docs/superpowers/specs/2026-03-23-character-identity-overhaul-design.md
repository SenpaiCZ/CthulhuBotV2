# Spec: Character Identity & Backstory Architectural Overhaul (Phase 4)

## Goal
Refactor character identity, backstory, and lifecycle management commands to improve maintainability, UI responsiveness, and logic reuse across Discord and the Web Dashboard.

## Architecture
- **Data Layer:** Expanded `Investigator` table in SQLite with dedicated backstory and metadata columns.
- **Service Layer:** `CharacterService` expansion to handle renames, backstory manipulation, and retirement status.
- **View Layer:** Unified `CharacterProfileView` in `views/character_profile.py` to replace massive legacy view files.
- **Command Layer:** Refactored Phase 4 commands into lightweight (< 100 lines) entry points.

## Components
1. `models/investigator.py`: Updated with `backstory` (JSON), `biography` (JSON), `retirement_date` (DateTime), and `last_played` (DateTime).
2. `services/character_service.py`: New methods for `rename_investigator`, `manage_backstory`, `rename_skill`, and `toggle_retirement`.
3. `views/character_profile.py`: New tabbed Discord View for comprehensive character management.
4. `commands/`: 11 commands refactored to use the new service and view layers.

## Phase 4 Commands List
- `mycharacter.py`, `addbackstory.py`, `generatebackstory.py`, `removebackstory.py`, `updatebackstory.py`
- `rename.py`, `renameskill.py`, `skills.py`, `deleteinvestigator.py`, `retire_character.py`, `printcharacter.py`

## Data Flow
1. User triggers `/mycharacter`.
2. Bot fetches `Investigator` data via `CharacterService`.
3. Bot initializes `CharacterProfileView` and sends the interactive character card.
4. Interaction (e.g., clicking "Rename") triggers a Modal.
5. Modal submission calls `CharacterService.rename_investigator()` and refreshes the View.

## Success Criteria
- `commands/_mychar_view.py` (45KB legacy file) is removed.
- Character backstory and metadata are first-class citizens in the database.
- Web Dashboard and Discord share identical logic for identity management.
- All Phase 4 commands reduced to < 100 lines of code.
