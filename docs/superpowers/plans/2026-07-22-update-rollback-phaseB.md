# Update Rollback Phase B — Automatic Rollback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a fresh `/updatebot` run produces an unhealthy bot, automatically restore the latest pre-update backup and relaunch — exactly once, with no possibility of an infinite restart loop — instead of leaving the owner to notice and fix it by hand.

**Architecture:** This phase is thin orchestration on top of primitives Phase A already built and shipped (`restore_from_backup`, `launch_and_supervise`, `write_status_notice`, the `bot.py` health marker). It adds one new lookup function, `find_latest_backup()`, and replaces `run_update_mode()`'s placeholder "not healthy" branch (which today just logs and points the owner at the manual `/rollback` command) with the real auto-restore-and-relaunch sequence.

**Tech Stack:** Python 3.11+, pytest.

**Prerequisite:** Phase A (`docs/superpowers/plans/2026-07-22-update-rollback-phaseA.md`) must be fully merged before starting this plan — every task below calls functions Phase A introduced.

## Global Constraints

- Exactly one automatic rollback attempt ever — if the rollback itself doesn't produce a healthy bot, `run_update_mode` stops there and reports it; it never tries a second backup or loops.
- `find_latest_backup()` returns the most recent `backup_*.zip` in `BACKUP_DIR` by filename (the `YYYYMMDD_HHMMSS` timestamp format is lexicographically sortable, so no `stat()` calls are needed) — this is unambiguous because `create_backup()` is the only thing that ever writes `backup_*.zip` files into `BACKUP_DIR`.
- `restore_from_backup()` (Phase A) already snapshots the current state via `create_backup()` internally before applying anything — this phase's orchestration does not call `create_backup()` a second time itself.
- Three distinct outcomes after an unhealthy update must each produce a distinct, correctly-worded status notice: rollback succeeded; rollback was attempted but the restored bot still isn't healthy; no rollback was even attempted (no backup found, or `restore_from_backup` itself failed).

---

### Task 1: `find_latest_backup()`

**Files:**
- Modify: `updater.py`
- Test: `tests/test_updater.py`

**Interfaces:**
- Consumes: `BACKUP_DIR` (existing module constant).
- Produces: `find_latest_backup() -> str | None`. Consumed by Task 2.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_updater.py`:

```python
class TestFindLatestBackup:
    def test_returns_none_when_backup_dir_missing(self, tmp_path):
        assert updater.find_latest_backup() is None

    def test_returns_none_when_no_matching_files(self, tmp_path):
        os.makedirs(updater.BACKUP_DIR)
        with open(os.path.join(updater.BACKUP_DIR, "notes.txt"), "w") as f:
            f.write("x")
        assert updater.find_latest_backup() is None

    def test_returns_lexicographically_latest_backup(self, tmp_path):
        os.makedirs(updater.BACKUP_DIR)
        for name in ["backup_20260101_000000.zip", "backup_20260722_120000.zip", "backup_20260315_080000.zip"]:
            with open(os.path.join(updater.BACKUP_DIR, name), "w") as f:
                f.write("zip content")

        result = updater.find_latest_backup()

        assert result == os.path.join(updater.BACKUP_DIR, "backup_20260722_120000.zip")

    def test_ignores_files_not_matching_backup_prefix_pattern(self, tmp_path):
        os.makedirs(updater.BACKUP_DIR)
        with open(os.path.join(updater.BACKUP_DIR, "backup_20260101_000000.zip"), "w") as f:
            f.write("real backup")
        with open(os.path.join(updater.BACKUP_DIR, "update_pkg.zip"), "w") as f:
            f.write("not a backup")

        result = updater.find_latest_backup()

        assert result == os.path.join(updater.BACKUP_DIR, "backup_20260101_000000.zip")
```

(This test file already has an `isolated_cwd` autouse fixture from Phase A's Task 1 that `monkeypatch.chdir(tmp_path)` for every test — `os.makedirs(updater.BACKUP_DIR)` above creates `backups/` inside that isolated temp directory, not the real repo.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_updater.py -v -k FindLatestBackup`
Expected: `AttributeError: module 'updater' has no attribute 'find_latest_backup'`

- [ ] **Step 3: Write minimal implementation**

