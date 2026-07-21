import io
import json
import pytest
from dashboard.app import app
from unittest.mock import AsyncMock, patch
from werkzeug.datastructures import FileStorage


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


@pytest.mark.asyncio
async def test_admin_fonts_authenticated_renders_dashboard(client):
    await login(client)
    response = await client.get('/admin/fonts')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '<title>' in html


@pytest.mark.asyncio
async def test_fonts_list_authenticated_returns_configured_fonts(client, tmp_path):
    await login(client)
    (tmp_path / 'Cinzel.ttf').write_bytes(b'fake-font')
    (tmp_path / 'ignored.txt').write_text('not a font')
    with patch('dashboard.blueprints.fonts_admin.FONTS_FOLDER', str(tmp_path)), \
         patch('dashboard.blueprints.fonts_admin.load_fonts_config', new_callable=AsyncMock) as mock_cfg:
        mock_cfg.return_value = {'Cinzel.ttf': 'Display'}
        response = await client.get('/api/fonts/list')
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"fonts": [{"filename": "Cinzel.ttf", "category": "Display"}]}


@pytest.mark.asyncio
async def test_fonts_upload_no_files_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/fonts/upload',
        form={'category': 'Decorative'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_fonts_upload_authenticated_saves_file_and_config(client, tmp_path):
    await login(client)
    upload = FileStorage(stream=io.BytesIO(b'fake-font-bytes'), filename='Special Elite.ttf')
    with patch('dashboard.blueprints.fonts_admin.FONTS_FOLDER', str(tmp_path)), \
         patch('dashboard.blueprints.fonts_admin.load_fonts_config', new_callable=AsyncMock) as mock_load_cfg, \
         patch('dashboard.blueprints.fonts_admin.save_fonts_config', new_callable=AsyncMock) as mock_save_cfg:
        mock_load_cfg.return_value = {}
        response = await client.post(
            '/api/fonts/upload',
            form={'category': 'Handwriting'},
            files={'files': upload},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data['status'] == 'success'
        assert len(list(tmp_path.iterdir())) == 1
        mock_save_cfg.assert_awaited_once()
        saved_config = mock_save_cfg.await_args.args[0]
        assert list(saved_config.values()) == ['Handwriting']


@pytest.mark.asyncio
async def test_fonts_delete_missing_filename_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/fonts/delete',
        json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_fonts_delete_rejects_path_traversal(client):
    await login(client)
    response = await client.post(
        '/api/fonts/delete',
        json={'filename': '../../etc/passwd'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_fonts_delete_not_found_returns_404(client, tmp_path):
    await login(client)
    with patch('dashboard.blueprints.fonts_admin.FONTS_FOLDER', str(tmp_path)):
        response = await client.post(
            '/api/fonts/delete',
            json={'filename': 'Nonexistent.ttf'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_fonts_delete_authenticated_removes_file_and_config_entry(client, tmp_path):
    await login(client)
    (tmp_path / 'Cinzel.ttf').write_bytes(b'fake-font')
    with patch('dashboard.blueprints.fonts_admin.FONTS_FOLDER', str(tmp_path)), \
         patch('dashboard.blueprints.fonts_admin.load_fonts_config', new_callable=AsyncMock) as mock_load_cfg, \
         patch('dashboard.blueprints.fonts_admin.save_fonts_config', new_callable=AsyncMock) as mock_save_cfg:
        mock_load_cfg.return_value = {'Cinzel.ttf': 'Display'}
        response = await client.post(
            '/api/fonts/delete',
            json={'filename': 'Cinzel.ttf'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        assert not (tmp_path / 'Cinzel.ttf').exists()
        mock_save_cfg.assert_awaited_once_with({})


@pytest.mark.asyncio
async def test_fonts_update_category_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/fonts/update_category',
        json={'filename': 'Cinzel.ttf'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_fonts_update_category_authenticated_persists_category(client):
    await login(client)
    with patch('dashboard.blueprints.fonts_admin.load_fonts_config', new_callable=AsyncMock) as mock_load_cfg, \
         patch('dashboard.blueprints.fonts_admin.save_fonts_config', new_callable=AsyncMock) as mock_save_cfg:
        mock_load_cfg.return_value = {}
        response = await client.post(
            '/api/fonts/update_category',
            json={'filename': 'Cinzel.ttf', 'category': 'Display'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        mock_save_cfg.assert_awaited_once_with({'Cinzel.ttf': 'Display'})
