import json
import os
import zipfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from dashboard.app import app
import dashboard.blueprints.backup as backup


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


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.fixture
def isolated_backup_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "BACKUP_FOLDER", str(tmp_path))
    return tmp_path


def make_zip(folder, name, content=b"data"):
    path = os.path.join(str(folder), name)
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr("file.txt", content)
    return path


@pytest.mark.asyncio
async def test_admin_backup_redirects_if_not_logged_in(client):
    response = await client.get('/admin/backup')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_admin_backup_renders_configured_backup_time(client):
    await login(client)
    with patch.object(backup, 'load_settings_async', new=AsyncMock(return_value={'backup_time': '03:30'})):
        response = await client.get('/admin/backup')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '03:30' in html


@pytest.mark.asyncio
async def test_backup_save_unauthorized_without_session(client):
    response = await client.post(
        '/api/backup/save', json={"backup_time": "04:15"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_backup_save_invalid_time_format_returns_400(client):
    await login(client)
    with patch.object(backup, 'load_settings_async', new=AsyncMock(return_value={})), \
         patch.object(backup, 'save_settings', new=AsyncMock()) as mock_save:
        response = await client.post(
            '/api/backup/save', json={"backup_time": "not-a-time"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 400
    mock_save.assert_not_called()


@pytest.mark.asyncio
async def test_backup_save_persists_valid_time(client):
    await login(client)
    settings = {"admin_password": "x"}
    with patch.object(backup, 'load_settings_async', new=AsyncMock(return_value=settings)), \
         patch.object(backup, 'save_settings', new=AsyncMock()) as mock_save:
        response = await client.post(
            '/api/backup/save', json={"backup_time": "04:15"},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}
    mock_save.assert_awaited_once_with({"admin_password": "x", "backup_time": "04:15"})


@pytest.mark.asyncio
async def test_backup_save_allows_clearing_time(client):
    await login(client)
    settings = {"admin_password": "x", "backup_time": "04:15"}
    with patch.object(backup, 'load_settings_async', new=AsyncMock(return_value=settings)), \
         patch.object(backup, 'save_settings', new=AsyncMock()) as mock_save:
        response = await client.post(
            '/api/backup/save', json={"backup_time": ""},
            headers={"Origin": "http://localhost"},
        )
    assert response.status_code == 200
    mock_save.assert_awaited_once_with({"admin_password": "x", "backup_time": ""})


@pytest.mark.asyncio
async def test_backup_run_unauthorized_without_session(client):
    response = await client.post('/api/backup/run', headers={"Origin": "http://localhost"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_backup_run_bot_not_ready_returns_500(client):
    await login(client)
    with patch('dashboard.app.app.bot', None):
        response = await client.post('/api/backup/run', headers={"Origin": "http://localhost"})
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_backup_run_cog_not_loaded_returns_500(client):
    await login(client)
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = None
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post('/api/backup/run', headers={"Origin": "http://localhost"})
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_backup_run_success_returns_filename(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.perform_backup = AsyncMock(return_value=(True, "backup_20260718.zip"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post('/api/backup/run', headers={"Origin": "http://localhost"})
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success", "filename": "backup_20260718.zip"}


@pytest.mark.asyncio
async def test_backup_run_failure_returns_500_with_message(client):
    await login(client)
    mock_cog = MagicMock()
    mock_cog.perform_backup = AsyncMock(return_value=(False, "Disk full"))
    mock_bot = MagicMock()
    mock_bot.get_cog.return_value = mock_cog
    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.post('/api/backup/run', headers={"Origin": "http://localhost"})
    assert response.status_code == 500
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "error", "message": "Disk full"}


@pytest.mark.asyncio
async def test_backup_files_list_unauthorized_without_session(client):
    response = await client.get('/api/backup/files')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_backup_files_list_sorted_newest_first(client, isolated_backup_folder):
    await login(client)
    older = make_zip(isolated_backup_folder, "old.zip")
    newer = make_zip(isolated_backup_folder, "new.zip")
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    response = await client.get('/api/backup/files')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    names = [f["name"] for f in data]
    assert names == ["new.zip", "old.zip"]
    assert data[0]["size"] > 0


@pytest.mark.asyncio
async def test_backup_files_list_empty_folder_returns_empty_list(client, isolated_backup_folder):
    await login(client)
    response = await client.get('/api/backup/files')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == []


@pytest.mark.asyncio
async def test_backup_files_list_missing_folder_returns_empty_list(client, tmp_path, monkeypatch):
    await login(client)
    missing = tmp_path / "does-not-exist"
    monkeypatch.setattr(backup, "BACKUP_FOLDER", str(missing))
    response = await client.get('/api/backup/files')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == []


@pytest.mark.asyncio
async def test_backup_delete_unauthorized_without_session(client):
    response = await client.post(
        '/api/backup/delete', json={"filename": "gone.zip"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_backup_delete_missing_filename_returns_400(client, isolated_backup_folder):
    await login(client)
    response = await client.post(
        '/api/backup/delete', json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_backup_delete_rejects_non_zip_extension(client, isolated_backup_folder):
    await login(client)
    response = await client.post(
        '/api/backup/delete', json={"filename": "notes.txt"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Invalid file type"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_filename", ["../evil.zip", "sub/evil.zip", "sub\\evil.zip"])
async def test_backup_delete_rejects_path_traversal(client, isolated_backup_folder, bad_filename):
    await login(client)
    response = await client.post(
        '/api/backup/delete', json={"filename": bad_filename},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Invalid filename"


@pytest.mark.asyncio
async def test_backup_delete_file_not_found_returns_404(client, isolated_backup_folder):
    await login(client)
    response = await client.post(
        '/api/backup/delete', json={"filename": "missing.zip"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_backup_delete_removes_existing_file(client, isolated_backup_folder):
    await login(client)
    make_zip(isolated_backup_folder, "gone.zip")

    response = await client.post(
        '/api/backup/delete', json={"filename": "gone.zip"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}
    assert not os.path.exists(os.path.join(str(isolated_backup_folder), "gone.zip"))


@pytest.mark.asyncio
async def test_backup_download_redirects_if_not_logged_in(client):
    response = await client.get('/admin/backup/download/some.zip')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_backup_download_file_not_found_returns_404(client, isolated_backup_folder):
    await login(client)
    response = await client.get('/admin/backup/download/missing.zip')
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_backup_download_rejects_path_traversal(client, isolated_backup_folder):
    await login(client)
    response = await client.get('/admin/backup/download/..%2F..%2Fetc%2Fpasswd')
    assert response.status_code in (400, 404)


@pytest.mark.asyncio
async def test_backup_download_returns_file_contents(client, isolated_backup_folder):
    await login(client)
    make_zip(isolated_backup_folder, "download_me.zip", content=b"payload-bytes")

    response = await client.get('/admin/backup/download/download_me.zip')
    assert response.status_code == 200
    body = await response.get_data(as_text=False)
    assert body[:2] == b"PK"