In `updater.py`, add this function right after `write_status_notice` (the last function Phase A's Task 4 added, immediately before `restart_bot`):

```python
def find_latest_backup() -> str | None:
    """Return the path to the most recent backup_*.zip in BACKUP_DIR, or None if there
    isn't one. create_backup() is the only thing that ever writes backup_*.zip files here,
    so 'the latest one' is unambiguous."""
    if not os.path.exists(BACKUP_DIR):
        return None
    zips = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".zip"))
    return os.path.join(BACKUP_DIR, zips[-1]) if zips else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_updater.py -v -k FindLatestBackup`
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add updater.py tests/test_updater.py
git commit -m "feat: add find_latest_backup for automatic rollback"
```

---

### Task 2: Wire automatic rollback into `run_update_mode`

**Files:**
- Modify: `updater.py`
- Modify: `tests/test_updater.py`

**Interfaces:**
- Consumes: `find_latest_backup` (Task 1), `restore_from_backup`/`launch_and_supervise`/`write_status_notice` (all Phase A).
- Produces: nothing consumed by a later task — this is the last functional task in Phase B.

- [ ] **Step 1: Write the failing tests**

In `tests/test_updater.py`, find the existing `test_unhealthy_update_writes_notice_pointing_at_manual_rollback` test (added in Phase A's Task 5, inside `TestRunUpdateMode`) — its assertion (`"/rollback" in mock_notice.call_args[0][0]`) describes Phase A's now-superseded placeholder behavior. Delete it:

```python
    def test_unhealthy_update_writes_notice_pointing_at_manual_rollback(self, tmp_path):
        args = argparse.Namespace(no_backup=True, no_restart=False)
        with patch.object(updater, "download_update"), \
             patch.object(updater, "extract_and_apply"), \
             patch.object(updater, "update_dependencies"), \
             patch.object(updater, "launch_and_supervise", return_value=False), \
             patch.object(updater, "write_status_notice") as mock_notice:
            updater.run_update_mode(args)

        assert "/rollback" in mock_notice.call_args[0][0]
```

Append its replacement — a new test class covering all of the unhealthy-update branch's real behavior — at the end of `tests/test_updater.py`:

```python
class TestRunUpdateModeAutoRollback:
    def test_healthy_update_never_attempts_rollback(self, tmp_path):
        args = argparse.Namespace(no_backup=True, no_restart=False)
        with patch.object(updater, "download_update"), \
             patch.object(updater, "extract_and_apply"), \
             patch.object(updater, "update_dependencies"), \
             patch.object(updater, "launch_and_supervise", return_value=True), \
             patch.object(updater, "find_latest_backup") as mock_find, \
             patch.object(updater, "restore_from_backup") as mock_restore:
            updater.run_update_mode(args)

        mock_find.assert_not_called()
        mock_restore.assert_not_called()

    def test_unhealthy_update_auto_restores_and_succeeds(self, tmp_path):
        args = argparse.Namespace(no_backup=True, no_restart=False)
        with patch.object(updater, "download_update"), \
             patch.object(updater, "extract_and_apply"), \
             patch.object(updater, "update_dependencies"), \
             patch.object(updater, "launch_and_supervise", side_effect=[False, True]), \
             patch.object(updater, "find_latest_backup", return_value="/backups/backup_x.zip"), \
             patch.object(updater, "restore_from_backup", return_value=True) as mock_restore, \
             patch.object(updater, "write_status_notice") as mock_notice:
            updater.run_update_mode(args)

        mock_restore.assert_called_once_with("/backups/backup_x.zip")
        assert updater.launch_and_supervise.call_count == 2
        assert "automatically rolled back" in mock_notice.call_args[0][0]

    def test_unhealthy_update_auto_restore_also_unhealthy(self, tmp_path):
        args = argparse.Namespace(no_backup=True, no_restart=False)
        with patch.object(updater, "download_update"), \
             patch.object(updater, "extract_and_apply"), \
             patch.object(updater, "update_dependencies"), \
             patch.object(updater, "launch_and_supervise", side_effect=[False, False]), \
             patch.object(updater, "find_latest_backup", return_value="/backups/backup_x.zip"), \
             patch.object(updater, "restore_from_backup", return_value=True), \
             patch.object(updater, "write_status_notice") as mock_notice:
            updater.run_update_mode(args)

        assert "rollback also failed" in mock_notice.call_args[0][0]

    def test_unhealthy_update_no_backup_available_skips_restore(self, tmp_path):
        args = argparse.Namespace(no_backup=True, no_restart=False)
        with patch.object(updater, "download_update"), \
             patch.object(updater, "extract_and_apply"), \
             patch.object(updater, "update_dependencies"), \
             patch.object(updater, "launch_and_supervise", return_value=False), \
             patch.object(updater, "find_latest_backup", return_value=None), \
             patch.object(updater, "restore_from_backup") as mock_restore, \
             patch.object(updater, "write_status_notice") as mock_notice:
            updater.run_update_mode(args)

        mock_restore.assert_not_called()
        assert "could not automatically roll back" in mock_notice.call_args[0][0]

    def test_unhealthy_update_restore_itself_fails(self, tmp_path):
        args = argparse.Namespace(no_backup=True, no_restart=False)
        with patch.object(updater, "download_update"), \
             patch.object(updater, "extract_and_apply"), \
             patch.object(updater, "update_dependencies"), \
             patch.object(updater, "launch_and_supervise", return_value=False), \
             patch.object(updater, "find_latest_backup", return_value="/backups/backup_x.zip"), \
             patch.object(updater, "restore_from_backup", return_value=False), \
             patch.object(updater, "write_status_notice") as mock_notice:
            updater.run_update_mode(args)

        # restore_from_backup returning False means launch_and_supervise is never called a
        # second time -- only the initial (failed) attempt from the top of run_update_mode.
        assert updater.launch_and_supervise.call_count == 1
        assert "could not automatically roll back" in mock_notice.call_args[0][0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_updater.py -v -k RunUpdateModeAutoRollback`
Expected: all 5 new tests fail — `run_update_mode`'s current (Phase A) "not healthy" branch never calls `find_latest_backup`/`restore_from_backup` at all and writes a different message, so every assertion above fails (either the `assert_not_called()` calls incorrectly succeed while the message assertions fail, or vice versa depending on the specific test).

- [ ] **Step 3: Write minimal implementation**

In `updater.py`, inside `run_update_mode`, replace the `else` branch that currently reads:

```python
        else:
            log("CRITICAL: update produced an unhealthy bot.")
            write_status_notice(
                "🚨 Your last update failed to start correctly. Automatic rollback isn't "
                "wired up yet — use /rollback or the dashboard to restore a previous backup."
            )
```

with:

```python
        else:
            log("Update produced an unhealthy bot -- attempting automatic rollback...")
            latest_backup = find_latest_backup()
            if latest_backup and restore_from_backup(latest_backup):
                if launch_and_supervise():
                    log("Automatic rollback succeeded.")
                    write_status_notice(
                        "⚠️ Your last update failed to start, so I automatically rolled back "
                        "to the previous version."
                    )
                else:
                    log("CRITICAL: automatic rollback also failed to produce a healthy bot.")
                    write_status_notice(
                        "🚨 Your last update failed AND the automatic rollback also failed to "
                        "start. Manual intervention needed — check the server directly."
                    )
            else:
                log("CRITICAL: update failed and no usable backup was available to roll back to.")
                write_status_notice(
                    "🚨 Your last update failed and I could not automatically roll back (no "
                    "backup available, or restore itself failed). Manual intervention needed."
                )
```

The `if` branch above it (`if launch_and_supervise(): log("Update successful, bot is healthy.")`) is unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_updater.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add updater.py tests/test_updater.py
git commit -m "feat: wire automatic rollback into run_update_mode on unhealthy update"
```

---

### Task 3: Full regression pass

**Files:**
- Verify only — no source changes expected unless this step uncovers a regression.

**Interfaces:**
- Consumes: everything from Tasks 1-2 (and, transitively, all of Phase A).
- Produces: nothing — this is the last task in Phase B, and in the whole update-rollback feature.

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass, including the pre-existing suite plus every test added across both Phase A and Phase B — no regressions.

- [ ] **Step 2: Manually re-verify the "exactly one attempt" safety property**

Run:
```bash
grep -n "def run_update_mode" -A 25 updater.py
```
Confirm by inspection: the unhealthy-update branch calls `launch_and_supervise()` at most twice total (once for the fresh update, once after a successful `restore_from_backup`) — there is no loop, no recursion, and no third attempt under any combination of outcomes. If `restore_from_backup` itself returns `False`, `launch_and_supervise` is not called again at all.

- [ ] **Step 3: Commit (only if Step 1 required a fix)**

```bash
git add -A
git commit -m "fix: address regression found in rollback Phase B full-suite pass"
```

If Step 1 found no regressions, skip this step — there is nothing to commit.

---

## Self-Review Notes

- **Spec coverage:** design spec section 3's remaining piece after Phase A (the `find_latest_backup` lookup and the auto-rollback orchestration wired into the normal update flow) → Tasks 1-2. All three failure-mode branches described in the spec (rollback succeeds; rollback attempted but still unhealthy; no rollback attempted at all) have a dedicated test in Task 2.
- **Placeholder scan:** no TBD/TODO. Task 2 explicitly deletes the Phase A placeholder test whose assertion no longer matches reality, rather than leaving a now-incorrect test passing by accident.
- **Type consistency:** `find_latest_backup() -> str | None` matches between Task 1's definition and Task 2's `run_update_mode` usage (`if latest_backup and restore_from_backup(latest_backup):` — correctly treats `None` as falsy). All three `write_status_notice(message: str)` call sites in Task 2 match the Phase A signature exactly (single positional string argument).
