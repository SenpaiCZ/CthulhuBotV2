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
