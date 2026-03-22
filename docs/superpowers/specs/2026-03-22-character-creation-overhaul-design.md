# Spec: Character Creation Architectural Overhaul

## Goal
Refactor the character creation process (`newinvestigator.py`) to improve maintainability, data integrity, and architectural separation using a database-backed service-oriented approach.

## Architecture
- **Data Layer:** SQLite database managed by SQLAlchemy ORM.
- **Validation Layer:** Pydantic models for data integrity and business rule enforcement.
- **Service Layer:** `services/character_service.py` containing all game logic (skill point calculation, finalization).
- **View Layer:** Decoupled Discord UI components (`views/investigator_wizard.py`) that consume services.
- **Dashboard Integration:** Shared models and services between the Discord bot and the Quart web app.

## Components
1. `models/investigator.py`: SQLAlchemy database models.
2. `schemas/investigator.py`: Pydantic schemas for validation.
3. `services/character_service.py`: Business logic for character creation/editing.
4. `views/investigator_wizard.py`: Refactored Discord UI components.
5. `commands/newinvestigator.py`: Lightweight command entry point.

## Data Flow
1. User triggers `/newinvestigator`.
2. Bot initializes `InvestigatorCreateSchema` and launches `InvestigatorWizardView`.
3. User interacts with UI; data is validated against the Pydantic schema.
4. Upon confirmation, the View calls `CharacterService.finalize_investigator()`.
5. Service saves the data to SQLite via SQLAlchemy.

## Success Criteria
- JSON file dependencies for character creation are removed.
- Character logic can be tested without Discord.
- Dashboard can reuse the same logic for character editing.
