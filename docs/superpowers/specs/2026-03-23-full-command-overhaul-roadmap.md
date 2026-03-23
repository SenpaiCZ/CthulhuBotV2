# Spec: Master Command Overhaul Roadmap

## Goal
Systematically refactor all remaining bot commands into the new service-oriented, database-backed architecture to achieve zero JSON dependency, logic parity between Discord and Web Dashboard, and high maintainability.

## Architecture Standards
- **Data Layer:** All state persisted in SQLite via SQLAlchemy ORM.
- **Service Layer:** All business logic encapsulated in pure Python services (reusable by Web Dashboard).
- **View Layer:** All Discord interactions moved from command files into modular `discord.ui.View` components in the `views/` directory.
- **Validation:** Pydantic models for all data transfers and logic results.

## Phase 4: Character Identity & Backstory
- **Objective:** Consolidate character metadata and management.
- **Commands:** `mycharacter.py`, `addbackstory.py`, `generatebackstory.py`, `removebackstory.py`, `updatebackstory.py`, `rename.py`, `renameskill.py`, `skills.py`.
- **Primary Service:** `CharacterService` (expanded).
- **Deliverable:** Unified `CharacterProfileView` and expanded `Investigator` DB model.

## Phase 5: Campaign & Social Engagement
- **Objective:** Move collaborative world-building data to the database.
- **Commands:** `journal.py`, `handout.py`, `macguffin.py`, `loot.py`, `karma.py`.
- **Primary Service:** `CampaignService`.
- **Deliverable:** Database tables for Journals, Macguffins, and Karma logs.

## Phase 6: Game Sessions & Mechanics
- **Objective:** Manage real-time state for active gameplay.
- **Commands:** `combat.py`, `chase.py`, `versus.py`, `madness.py`, `session.py`.
- **Primary Service:** `CombatService`, `SessionService`.
- **Deliverable:** Real-time state trackers for combat and active game sessions.

## Phase 7: Administration & Meta-Features
- **Objective:** Consolidate bot-wide utilities and administration.
- **Commands:** `polls.py`, `giveaway.py`, `rss.py`, `autoroom.py`, `reminders.py`, `botstatus.py`, `backup.py`, `reportbug.py`, `pogo.py`.
- **Primary Service:** `AdminService`.
- **Deliverable:** Database tables for Polls, Giveaways, RSS feeds, and Reminders.

## Success Criteria
- All command files are reduced to lightweight entry points (< 100 lines).
- No JSON files are used for active guild or user state.
- Web Dashboard can perform any action available in Discord via shared services.
