# Implementation Plan: Finish Dashboard UI Overhaul

## Phase 1: Refactoring Utilities & Tools [checkpoint: 92e9387]
- [x] Task: Refactor `file_browser.html` and `json_editor.html` (c49565f)
    - [x] Write unit tests verifying these routes return 200 OK and incorporate the new layout structure
    - [x] Apply the new "Modern Cthulhu" design system, using `card-h` and `btn-eld` classes
    - [x] Ensure mobile responsiveness and Card-Based Layouts for any tables
- [x] Task: Refactor `newspaper_dashboard.html` (c49565f)
    - [x] Verify test coverage for this route
    - [x] Apply the responsive Card-Based Layout and mobile-friendly form controls
- [x] Task: Conductor - User Manual Verification 'Phase 1: Refactoring Utilities & Tools' (Protocol in workflow.md) (92e9387)

## Phase 2: Refactoring Auth & Notifications [checkpoint: d4a7bf8]
- [x] Task: Refactor `login.html` and `karma_notification.html` (a1180c2)
    - [x] Write failing UI structure tests if necessary for new markup
    - [x] Update the templates to use the new design system
    - [x] Ensure the login form and notifications look correct on mobile devices
- [x] Task: Conductor - User Manual Verification 'Phase 2: Refactoring Auth & Notifications' (Protocol in workflow.md) (d4a7bf8)

## Phase 3: Refactoring Render Pages
- [x] Task: Refactor character and entity render pages (`render_character.html`, `render_monster.html`, `render_deity.html`, `render_spell.html`, `render_weapon.html`) (12f78e1)
    - [x] Write route tests confirming the pages render without errors
    - [x] Apply the design overhaul to these pages
    - [x] **CRITICALLY: Do NOT modify any files with "origin" in the title.**
- [ ] Task: Refactor remaining render pages (`render_archetype.html`, `render_pulp_talent.html`, `render_occupation.html`, `render_poison.html`, `render_simple_entry.html`, `render_timeline.html`, `render_letter.html`, `render_script.html`, `render_telegram.html`, `render_morse.html`)
    - [ ] Verify test coverage for these routes
    - [ ] Apply the responsive design system
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Refactoring Render Pages' (Protocol in workflow.md)