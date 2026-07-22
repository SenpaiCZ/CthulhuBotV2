# Update Rollback System — Design

Date: 2026-07-22
Status: Approved by user, ready for implementation planning

## Goal

Let the bot recover from a bad `/updatebot` run: an owner can manually restore a previous
backup (Discord command or dashboard button), and the bot automatically detects when a fresh
update fails to start correctly and reverts to the last known-good backup on its own, without
requiring a human to notice first.

## Why

`updater.py` already takes a full pre-update code backup (`create_backup()`, into `backups/`)
before every `/updatebot` run, and the dashboard (`dashboard/blueprints/backup.py`, `/admin/backup`)
already lists/downloads/deletes those zips. But nothing can actually apply one back onto the
running bot, and nothing detects "the update broke the bot" at all — today, a bad update just
leaves the owner to notice the bot is down and fix it by hand.

## Non-Goals

- Rollback restores code only, using the exact same file scope the existing backup/update
  machinery already respects (`data/`, `infodata/`, `venv`, `cookies`, `config.json`, etc. are
  already `PROTECTED_DIRS`/`PROTECTED_FILES`/`BACKUP_EXCLUDE_DIRS` in `updater.py` and are never
  touched by any code path this design adds). It does **not** revert `pip`-installed dependency
  versions — no dependency-version snapshot exists today, and reliably reverting packages is a
  much bigger problem than this feature is scoped to solve. If a bad update also bumped a
  dependency, rollback restores the old code but leaves the new package installed.
- The plain `/restart` command (`restarter.py`, e.g. for picking up a config change with no code
  update) is untouched — no backup exists before a plain restart, so there's nothing to roll back
  to, and this feature only wires into the `/updatebot` → `updater.py` path.
- No backup retention/rotation limits — backups already accumulate forever today; unchanged.
- **Acknowledged, unmitigated risk:** rollback never touches `data/`, so restored older code
  reads whatever `data/` currently contains — which may have been written/shaped by the *newer*
  code the rollback just undid. If a bad update had also changed a data file's structure (not
  just its logic), the restored older code could misinterpret the newer-shaped file. This is not
  a new risk this feature introduces — it's the same risk as manually checking out an older git
  commit while keeping the same data directory — but it's real, not something rollback can detect
  or fix, and is called out here rather than implied away.

## Current Behavior (for reference)

- `updater.py`'s `create_backup()` zips the whole tree (excluding `venv`, `.git`, `infodata`,
  `data`, `cookies`, etc.) into `backups/backup_<timestamp>.zip` before every update.
- `updater.py`'s `extract_and_apply()` downloads the GitHub zip, then does two things: `sync_files()`
  deletes obsolete files (anything in the current tree not present in the new source, skipping
  `PROTECTED_DIRS`), then a copy loop overwrites/creates files from the new source (skipping
  `PROTECTED_FILES` and `PROTECTED_DIRS`, with a special case for self-updating `updater.py` via
  `update_self_in_place()`).
- `updater.py`'s `restart_bot(detached=True)` fires-and-forgets: launches `bot.py` and immediately
  `sys.exit(0)`s — nothing observes whether the new process actually comes up healthy.
- `commands/updatebot.py`'s `UpdateBotView._run_updater()` spawns `updater.py <pid> [--update-infodata]`
  detached, then `await self.bot.close()`. `updater.py`'s `wait_for_pid()` blocks until that PID is
  gone before touching any files — so file operations never race a still-running bot process.
- `dashboard/blueprints/backup.py` has `get_system_backups()` (lists `backups/*.zip` by
  name/size/created, sorted newest-first) backing `/api/backup/files`, `/api/backup/delete`,
  `/admin/backup/download/<filename>` — list/delete/download, no restore.
- `bot.py`'s `on_ready` (bot.py:31) is the natural "fully started" signal — it only fires after
  Discord login succeeds and `load()` (cog loading) has already run in `main()`. It already
  resolves the bot owner (handling `discord.Team` ownership) to DM a startup-issues report when
  `bot.failed_extensions` is non-empty.

## Design

