import io
import zipfile

import pytest
from unittest.mock import AsyncMock, patch
from werkzeug.datastructures import FileStorage

import loadnsave
from dashboard.app import app
import dashboard.blueprints.soundboard as soundboard


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('dashboard.app.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'admin_password': 'testpassword',
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': '', 'body': '', 'special': ''},
            'origin_fonts': {'headers': '', 'body': '', 'special': ''}
        }
        yield


@pytest.fixture(autouse=True)
def reset_bot(monkeypatch):
    monkeypatch.setattr(app, "bot", None)


@pytest.fixture
def isolated_soundboard_env(tmp_path, monkeypatch):
    soundboard_dir = tmp_path / "soundboard"
    soundboard_dir.mkdir()
    # SOUNDBOARD_FOLDER is imported BY VALUE (`from dashboard.state import
    # SOUNDBOARD_FOLDER`), so the blueprint's own module-level binding must be
    # patched directly -- patching dashboard.state.SOUNDBOARD_FOLDER has no effect
    # on code in soundboard.py.
    monkeypatch.setattr(soundboard, "SOUNDBOARD_FOLDER", str(soundboard_dir))
    monkeypatch.setattr(soundboard, "server_volumes", {})
    monkeypatch.setattr(soundboard, "guild_mixers", {})

    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path / "data"))
    monkeypatch.setattr(loadnsave, "_SOUNDBOARD_SETTINGS_CACHE", None)
    return soundboard_dir


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


# --- /api/soundboard/folder/color ---

