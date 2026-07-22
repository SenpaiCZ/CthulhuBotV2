# Update Rollback Phase A — Manual Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an owner manually restore the bot from a previous pre-update backup, via a new Discord `/rollback` command or a new dashboard button, with a clear "did the restore actually produce a healthy bot?" confirmation — building the primitives Phase B's automatic rollback will reuse.

**Architecture:** `updater.py` gains a shared `apply_source_to_tree()` (factored out of its existing `extract_and_apply()`), a new `restore_from_backup()` built on it, and a new `launch_and_supervise()` that replaces today's fire-and-forget restart with a health-marker-based wait (the marker is written by a new `bot.py` `on_ready` addition). A new `backup_utils.py` centralizes backup listing (moved out of the dashboard blueprint) so both the new Discord command and the existing dashboard route can list backups without an awkward cross-import. `updater.py`'s `__main__` block gains a `--restore FILENAME` mode, factored into a testable `run_restore_mode()` function alongside a `run_update_mode()` (the existing normal-update path, also factored out for the same reason).

**Tech Stack:** Python 3.11+, discord.py 2.7.1, Quart, pytest + pytest-asyncio.

## Global Constraints

- Restore never touches `data/`, `infodata/`, `config.json`, `cookies/`, `venv/`, etc. — it reuses the exact same `PROTECTED_DIRS`/`PROTECTED_FILES`/`sync_files()` logic the existing update path already respects, via the shared `apply_source_to_tree()`.
- Exactly one supervised launch attempt per restore in this phase — no auto-rollback chaining (see design spec's Phase A/B split): if a manually-chosen backup doesn't produce a healthy bot, that's reported via a status notice, not silently reverted again.
- `restore_from_backup()` always snapshots the current state via `create_backup()` before applying anything, unconditionally — a restore is always itself reversible.
- `launch_and_supervise()` must forcibly terminate a still-running-but-unhealthy process on timeout before returning `False` — this is the fix for the double-write data-race risk found during design review; a test must pin this down explicitly.
- `get_system_backups()` takes its folder path as an explicit parameter (not a module-level global) — this is a deliberate refinement over the design spec's original sketch, made during planning: the existing `dashboard/blueprints/backup.py` test suite patches `dashboard.blueprints.backup.BACKUP_FOLDER` (a by-value import), which would silently stop affecting `get_system_backups()`'s behavior once it moved to a different module if it read a module-level global instead of a parameter — the explicit-parameter form sidesteps that cross-module-patching pitfall entirely per `CLAUDE.md`'s testing conventions on patch targets.
- `updater.py`'s `__main__` block logic is factored into `run_restore_mode(args)` and `run_update_mode(args)` — a deliberate refinement over the design spec (which described this as inline `__main__` content): this repo has no existing test coverage for `updater.py`'s `__main__` block, and testing it as literal top-level script code (vs. calling named functions with mocked collaborators) isn't practical without spawning real subprocesses or hitting the real network. Extracting these as named functions matches this session's established pattern (e.g. `commands/music.py`'s `play()` orchestrating smaller testable helpers).
- discord.py 2.7.1 UI-test conventions from `CLAUDE.md`'s Testing section apply to `commands/rollback.py`'s `BackupSelect`/`BackupSelectView`: mock only the `interaction.response`/`.followup` methods a test exercises; simulate a Select choice with `select._values = [...]`.
- Dashboard route tests use Quart's test client against the real blueprint-registered `app` from `dashboard.app`, with `login(client)` + an `Origin` header, per `CLAUDE.md`'s Testing section.

---

### Task 1: `apply_source_to_tree()` + `restore_from_backup()`

**Files:**
- Modify: `updater.py`
- Create: `tests/test_updater.py`

**Interfaces:**
- Consumes: nothing from other tasks — this is the foundation layer.
- Produces: `apply_source_to_tree(source_root: str) -> None` and `restore_from_backup(backup_zip_path: str) -> bool`. Consumed by Task 5 (`run_restore_mode`) and, later, Phase B's automatic-rollback orchestration.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_updater.py`:

```python
import os
import zipfile
from unittest.mock import patch

import pytest

import updater


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestApplySourceToTree:
    def test_copies_new_files_and_deletes_obsolete_ones(self, tmp_path):
        os.makedirs("existing_dir")
        with open("existing_dir/obsolete.txt", "w") as f:
            f.write("old")
        with open("keep.txt", "w") as f:
            f.write("kept")

        source = tmp_path / "source"
        source.mkdir()
        (source / "new.txt").write_text("new content")
        (source / "keep.txt").write_text("updated content")

        updater.apply_source_to_tree(str(source))

        assert not os.path.exists("existing_dir/obsolete.txt")
        assert os.path.exists("new.txt")
        with open("keep.txt") as f:
            assert f.read() == "updated content"

    def test_skips_protected_dirs_and_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(updater, "PROTECTED_DIRS", {"data"})
        monkeypatch.setattr(updater, "PROTECTED_FILES", {"config.json"})

        os.makedirs("data")
        with open("data/player_stats.json", "w") as f:
            f.write("real player data")
        with open("config.json", "w") as f:
            f.write("real config")

        source = tmp_path / "source"
        source.mkdir()
        (source / "config.json").write_text("attacker config")
        # source has no data/ dir at all -- if data/ weren't protected, sync_files would
        # delete data/player_stats.json since it's "obsolete" (missing from source).

        updater.apply_source_to_tree(str(source))

        with open("data/player_stats.json") as f:
            assert f.read() == "real player data"
        with open("config.json") as f:
            assert f.read() == "real config"

    def test_self_updates_updater_py_via_rename(self, tmp_path, monkeypatch):
        monkeypatch.setattr(updater, "PROTECTED_DIRS", set())
        monkeypatch.setattr(updater, "PROTECTED_FILES", set())

        with open("updater.py", "w") as f:
            f.write("old updater code")

        source = tmp_path / "source"
        source.mkdir()
        (source / "updater.py").write_text("new updater code")

        updater.apply_source_to_tree(str(source))

        assert os.path.exists("updater.py.old")
        with open("updater.py.old") as f:
            assert f.read() == "old updater code"
        with open("updater.py") as f:
            assert f.read() == "new updater code"


class TestRestoreFromBackup:
    def test_returns_false_when_backup_file_missing(self, tmp_path):
        result = updater.restore_from_backup(str(tmp_path / "nonexistent.zip"))
        assert result is False

    def test_snapshots_current_state_before_restoring(self, tmp_path):
        with open("live_file.txt", "w") as f:
            f.write("live content")

        backup_zip = tmp_path / "backup_20260101_000000.zip"
        with zipfile.ZipFile(backup_zip, 'w') as zf:
            zf.writestr("restored_file.txt", "restored content")

        with patch.object(updater, "create_backup") as mock_create_backup:
            result = updater.restore_from_backup(str(backup_zip))

        assert result is True
        mock_create_backup.assert_called_once()
        with open("restored_file.txt") as f:
            assert f.read() == "restored content"

    def test_cleans_up_temp_extraction_dir_on_success_and_failure(self, tmp_path):
        backup_zip = tmp_path / "backup_20260101_000000.zip"
        with zipfile.ZipFile(backup_zip, 'w') as zf:
            zf.writestr("file.txt", "content")

        with patch.object(updater, "create_backup"):
            updater.restore_from_backup(str(backup_zip))
        assert not os.path.exists("restore_extract_temp")

        bad_zip = tmp_path / "corrupt.zip"
        bad_zip.write_bytes(b"not a real zip")
        with patch.object(updater, "create_backup"):
            result = updater.restore_from_backup(str(bad_zip))
        assert result is False
        assert not os.path.exists("restore_extract_temp")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_updater.py -v`
Expected: `AttributeError: module 'updater' has no attribute 'apply_source_to_tree'` (and similarly for `restore_from_backup`).

- [ ] **Step 3: Write minimal implementation**

In `updater.py`, replace the existing `extract_and_apply()` function (updater.py:201-260) with:

```python
def apply_source_to_tree(source_root: str):
    """Sync + copy source_root's contents onto the current directory tree, respecting
    PROTECTED_DIRS/PROTECTED_FILES exactly as extract_and_apply() always did."""
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


def extract_and_apply():
    log("Extracting update...")
    try:
        with zipfile.ZipFile(ZIP_FILENAME, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)

        entries = os.listdir(EXTRACT_DIR)
        if not entries:
            raise Exception("Empty zip file")

        extracted_root = os.path.join(EXTRACT_DIR, entries[0])

        log(f"Applying updates from {extracted_root}...")
        apply_source_to_tree(extracted_root)

        log("Update applied successfully.")

    except Exception as e:
        log(f"Extraction failed: {e}")
        sys.exit(1)
    finally:
        if os.path.exists(EXTRACT_DIR):
            try:
                shutil.rmtree(EXTRACT_DIR)
            except:
                pass
        if os.path.exists(ZIP_FILENAME):
            try:
                os.remove(ZIP_FILENAME)
            except:
                pass


def restore_from_backup(backup_zip_path: str) -> bool:
    """Apply a specific backup zip onto the current tree, after snapshotting the current
    (possibly-bad) state so the restore itself is always reversible too."""
    if not os.path.exists(backup_zip_path):
        log(f"Backup file not found: {backup_zip_path}")
        return False

    log("Snapshotting current state before restore...")
    create_backup()

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_updater.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add updater.py tests/test_updater.py
git commit -m "refactor: extract apply_source_to_tree from extract_and_apply, add restore_from_backup"
```

---

### Task 2: `backup_utils.py`

**Files:**
- Create: `backup_utils.py`
- Modify: `dashboard/blueprints/backup.py`
- Modify: `tests/test_blueprint_backup.py` (remove the two `get_system_backups`-specific tests, now covered in the new file below; route-level tests are unaffected)
- Create: `tests/test_backup_utils.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `get_system_backups(backup_folder: str) -> list[dict]` (each dict: `name`, `size`, `created`). Consumed by Task 6 (`commands/rollback.py`) and the existing `/api/backup/files` route.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_backup_utils.py`:

```python
import os
import zipfile

from backup_utils import get_system_backups


def make_zip(folder, name, content=b"data"):
    path = os.path.join(str(folder), name)
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr("file.txt", content)
    return path


def test_missing_folder_returns_empty_list(tmp_path):
    missing = tmp_path / "nope"
    assert get_system_backups(str(missing)) == []


def test_scans_folder_for_zip_files(tmp_path):
    make_zip(tmp_path, "direct.zip")
    files = get_system_backups(str(tmp_path))
    assert len(files) == 1
    assert files[0]["name"] == "direct.zip"
    assert files[0]["size"] > 0


def test_ignores_non_zip_files(tmp_path):
    make_zip(tmp_path, "backup.zip")
    (tmp_path / "notes.txt").write_text("not a backup")
    files = get_system_backups(str(tmp_path))
    assert len(files) == 1
    assert files[0]["name"] == "backup.zip"


def test_sorted_newest_first(tmp_path):
    older = make_zip(tmp_path, "old.zip")
    newer = make_zip(tmp_path, "new.zip")
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    files = get_system_backups(str(tmp_path))
    assert [f["name"] for f in files] == ["new.zip", "old.zip"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_backup_utils.py -v`
Expected: `ModuleNotFoundError: No module named 'backup_utils'`

- [ ] **Step 3: Write minimal implementation**

Create `backup_utils.py`:

```python
import os
import datetime


def get_system_backups(backup_folder: str) -> list[dict]:
    if not os.path.exists(backup_folder):
        return []

    files = []
    try:
        for f in os.listdir(backup_folder):
            if f.endswith('.zip'):
                full_path = os.path.join(backup_folder, f)
                stat = os.stat(full_path)
                files.append({
                    "name": f,
                    "size": stat.st_size,
                    "created": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
        files.sort(key=lambda x: x['created'], reverse=True)
    except Exception as e:
        print(f"Error scanning backups: {e}")

    return files
```

In `dashboard/blueprints/backup.py`, replace the existing `get_system_backups()` function definition (currently around lines 60-80, the `def get_system_backups(): ... return files` block) with an import at the top of the file — change:

```python
from dashboard.app import app, is_admin
from dashboard.state import BACKUP_FOLDER
from loadnsave import load_settings_async, save_settings
```

to:

```python
from dashboard.app import app, is_admin
from dashboard.state import BACKUP_FOLDER
from loadnsave import load_settings_async, save_settings
from backup_utils import get_system_backups
```

and delete the old `def get_system_backups(): ...` function body entirely (the `# --- System Backups (Physical Files) ---` comment above it can stay). Then change the `/api/backup/files` route from:

```python
@backup_bp.route('/api/backup/files')
async def backup_files_list():
    if not is_admin(): return "Unauthorized", 401
    return jsonify(get_system_backups())
```

to:

```python
@backup_bp.route('/api/backup/files')
async def backup_files_list():
    if not is_admin(): return "Unauthorized", 401
    return jsonify(get_system_backups(BACKUP_FOLDER))
```

In `tests/test_blueprint_backup.py`, delete these two tests (they move to `tests/test_backup_utils.py` above, already covering the same behavior):

```python
@pytest.mark.asyncio
async def test_get_system_backups_directly_scans_folder(isolated_backup_folder):
    make_zip(isolated_backup_folder, "direct.zip")
    files = backup.get_system_backups()
    assert len(files) == 1
    assert files[0]["name"] == "direct.zip"


def test_get_system_backups_missing_folder_returns_empty_list(tmp_path, monkeypatch):
    missing = tmp_path / "nope"
    monkeypatch.setattr(backup, "BACKUP_FOLDER", str(missing))
    assert backup.get_system_backups() == []
```

Every other test in that file is unaffected: `isolated_backup_folder` still patches `dashboard.blueprints.backup.BACKUP_FOLDER`, and the `/api/backup/files` route still reads that same patched attribute and now passes it explicitly to `get_system_backups(BACKUP_FOLDER)` — no cross-module patching gap.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_backup_utils.py tests/test_blueprint_backup.py -v`
Expected: all tests pass (4 new in `test_backup_utils.py`; `test_blueprint_backup.py` has 2 fewer tests than before but all remaining ones still pass).

- [ ] **Step 5: Commit**

```bash
git add backup_utils.py dashboard/blueprints/backup.py tests/test_backup_utils.py tests/test_blueprint_backup.py
git commit -m "refactor: extract get_system_backups into backup_utils.py"
```

---

### Task 3: Health marker + owner resolution + rollback-notice reading (`bot.py`)

**Files:**
- Modify: `bot.py`
- Create: `tests/test_bot_startup.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `UPDATE_HEALTH_MARKER`, `ROLLBACK_NOTICE_FILE` (module constants — their literal string values, `"update_health.marker"` and `"rollback_notice.txt"`, must match the copies added to `updater.py`'s `PROTECTED_FILES` and used by `launch_and_supervise()`/`write_status_notice()` in Task 4). `_get_owner(bot_instance) -> discord.User | None`, `_write_health_marker() -> None`, `_send_rollback_notice_if_present(bot_instance) -> None` — all consumed by `on_ready` in this same task; `_get_owner`/the marker file are also relied on by Task 4's `launch_and_supervise()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bot_startup.py`:

```python
import os
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

import bot as bot_module


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def make_fake_bot(owner=None):
    fake_bot = MagicMock()
    app_info = MagicMock()
    app_info.owner = owner
    fake_bot.application_info = AsyncMock(return_value=app_info)
    fake_bot.fetch_user = AsyncMock()
    return fake_bot


class TestGetOwner:
    @pytest.mark.asyncio
    async def test_returns_direct_owner(self):
        owner = MagicMock()
        owner.send = AsyncMock()
        fake_bot = make_fake_bot(owner=owner)

        result = await bot_module._get_owner(fake_bot)

        assert result is owner

    @pytest.mark.asyncio
    async def test_resolves_team_owner_by_fetching_user(self):
        team = MagicMock(spec=discord.Team)
        team.owner = 12345
        fetched_user = MagicMock()
        fetched_user.send = AsyncMock()
        fake_bot = make_fake_bot(owner=team)
        fake_bot.fetch_user = AsyncMock(return_value=fetched_user)

        result = await bot_module._get_owner(fake_bot)

        fake_bot.fetch_user.assert_awaited_once_with(12345)
        assert result is fetched_user

    @pytest.mark.asyncio
    async def test_returns_none_when_application_info_raises(self):
        fake_bot = MagicMock()
        fake_bot.application_info = AsyncMock(side_effect=Exception("network error"))

        result = await bot_module._get_owner(fake_bot)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_owner_has_no_send(self):
        fake_bot = make_fake_bot(owner=object())  # no .send attribute

        result = await bot_module._get_owner(fake_bot)

        assert result is None


class TestWriteHealthMarker:
    def test_creates_marker_file(self):
        bot_module._write_health_marker()
        assert os.path.exists(bot_module.UPDATE_HEALTH_MARKER)

    def test_does_not_raise_on_write_failure(self, monkeypatch):
        def _raise(*a, **kw):
            raise OSError("disk full")
        monkeypatch.setattr("builtins.open", _raise)
        bot_module._write_health_marker()  # must not raise


class TestSendRollbackNoticeIfPresent:
    @pytest.mark.asyncio
    async def test_noop_when_no_notice_file(self):
        fake_bot = MagicMock()
        await bot_module._send_rollback_notice_if_present(fake_bot)
        fake_bot.application_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_notice_content_to_owner_and_deletes_file(self):
        with open(bot_module.ROLLBACK_NOTICE_FILE, "w") as f:
            f.write("The bot was rolled back.")
        owner = MagicMock()
        owner.send = AsyncMock()
        fake_bot = make_fake_bot(owner=owner)

        await bot_module._send_rollback_notice_if_present(fake_bot)

        owner.send.assert_awaited_once_with("The bot was rolled back.")
        assert not os.path.exists(bot_module.ROLLBACK_NOTICE_FILE)

    @pytest.mark.asyncio
    async def test_deletes_file_even_if_owner_unavailable(self):
        with open(bot_module.ROLLBACK_NOTICE_FILE, "w") as f:
            f.write("notice")
        fake_bot = MagicMock()
        fake_bot.application_info = AsyncMock(side_effect=Exception("no owner"))

        await bot_module._send_rollback_notice_if_present(fake_bot)

        assert not os.path.exists(bot_module.ROLLBACK_NOTICE_FILE)


class TestOnReadyWiring:
    @pytest.mark.asyncio
    async def test_writes_health_marker(self, monkeypatch):
        monkeypatch.setattr(bot_module.bot, "user", MagicMock())
        monkeypatch.setattr(bot_module.bot, "failed_extensions", [])
        monkeypatch.setattr(bot_module.bot, "application_info", AsyncMock(side_effect=Exception("no network in test")))

        await bot_module.on_ready()

        assert os.path.exists(bot_module.UPDATE_HEALTH_MARKER)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_bot_startup.py -v`
Expected: `AttributeError: module 'bot' has no attribute '_get_owner'` (and similarly for the other new names).

- [ ] **Step 3: Write minimal implementation**

In `bot.py`, replace the existing `on_ready` function (bot.py:30-62) with:

```python
UPDATE_HEALTH_MARKER = "update_health.marker"  # must match updater.py's copy of this filename
ROLLBACK_NOTICE_FILE = "rollback_notice.txt"   # must match updater.py's copy of this filename


async def _get_owner(bot_instance):
    """Resolve the bot owner (handling Team ownership), or None if unavailable."""
    try:
        app_info = await bot_instance.application_info()
        owner = app_info.owner

        # Handle Team ownership edge case
        if isinstance(owner, discord.Team):
            owner = getattr(owner, 'owner', None)
            if isinstance(owner, int):
                owner = await bot_instance.fetch_user(owner)

        return owner if owner and hasattr(owner, 'send') else None
    except Exception as e:
        print(f"Failed to resolve bot owner: {e}")
        return None


def _write_health_marker():
    try:
        open(UPDATE_HEALTH_MARKER, "w").close()
    except Exception as e:
        print(f"Failed to write health marker: {e}")


async def _send_rollback_notice_if_present(bot_instance):
    if not os.path.exists(ROLLBACK_NOTICE_FILE):
        return
    try:
        with open(ROLLBACK_NOTICE_FILE, "r", encoding="utf-8") as f:
            message = f.read()
        owner = await _get_owner(bot_instance)
        if owner:
            await owner.send(message)
    except Exception as e:
        print(f"Failed to send rollback notice: {e}")
    finally:
        try:
            os.remove(ROLLBACK_NOTICE_FILE)
        except Exception:
            pass


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

    _write_health_marker()

    if hasattr(bot, 'failed_extensions') and bot.failed_extensions:
        try:
            owner = await _get_owner(bot)

            if owner:
                error_message = "**⚠️ Startup Issues:**\nThe following extensions failed to load:\n\n"
                for filename, error in bot.failed_extensions:
                    error_message += f"**{filename}**:\n`{error}`\n\n"

                # Send DM (chunk if necessary)
                if len(error_message) > 2000:
                    chunks = [error_message[i:i+1900] for i in range(0, len(error_message), 1900)]
                    for chunk in chunks:
                        await owner.send(chunk)
                else:
                    await owner.send(error_message)

                print(f"Sent error report to owner: {owner}")
                bot.failed_extensions = [] # Clear after sending
        except Exception as e:
            print(f"Failed to send error report to owner: {e}")

    await _send_rollback_notice_if_present(bot)
```

This is behavior-preserving for the existing `failed_extensions` block (same outer `try/except`, same message-chunking) — the only change there is calling `_get_owner(bot)` instead of the inline `app_info`/Team-resolution code, which now lives once in `_get_owner` instead of duplicated for the new rollback-notice path.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_bot_startup.py -v`
Expected: all 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot_startup.py
git commit -m "feat: write a health marker on_ready and send rollback notices to the owner"
```

---

### Task 4: `launch_and_supervise()` + `reset_health_marker()` + `write_status_notice()`

**Files:**
- Modify: `updater.py`
- Test: `tests/test_updater.py`

**Interfaces:**
- Consumes: `UPDATE_HEALTH_MARKER`/`ROLLBACK_NOTICE_FILE` filename values (Task 3 — duplicated here as `updater.py`'s own copies, matching this project's existing convention for cross-process constants, e.g. `BACKUP_DIR`'s "must match `BACKUP_FOLDER`" comment).
- Produces: `reset_health_marker() -> None`, `launch_and_supervise(timeout=60) -> bool`, `write_status_notice(message: str) -> None`. Consumed by Task 5 (`run_restore_mode`/`run_update_mode`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_updater.py`:

```python
from unittest.mock import MagicMock


class TestLaunchAndSupervise:
    def test_returns_true_when_marker_appears_while_alive(self, tmp_path):
        fake_proc = MagicMock()
        fake_proc.poll.return_value = None  # still running

        call_count = {"n": 0}
        def fake_sleep(seconds):
            call_count["n"] += 1
            if call_count["n"] == 1:
                open(updater.UPDATE_HEALTH_MARKER, "w").close()

        with patch("updater.subprocess.Popen", return_value=fake_proc), \
             patch("updater.time.sleep", side_effect=fake_sleep):
            result = updater.launch_and_supervise(timeout=5)

        assert result is True
        fake_proc.terminate.assert_not_called()

    def test_returns_false_without_terminate_when_process_exits_early(self, tmp_path):
        fake_proc = MagicMock()
        fake_proc.poll.return_value = 1  # already exited

        with patch("updater.subprocess.Popen", return_value=fake_proc):
            result = updater.launch_and_supervise(timeout=5)

        assert result is False
        fake_proc.terminate.assert_not_called()

    def test_terminates_stuck_process_on_timeout(self, tmp_path):
        fake_proc = MagicMock()
        fake_proc.poll.return_value = None  # never exits, marker never appears
        fake_proc.wait.return_value = None

        with patch("updater.subprocess.Popen", return_value=fake_proc), \
             patch("updater.time.sleep"):
            result = updater.launch_and_supervise(timeout=0.01)

        assert result is False
        fake_proc.terminate.assert_called_once()
        fake_proc.kill.assert_not_called()

    def test_kills_process_if_terminate_does_not_stop_it_in_time(self, tmp_path):
        fake_proc = MagicMock()
        fake_proc.poll.return_value = None
        fake_proc.wait.side_effect = updater.subprocess.TimeoutExpired(cmd="bot.py", timeout=10)

        with patch("updater.subprocess.Popen", return_value=fake_proc), \
             patch("updater.time.sleep"):
            result = updater.launch_and_supervise(timeout=0.01)

        assert result is False
        fake_proc.terminate.assert_called_once()
        fake_proc.kill.assert_called_once()


class TestWriteStatusNotice:
    def test_writes_message_to_file(self, tmp_path):
        updater.write_status_notice("test message")
        with open(updater.ROLLBACK_NOTICE_FILE) as f:
            assert f.read() == "test message"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_updater.py -v -k "LaunchAndSupervise or WriteStatusNotice"`
Expected: `AttributeError: module 'updater' has no attribute 'launch_and_supervise'` (and similarly for `write_status_notice`).

- [ ] **Step 3: Write minimal implementation**

In `updater.py`, add two new module constants right after `BACKUP_DIR` (updater.py:18):

```python
BACKUP_DIR = "backups"  # Must match BACKUP_FOLDER in dashboard/app.py
UPDATE_HEALTH_MARKER = "update_health.marker"  # must match bot.py's copy of this filename
ROLLBACK_NOTICE_FILE = "rollback_notice.txt"   # must match bot.py's copy of this filename
```

Add both new filenames to `PROTECTED_FILES` (updater.py:35-37):

```python
PROTECTED_FILES = {
    "config.json", ZIP_FILENAME, "updater.py.old", "update_temp_script.ps1",
    UPDATE_HEALTH_MARKER, ROLLBACK_NOTICE_FILE,
}
```

Add the following functions right after `update_dependencies()` (updater.py:262-269) and before `restart_bot()`:

```python
def reset_health_marker():
    try:
        if os.path.exists(UPDATE_HEALTH_MARKER):
            os.remove(UPDATE_HEALTH_MARKER)
    except Exception:
        pass


def launch_and_supervise(timeout=60) -> bool:
    """Launch bot.py; return True only if it signals healthy (marker appears) while still
    alive within `timeout` seconds. On crash or timeout, returns False -- and on timeout
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

    log(f"Bot did not become healthy within {timeout}s -- terminating stuck process.")
    try:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception as e:
        log(f"Failed to terminate stuck process: {e}")
    return False


def write_status_notice(message: str):
    try:
        with open(ROLLBACK_NOTICE_FILE, "w", encoding="utf-8") as f:
            f.write(message)
    except Exception as e:
        log(f"Failed to write status notice: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_updater.py -v`
Expected: all tests pass (11 total so far).

- [ ] **Step 5: Commit**

```bash
git add updater.py tests/test_updater.py
git commit -m "feat: add launch_and_supervise, reset_health_marker, write_status_notice"
```

---

### Task 5: `--restore` CLI mode (`run_restore_mode`/`run_update_mode`)

**Files:**
- Modify: `updater.py`
- Test: `tests/test_updater.py`

**Interfaces:**
- Consumes: `restore_from_backup` (Task 1), `launch_and_supervise`/`write_status_notice` (Task 4), and the existing `create_backup`/`download_update`/`extract_and_apply`/`update_dependencies`.
- Produces: `run_restore_mode(args)`, `run_update_mode(args)`. Consumed only by `updater.py`'s own `__main__` block — no other task depends on these directly, but Phase B replaces `run_update_mode`'s "not healthy" branch with real auto-rollback orchestration.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_updater.py`:

```python
import argparse


class TestRunRestoreMode:
    def test_success_path_calls_restore_and_supervises(self, tmp_path):
        args = argparse.Namespace(restore="backup_x.zip", no_restart=False)
        with patch.object(updater, "restore_from_backup", return_value=True) as mock_restore, \
             patch.object(updater, "launch_and_supervise", return_value=True) as mock_launch, \
             patch.object(updater, "write_status_notice") as mock_notice:
            updater.run_restore_mode(args)

        mock_restore.assert_called_once_with(os.path.join(updater.BACKUP_DIR, "backup_x.zip"))
        mock_launch.assert_called_once()
        mock_notice.assert_called_once()
        assert "succeeded" in mock_notice.call_args[0][0]

    def test_exits_nonzero_when_restore_fails(self, tmp_path):
        args = argparse.Namespace(restore="backup_x.zip", no_restart=False)
        with patch.object(updater, "restore_from_backup", return_value=False), \
             patch.object(updater, "launch_and_supervise") as mock_launch:
            with pytest.raises(SystemExit) as exc_info:
                updater.run_restore_mode(args)

        assert exc_info.value.code == 1
        mock_launch.assert_not_called()

    def test_unhealthy_after_restore_writes_warning_notice(self, tmp_path):
        args = argparse.Namespace(restore="backup_x.zip", no_restart=False)
        with patch.object(updater, "restore_from_backup", return_value=True), \
             patch.object(updater, "launch_and_supervise", return_value=False), \
             patch.object(updater, "write_status_notice") as mock_notice:
            updater.run_restore_mode(args)

        assert "did not become healthy" in mock_notice.call_args[0][0]

    def test_no_restart_skips_supervision(self, tmp_path):
        args = argparse.Namespace(restore="backup_x.zip", no_restart=True)
        with patch.object(updater, "restore_from_backup", return_value=True), \
             patch.object(updater, "launch_and_supervise") as mock_launch:
            updater.run_restore_mode(args)

        mock_launch.assert_not_called()


class TestRunUpdateMode:
    def test_normal_flow_calls_steps_in_order_and_reports_healthy(self, tmp_path):
        args = argparse.Namespace(no_backup=False, no_restart=False)
        calls = []
        with patch.object(updater, "create_backup", side_effect=lambda: calls.append("backup")), \
             patch.object(updater, "download_update", side_effect=lambda: calls.append("download")), \
             patch.object(updater, "extract_and_apply", side_effect=lambda: calls.append("apply")), \
             patch.object(updater, "update_dependencies", side_effect=lambda: calls.append("deps")), \
             patch.object(updater, "launch_and_supervise", return_value=True), \
             patch.object(updater, "write_status_notice") as mock_notice:
            updater.run_update_mode(args)

        assert calls == ["backup", "download", "apply", "deps"]
        mock_notice.assert_not_called()

    def test_no_backup_flag_skips_backup(self, tmp_path):
        args = argparse.Namespace(no_backup=True, no_restart=False)
        with patch.object(updater, "create_backup") as mock_backup, \
             patch.object(updater, "download_update"), \
             patch.object(updater, "extract_and_apply"), \
             patch.object(updater, "update_dependencies"), \
             patch.object(updater, "launch_and_supervise", return_value=True):
            updater.run_update_mode(args)

        mock_backup.assert_not_called()

    def test_unhealthy_update_writes_notice_pointing_at_manual_rollback(self, tmp_path):
        args = argparse.Namespace(no_backup=True, no_restart=False)
        with patch.object(updater, "download_update"), \
             patch.object(updater, "extract_and_apply"), \
             patch.object(updater, "update_dependencies"), \
             patch.object(updater, "launch_and_supervise", return_value=False), \
             patch.object(updater, "write_status_notice") as mock_notice:
            updater.run_update_mode(args)

        assert "/rollback" in mock_notice.call_args[0][0]

    def test_no_restart_flag_skips_supervision(self, tmp_path):
        args = argparse.Namespace(no_backup=True, no_restart=True)
        with patch.object(updater, "download_update"), \
             patch.object(updater, "extract_and_apply"), \
             patch.object(updater, "update_dependencies"), \
             patch.object(updater, "launch_and_supervise") as mock_launch:
            updater.run_update_mode(args)

        mock_launch.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_updater.py -v -k "RunRestoreMode or RunUpdateMode"`
Expected: `AttributeError: module 'updater' has no attribute 'run_restore_mode'` (and similarly for `run_update_mode`).

- [ ] **Step 3: Write minimal implementation**

In `updater.py`, replace the entire `if __name__ == "__main__":` block (updater.py:289-330) with:

```python
def run_restore_mode(args):
    log(f"Restoring from backup: {args.restore}")
    restore_path = os.path.join(BACKUP_DIR, args.restore)
    if not restore_from_backup(restore_path):
        log("Restore failed -- aborting, bot NOT restarted automatically.")
        sys.exit(1)

    if not args.no_restart:
        if launch_and_supervise():
            log("Manual rollback succeeded -- bot restored and healthy.")
            write_status_notice("✅ Manual rollback succeeded — bot restored and healthy.")
        else:
            log("Manual rollback applied, but the bot did not become healthy afterward.")
            write_status_notice(
                "⚠️ Manual rollback applied, but the bot did not become healthy afterward. "
                "Check logs or try a different backup."
            )
    else:
        log("Restore finished. Please restart the bot manually.")


def run_update_mode(args):
    if not args.no_backup:
        create_backup()

    download_update()
    extract_and_apply()
    update_dependencies()

    if not args.no_restart:
        if launch_and_supervise():
            log("Update successful, bot is healthy.")
        else:
            log("CRITICAL: update produced an unhealthy bot.")
            write_status_notice(
                "🚨 Your last update failed to start correctly. Automatic rollback isn't "
                "wired up yet — use /rollback or the dashboard to restore a previous backup."
            )
    else:
        log("Update finished. Please restart the bot manually.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CthulhuBotV2 Auto-Updater")
    parser.add_argument("pid", nargs='?', type=int, help="PID of the process to wait for")
    parser.add_argument("--no-restart", action="store_true", help="Do not restart the bot automatically")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup")
    parser.add_argument("--update-infodata", action="store_true", help="Update infodata folder (overwrite changes)")
    parser.add_argument("--restore", metavar="FILENAME", help="Restore a specific backup zip from backups/ instead of downloading an update")
    args = parser.parse_args()

    # Update global sets based on arguments
    if args.update_infodata:
        if "infodata" in BACKUP_EXCLUDE_DIRS:
            BACKUP_EXCLUDE_DIRS.remove("infodata")
        if "infodata" in PROTECTED_DIRS:
            PROTECTED_DIRS.remove("infodata")
        log("Infodata update enabled. 'infodata' removed from exclusion/protection.")

    # 0. Cleanup old updater if exists
    cleanup_old_updater()

    # 1. Wait
    if args.pid:
        wait_for_pid(args.pid)
        time.sleep(2)

    if args.restore:
        run_restore_mode(args)
    else:
        run_update_mode(args)
```

`restart_bot()` (updater.py:271-287) is left in place but is now dead code (no longer called anywhere) — do not delete it in this task, since Phase B's plan will decide whether anything still needs it; deleting unused code the plan didn't ask you to remove is out of scope here.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_updater.py -v`
Expected: all tests pass (19 total so far).

- [ ] **Step 5: Commit**

```bash
git add updater.py tests/test_updater.py
git commit -m "feat: add --restore CLI mode via run_restore_mode/run_update_mode"
```

---

### Task 6: `/rollback` Discord command

**Files:**
- Create: `commands/rollback.py`
- Create: `tests/test_commands_rollback.py`

**Interfaces:**
- Consumes: `get_system_backups` (Task 2, called with `BACKUP_FOLDER` imported from `dashboard.state`, matching the existing `from dashboard.state import guild_mixers, server_volumes` cross-import pattern already used by `commands/music.py`).
- Produces: nothing consumed by another task in this plan.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_commands_rollback.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from commands.rollback import Rollback, BackupSelect, BackupSelectView


def make_interaction(user=None):
    interaction = MagicMock()
    interaction.user = user or MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup.send = AsyncMock()
    interaction.client.close = AsyncMock()
    return interaction


class TestRollbackCommand:
    @pytest.mark.asyncio
    async def test_rejects_non_owner(self):
        bot = MagicMock()
        bot.is_owner = AsyncMock(return_value=False)
        cog = Rollback(bot)
        interaction = make_interaction()

        await Rollback.rollback.callback(cog, interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "⛔ You do not have permission to run this command.", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_no_backups_available_shows_message(self):
        bot = MagicMock()
        bot.is_owner = AsyncMock(return_value=True)
        cog = Rollback(bot)
        interaction = make_interaction()

        with patch("commands.rollback.get_system_backups", return_value=[]):
            await Rollback.rollback.callback(cog, interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "No backups available to restore.", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_shows_select_view_with_backups(self):
        bot = MagicMock()
        bot.is_owner = AsyncMock(return_value=True)
        cog = Rollback(bot)
        interaction = make_interaction()
        backups = [{"name": "backup_1.zip", "size": 2048, "created": "2026-07-22 10:00:00"}]

        with patch("commands.rollback.get_system_backups", return_value=backups):
            await Rollback.rollback.callback(cog, interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], BackupSelectView)


class TestBackupSelectCallback:
    @pytest.mark.asyncio
    async def test_spawns_updater_restore_and_closes_bot(self):
        backups = [{"name": "backup_1.zip", "size": 2048, "created": "2026-07-22 10:00:00"}]
        select = BackupSelect(backups)
        select._values = ["backup_1.zip"]
        interaction = make_interaction()

        with patch("commands.rollback.subprocess.Popen") as mock_popen, \
             patch("commands.rollback.os.getpid", return_value=4242), \
             patch("commands.rollback.sys.executable", "/usr/bin/python3"), \
             patch("commands.rollback.os.name", "posix"):
            await select.callback(interaction)

        mock_popen.assert_called_once_with(
            ["/usr/bin/python3", "updater.py", "4242", "--restore", "backup_1.zip"]
        )
        interaction.client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_popen_failure_sends_error_and_does_not_close_bot(self):
        backups = [{"name": "backup_1.zip", "size": 2048, "created": "2026-07-22 10:00:00"}]
        select = BackupSelect(backups)
        select._values = ["backup_1.zip"]
        interaction = make_interaction()

        with patch("commands.rollback.subprocess.Popen", side_effect=OSError("no permission")):
            await select.callback(interaction)

        interaction.followup.send.assert_awaited_once()
        interaction.client.close.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_commands_rollback.py -v`
Expected: `ModuleNotFoundError: No module named 'commands.rollback'`

- [ ] **Step 3: Write minimal implementation**

Create `commands/rollback.py`:

```python
import discord
from discord import app_commands
from discord.ext import commands
import os
import sys
import subprocess

from dashboard.state import BACKUP_FOLDER
from backup_utils import get_system_backups


class BackupSelect(discord.ui.Select):
    def __init__(self, backups: list[dict]):
        options = [
            discord.SelectOption(
                label=b["name"],
                description=f"{b['created']} · {b['size'] // 1024} KB",
            )
            for b in backups
        ]
        super().__init__(placeholder="Choose a backup to restore...", options=options)

    async def callback(self, interaction: discord.Interaction):
        filename = self.values[0]
        await interaction.response.edit_message(
            content=f"🔄 **Restoring `{filename}`...**\nBot is restarting.", view=None
        )

        pid = str(os.getpid())
        python_exe = sys.executable
        cmd = [python_exe, "updater.py", pid, "--restore", filename]

        try:
            if os.name == 'nt':
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to start restore: {e}", ephemeral=True)
            return

        await interaction.client.close()


class BackupSelectView(discord.ui.View):
    def __init__(self, backups: list[dict]):
        super().__init__(timeout=60)
        self.add_item(BackupSelect(backups))


class Rollback(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='rollback', description="⏪ Restore the bot from a previous backup. Owner only.")
    async def rollback(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("⛔ You do not have permission to run this command.", ephemeral=True)
            return

        backups = get_system_backups(BACKUP_FOLDER)
        if not backups:
            await interaction.response.send_message("No backups available to restore.", ephemeral=True)
            return

        view = BackupSelectView(backups[:25])
        await interaction.response.send_message(
            "⚠️ **Rollback**\n\nSelect a backup to restore. The bot will restart after applying it.",
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Rollback(bot))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_commands_rollback.py -v`
Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add commands/rollback.py tests/test_commands_rollback.py
git commit -m "feat: add /rollback Discord command"
```

---

### Task 7: Dashboard restore route + button

**Files:**
- Modify: `dashboard/blueprints/backup.py`
- Modify: `dashboard/templates/backup_dashboard.html`
- Modify: `tests/test_blueprint_backup.py`

**Interfaces:**
- Consumes: nothing new from other tasks in this plan (spawns `updater.py --restore` the same way Task 6 does, but as a POST route instead of a Discord command).
- Produces: nothing consumed by another task.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_blueprint_backup.py`:

```python
@pytest.mark.asyncio
async def test_backup_restore_unauthorized_without_session(client):
    response = await client.post(
        '/api/backup/restore', json={"filename": "x.zip"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_backup_restore_rejects_path_traversal(client, isolated_backup_folder):
    await login(client)
    response = await client.post(
        '/api/backup/restore', json={"filename": "../evil.zip"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_backup_restore_file_not_found_returns_404(client, isolated_backup_folder):
    await login(client)
    response = await client.post(
        '/api/backup/restore', json={"filename": "missing.zip"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_backup_restore_bot_not_ready_returns_500(client, isolated_backup_folder):
    await login(client)
    make_zip(isolated_backup_folder, "backup_1.zip")
    with patch('dashboard.app.app.bot', None):
        response = await client.post(
            '/api/backup/restore', json={"filename": "backup_1.zip"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_backup_restore_spawns_updater_and_closes_bot(client, isolated_backup_folder):
    await login(client)
    make_zip(isolated_backup_folder, "backup_1.zip")
    mock_bot = MagicMock()
    mock_bot.close = AsyncMock()
    with patch('dashboard.app.app.bot', mock_bot), \
         patch('dashboard.blueprints.backup.subprocess.Popen') as mock_popen, \
         patch('dashboard.blueprints.backup.os.getpid', return_value=999):
        response = await client.post(
            '/api/backup/restore', json={"filename": "backup_1.zip"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 200
    mock_popen.assert_called_once()
    mock_bot.close.assert_awaited_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_blueprint_backup.py -v -k restore`
Expected: all 5 new tests fail (404 for unregistered route, since `/api/backup/restore` doesn't exist yet — Quart returns 404 for any unmatched route regardless of method).

- [ ] **Step 3: Write minimal implementation**

In `dashboard/blueprints/backup.py`, add `sys` and `subprocess` to the imports at the top:

```python
import os
import re
import sys
import subprocess
import datetime
from quart import Blueprint, request, jsonify, redirect, url_for, render_template, send_from_directory

from dashboard.app import app, is_admin
from dashboard.state import BACKUP_FOLDER
from loadnsave import load_settings_async, save_settings
from backup_utils import get_system_backups
```

Add a new route right after `/api/backup/delete` (`backup_delete_file`) and before `/admin/backup/download/<filename>`:

```python
@backup_bp.route('/api/backup/restore', methods=['POST'])
async def backup_restore():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    filename = data.get('filename')

    if not filename or not filename.endswith('.zip'):
        return jsonify({"status": "error", "message": "Invalid filename"}), 400
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({"status": "error", "message": "Invalid filename"}), 400

    target_path = os.path.join(BACKUP_FOLDER, filename)
    if not os.path.exists(target_path):
        return jsonify({"status": "error", "message": "File not found"}), 404

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    pid = str(os.getpid())
    cmd = [sys.executable, "updater.py", pid, "--restore", filename]

    try:
        if os.name == 'nt':
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(cmd)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to start restore: {e}"}), 500

    await app.bot.close()
    return jsonify({"status": "success"})
```

In `dashboard/templates/backup_dashboard.html`, replace the action buttons cell:

```html
                <td class="pe-4 py-3 align-middle text-md-end">
                    <div style="display:flex; gap:8px; justify-content: flex-end">
                        <a href="/admin/backup/download/${file.name}" class="btn-eld on" style="padding: 6px 12px; font-size: 10px">DOWNLOAD</a>
                        <button class="btn-eld rust" style="padding: 6px 12px; font-size: 10px" onclick="deleteBackup('${file.name}')">DELETE</button>
                    </div>
                </td>
```

with:

```html
                <td class="pe-4 py-3 align-middle text-md-end">
                    <div style="display:flex; gap:8px; justify-content: flex-end">
                        <a href="/admin/backup/download/${file.name}" class="btn-eld on" style="padding: 6px 12px; font-size: 10px">DOWNLOAD</a>
                        <button class="btn-eld primary" style="padding: 6px 12px; font-size: 10px" onclick="restoreBackup('${file.name}')">RESTORE</button>
                        <button class="btn-eld rust" style="padding: 6px 12px; font-size: 10px" onclick="deleteBackup('${file.name}')">DELETE</button>
                    </div>
                </td>
```

Add a new `restoreBackup` function right after the existing `deleteBackup` function:

```javascript
async function restoreBackup(filename) {
    if (!confirm(`Restore ${filename}? The bot will restart immediately after applying it.`)) return;
    try {
        const response = await fetch('/api/backup/restore', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename })
        });
        const data = await response.json();
        if (data.status === 'success') {
            alert('Restore started — the bot is restarting.');
        } else {
            alert('Error: ' + data.message);
        }
    } catch (e) { alert("Error: " + e); }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_blueprint_backup.py -v`
Expected: all tests pass.

- [ ] **Step 5: Structural verification of the HTML/JS changes**

Run:
```bash
grep -n "function restoreBackup\|onclick=\"restoreBackup(" dashboard/templates/backup_dashboard.html
```
Expected: both the function definition and its one call site are found. Note in your report that a human should manually verify in a browser (open `/admin/backup` with at least one backup listed, click RESTORE, confirm the dialog, verify the bot restarts) — this repo has no JS test harness for dashboard templates, consistent with how the music dashboard's seek UI was verified in an earlier feature.

- [ ] **Step 6: Commit**

```bash
git add dashboard/blueprints/backup.py dashboard/templates/backup_dashboard.html tests/test_blueprint_backup.py
git commit -m "feat: add dashboard restore route and button for backups"
```

---

### Task 8: Full regression pass

**Files:**
- Verify only — no source changes expected unless this step uncovers a regression.

**Interfaces:**
- Consumes: everything from Tasks 1-7.
- Produces: nothing — this is the last task in Phase A. Phase B (a separate plan) starts from this state.

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass, including the pre-existing suite plus every test added in Tasks 1-7 — no regressions in any other module (in particular: the existing `/updatebot` command and its `updater.py` normal-update path, which Task 5 refactored but should not have changed the behavior of).

- [ ] **Step 2: Manually re-verify the two safety properties called out in this plan's Global Constraints**

Run:
```bash
grep -n "def restore_from_backup" -A 3 updater.py
grep -n "proc.terminate()" -A 6 updater.py
```
Confirm by inspection: `restore_from_backup` calls `create_backup()` unconditionally near its start (no `if` guarding it) — a restore is always itself reversible; `launch_and_supervise`'s timeout branch calls `proc.terminate()` (then `proc.kill()` on a `TimeoutExpired`) before returning `False` — a stuck process is never left running when the function reports failure.

- [ ] **Step 3: Commit (only if Step 1 required a fix)**

```bash
git add -A
git commit -m "fix: address regression found in rollback Phase A full-suite pass"
```

If Step 1 found no regressions, skip this step — there is nothing to commit.

---

## Self-Review Notes

- **Spec coverage:** design spec section 1 (shared restore primitive) → Tasks 1-2; section 2 (health signal + rollback notice) → Task 3; the `launch_and_supervise`/`write_status_notice` primitives (moved into this phase per the corrected phase-boundary in the spec's Rollout/Risk section) → Task 4; section 4 (manual restore surfaces) → Tasks 5-7.
- **Placeholder scan:** no TBD/TODO; Task 5's `run_update_mode` "not healthy" branch is an intentional, honest Phase-A-only behavior (points the owner at the now-available manual `/rollback`/dashboard restore), explicitly documented as something Phase B replaces — not a stub silently left unfinished.
- **Type consistency:** `restore_from_backup(backup_zip_path: str) -> bool` matches between Task 1's definition and Task 5's `run_restore_mode` call site. `launch_and_supervise(timeout=60) -> bool` matches between Task 4's definition and both `run_restore_mode`/`run_update_mode`'s call sites in Task 5. `get_system_backups(backup_folder: str) -> list[dict]` matches between Task 2's definition and both the dashboard route (Task 2) and `commands/rollback.py` (Task 6) call sites. `UPDATE_HEALTH_MARKER`/`ROLLBACK_NOTICE_FILE` string literals (`"update_health.marker"`/`"rollback_notice.txt"`) are identical between `bot.py` (Task 3) and `updater.py` (Task 4).
