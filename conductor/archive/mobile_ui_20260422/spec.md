# Specification: Mobile-Friendly Dashboard UI Overhaul

## Overview
This track focuses on overhauling the entire CthulhuBotV2 web dashboard UI to ensure all pages match the new design language established by the `index.html` (main page) and `soundboard.html`. A primary goal is to make the dashboard fully responsive and usable on mobile devices.

## Goals
- Apply the new design system uniformly across all dashboard templates.
- Implement a responsive Hamburger Sidebar for mobile navigation.
- Convert existing data tables into a stacked Card-Based Layout on small screens for improved readability.
- Prioritize the updates for Interactive Dashboards and Admin & Settings pages.

## Scope
### In Scope
- Update CSS and HTML layout for all relevant dashboard templates.
- Implement a mobile-first approach using media queries (e.g., in `themes.css` or `base.html`).
- Update the sidebar logic (e.g., `sidebar.jsx`) to support a hamburger menu toggle on mobile screens.
- Refactor list/table views to use CSS Grid/Flexbox cards on small screens.

### Out of Scope
- Modifying any render pages that contain "origin" in their filename (e.g., `render_deity_origin.html`, `render_monster_origin.html`).
- Changing the underlying Python/Quart backend route logic, unless strictly required to serve the new UI structure.
- Introducing new dashboard features not related to the UI overhaul.

## Requirements
- The new design must be visually consistent with `index.html` and `soundboard.html`.
- The dashboard must be fully functional and readable on standard smartphone screen sizes.
- Horizontal scrolling on the main page body must be eliminated.
- The sidebar must collapse behind a hamburger icon on mobile and smoothly transition when opened.