# Spec: Atomic Command Refactor (Phase 10)

## Goal
Finalize the architectural cleanup by systematically reducing all remaining command files to < 100 lines. This will be achieved by extracting UI components into the `views/` directory and complex logic into the `services/` layer.

## Architectural Standards
- **Entry Points**: `commands/*.py` must only handle Discord interaction routing and basic input gathering.
- **UI Decoupling**: All classes inheriting from `discord.ui.View`, `discord.ui.Modal`, or `discord.ui.Select` must reside in `views/`.
- **Logic Centralization**: All game math, search algorithms, and data manipulation must reside in `services/`.

## Target Files & Refactor Strategy

### 1. Dice & Roll (`roll.py`)
- **Extract to `views/dice_tray_view.py`**: `DiceTrayView`.
- **Extract to `views/roll_utility_views.py`**: `SessionView`, `DisambiguationView`, `QuickSkillSelect`.
- **Move to `RollService`**: `_resolve_skill` logic and autocomplete processing.

### 2. Help System (`help.py`)
- **Extract to `views/help_view.py`**: `HelpView`, `HelpSelect`.
- **Move to `AdminService`**: Categorization of commands and manual page generation.

### 3. Engagement: Giveaway, Pogo, RSS (`giveaway.py`, `pogo.py`, `rss.py`)
- **Extract to `views/engagement_views.py`**: All modals and interactive views for these features.
- **Move to `EngagementService`**: 
    - Giveaway: Winner picking, participant tracking.
    - Pogo: Event management and countdown math.
    - RSS: Feed parsing and change detection.

### 4. User Utilities: Reminders, Gameroles, Polls (`reminders.py`, `gameroles.py`, `polls.py`)
- **Extract to `views/utility_views.py`**: 
    - `ReminderListView`, `ReminderDeleteSelect`, `ReminderContextMenuModal`.
    - `GameroleView`, `GameroleSelect`.
    - `PollView` (if not already moved).
- **Consolidate in Services**: Ensure all "Manager" methods are in `AdminService` or `EngagementService`.

### 5. Game Mechanics: Chase & Random NPC (`chase.py`, `randomnpc.py`)
- **Extract to `views/mechanics_views.py`**: `ChaseView`, `NPCView`.
- **Move to Services**: 
    - `ChaseService`: All chase progression and obstacle math.
    - `CodexService`: Random NPC generation logic using codex data.

## Success Criteria
- All target command files are < 100 lines of code.
- `views/` directory contains modular, reusable UI components.
- `services/` layer contains 100% of the "Business Logic".
- No functional regressions in Discord or the Web Dashboard.
