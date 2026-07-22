import os
import zipfile
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
