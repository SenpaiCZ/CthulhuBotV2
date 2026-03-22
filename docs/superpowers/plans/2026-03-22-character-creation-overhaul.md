# Character Creation Architectural Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor character creation from JSON-based storage to a service-oriented architecture with a SQLite database, SQLAlchemy ORM, and Pydantic validation.

**Architecture:** 
- **Data Layer:** SQLite database with SQLAlchemy.
- **Service Layer:** `services/character_service.py` for business logic.
- **View Layer:** Refactored Discord UI components using Pydantic schemas.
- **Migration:** Automated script to transition data from JSON to SQL.

**Tech Stack:** Python, SQLAlchemy, Pydantic, SQLite, Discord.py.

---

### Task 1: Project Setup & Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add new dependencies to requirements.txt**
```text
sqlalchemy
pydantic
```
- [ ] **Step 2: Install dependencies**
Run: `pip install -r requirements.txt`
Expected: Successfully installed sqlalchemy and pydantic.
- [ ] **Step 3: Commit**
```bash
git add requirements.txt
git commit -m "chore: add sqlalchemy and pydantic dependencies"
```

### Task 2: Data Modeling (SQLAlchemy)

**Files:**
- Create: `models/investigator.py`
- Create: `models/base.py`

- [ ] **Step 1: Create the base SQLAlchemy model**
```python
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()
```
- [ ] **Step 2: Create the Investigator database model**
Include fields for all character stats (STR, CON, SIZ, DEX, APP, INT, POW, EDU, Luck, Skills).
- [ ] **Step 3: Commit**
```bash
git add models/base.py models/investigator.py
git commit -m "feat: add investigator database models"
```

### Task 3: Pydantic Schemas for Validation

**Files:**
- Create: `schemas/investigator.py`

- [ ] **Step 1: Define the InvestigatorCreate schema**
Include validation for skill points and characteristic ranges.
- [ ] **Step 2: Commit**
```bash
git add schemas/investigator.py
git commit -m "feat: add pydantic schemas for investigator validation"
```

### Task 4: Character Service Implementation

**Files:**
- Create: `services/character_service.py`

- [ ] **Step 1: Implement skill point calculation logic**
Move logic from `newinvestigator.py` to `character_service.py`.
- [ ] **Step 2: Implement finalize_investigator logic**
Handle saving the Pydantic model to the SQLite database.
- [ ] **Step 3: Commit**
```bash
git add services/character_service.py
git commit -m "feat: implement character service layer"
```

### Task 5: Character Service Testing

**Files:**
- Create: `tests/test_character_service.py`

- [ ] **Step 1: Write unit tests for skill point calculations**
- [ ] **Step 2: Write integration tests for finalize_investigator (using in-memory SQLite)**
- [ ] **Step 3: Run tests and verify coverage**
Expected: Tests pass without requiring a Discord client.
- [ ] **Step 4: Commit**
```bash
git add tests/test_character_service.py
git commit -m "test: add unit and integration tests for character service"
```

### Task 6: Migration Utility & Verification

**Files:**
- Create: `tools/migrate_json_to_sql.py`

- [ ] **Step 1: Implement JSON to SQL migration script**
Read `player_stats.json` and `retired_characters_data.json` and insert into SQLite.
- [ ] **Step 2: Implement a field-by-field verification step**
Compare stats (STR, DEX, etc.) in JSON vs SQL and log any discrepancies.
- [ ] **Step 3: Run and verify migration**
Expected: Data in SQLite matches JSON content exactly.
- [ ] **Step 4: Commit**
```bash
git add tools/migrate_json_to_sql.py
git commit -m "feat: add json-to-sql migration utility with verification"
```

### Task 7: Update loadnsave.py & Dashboard Integration

**Files:**
- Modify: `loadnsave.py`
- Modify: `dashboard/app.py`

- [ ] **Step 1: Add "Database Switch" logic to loadnsave.py**
Enable toggling between JSON and SQL for character data.
- [ ] **Step 2: Refactor dashboard/app.py to use the new Service Layer**
Replace manual JSON dictionary reads with calls to `character_service`.
- [ ] **Step 3: Verify dashboard functionality**
Expected: Characters are rendered correctly in the web UI using database data.
- [ ] **Step 4: Commit**
```bash
git add loadnsave.py dashboard/app.py
git commit -m "refactor: integrate database and service layer into dashboard and loadnsave"
```

### Task 8: Refactor Discord UI (Views)

**Files:**
- Create: `views/investigator_wizard.py`
- Modify: `commands/newinvestigator.py`

- [ ] **Step 1: Move UI logic from command to new View components**
- [ ] **Step 2: Update /newinvestigator to use the service layer**
- [ ] **Step 3: Verify character creation in Discord**
Expected: Character created and saved to the database correctly.
- [ ] **Step 4: Commit**
```bash
git add views/investigator_wizard.py commands/newinvestigator.py
git commit -m "refactor: decouple character creation UI and logic"
```
