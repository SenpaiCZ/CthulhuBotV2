# Implementation Plan: Mobile-Friendly Dashboard UI Overhaul

## Phase 1: CSS Framework and Base Layout Updates
- [ ] Task: Update `base.html` and `themes.css` with responsive design foundations
    - [ ] Write or verify basic structural route tests for the main layout
    - [ ] Implement media queries and CSS grid/flexbox foundations for mobile responsiveness
    - [ ] Add the hamburger menu button and hidden sidebar styles for mobile in `themes.css`
    - [ ] Ensure `index.html` and `soundboard.html` still look correct with the new base styles
- [ ] Task: Update Sidebar Component (`sidebar.jsx` or equivalent)
    - [ ] Write a test to ensure the sidebar logic renders correctly
    - [ ] Implement React/JS logic to toggle the sidebar via the hamburger menu
    - [ ] Refactor the navigation links for better touch targets (44x44px minimum)
- [ ] Task: Conductor - User Manual Verification 'Phase 1: CSS Framework and Base Layout Updates' (Protocol in workflow.md)

## Phase 2: Refactoring Admin & Settings Pages
- [ ] Task: Refactor `admin_dashboard.html`, `bot_config.html`, and `game_settings.html`
    - [ ] Write unit tests verifying these routes return 200 OK and incorporate the new layout structure
    - [ ] Convert any static tables to the new Card-Based Layout on mobile
    - [ ] Apply the new design system to all forms and inputs
- [ ] Task: Refactor Roles, Backup, and Deleter Dashboards
    - [ ] Verify test coverage for these routes
    - [ ] Apply the responsive Card-Based Layout and mobile-friendly form controls
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Refactoring Admin & Settings Pages' (Protocol in workflow.md)

## Phase 3: Refactoring Interactive Dashboards
- [ ] Task: Refactor `music_dashboard.html`, `autoroom_dashboard.html`, and `polls_dashboard.html`
    - [ ] Write failing UI structure tests if necessary for new markup
    - [ ] Apply mobile-friendly design and interactive controls for music and polls
    - [ ] Ensure interactive elements are usable on touch devices
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Refactoring Interactive Dashboards' (Protocol in workflow.md)

## Phase 4: Refactoring Codex & Reference Pages
- [ ] Task: Refactor `monsters.html`, `spells.html`, `weapons.html` and other list templates
    - [ ] Write route tests confirming the lists render without errors
    - [ ] Convert large data tables into stackable cards via CSS
    - [ ] Apply the design overhaul to all remaining list items (explicitly excluding pages with `origin`)
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Refactoring Codex & Reference Pages' (Protocol in workflow.md)