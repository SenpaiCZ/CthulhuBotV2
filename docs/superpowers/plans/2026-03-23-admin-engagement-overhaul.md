# Administration & Engagement Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize the architectural overhaul by refactoring all administrative and social engagement features to a database-backed, service-oriented structure, achieving zero JSON dependency for state.

**Architecture:**
- **Data Layer:** 8+ new relational tables for administrative and social data.
- **Service Layer:** `EngagementService` and `AdminService`.
- **View Layer:** Modular UI components for polls and administrative controls.
- **Simplification:** Reduction of 21 command files to lightweight entry points.

**Tech Stack:** Python, SQLAlchemy, Pydantic, SQLite, Discord.py.

---

### Task 1: Data Modeling (The Final Tables)

**Files:**
- Modify: `models/admin.py` (create)
- Modify: `models/social.py` (create)
- Modify: `models/database.py`

- [ ] **Step 1: Create administrative models**
`autorooms`, `deleter_jobs`, `rss_feeds`.
- [ ] **Step 2: Create social and engagement models**
`polls`, `giveaways`, `reminders`, `pogo_events`, `gameroles`.
- [ ] **Step 3: Register models in database.py**
- [ ] **Step 4: Commit**
```bash
git add models/
git commit -m "feat: add final administrative and social database models"
```

### Task 2: Service Layer Implementation

**Files:**
- Create: `services/engagement_service.py`
- Create: `services/admin_service.py`
- Create: `schemas/admin.py`, `schemas/social.py`

- [ ] **Step 1: Implement EngagementService**
Logic for polls, giveaways, and RSS polling.
- [ ] **Step 2: Implement AdminService**
Logic for backups, restarts, and bot presence.
- [ ] **Step 3: Commit**
```bash
git add schemas/ services/
git commit -m "feat: implement Engagement and Admin services"
```

### Task 3: Command Refactoring (21 Files)

**Files:**
- Modify: `commands/polls.py`, `commands/giveaway.py`, `commands/rss.py`, `commands/autoroom.py`, `commands/reminders.py`, `commands/botstatus.py`, `commands/backup.py`, `commands/reportbug.py`, `commands/pogo.py`, `commands/enroll.py`, `commands/deleter.py`, `commands/gameroles.py`, `commands/rolepanel.py`, `commands/reactionroles.py`, `commands/smartreaction.py`, `commands/help.py`, `commands/ping.py`, `commands/uptime.py`, `commands/restart.py`, `commands/updatebot.py`, `commands/admin_slash.py`

- [ ] **Step 1: Gut logic from 21 commands and delegate to services**
- [ ] **Step 2: Verify all commands are < 100 lines**
- [ ] **Step 3: Commit**
```bash
git add commands/
git commit -m "refactor: simplify Phase 7 commands and use centralized services"
```

### Task 4: UI Refactoring (Admin Hub & Poll Views)

**Files:**
- Create: `views/admin_hub.py`
- Create: `views/poll_view.py`

- [ ] **Step 1: Implement AdminHubView for bot owners**
- [ ] **Step 2: Implement interactive PollView**
- [ ] **Step 3: Commit**
```bash
git add views/
git commit -m "feat: implement unified admin and engagement views"
```

### Task 5: Final Migration & Cleanup

**Files:**
- Create: `tools/migrate_admin_to_sql.py`
- Modify: `loadnsave.py`

- [ ] **Step 1: Implement migration for remaining JSON files (Polls, Reminders, RSS, etc.)**
- [ ] **Step 2: Update loadnsave.py to bridge the final data sources**
- [ ] **Step 3: Run final migration and verify**
- [ ] **Step 4: Commit**
```bash
git add tools/ loadnsave.py
git commit -m "feat: complete final data migration and JSON cleanup"
```

### Task 6: Dashboard Integration & Verification

**Files:**
- Modify: `dashboard/app.py`

- [ ] **Step 1: Refactor administrative routes to use AdminService**
- [ ] **Step 2: Implement live task monitor on the web UI**
- [ ] **Step 3: Final end-to-end verification of the entire system**
- [ ] **Step 4: Commit**
```bash
git add dashboard/app.py
git commit -m "refactor: integrate final services into dashboard"
```
