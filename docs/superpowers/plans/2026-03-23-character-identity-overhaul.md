# Character Identity & Backstory Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor character identity and backstory management to a service-oriented architecture with an expanded database model and a unified Discord UI.

**Architecture:**
- **Data Layer:** Expanded `Investigator` model with backstory and biography fields.
- **Service Layer:** `CharacterService` expansion for identity logic.
- **View Layer:** `views/character_profile.py` for tabbed management.
- **Simplification:** Reduction of 11 command files to lightweight entry points.

**Tech Stack:** Python, SQLAlchemy, Pydantic, SQLite, Discord.py.

---

### Task 1: Data Model Expansion

**Files:**
- Modify: `models/investigator.py`
- Modify: `schemas/investigator.py`

- [ ] **Step 1: Update Investigator database model**
Add `backstory` (JSON), `biography` (JSON), `retirement_date` (DateTime), and `last_played` (DateTime).
- [ ] **Step 2: Update Pydantic schemas**
Reflect the new fields in `InvestigatorBase` and `InvestigatorUpdate`.
- [ ] **Step 3: Commit**
```bash
git add models/investigator.py schemas/investigator.py
git commit -m "feat: expand Investigator model for backstory and metadata"
```

### Task 2: Identity Service Logic

**Files:**
- Modify: `services/character_service.py`

- [ ] **Step 1: Implement rename_investigator and rename_skill logic**
- [ ] **Step 2: Implement manage_backstory logic (Add/Edit/Remove)**
- [ ] **Step 3: Implement toggle_retirement logic**
- [ ] **Step 4: Commit**
```bash
git add services/character_service.py
git commit -m "feat: add identity and backstory methods to CharacterService"
```

### Task 3: Unified Character Profile View

**Files:**
- Create: `views/character_profile.py`

- [ ] **Step 1: Implement CharacterProfileView with tabbed UI**
- [ ] **Step 2: Add modals for renaming and backstory editing**
- [ ] **Step 3: Integrate with CharacterService**
- [ ] **Step 4: Commit**
```bash
git add views/character_profile.py
git commit -m "feat: implement unified CharacterProfileView"
```

### Task 4: Command Refactoring (11 Files)

**Files:**
- Modify: `commands/mycharacter.py`, `commands/addbackstory.py`, `commands/generatebackstory.py`, `commands/removebackstory.py`, `commands/updatebackstory.py`, `commands/rename.py`, `commands/renameskill.py`, `commands/skills.py`, `commands/deleteinvestigator.py`, `commands/retire_character.py`, `commands/printcharacter.py`
- Delete: `commands/_mychar_view.py`, `commands/_backstory_common.py`

- [ ] **Step 1: Refactor each command to use the new service and view layers**
- [ ] **Step 2: Delete legacy view files**
- [ ] **Step 3: Verify all commands are < 100 lines**
- [ ] **Step 4: Commit**
```bash
git add commands/
git commit -m "refactor: simplify Phase 4 commands and remove legacy views"
```

### Task 5: Integration & Verification

**Files:**
- Modify: `loadnsave.py`
- Modify: `dashboard/app.py`

- [ ] **Step 1: Update legacy bridge in loadnsave.py**
- [ ] **Step 2: Refactor dashboard character sheet to use new service methods**
- [ ] **Step 3: Final verification in Discord and Dashboard**
- [ ] **Step 4: Commit**
```bash
git add loadnsave.py dashboard/app.py
git commit -m "refactor: integrate identity services into dashboard"
```
