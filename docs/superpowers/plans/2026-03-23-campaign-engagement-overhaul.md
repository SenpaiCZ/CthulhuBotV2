# Campaign & Social Engagement Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor campaign world-building and social reward features to a database-backed architecture with a unified campaign dashboard and service layer.

**Architecture:**
- **Data Layer:** New tables for `journal_entries`, `inventory_items`, `handouts`, and `karma_stats`.
- **Service Layer:** `CampaignService` for all campaign logic.
- **View Layer:** `views/campaign_dashboard.py` for tabbed interaction.
- **Simplification:** Reduction of 5 command files to lightweight entry points.

**Tech Stack:** Python, SQLAlchemy, Pydantic, SQLite, Discord.py.

---

### Task 1: Data Modeling (Campaign Tables)

**Files:**
- Modify: `models/` (create new model files)
- Modify: `models/database.py`

- [ ] **Step 1: Create journal and karma models**
Create `models/campaign.py` with `JournalEntry` and `KarmaStat` tables.
- [ ] **Step 2: Create inventory and handout models**
Create `models/inventory.py` with `InventoryItem` and `Handout` tables.
- [ ] **Step 3: Register models in database.py**
- [ ] **Step 4: Commit**
```bash
git add models/
git commit -m "feat: add campaign, inventory, and karma database models"
```

### Task 2: Campaign Service Implementation

**Files:**
- Create: `services/campaign_service.py`
- Create: `schemas/campaign.py`

- [ ] **Step 1: Define campaign schemas**
Include `JournalEntryCreate`, `InventoryItemCreate`, and `KarmaUpdate`.
- [ ] **Step 2: Implement CampaignService**
Methods for: `add_journal_entry`, `list_journal_entries`, `add_inventory_item`, `generate_loot`, `add_karma`.
- [ ] **Step 3: Commit**
```bash
git add schemas/campaign.py services/campaign_service.py
git commit -m "feat: implement CampaignService and schemas"
```

### Task 3: Unified Campaign Dashboard View

**Files:**
- Create: `views/campaign_dashboard.py`

- [ ] **Step 1: Implement CampaignDashboardView with tabbed UI**
Tabs for: 'Inventory', 'Handouts', 'Journal'.
- [ ] **Step 2: Integrate with CampaignService**
- [ ] **Step 3: Commit**
```bash
git add views/campaign_dashboard.py
git commit -m "feat: implement unified CampaignDashboardView"
```

### Task 4: Command Refactoring (5 Files)

**Files:**
- Modify: `commands/journal.py`, `commands/loot.py`, `commands/karma.py`, `commands/handout.py`, `commands/macguffin.py`

- [ ] **Step 1: Refactor commands to use CampaignService and CampaignDashboardView**
- [ ] **Step 2: Verify all commands are < 100 lines**
- [ ] **Step 3: Commit**
```bash
git add commands/
git commit -m "refactor: simplify Phase 5 commands and use campaign service"
```

### Task 5: Campaign Data Migration

**Files:**
- Create: `tools/migrate_campaign_to_sql.py`

- [ ] **Step 1: Implement migration script for journal and karma JSON files**
- [ ] **Step 2: Implement migration for investigator gear -> inventory items**
- [ ] **Step 3: Run and verify migration**
- [ ] **Step 4: Commit**
```bash
git add tools/migrate_campaign_to_sql.py
git commit -m "feat: add campaign data migration utility"
```

### Task 6: Integration & Final Verification

**Files:**
- Modify: `loadnsave.py`
- Modify: `dashboard/app.py`

- [ ] **Step 1: Update loadnsave.py bridge for campaign data**
- [ ] **Step 2: Refactor dashboard campaign pages to use CampaignService**
- [ ] **Step 3: Final end-to-end verification**
- [ ] **Step 4: Commit**
```bash
git add loadnsave.py dashboard/app.py
git commit -m "refactor: integrate campaign services into dashboard"
```
