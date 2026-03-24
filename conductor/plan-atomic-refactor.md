# Phase 10: Atomic Command Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce all remaining command files to < 100 lines by extracting UI components to `views/` and business logic to `services/`.

**Architecture:**
- **View Extraction**: Creation of specialized view files in the `views/` directory.
- **Service Centralization**: Expansion of `RollService`, `EngagementService`, `AdminService`, and `CodexService`.
- **Command Thinning**: Refactoring the entry point commands to be minimal.

**Tech Stack:** Python, Discord.py, SQLAlchemy.

---

### Task 1: Roll & Dice UI Extraction

**Files:**
- Create: `views/dice_tray_view.py`
- Create: `views/roll_utility_views.py`
- Modify: `commands/roll.py`
- Modify: `services/roll_service.py`

- [ ] **Step 1: Move DiceTrayView to views/dice_tray_view.py**
- [ ] **Step 2: Move SessionView, DisambiguationView, and QuickSkillSelect to views/roll_utility_views.py**
- [ ] **Step 3: Move fuzzy matching and autocomplete logic to RollService**
- [ ] **Step 4: Refactor commands/roll.py to use the new views and service methods**
- [ ] **Step 5: Verify roll.py is < 100 lines and functional**
- [ ] **Step 6: Commit**

### Task 2: Help System Refactor

**Files:**
- Create: `views/help_view.py`
- Modify: `commands/help.py`
- Modify: `services/admin_service.py`

- [ ] **Step 1: Move HelpView and HelpSelect to views/help_view.py**
- [ ] **Step 2: Move command categorization and formatting logic to AdminService (or a new HelpService)**
- [ ] **Step 3: Refactor commands/help.py to a minimal entry point**
- [ ] **Step 4: Verify help.py is < 100 lines**
- [ ] **Step 5: Commit**

### Task 3: Engagement Bundle Refactor (Giveaway, Pogo, RSS)

**Files:**
- Create: `views/engagement_views.py`
- Modify: `commands/giveaway.py`, `commands/pogo.py`, `commands/rss.py`
- Modify: `services/engagement_service.py`

- [ ] **Step 1: Extract all UI components (Views/Modals) from giveaway, pogo, and rss to views/engagement_views.py**
- [ ] **Step 2: Move winner picking and event math to EngagementService**
- [ ] **Step 3: Refactor command files to < 100 lines**
- [ ] **Step 4: Commit**

### Task 4: Utility & Mechanics Refactor (Reminders, Gameroles, Chase, RandomNPC)

**Files:**
- Create: `views/utility_views.py`
- Create: `views/mechanics_views.py`
- Modify: `commands/reminders.py`, `commands/gameroles.py`, `commands/chase.py`, `commands/randomnpc.py`
- Modify: `services/chase_service.py`, `services/codex_service.py`

- [ ] **Step 1: Extract UI for reminders and gameroles to views/utility_views.py**
- [ ] **Step 2: Extract UI for chase and npc to views/mechanics_views.py**
- [ ] **Step 3: Move NPC generation logic to CodexService**
- [ ] **Step 4: Refactor command files to < 100 lines**
- [ ] **Step 5: Commit**

### Task 5: Final Cleanup & Verification

**Files:**
- Modify: `commands/music.py`, `commands/polls.py`, `commands/codex.py` (Final gutting)

- [ ] **Step 1: Ensure all remaining Phase 6/7/8 commands are < 100 lines**
- [ ] **Step 2: Perform final end-to-end verification of all Discord interactions**
- [ ] **Step 3: Commit**
