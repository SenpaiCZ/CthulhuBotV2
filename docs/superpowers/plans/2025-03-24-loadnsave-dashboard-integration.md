# Task 6: LoadNSave & Dashboard Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `loadnsave.py` to delegate settings management to `SettingsService` and refactor dashboard routes to use the new service layer.

**Architecture:** We will modify `loadnsave.py` to act as a bridge, delegating to `SettingsService` when `USE_DATABASE` is True. This ensures that the rest of the bot (which relies on `loadnsave.py`) gets database support without changing every call site. Simultaneously, we'll update `dashboard/app.py` to use `SettingsService` directly for settings-related operations to ensure consistency.

**Tech Stack:** Python, SQLAlchemy, Quart, discord.py

---

### Task 1: Research and Preparation

**Files:**
- Research: `services/settings_service.py`
- Research: `schemas/settings.py`

- [ ] **Step 1: Verify SettingsService capabilities**
  Check which settings are currently supported by `SettingsService` to ensure all 15+ settings from `loadnsave.py` can be handled.

- [ ] **Step 2: Check database schema for settings**
  Verify `models/guild_settings.py` supports all required keys.

### Task 2: Modify loadnsave.py to delegate to SettingsService

**Files:**
- Modify: `loadnsave.py`

- [ ] **Step 1: Add imports and helper for SettingsService**
  Import `SettingsService` and `SessionLocal`. Create a helper to get/save settings from DB.

- [ ] **Step 2: Refactor load_server_stats and save_server_stats**
  Delegate to `SettingsService.get_setting(db, guild_id, "prefix")`.

- [ ] **Step 3: Refactor load_luck_stats and save_luck_stats**
  Delegate to `SettingsService.get_setting(db, guild_id, "luck_threshold")`.

- [ ] **Step 4: Refactor load_skill_settings and save_skill_settings**
  Delegate to `SettingsService.get_setting(db, guild_id, "max_starting_skill")`.

- [ ] **Step 5: Refactor load_bot_status and save_bot_status**
  Delegate to `SettingsService.get_setting(db, "global", "bot_status")`.

- [ ] **Step 6: Refactor load_karma_settings and save_karma_settings**
  Delegate to `SettingsService.get_setting(db, guild_id, "karma_settings")`.

- [ ] **Step 7: Refactor other settings functions**
  Apply same pattern to: `load_server_volumes`, `smartreact_load`, `autoroom_load`, `load_pogo_settings`, `load_gamerole_settings`, `load_enroll_settings`, `load_loot_settings`, `load_skill_sound_settings`, `load_fonts_config`.

- [ ] **Step 8: Handle load_settings (config.json)**
  Delegate to `SettingsService` for global settings like `admin_password`, `dashboard_theme`, `dashboard_fonts`, etc.

### Task 3: Refactor dashboard/app.py

**Files:**
- Modify: `dashboard/app.py`

- [ ] **Step 1: Import SettingsService and SessionLocal**

- [ ] **Step 2: Update app_startup**
  Use `SettingsService` to check/update `admin_password`.

- [ ] **Step 3: Update inject_theme**
  Use `SettingsService` for theme and font settings.

- [ ] **Step 4: Update settings routes**
  Update `save_fonts`, `save_origin_fonts`, `save_design`, `save_status`, `save_prefix`, `save_general_settings`, `game_loot_save`, `game_sounds_save`, `save_karma`, `save_karma_roles`.

- [ ] **Step 5: Update data fetching routes**
  Update `game_settings_data`, `game_loot_data`, `game_sounds_data`, `fonts_list`, `admin_karma`, `admin_bot_config`.

### Task 4: Verification

- [ ] **Step 1: Run basic tests**
  Ensure the dashboard still loads and settings can be saved/loaded.

- [ ] **Step 2: Verify database entries**
  Check that settings are actually being written to the database.

- [ ] **Step 3: Commit changes**
  `git add loadnsave.py dashboard/app.py`
  `git commit -m "refactor: integrate settings service into loadnsave and dashboard"`
