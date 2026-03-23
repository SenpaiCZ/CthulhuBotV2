# Game Mechanics & The Codex Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor core game mechanics and the reference library to a database-backed, service-oriented architecture, gutting the massive legacy `codex.py` and `combat.py` files.

**Architecture:**
- **Data Layer:** Unified `codex_entries` table and relational game state tables.
- **Service Layer:** `CodexService`, `CombatService`, and `SessionService`.
- **View Layer:** Modular UI components for combat tracking and rule rendering.
- **Simplification:** Reduction of 10 command files to lightweight entry points.

**Tech Stack:** Python, SQLAlchemy, Pydantic, SQLite, Discord.py.

---

### Task 1: Data Modeling (Codex & Game State)

**Files:**
- Modify: `models/` (create codex.py and game_state.py)
- Modify: `models/database.py`

- [ ] **Step 1: Create the Codex database model**
Include `category`, `name`, `content` (JSON), and `image_filename`.
- [ ] **Step 2: Create the Game State database models**
`CombatSession`, `CombatParticipant`, and `SessionLog`.
- [ ] **Step 3: Register models in database.py**
- [ ] **Step 4: Commit**
```bash
git add models/
git commit -m "feat: add codex and game state database models"
```

### Task 2: Codex Service Implementation

**Files:**
- Create: `services/codex_service.py`
- Create: `schemas/codex.py`

- [ ] **Step 1: Define Codex schemas**
- [ ] **Step 2: Implement search and autocomplete logic**
Port existing search logic from `codex.py` to the service.
- [ ] **Step 3: Implement data retrieval methods**
- [ ] **Step 4: Commit**
```bash
git add schemas/codex.py services/codex_service.py
git commit -m "feat: implement CodexService and schemas"
```

### Task 3: Game Mechanics Services (Combat & Session)

**Files:**
- Create: `services/combat_service.py`
- Create: `services/session_service.py`

- [ ] **Step 1: Implement CombatService logic**
Initiatives, turn transitions, and participant management.
- [ ] **Step 2: Implement SessionService logic**
Duration tracking and unified event logging.
- [ ] **Step 3: Commit**
```bash
git add services/combat_service.py services/session_service.py
git commit -m "feat: implement Combat and Session services"
```

### Task 4: UI Refactoring (Combat Tracker & Codex Renderer)

**Files:**
- Create: `views/combat_tracker.py`
- Create: `views/codex_renderer.py`

- [ ] **Step 1: Implement interactive CombatTrackerView**
- [ ] **Step 2: Implement consistent CodexRendererView**
- [ ] **Step 3: Commit**
```bash
git add views/
git commit -m "feat: implement unified combat and codex views"
```

### Task 5: Command Refactoring (10 Files)

**Files:**
- Modify: `commands/codex.py`, `commands/combat.py`, `commands/chase.py`, `commands/versus.py`, `commands/madness.py`, `commands/session.py`, `commands/stat.py`, `commands/changeluck.py`, `commands/randomname.py`, `commands/randomnpc.py`

- [ ] **Step 1: Gut logic from commands and delegate to services**
- [ ] **Step 2: Verify all commands are < 100 lines**
- [ ] **Step 3: Commit**
```bash
git add commands/
git commit -m "refactor: simplify Phase 6 commands and use game services"
```

### Task 6: Big Migration (The Codex & Active Games)

**Files:**
- Create: `tools/migrate_game_to_sql.py`

- [ ] **Step 1: Implement migration script for all infodata/*.json files**
- [ ] **Step 2: Implement migration for active combat sessions**
- [ ] **Step 3: Run and verify migration**
- [ ] **Step 4: Commit**
```bash
git add tools/migrate_game_to_sql.py
git commit -m "feat: add codex and game state migration utility"
```

### Task 7: Integration & Dashboard Update

**Files:**
- Modify: `loadnsave.py`
- Modify: `dashboard/app.py`

- [ ] **Step 1: Refactor dashboard to search the SQL Codex**
- [ ] **Step 2: Implement live combat tracking on the web UI**
- [ ] **Step 3: Final end-to-end verification**
- [ ] **Step 4: Commit**
```bash
git add loadnsave.py dashboard/app.py
git commit -m "refactor: integrate game services into dashboard"
```