@pytest.mark.asyncio
async def test_folder_color_missing_arguments_returns_400(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/folder/color', json={"folder_name": "Foo"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_folder_color_persists_setting(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/folder/color',
        json={"folder_name": "Chants", "color": "#ff0000"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_soundboard_settings()
    assert reloaded["folder_colors"]["Chants"] == "#ff0000"


# --- /api/soundboard/file/settings ---

@pytest.mark.asyncio
async def test_file_settings_blocks_path_traversal(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/file/settings',
        json={"file_path": "../outside.mp3", "volume": 50, "loop": False},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_file_settings_stores_non_default_values(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/file/settings',
        json={"file_path": "sound.mp3", "volume": 60, "loop": True},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_soundboard_settings()
    assert reloaded["files"]["sound.mp3"] == {"volume": 60, "loop": True}


@pytest.mark.asyncio
async def test_file_settings_removes_entry_when_reset_to_defaults(client, isolated_soundboard_env):
    await login(client)
    await loadnsave.save_soundboard_settings({"files": {"sound.mp3": {"volume": 60, "loop": True}}})

    response = await client.post(
        '/api/soundboard/file/settings',
        json={"file_path": "sound.mp3", "volume": 100, "loop": False},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    reloaded = await loadnsave.load_soundboard_settings()
    assert "files" not in reloaded  # cleaned up because it became empty


# --- /api/soundboard/file/favorite ---

@pytest.mark.asyncio
async def test_file_favorite_add_and_remove(client, isolated_soundboard_env):
    await login(client)
    add_response = await client.post(
        '/api/soundboard/file/favorite',
        json={"file_path": "sound.mp3", "favorited": True},
        headers={"Origin": "http://localhost"}
    )
    assert add_response.status_code == 200
    settings = await loadnsave.load_soundboard_settings()
    assert settings["favorites"] == ["sound.mp3"]

    remove_response = await client.post(
        '/api/soundboard/file/favorite',
        json={"file_path": "sound.mp3", "favorited": False},
        headers={"Origin": "http://localhost"}
    )
    assert remove_response.status_code == 200
    settings = await loadnsave.load_soundboard_settings()
    assert settings["favorites"] == []


# --- /api/soundboard/folder/create, /delete, /rename ---

@pytest.mark.asyncio
async def test_create_folder_missing_name_returns_400(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/folder/create', json={}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_folder_sanitizes_name_and_creates_directory(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/folder/create',
        json={"folder_name": "My Chants!!"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert data["folder"] == "My_Chants__"
    assert (isolated_soundboard_env / "My_Chants__").is_dir()


@pytest.mark.asyncio
async def test_create_folder_rejects_existing(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "Existing").mkdir()
    response = await client.post(
        '/api/soundboard/folder/create',
        json={"folder_name": "Existing"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_folder_protects_root(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/folder/delete', json={"folder_name": ""}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_folder_removes_directory(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "Removable").mkdir()

    response = await client.post(
        '/api/soundboard/folder/delete',
        json={"folder_name": "Removable"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert not (isolated_soundboard_env / "Removable").exists()


@pytest.mark.asyncio
async def test_rename_folder_updates_settings_keys(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "OldName").mkdir()
    await loadnsave.save_soundboard_settings({
        "folder_colors": {"OldName": "#123456"},
        "files": {"OldName/song.mp3": {"volume": 80, "loop": False}},
        "favorites": ["OldName/song.mp3"],
    })

    response = await client.post(
        '/api/soundboard/folder/rename',
        json={"old_name": "OldName", "new_name": "NewName"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert (isolated_soundboard_env / "NewName").is_dir()

    reloaded = await loadnsave.load_soundboard_settings()
    assert reloaded["folder_colors"]["NewName"] == "#123456"
    assert "NewName/song.mp3" in reloaded["files"]
    assert reloaded["favorites"] == ["NewName/song.mp3"]


# --- /api/soundboard/file/delete, /file/rename ---

@pytest.mark.asyncio
async def test_delete_file_blocks_path_traversal(client, isolated_soundboard_env):
    await login(client)
    response = await client.post(
        '/api/soundboard/file/delete',
        json={"file_path": "../outside.mp3"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_file_removes_file_and_settings_entry(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "sound.mp3").write_bytes(b"data")
    await loadnsave.save_soundboard_settings({"files": {"sound.mp3": {"volume": 50, "loop": False}}})

    response = await client.post(
        '/api/soundboard/file/delete',
        json={"file_path": "sound.mp3"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    assert not (isolated_soundboard_env / "sound.mp3").exists()
    reloaded = await loadnsave.load_soundboard_settings()
    assert "sound.mp3" not in reloaded.get("files", {})


@pytest.mark.asyncio
async def test_rename_file_preserves_extension_and_updates_settings(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "old.mp3").write_bytes(b"data")
    await loadnsave.save_soundboard_settings({
        "files": {"old.mp3": {"volume": 70, "loop": True}},
        "favorites": ["old.mp3"],
    })

    response = await client.post(
        '/api/soundboard/file/rename',
        json={"file_path": "old.mp3", "new_name": "new name!!"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert data["new_path"] == "new_name__.mp3"
    assert (isolated_soundboard_env / "new_name__.mp3").exists()

    reloaded = await loadnsave.load_soundboard_settings()
    assert reloaded["files"]["new_name__.mp3"] == {"volume": 70, "loop": True}
    assert reloaded["favorites"] == ["new_name__.mp3"]


@pytest.mark.asyncio
async def test_rename_file_rejects_existing_target(client, isolated_soundboard_env):
    await login(client)
    (isolated_soundboard_env / "old.mp3").write_bytes(b"data")
    (isolated_soundboard_env / "new.mp3").write_bytes(b"data")

    response = await client.post(
        '/api/soundboard/file/rename',
        json={"file_path": "old.mp3", "new_name": "new"},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 400


# --- /api/soundboard/upload ---

@pytest.mark.asyncio
async def test_upload_rejects_disallowed_extension(client, isolated_soundboard_env):
    await login(client)
    file_storage = FileStorage(stream=io.BytesIO(b"not audio"), filename="malware.exe")

    response = await client.post(
        '/api/soundboard/upload',
        form={"folder": ""},
        files={"files": file_storage},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert any("Skipped" in r for r in data["results"])
    assert not (isolated_soundboard_env / "malware.exe").exists()


@pytest.mark.asyncio
async def test_upload_saves_allowed_audio_file(client, isolated_soundboard_env):
    await login(client)
    file_storage = FileStorage(stream=io.BytesIO(b"fake-mp3-bytes"), filename="new sound!!.mp3")

    response = await client.post(
        '/api/soundboard/upload',
        form={"folder": ""},
        files={"files": file_storage},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert any("Uploaded" in r for r in data["results"])
    assert (isolated_soundboard_env / "new_sound__.mp3").exists()


@pytest.mark.asyncio
async def test_upload_extracts_zip_of_audio_files(client, isolated_soundboard_env):
    await login(client)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr("track.mp3", b"fake-mp3-bytes")
        zf.writestr("notes.txt", b"ignored, not an audio extension")
    buf.seek(0)
    file_storage = FileStorage(stream=buf, filename="pack.zip")

    response = await client.post(
        '/api/soundboard/upload',
        form={"folder": ""},
        files={"files": file_storage},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200
    data = await response.get_json()
    assert any("Unzipped" in r for r in data["results"])
    assert (isolated_soundboard_env / "pack" / "track.mp3").exists()
    assert not (isolated_soundboard_env / "pack" / "notes.txt").exists()
    # The temp zip must be cleaned up after extraction.
    assert not (isolated_soundboard_env / "temp_pack.zip").exists()
