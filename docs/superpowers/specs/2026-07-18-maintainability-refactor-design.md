# CthulhuBotV2 Maintainability Refactor — Design

Date: 2026-07-18
Status: Approved by user, ready for phased implementation planning

## Goal

Improve maintainability of CthulhuBotV2 across the whole codebase with **zero functional
regressions**. The bot's behavior (slash commands, dashboard routes, data persistence) must be
identical before and after each phase. Each phase is an independent sub-project with its own
implementation plan, executed in order, verified before moving to the next.

## Why

- `dashboard/app.py` is 4577 lines / 156 routes in a single file — hard to navigate, high merge-
  conflict risk, hard to reason about which routes touch which shared state.
- Several `commands/` cogs exceed 700–1500 lines (`newinvestigator.py`, `roll.py`, `codex.py`,
  `_mychar_view.py`, `karma.py`, `journal.py`), mixing UI, game logic, and persistence concerns.
- Only 6 test files exist for a ~25.7k line Python codebase; `commands/` has zero test coverage.
  Refactoring without a safety net risks silently breaking game logic (combat, chase, character
  creation) that players depend on.

## Non-Goals

- No behavior changes, new features, or UI redesign (UI unification already just landed).
- No database/storage format migration — `data/`, `infodata/`, `gamedata/` JSON layout stays as-is
  unless a phase explicitly says otherwise (none do).
- No dependency upgrades unless required to fix something the refactor touches.

## Guiding Principles

- Every phase must leave the bot in a runnable, fully-functional state — no half-migrated phases
  left in the tree between sessions.
- Prefer moving code over rewriting it during structural phases (0–3). Behavior-preserving first,
  cleanup-in-place second.
- Each extracted module must be independently understandable: what it does, how it's used, what it
  depends on — per existing `_foo.py` shared-module convention in `commands/`.
- Tests added in Phase 0 act as the regression net for Phases 1–3; if a phase touches code with no
  test yet, add a characterization test for that code path first.

---

## Phase 0 — Safety Net (characterization tests)

Add tests that lock in *current* behavior before anything moves, focused on the highest-risk,
currently-untested surfaces:

- Dashboard: smoke-test that every registered route in `app.py` responds (not 500) for at least
  one representative request, using the existing `tests/test_dashboard_routes.py` as a base.
- Game logic: `commands/combat.py`, `commands/chase.py`, `commands/roll.py` skill-check resolution,
  `commands/newinvestigator.py` wizard step transitions — cover the core state-machine paths.
- `loadnsave.py`: round-trip tests (save → load → same data) for each entity type already covered
  by `load_X`/`save_X` pairs.

Output: test suite green, no production code changes. This phase gates all later phases — a later
phase should not proceed past its own implementation until its touched surface has coverage here
or added inline as part of that phase.

## Phase 1 — Dashboard Decomposition (`dashboard/app.py` → Blueprints)

Split the single file by existing route grouping (89 `/api`, 22 `/admin`, 21 `/render`, plus static/
misc) into Quart Blueprints:

- `dashboard/blueprints/auth.py`
- `dashboard/blueprints/admin.py`
- `dashboard/blueprints/render.py`
- `dashboard/blueprints/api_characters.py`, `api_music.py`, `api_files.py`, etc. — split `/api`
  further by resource, not left as one 89-route blueprint.
- Route handlers stay thin; business logic currently inlined in routes moves to
  `dashboard/services/*.py` modules.
- Shared mutable state (`guild_mixers`, `server_volumes`) currently shared with
  `commands/music.py` moves to a dedicated `dashboard/shared_state.py` that both sides import, to
  remove the app.py ↔ music.py coupling and avoid import cycles.
- `app.py` becomes a thin composition root: create app, register blueprints, register shared
  state, start hypercorn.

Target: no single dashboard file over ~500 lines; every blueprint has one clear domain.

## Phase 2 — `commands/` Cog Decomposition & Consistency

For each oversized cog, split UI components (Views/Modals/Selects) and pure helper logic out into
`_foo.py`-style shared modules, following the convention already established
(`_mychar_view.py`, `_backstory_common.py`, etc.):

- `newinvestigator.py` (1516 lines) — wizard steps/modals per era likely split further.
- `roll.py` (1154 lines) — separate dice-parsing/roll-resolution logic from the command surface.
- `codex.py` (1112 lines) — already has `_codex_embeds.py`; audit for more extractable pieces.
- `_mychar_view.py` (1084 lines), `karma.py` (880), `journal.py` (785) — same treatment.
- Audit for duplicated logic across cogs (e.g. repeated `session_success`/`MockContext` usage
  patterns) and consolidate into `support_functions.py` where genuinely shared.

Target: no cog file over ~600 lines without a clear single-responsibility reason; duplicated
patterns centralized.

## Phase 3 — `loadnsave.py` Audit

- Grep the full codebase for direct `json.load`/`open(...)` on files under `data/`, `infodata/`,
  `gamedata/` outside of `loadnsave.py` — any hit is a bypass of the caching/backup-on-error
  pattern and gets routed through `load_X`/`save_X` instead.
- If `loadnsave.py` has grown unwieldy after Phase 1–2 touch it indirectly, consider splitting by
  data domain (character data vs. server/session data vs. static reference), keeping the existing
  `load_X()`/`save_X()` + `_X_CACHE` pattern per file.

## Phase 4 — Test Coverage Expansion

- Add unit tests for every module extracted in Phases 1–2 (blueprints, services, cog helper
  modules) — these didn't exist as standalone units before, so they get first-class tests now.
- Expand regression coverage on the game-logic state machines identified in Phase 0 beyond smoke
  level (edge cases: combat death/unconsciousness, chase escape/capture, wizard back-navigation).

## Phase 5 — Conventions & Documentation

- Update `CLAUDE.md` with the new module map (blueprints, services, shared-state module).
- Add a short internal styleguide note (in `CLAUDE.md` or a new `docs/CONTRIBUTING.md`) codifying
  the `_foo.py` shared-module convention and the blueprint/service split, so future additions follow
  the same shape.

---

## Execution Model

Each phase above becomes its own implementation plan (via the writing-plans skill), executed and
verified independently before the next phase starts:

1. Phase 0 plan → implement → verify (tests green, bot still runs).
2. Phase 1 plan → implement → verify (dashboard still serves all routes identically).
3. Phase 2 plan → implement → verify (all slash commands still work).
4. Phase 3 plan → implement → verify.
5. Phase 4 plan → implement → verify.
6. Phase 5 plan → implement → verify.

If a phase reveals the next phase's scope needs adjusting (e.g. Phase 1 uncovers additional shared
state), that adjustment is folded into that next phase's plan, not retrofitted silently.

## Testing Strategy

- `pytest` + `pytest-asyncio` (already a dependency) for all new tests.
- Dashboard route tests use Quart's test client against the blueprint-registered app.
- No manual/browser verification required for backend-only phases (0, 2, 3, 4); Phase 1 dashboard
  routes get at least a `pytest` smoke pass plus a manual spot-check of the dashboard in a browser
  before sign-off, per project convention for UI-adjacent changes.

## Rollout / Risk

- Each phase lands as its own set of commits (not one giant refactor commit), so any regression is
  bisectable to a single phase.
- Bot must remain runnable (`python bot.py`) after every phase — no phase leaves the tree broken
  between sessions.
