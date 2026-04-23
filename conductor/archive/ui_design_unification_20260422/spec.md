# Specification: UI Design Unification

## Overview
This track focuses on unifying the design of all remaining dashboard pages to match the style established by the main page (`index.html`) and the soundboard (`/admin/soundboard`). The goal is to correct inconsistent fonts, colors, missing content blocks, and replace emojis with thematic symbols.

## Goals
- Update all remaining dashboard templates to use the "Modern Cthulhu" design system.
- Correct fonts and color palettes to match `themes.css`.
- Implement missing content blocks using the custom `card-h` styled containers with corners.
- Replace emojis with thematic text symbols (similar to those used in the left sidebar menu).

## Scope
### In Scope
- All remaining dashboard pages (Admin & Settings, Grimoire, and Render pages).
- Replacing standard Bootstrap or raw HTML layouts with `card-h` components.
- Replacing emojis with unicode symbols matching the sidebar's style.
- Ensuring responsive layouts.

### Out of Scope
- Adding new functionality or changing backend logic.
- **CRITICALLY: Do NOT modify any files that have "origin" in their name (e.g., `render_deity_origin.html`).**

## Requirements
- The design must perfectly match `index.html` and `soundboard.html`.
- Use the established CSS variables (`--sigil`, `--bone`, `--void-1`, etc.).
- Content blocks must be wrapped in `<div class="card-h">` with `<window.Corners/>` or equivalent HTML.
- Emojis must be replaced by thematic unicode characters (e.g., ✶, ◈, ◷).