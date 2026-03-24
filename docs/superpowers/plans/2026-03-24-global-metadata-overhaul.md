# Global Emoji & Metadata Overhaul Implementation Plan (Phase 9)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize all emoji mappings and system metadata into the SQLite database, providing a Service layer and backward-compatible bridges.

**Architecture:**
- **Data Layer:** `global_emojis` table in SQLAlchemy.
- **Service Layer:** `MetadataService` with in-memory caching for performance.
- **Bridge Layer:** Refactored `emojis.py` and `occupation_emoji.py` that call the service.
- **Migration:** Script to ingest hardcoded dictionaries into the database.

**Tech Stack:** Python, SQLAlchemy, Pydantic, SQLite.

---

### Task 1: Data Modeling (Metadata Table)

**Files:**
- Create: `models/metadata.py`
- Modify: `models/database.py`

- [ ] **Step 1: Create the Metadata database model**
Include `category` (Stat, Skill, Occupation, Language, Item, System), `key`, and `value` (emoji).
- [ ] **Step 2: Register model in database.py**
- [ ] **Step 3: Commit**
```bash
git add models/metadata.py models/database.py
git commit -m "feat: add global_emojis database model"
```

### Task 2: Metadata Service Implementation

**Files:**
- Create: `services/metadata_service.py`
- Create: `schemas/metadata.py`

- [ ] **Step 1: Define Metadata schemas**
- [ ] **Step 2: Implement MetadataService**
Methods for `get_emoji`, `get_all_emojis`, and `sync_cache` (in-memory dict).
- [ ] **Step 3: Commit**
```bash
git add schemas/metadata.py services/metadata_service.py
git commit -m "feat: implement MetadataService and schemas"
```

### Task 3: Emoji Migration Utility

**Files:**
- Create: `tools/migrate_emojis_to_sql.py`

- [ ] **Step 1: Implement migration script**
Import `stat_emojis` from `emojis.py` and `occupation_emojis` from `occupation_emoji.py`. Categorize and insert into `global_emojis`.
- [ ] **Step 2: Run migration and verify count**
- [ ] **Step 3: Commit**
```bash
git add tools/migrate_emojis_to_sql.py
git commit -m "feat: add emoji migration utility"
```

### Task 4: Bridge Refactoring (Backward Compatibility)

**Files:**
- Modify: `emojis.py`
- Modify: `occupation_emoji.py`

- [ ] **Step 1: Refactor occupation_emoji.py**
Replace the static dict with a call to `MetadataService` (keeping the `get_occupation_emoji` function signature).
- [ ] **Step 2: Refactor emojis.py**
    - Implement a dynamic Proxy class for `stat_emojis` that supports `.get()`, `.items()`, and iteration by fetching from `MetadataService.cache`.
    - Refactor `get_emoji_for_item` to use a prioritized list of keywords fetched from the database ('Item' category).
    - Refactor `get_health_bar` to use 'System' category emojis for progress bars.
- [ ] **Step 3: Commit**
```bash
git add emojis.py occupation_emoji.py
git commit -m "refactor: convert emoji files to services bridges with proxy support"
```

### Task 5: Dashboard Asset Management & Sync

**Files:**
- Modify: `dashboard/app.py`
- Create: `dashboard/templates/admin_metadata.html`
- Modify: `bot.py`

- [ ] **Step 1: Add dashboard route to manage global emojis**
- [ ] **Step 2: Implement the Glassmorphic management UI**
- [ ] **Step 3: Implement Cache Invalidation**
Add a mechanism (e.g., a shared state or internal API call) so the Dashboard update triggers `MetadataService.sync_cache()` in the bot process.
- [ ] **Step 4: Final verification of emojis in Discord and Dashboard**
- [ ] **Step 5: Commit**
```bash
git add dashboard/ bot.py
git commit -m "feat: add global emoji management and real-time sync"
```
