import os
import zipfile
import argparse
from unittest.mock import patch, MagicMock

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

    def test_rejects_path_traversal_with_dotdot(self, tmp_path):
        args = argparse.Namespace(restore="../evil.zip", no_restart=False)
        with patch.object(updater, "restore_from_backup") as mock_restore, \
             patch.object(updater, "launch_and_supervise") as mock_launch:
            with pytest.raises(SystemExit) as exc_info:
                updater.run_restore_mode(args)

        assert exc_info.value.code == 1
        mock_restore.assert_not_called()
        mock_launch.assert_not_called()

    def test_rejects_path_traversal_with_forward_slash(self, tmp_path):
        args = argparse.Namespace(restore="../subdir/evil.zip", no_restart=False)
        with patch.object(updater, "restore_from_backup") as mock_restore, \
             patch.object(updater, "launch_and_supervise") as mock_launch:
            with pytest.raises(SystemExit) as exc_info:
                updater.run_restore_mode(args)

        assert exc_info.value.code == 1
        mock_restore.assert_not_called()
        mock_launch.assert_not_called()

    def test_rejects_path_traversal_with_backslash(self, tmp_path):
        args = argparse.Namespace(restore="..\\evil.zip", no_restart=False)
        with patch.object(updater, "restore_from_backup") as mock_restore, \
             patch.object(updater, "launch_and_supervise") as mock_launch:
            with pytest.raises(SystemExit) as exc_info:
                updater.run_restore_mode(args)

        assert exc_info.value.code == 1
        mock_restore.assert_not_called()
        mock_launch.assert_not_called()


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

    def test_no_restart_flag_skips_supervision(self, tmp_path):
        args = argparse.Namespace(no_backup=True, no_restart=True)
        with patch.object(updater, "download_update"), \
             patch.object(updater, "extract_and_apply"), \
             patch.object(updater, "update_dependencies"), \
             patch.object(updater, "launch_and_supervise") as mock_launch:
            updater.run_update_mode(args)

        mock_launch.assert_not_called()


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
             patch.object(updater, "launch_and_supervise", side_effect=[False, True]) as mock_launch, \
             patch.object(updater, "find_latest_backup", return_value="/backups/backup_x.zip"), \
             patch.object(updater, "restore_from_backup", return_value=True) as mock_restore, \
             patch.object(updater, "write_status_notice") as mock_notice:
            updater.run_update_mode(args)

        mock_restore.assert_called_once_with("/backups/backup_x.zip")
        assert mock_launch.call_count == 2
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
             patch.object(updater, "launch_and_supervise", return_value=False) as mock_launch, \
             patch.object(updater, "find_latest_backup", return_value="/backups/backup_x.zip"), \
             patch.object(updater, "restore_from_backup", return_value=False), \
             patch.object(updater, "write_status_notice") as mock_notice:
            updater.run_update_mode(args)

        # restore_from_backup returning False means launch_and_supervise is never called a
        # second time -- only the initial (failed) attempt from the top of run_update_mode.
        assert mock_launch.call_count == 1
        assert "could not automatically roll back" in mock_notice.call_args[0][0]

    def test_auto_rollback_success_writes_notice_before_supervise(self, tmp_path):
        """Verify that write_status_notice is called before the second launch_and_supervise,
        so the notice file exists when the bot's on_ready checks for it."""
        args = argparse.Namespace(no_backup=True, no_restart=False)
        call_order = []

        class CallTracker:
            def __init__(self, call_order_list):
                self.call_order = call_order_list
                self.call_count = 0

            def __call__(self, *args, **kwargs):
                self.call_count += 1
                if self.call_count == 1:
                    # First call: unhealthy update
                    return False
                elif self.call_count == 2:
                    # Second call: after rollback
                    self.call_order.append("supervise")
                    return True
                return False

        def track_notice(msg):
            call_order.append("notice")

        tracker = CallTracker(call_order)

        with patch.object(updater, "download_update"), \
             patch.object(updater, "extract_and_apply"), \
             patch.object(updater, "update_dependencies"), \
             patch.object(updater, "launch_and_supervise", side_effect=tracker), \
             patch.object(updater, "find_latest_backup", return_value="/backups/backup_x.zip"), \
             patch.object(updater, "restore_from_backup", return_value=True), \
             patch.object(updater, "write_status_notice", side_effect=track_notice):
            updater.run_update_mode(args)

        # call_order should record notice before supervise, not after
        assert call_order == ["notice", "supervise"]
