# Dice Rolling & Settings Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor dice rolling and server settings to a service-oriented architecture with a centralized database, ensuring bit-perfect parity with legacy logic.

**Architecture:**
- **Data Layer:** `GuildSettings` table in SQLite with SQLAlchemy.
- **Service Layer:** `services/roll_service.py` (logic) and `services/settings_service.py` (config).
- **View Layer:** `views/roll_view.py` for Discord interactions.
- **Verification:** Deterministic RNG seeding for parity testing.

**Tech Stack:** Python, SQLAlchemy, Pydantic, SQLite, Discord.py.

---

### Task 1: Data Modeling (Guild Settings)

**Files:**
- Create: `models/guild_settings.py`
- Modify: `models/database.py` (to register the new model)

- [ ] **Step 1: Create the GuildSettings database model**
Include fields for all 15+ settings identified in the spec (Luck thresholds, skill caps, game modes, autorooms, etc.).
- [ ] **Step 2: Register model in database.py**
- [ ] **Step 3: Commit**
```bash
git add models/guild_settings.py models/database.py
git commit -m "feat: add GuildSettings database model"
```

### Task 2: Settings Service & Schemas

**Files:**
- Create: `schemas/settings.py`
- Create: `services/settings_service.py`

- [ ] **Step 1: Define Pydantic schemas for settings**
- [ ] **Step 2: Implement SettingsService**
Methods for `get_guild_settings`, `update_guild_settings`, and `initialize_guild`.
- [ ] **Step 3: Commit**
```bash
git add schemas/settings.py services/settings_service.py
git commit -m "feat: implement settings service and schemas"
```

### Task 3: Roll Service & Schemas

**Files:**
- Create: `schemas/roll.py`
- Create: `services/roll_service.py`

- [ ] **Step 1: Define RollResult and RollRequest schemas**
- [ ] **Step 2: Port dice parsing and skill check logic from roll.py**
Implement `calculate_roll` in `RollService`.
- [ ] **Step 3: Commit**
```bash
git add schemas/roll.py services/roll_service.py
git commit -m "feat: implement roll service and schemas"
```

### Task 4: Deterministic Parity Testing

**Files:**
- Create: `tests/test_roll_parity.py`

- [ ] **Step 1: Implement parity test with fixed RNG seed**
Compare output of `RollService` vs legacy `_perform_roll` (from `roll.py`).
- [ ] **Step 2: Run tests and verify 100% parity**
Run: `python -m pytest tests/test_roll_parity.py`
- [ ] **Step 3: Commit**
```bash
git add tests/test_roll_parity.py
git commit -m "test: add deterministic parity tests for dice rolling"
```

### Task 5: Settings Migration Utility

**Files:**
- Create: `tools/migrate_settings_to_sql.py`

- [ ] **Step 1: Implement migration for all 15+ JSON files**
- [ ] **Step 2: Implement parity verification for migrated settings**
- [ ] **Step 3: Run migration and verify**
- [ ] **Step 4: Commit**
```bash
git add tools/migrate_settings_to_sql.py
git commit -m "feat: add settings migration utility with verification"
```

### Task 6: LoadNSave & Dashboard Integration

**Files:**
- Modify: `loadnsave.py`
- Modify: `dashboard/app.py`

- [ ] **Step 1: Update loadnsave.py to delegate settings to SettingsService**
- [ ] **Step 2: Update dashboard routes to use the new services**
- [ ] **Step 3: Verify dashboard settings management**
- [ ] **Step 4: Commit**
```bash
git add loadnsave.py dashboard/app.py
git commit -m "refactor: integrate settings service into loadnsave and dashboard"
```

### Task 7: Discord UI Refactor (Roll Views)

**Files:**
- Create: `views/roll_view.py`
- Modify: `commands/roll.py`
- Modify: `commands/gamesettings.py`

- [ ] **Step 1: Move UI logic from roll.py to RollView**
- [ ] **Step 2: Update /roll and /gamesettings commands to use services**
- [ ] **Step 3: Final verification in Discord**
- [ ] **Step 4: Commit**
```bash
git add views/roll_view.py commands/roll.py commands/gamesettings.py
git commit -m "refactor: decouple roll and settings UI from logic"
```