This is split into two phases sharing this one spec: **Phase A** (manual restore — useful and
shippable standalone) and **Phase B** (automatic detection, built directly on Phase A's restore
primitive). See Rollout/Risk for why.

### 1. Shared restore primitive (`updater.py`)

Factor the existing "sync obsolete files, then copy/overwrite from a source tree" logic (today
inlined in `extract_and_apply()`) into a reusable function both the update path and a new restore
path call:

```python
def apply_source_to_tree(source_root: str):
    """Sync + copy source_root's contents onto the current directory tree, respecting
    PROTECTED_DIRS/PROTECTED_FILES exactly as before."""
    sync_files(source_root, ".")

    for root, dirs, files in os.walk(source_root):
        rel_path = os.path.relpath(root, source_root)
        dest_dir = os.path.join(".", rel_path)

        if rel_path == ".":
            dirs[:] = [d for d in dirs if d not in PROTECTED_DIRS]

        if rel_path != "." and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)

        for file in files:
            src_file = os.path.join(root, file)
            dest_file = os.path.join(dest_dir, file)

            if rel_path == "." and file in PROTECTED_FILES:
                continue
            if rel_path == "." and file == "updater.py":
                update_self_in_place(src_file, dest_file)
                continue

            try:
                shutil.copy2(src_file, dest_file)
            except Exception as e:
                log(f"Failed to copy {file}: {e}")
```

`extract_and_apply()` shrinks to: extract the GitHub zip, resolve `extracted_root = EXTRACT_DIR/<entries[0]>`
(unchanged — GitHub zips have one top-level folder), call `apply_source_to_tree(extracted_root)`.

A new `restore_from_backup(backup_zip_path: str) -> bool`:

```python
def restore_from_backup(backup_zip_path: str) -> bool:
    if not os.path.exists(backup_zip_path):
        log(f"Backup file not found: {backup_zip_path}")
        return False

    log("Snapshotting current state before restore...")
    create_backup()  # so the restore itself is always reversible too

    restore_dir = "restore_extract_temp"
    try:
        with zipfile.ZipFile(backup_zip_path, 'r') as zip_ref:
            zip_ref.extractall(restore_dir)
        log(f"Applying backup contents from {backup_zip_path}...")
        apply_source_to_tree(restore_dir)  # backup zips have no extra top-level folder
        log("Restore applied successfully.")
        return True
    except Exception as e:
        log(f"Restore failed: {e}")
        return False
    finally:
        if os.path.exists(restore_dir):
            try:
                shutil.rmtree(restore_dir)
            except Exception:
                pass
```

Note the different zip layout: `create_backup()` zips `temp_backup_dir`'s *contents* directly at
the archive root (via `shutil.make_archive`), unlike the GitHub download which has one extra
top-level folder — `restore_from_backup` passes `restore_dir` itself to `apply_source_to_tree`,
not a subfolder, matching that layout. Every file operation inside `apply_source_to_tree` already
respects `PROTECTED_DIRS`/`PROTECTED_FILES` identically regardless of caller, so `data/`,
`infodata/`, `config.json`, etc. are exactly as untouched during a restore as during a normal
update.

