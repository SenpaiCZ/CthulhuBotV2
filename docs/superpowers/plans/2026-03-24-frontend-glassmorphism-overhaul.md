# Frontend Glassmorphism Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the bot's web dashboard from Bootstrap 5 to a custom Tailwind CSS-based Glassmorphism design, enhancing the immersive Call of Cthulhu atmosphere.

**Architecture:**
- **Framework:** Tailwind CSS (via CDN for Phase 8 development).
- **Core Layout:** New `base_glass.html` for parallel coexistence.
- **Components:** Jinja2 macros for reusable "Glass" UI elements.
- **Migration:** Incremental, page-by-page refactoring.

**Tech Stack:** Tailwind CSS, Jinja2, Quart, JavaScript.

---

### Task 1: Infrastructure & Core Shell

**Files:**
- Create: `dashboard/templates/base_glass.html`
- Create: `dashboard/static/css/glass.css`

- [ ] **Step 1: Set up Tailwind CDN and custom config in base_glass.html**
Define the Eldritch color palette and glass utility classes.
- [ ] **Step 2: Implement the Abyssal Gradient background and glass navbar**
- [ ] **Step 3: Create the base layout structure (Main content area, footer)**
- [ ] **Step 4: Commit**
```bash
git add dashboard/templates/base_glass.html dashboard/static/css/glass.css
git commit -m "feat: add base_glass infrastructure and core layout"
```

### Task 2: Glass Component Library

**Files:**
- Create: `dashboard/templates/includes/glass_components.html`

- [ ] **Step 1: Implement glass_card macro**
Parameters: title, footer, padding, extra_classes.
- [ ] **Step 2: Implement glass_button and glass_input macros**
- [ ] **Step 3: Implement glass_modal macro (Vanilla JS)**
- [ ] **Step 4: Commit**
```bash
git add dashboard/templates/includes/glass_components.html
git commit -m "feat: implement glass component library macros"
```

### Task 3: Landing Page Refactor (index.html)

**Files:**
- Modify: `dashboard/templates/index.html`

- [ ] **Step 1: Switch index.html to inherit from base_glass.html**
- [ ] **Step 2: Refactor hero section and bot status cards using Glass components**
- [ ] **Step 3: Update navigation links to point to other migrated pages (when ready)**
- [ ] **Step 4: Commit**
```bash
git add dashboard/templates/index.html
git commit -m "refactor: migrate landing page to Glassmorphism"
```

### Task 4: Character Core Refactor

**Files:**
- Modify: `dashboard/templates/list_characters.html`
- Modify: `dashboard/templates/render_character.html`

- [ ] **Step 1: Refactor character list into a grid of interactive glass cards**
- [ ] **Step 2: Redesign the character sheet (render_character) with Glass tabs and stats**
- [ ] **Step 3: Ensure responsive layout for mobile character viewing**
- [ ] **Step 4: Commit**
```bash
git add dashboard/templates/list_characters.html dashboard/templates/render_character.html
git commit -m "refactor: migrate character core to Glassmorphism"
```

### Task 5: Knowledge Base Refactor (Codex)

**Files:**
- Modify: `dashboard/templates/monsters.html`
- Modify: `dashboard/templates/render_monster.html`
- Modify: `dashboard/templates/spells.html` (and others)

- [ ] **Step 1: Refactor codex search results into glass lists/cards**
- [ ] **Step 2: Apply glass styling to monster and spell render templates**
- [ ] **Step 3: Verify image integration and eldritch typography**
- [ ] **Step 4: Commit**
```bash
git add dashboard/templates/monsters.html dashboard/templates/render_monster.html dashboard/templates/spells.html
git commit -m "refactor: migrate knowledge base to Glassmorphism"
```

### Task 6: Final Polish & Switch

**Files:**
- Modify: `dashboard/app.py`
- Modify: `dashboard/templates/base.html` (Optional: full replacement)

- [ ] **Step 1: Add a global theme switch to app.py (default to Glass)**
- [ ] **Step 2: Final audit of 40+ remaining admin pages (CSS bridge logic)**
- [ ] **Step 3: Final end-to-end verification of responsiveness and performance**
- [ ] **Step 4: Commit**
```bash
git add dashboard/app.py
git commit -m "feat: finalize frontend overhaul and set Glass as default theme"
```
