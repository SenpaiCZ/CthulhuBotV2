# Spec: Master Command Overhaul Roadmap

## Goal
Systematically refactor all remaining bot commands into the new service-oriented, database-backed architecture to achieve zero JSON dependency, logic parity between Discord and Web Dashboard, and high maintainability.

## Architecture Standards
- **Data Layer:** All state persisted in SQLite via SQLAlchemy ORM.
- **Service Layer:** All business logic encapsulated in pure Python services (reusable by Web Dashboard).
- **View Layer:** All Discord interactions moved from command files into modular `discord.ui.View` components in the `views/` directory.
- **Logic Goal:** Command files should be reduced to lightweight entry points (< 100 lines).

## Phase 4: Character Identity & Backstory
- **Objective:** Consolidate character metadata and lifecycle management.
- **Commands:** `mycharacter.py`, `addbackstory.py`, `generatebackstory.py`, `removebackstory.py`, `updatebackstory.py`, `rename.py`, `renameskill.py`, `skills.py`, `deleteinvestigator.py`, `retire_character.py`, `printcharacter.py`.
- **Primary Service:** `CharacterService` (expanded).
- **Deliverable:** Unified `CharacterProfileView` and expanded `Investigator` DB model.

## Phase 5: Campaign & Social Engagement
- **Objective:** Move collaborative world-building and social data to the database.
- **Commands:** `journal.py`, `handout.py`, `macguffin.py`, `loot.py`, `karma.py`.
- **Primary Service:** `CampaignService`.
- **Deliverable:** Database tables for Journals, Macguffins, and Karma logs.

## Phase 6: Game Mechanics & The Codex
- **Objective:** Manage real-time mechanics and the massive reference library.
- **Commands:** `combat.py`, `chase.py`, `versus.py`, `madness.py`, `session.py`, `stat.py`, `changeluck.py`, `codex.py`, `randomname.py`, `randomnpc.py`.
- **Primary Services:** `CombatService`, `SessionService`, `CodexService`.
- **Deliverable:** Real-time combat trackers and a searchable SQL-backed Codex.

## Phase 7: Administration & Engagement
- **Objective:** Consolidate bot-wide utilities, roles, and administration.
- **Commands:** `polls.py`, `giveaway.py`, `rss.py`, `autoroom.py`, `reminders.py`, `botstatus.py`, `backup.py`, `reportbug.py`, `pogo.py`, `enroll.py`, `deleter.py`, `gameroles.py`, `rolepanel.py`, `reactionroles.py`, `smartreaction.py`, `help.py`, `ping.py`, `uptime.py`, `restart.py`, `updatebot.py`, `admin_slash.py`.
- **Primary Service:** `AdminService`.
- **Deliverable:** Centralized admin tools and automated social engagement systems.

## Success Criteria
- All command files (including `roll.py` and `music.py`) are reduced to lightweight entry points (< 100 lines).
- No JSON files are used for active guild or user state.
- Web Dashboard can perform any action available in Discord via shared services.
- Searchable, efficient SQL-backed Codex replacing the legacy `infodata` JSON files.