`get_system_backups()` moves from `dashboard/blueprints/backup.py` into a new small root-level
module, `backup_utils.py` (pure function, no side effects — same shape as the existing
`restarter.py`/`updater.py` root-level shared scripts), so both the dashboard blueprint and the
new Discord command can list backups without an awkward `commands/` → `dashboard/blueprints/`
import (or importing script-shaped `updater.py`, which has an import-time `signal.signal(...)`
call that shouldn't run inside the main bot process). `dashboard/blueprints/backup.py` becomes
`from backup_utils import get_system_backups` — a one-line, behavior-preserving change.

### 2. Health signal + rollback notice (`bot.py`)

`on_ready` unconditionally writes a marker file the moment it fires — regardless of whether any
extensions failed to load (a bot with a broken cog still reaches `on_ready` and is otherwise
running; that's a separate, milder problem the existing `failed_extensions` DM already reports,
not a "the update broke the bot" condition). It also checks for a plain-text notice file
`write_status_notice()` (section 3) may have left behind, DMing its contents to the owner and
deleting it — reusing the exact owner-resolution logic (including `discord.Team` handling)
`on_ready` already has inline for the `failed_extensions` report, factored out so both blocks
share it instead of duplicating the Team-ownership branch:

```python
UPDATE_HEALTH_MARKER = "update_health.marker"  # must match updater.py's copy of this filename
ROLLBACK_NOTICE_FILE = "rollback_notice.txt"   # must match updater.py's copy of this filename

async def _get_owner():
    """Resolve the bot owner (handling Team ownership), or None if unavailable."""
    try:
        app_info = await bot.application_info()
        owner = app_info.owner
        if isinstance(owner, discord.Team):
            owner = getattr(owner, 'owner', None)
            if isinstance(owner, int):
                owner = await bot.fetch_user(owner)
        return owner if owner and hasattr(owner, 'send') else None
    except Exception as e:
        print(f"Failed to resolve bot owner: {e}")
        return None

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

    try:
        open(UPDATE_HEALTH_MARKER, "w").close()
    except Exception as e:
        print(f"Failed to write health marker: {e}")

    if hasattr(bot, 'failed_extensions') and bot.failed_extensions:
        owner = await _get_owner()
        if owner:
            # ...existing error_message building + await owner.send(...) + clearing
            # bot.failed_extensions, unchanged except now calling _get_owner() instead of
            # the inline app_info/Team-resolution block it used before.
            ...

    if os.path.exists(ROLLBACK_NOTICE_FILE):
        try:
            with open(ROLLBACK_NOTICE_FILE, "r", encoding="utf-8") as f:
                message = f.read()
            owner = await _get_owner()
            if owner:
                await owner.send(message)
        except Exception as e:
            print(f"Failed to send rollback notice: {e}")
        finally:
            try:
                os.remove(ROLLBACK_NOTICE_FILE)
            except Exception:
                pass
```

`updater.py`'s `PROTECTED_FILES` gains `"update_health.marker"` and `"rollback_notice.txt"` so
update/restore file operations never touch them.

### 3. Supervised launch + auto-rollback (`updater.py`) — Phase B

Replace the current fire-and-forget `restart_bot(detached=True)` with a function that launches
`bot.py` and watches for either the health marker or an early exit, **and forcibly terminates a
stuck-but-still-running process on timeout** — this is the fix for the data-integrity gap caught
during design review: without it, a timed-out-but-alive process could still be running when a
restore starts rewriting code files under it, or worse, could still be connected to Discord and
writing `data/` at the same moment a second bot process comes up, corrupting player data via a
lost-write race. Forcibly terminating on timeout guarantees exactly one bot process is ever alive
at a time, the same invariant `wait_for_pid()` already provides for the forward-update path.

```python
def reset_health_marker():
    try:
        if os.path.exists(UPDATE_HEALTH_MARKER):
            os.remove(UPDATE_HEALTH_MARKER)
    except Exception:
        pass

def launch_and_supervise(timeout=60) -> bool:
    """Launch bot.py; return True only if it signals healthy (marker appears) while still
    alive within `timeout` seconds. On crash or timeout, returns False — and on timeout
    specifically, forcibly terminates the still-running process first, so at most one bot
    process is ever alive."""
    reset_health_marker()
    log("Launching bot.py...")
    cmd = [sys.executable, "bot.py"]
    if platform.system() == "Windows":
        proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        proc = subprocess.Popen(cmd, close_fds=True)

    start = time.time()
    while time.time() - start < timeout:
        if proc.poll() is not None:
            log(f"Bot process exited early (code {proc.returncode}) before becoming healthy.")
            return False
        if os.path.exists(UPDATE_HEALTH_MARKER):
            log("Bot signaled healthy.")
            return True
        time.sleep(1)

    log(f"Bot did not become healthy within {timeout}s — terminating stuck process.")
    try:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception as e:
        log(f"Failed to terminate stuck process: {e}")
    return False
```

`find_latest_backup()` returns the most recent `backup_*.zip` in `BACKUP_DIR` by filename (the
`YYYYMMDD_HHMMSS` timestamp format is already lexicographically sortable, so no `stat()` calls are
needed) — this is unambiguous because `create_backup()` is the *only* thing that ever writes
`backup_*.zip` files into `BACKUP_DIR`, so "the latest one" is always "the one just taken before
this update run":

```python
def find_latest_backup() -> str | None:
    if not os.path.exists(BACKUP_DIR):
        return None
    zips = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".zip"))
    return os.path.join(BACKUP_DIR, zips[-1]) if zips else None
```

```python
def write_status_notice(message: str):
    try:
        with open(ROLLBACK_NOTICE_FILE, "w", encoding="utf-8") as f:
            f.write(message)
    except Exception as e:
        log(f"Failed to write status notice: {e}")
```

`ROLLBACK_NOTICE_FILE = "rollback_notice.txt"` (same literal filename as `bot.py`'s copy in
section 2 — this project's established convention for cross-process constants that can't be
imported directly, matching how `BACKUP_DIR = "backups"` already carries a "must match
`BACKUP_FOLDER` in dashboard/state.py" comment). `bot.py`'s `on_ready` reads and deletes it if
present, DMing the owner its contents (section 2).

Wired into the main update flow's `__main__` block, replacing the current unconditional
`restart_bot(detached=True)` call:

```python
healthy = launch_and_supervise()
if not healthy:
    log("Update produced an unhealthy bot — attempting automatic rollback...")
    latest_backup = find_latest_backup()
    if latest_backup and restore_from_backup(latest_backup):
        if launch_and_supervise():
            log("Automatic rollback succeeded.")
            write_status_notice(
                "⚠️ Your last update failed to start, so I automatically rolled back to the "
                "previous version."
            )
        else:
            log("CRITICAL: automatic rollback also failed to produce a healthy bot.")
            write_status_notice(
                "🚨 Your last update failed AND the automatic rollback also failed to start. "
                "Manual intervention needed — check the server directly."
            )
    else:
        log("CRITICAL: update failed and no usable backup was available to roll back to.")
        write_status_notice(
            "🚨 Your last update failed and I could not automatically roll back "
            "(no backup available or restore itself failed). Manual intervention needed."
        )
else:
    log("Update successful, bot is healthy.")
```

Exactly **one** automatic rollback attempt is ever made — if the rollback itself doesn't produce
a healthy bot, the loop stops there rather than trying again, so there is no possibility of an
infinite restart loop. If everything fails, the last state on disk is whatever the failed rollback
attempt left behind (not further modified), and the plain-text notice plus the log file are the
two ways a human finds out.

### 4. Manual restore surfaces — Phase A

**`updater.py` restore mode:** a new `--restore FILENAME` CLI argument branches the `__main__`
block into a separate flow: wait for the given PID, `restore_from_backup(...)`, then a single
`launch_and_supervise()` call — **without** chaining into a further automatic rollback if that
particular pick is also unhealthy (chaining would be surprising here: the owner explicitly chose
this backup, so if it doesn't fix things, that's reported plainly via `write_status_notice`, not
silently reverted again to something else). Dependencies are **not** reinstalled in this mode
(matches the Non-Goals: no dependency rollback).

**`backup_utils.py`** (new file): just `get_system_backups()`, moved from
`dashboard/blueprints/backup.py` unchanged (see section 1).

**Discord command** (`commands/rollback.py`, new file): `/rollback` (owner-only, same
`bot.is_owner()` check `/updatebot` already uses) shows a `discord.ui.Select` populated from
`get_system_backups()` (label = filename, description = size + created timestamp), capped at the
Discord select-menu limit of 25 options (in practice showing the most recent ~10-25 backups,
newest first — `get_system_backups()` already sorts that way). Picking one spawns
`updater.py <pid> --restore <filename>` (mirroring `UpdateBotView._run_updater`'s subprocess
pattern exactly) and closes the bot.

**Dashboard** (`dashboard/blueprints/backup.py` + `dashboard/templates/backup_dashboard.html`):
a new `/api/backup/restore` POST route, mirroring `_run_updater`'s spawn-then-`bot.close()`
pattern (this route runs inside the same process as the bot, per `bot.py`'s `main()` — Hypercorn
serves the dashboard as a background task in the same event loop, so `os.getpid()` here is the
bot's own PID, exactly as it is in `commands/updatebot.py`). A new "RESTORE" button in each
backup row's action group, next to the existing DOWNLOAD/DELETE buttons, guarded by the same
`confirm(...)` pattern the existing `deleteBackup()`/`banTrack()` functions already use.

## Testing

- `tests/test_updater.py` (new file — this repo has no test file for `updater.py` yet):
  `apply_source_to_tree()` correctly skips `PROTECTED_DIRS`/`PROTECTED_FILES` (build a fake source
  tree and a fake current tree in `tmp_path`, monkeypatch `PROTECTED_DIRS`/`PROTECTED_FILES` to
  known values, assert protected paths are untouched and everything else is synced/copied) and
  correctly special-cases `updater.py` self-update via `update_self_in_place`. `find_latest_backup()`
  picks the lexicographically-last `backup_*.zip` and ignores non-matching filenames. `restore_from_backup()`
  calls `create_backup()` before applying (mock both), returns `False` and doesn't raise when the
  zip is missing/corrupt, cleans up its temp extraction dir in both the success and failure paths.
  `launch_and_supervise()`: returns `True` when the marker file appears while the mocked process
  is still "alive" (`proc.poll()` returns `None`); returns `False` and does **not** call
  `terminate()` when the process exits early on its own; returns `False` **and does** call
  `terminate()` (then `kill()` if `wait()` times out) when neither the marker nor an exit happens
  before the timeout — this is the concurrency-safety property from section 3, the one most
  important to pin down with a test.
- `tests/test_backup_utils.py` (new file): `get_system_backups()` moved verbatim — same
  assertions the current inline version would need (lists `.zip` files with name/size/created,
  sorted newest-first, tolerates a missing `BACKUP_FOLDER`).
- `tests/test_blueprint_backup.py` (existing file — confirm exact name before extending): update
  the import for `get_system_backups()`'s new location; add coverage for the new
  `/api/backup/restore` route (spawns the expected `updater.py <pid> --restore <filename>` command,
  calls `app.bot.close()`, rejects a filename containing `..`/`/`/`\\` the same way
  `backup_delete_file` already does, 404s a nonexistent file).
- `tests/test_commands_rollback.py` (new file): `/rollback` rejects non-owners; with no backups
  available, responds with a clear "nothing to restore" message instead of an empty/broken select;
  the select's callback spawns the expected `updater.py <pid> --restore <filename>` command and
  closes the bot.
- `tests/test_bot_startup.py` or extend whatever (if any) test already covers `bot.py` (check
  before creating a new file): `on_ready` writes the health marker unconditionally, even when
  `failed_extensions` is empty; reads and deletes `rollback_notice.txt` and DMs its contents to the
  resolved owner when present; does nothing extra when absent.

## Rollout / Risk

- **Two-phase implementation**, matching this repo's existing precedent (the original
  maintainability-refactor spec had 6 phases, each its own plan): **Phase A** (sections 1 and 4 —
  the shared restore primitive, manual Discord/dashboard restore) ships first and is independently
  useful — an owner can already recover from a bad update by hand, just not automatically yet.
  **Phase B** (sections 2 and 3 — the health marker and the supervised auto-rollback) builds
  directly on Phase A's `restore_from_backup()`/`find_latest_backup()` and ships second.
- No data-layer changes in either phase — `data/`, `infodata/`, `config.json`, `cookies/` are
  never read, written, or deleted by any code path this design adds, by construction (same
  protected-paths logic as the existing update path, not a new promise to keep separately).
- Exactly one automatic rollback attempt ever — no possibility of an infinite restart loop.
- The timeout-triggered forced termination (section 3) is the one genuinely new
  process-supervision behavior in this codebase; it's scoped narrowly to `updater.py`'s own
  `launch_and_supervise()` and doesn't change how `/restart`'s `restarter.py` behaves.
