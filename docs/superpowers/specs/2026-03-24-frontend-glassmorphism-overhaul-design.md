# Spec: Frontend Glassmorphism Overhaul (Phase 8)

## Goal
Transform the bot's web dashboard from a legacy Bootstrap 5 layout to a modern, immersive "Eldritch Glass" design using Tailwind CSS and Glassmorphism principles. This will enhance the atmospheric feel of the Call of Cthulhu experience while improving UI responsiveness and code maintainability.

## Architecture
- **Framework:** Tailwind CSS (utility-first styling).
- **Design Paradigm:** Glassmorphism (translucency, backdrop-blur, thin borders, vivid accents).
- **Implementation Strategy:** Parallel coexistence. A new `base_glass.html` will be created, and pages will be migrated one by one to avoid downtime.
- **Component Model:** Reusable Jinja2 macros for standard "Glass" UI elements.

## Design System (The Eldritch Glass)
- **Background:** Deep Abyssal Gradient (`bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950`).
- **Cards/Surfaces:** `bg-slate-900/40 backdrop-blur-xl border border-white/10 shadow-2xl`.
- **Primary Accent:** Eldritch Purple/Indigo (`text-indigo-400`, `border-indigo-500/30`).
- **Success Accent:** Mythic Green (`text-emerald-400`, `shadow-emerald-500/20`).
- **Danger Accent:** Sanity Loss Red (`text-rose-500`, `border-rose-500/20`).
- **Typography:** Preservation of custom eldritch fonts (`Ancient Arabica`, `Dark Rlyehain`) for headings, sharp Sans-Serif for body text.

## Components
1. `base_glass.html`: The new core layout with a Glassmorphic navbar and side-navigation.
2. `includes/glass_components.html`: Jinja2 macros for `glass_card`, `glass_button`, `glass_modal`, and `glass_input`.
3. `static/css/glass.css`: Custom Tailwind layer for complex eldritch animations (e.g., drifting fog, glowing borders).

## Migration Priority
1. **Infrastructure:** Tailwind setup and `base_glass.html`.
2. **Landing Page:** `index.html` refactor.
3. **Player Core:** `render_character.html` and `list_characters.html`.
4. **Knowledge Base:** `monsters.html`, `spells.html`, `deities.html`.
5. **GM Tools:** All dashboard settings and administrative pages.

## Success Criteria
- 100% removal of Bootstrap 5 dependency in migrated pages.
- Achieving a high-performance "Glass" look with < 100ms render time.
- Responsive design that works seamlessly on mobile, tablet, and desktop.
- Consistent eldritch atmosphere across all dashboard views.
