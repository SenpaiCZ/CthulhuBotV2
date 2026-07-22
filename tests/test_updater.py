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
