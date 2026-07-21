# Contributing to CthulhuBotV2

Internal conventions for extending this codebase. See `CLAUDE.md` for the module map and architecture overview — this file is the step-by-step "how do I add X" companion to it.

## Adding a new dashboard route

1. Find (or create) the matching `dashboard/blueprints/<feature>.py` file — one file per feature area (e.g. all karma routes live in `karma.py`, all giveaway routes in `giveaway.py`).
2. Define the route on that blueprint's `Blueprint` object, not on `app`:
   ```python
   from quart import Blueprint
   my_feature_bp = Blueprint('my_feature', __name__)

   @my_feature_bp.route('/admin/my_feature')
   async def admin_my_feature():
       ...
   ```
   `dashboard/app.py` never defines a route directly — if you're about to write `@app.route(...)` there, put it on a blueprint instead.
3. If the route needs shared mutable state (`guild_mixers`, `server_volumes`) or a folder-path constant (`IMAGES_FOLDER`, `BACKUP_FOLDER`, etc.), import it from `dashboard.state` — never redefine or re-derive it locally.
4. If this is a brand-new blueprint file (not an addition to an existing one), register it in `dashboard/app.py` near the bottom, alongside the other `from dashboard.blueprints.<x> import <x>_bp` / `app.register_blueprint(<x>_bp)` pairs.
5. If you're *moving* an existing route rather than adding a new one, update every `url_for('old_endpoint_name')` reference across the whole codebase (templates included) — Quart namespaces every blueprint endpoint as `<blueprint>.<name>`, even if the route was declared with an explicit `endpoint=` kwarg. A stale `url_for()` call raises `BuildError` at *request* time, not at import time, so it won't be caught by simply starting the app or importing the module.
6. Add or extend `tests/test_blueprint_<feature>.py` — see `CLAUDE.md`'s Testing section for the `login(client)` / `Origin` header / `DATA_FOLDER` isolation conventions that dashboard route tests need.

## Adding a new command, and when to split its UI classes out

1. If the Cog is small and self-contained, keep everything — the Cog class plus any `discord.ui.View`/`Modal`/`Select` classes it uses — in one `commands/<name>.py` file. Don't pre-split a file that doesn't need it yet.
2. Split UI classes into a sibling `commands/_<name>_<topic>.py` companion file once the parent Cog file has grown large enough that its own logic is hard to find among the UI class definitions (a few hundred lines is a reasonable trigger to reconsider, not a hard threshold). The leading underscore marks the file as a shared/internal module, **not** a standalone Cog.
3. A companion file must never define `async def setup(bot)` — `bot.py` tries to load every `.py` file directly under `commands/` as a discord.py extension, and a companion file with its own `setup()` will either fail to load or double-register commands.
4. In the companion file, import only what its own classes need — resist importing the whole parent module back in "just in case."
5. In the parent Cog file, import each companion class *by name* wherever the Cog constructs one directly: `from commands._newinvestigator_stats import CoreStatSelectView`. A class that is only ever constructed by another class *within the same companion file* (e.g. a `Select` a sibling `View` builds internally) doesn't need a Cog-level import — adding one anyway is dead-import clutter that the next reader has to figure out is safe to ignore.
6. Before finishing a split, grep the **whole repo**, not just `commands/`, for the class names you moved — a UI class is sometimes imported from a companion file by a *different* Cog than the one it was split out of (e.g. `commands/combat.py` and `commands/_mychar_roll.py` both import `RollResultView` from `commands/_roll_views.py`, not from `commands/roll.py`). Missing one of these is a `NameError` at runtime, not at import time, so it survives a casual smoke test.
7. Add or extend `tests/test_commands_<name>_<topic>.py` (companion file) and/or `tests/test_commands_<name>.py` (the Cog itself) — see `CLAUDE.md`'s Testing section for the discord.py 2.7.1 UI-construction conventions (`children[0]` ordering, `_values` for Selects, `.component._value` for `Label`-wrapped Modal fields).

## When *not* to split a file

Don't split a file just because it's long. Split when either is true:
- A reviewer could reasonably approve one part of the file while rejecting the other — i.e. the pieces are independently testable and independently changeable.
- The file mixes genuinely distinct responsibilities that different future changes will each touch on their own (a dashboard blueprint mixing two unrelated feature areas; a Cog file mixing command logic for two unrelated game systems).

A single handler or Cog method with a long, straight-line implementation is not by itself a reason to split. Three unrelated features awkwardly sharing one file because nobody moved them apart yet, is.
