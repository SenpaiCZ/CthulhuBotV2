# Specification: Finish Dashboard UI Overhaul

## Overview
This track completes the mobile-friendly dashboard UI overhaul by updating all remaining pages that were not covered in the previous phase. Crucially, this track will **NOT update any pages containing "origin" in the title**.

## Goals
- Finish updating all remaining dashboard pages to match the new "Modern Cthulhu" design system.
- Prioritize updates for Utilities & Tools (e.g., `file_browser.html`, `json_editor.html`, `newspaper_dashboard.html`) and Auth & Notifications (e.g., `login.html`, `karma_notification.html`).
- Ensure all pages are responsive and mobile-friendly.

## Scope
### In Scope
- Strictly adhere to the new design system used in the previously updated pages (Admin, Music, etc.).
- Use the exact same CSS classes (e.g., `card-h`, `btn-eld`) and structural conventions.
- Implement Card-Based Layouts for any remaining data tables on mobile devices.
- Refactor the following templates (and any other missed ones that do not have "origin" in the name):
    - `file_browser.html`
    - `json_editor.html`
    - `newspaper_dashboard.html`
    - `login.html`
    - `karma_notification.html`
    - `render_*` pages (excluding `*origin*`)

### Out of Scope
- Modifying any render pages that contain "origin" in their filename (e.g., `render_deity_origin.html`, `render_monster_origin.html`, `render_spell_origin.html`).
- Changing backend route logic, unless required to serve the new UI structure.

## Requirements
- The new design must be visually consistent with `index.html`, `soundboard.html`, and the recently updated Admin pages.
- The dashboard must be fully functional and readable on standard smartphone screen sizes.