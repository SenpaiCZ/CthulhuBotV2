import json
import pytest
from dashboard.app import app
from unittest.mock import AsyncMock, patch

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
async def test_file_browser_route(client):
    """Test that /admin/browse/infodata returns 200 OK and uses new design system in content"""
    await login(client)
    response = await client.get('/admin/browse/infodata')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    main_content = html.split('<main')[1]
    assert 'card-h' in main_content
    assert 'list-group' not in main_content 

@pytest.mark.asyncio
async def test_json_editor_route(client):
    """Test that /admin/edit/infodata/monsters.json returns 200 OK and uses new design system in content"""
    await login(client)
    with patch('dashboard.blueprints.file_browser._load_json_file', new_callable=AsyncMock) as mock_load_json:
        mock_load_json.return_value = {"test": "data"}
        response = await client.get('/admin/edit/infodata/monsters.json')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        main_content = html.split('<main')[1]
        assert 'card-h' in main_content
        # Old buttons should be gone
        assert 'btn-success' not in main_content
        assert 'btn-secondary' not in main_content

@pytest.mark.asyncio
async def test_newspaper_dashboard_route(client):
    """Test that /admin/newspaper returns 200 OK and uses new design system in content"""
    await login(client)
    response = await client.get('/admin/newspaper')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    main_content = html.split('<main')[1]
    assert 'card-h' in main_content
    # Old classes should be gone
    assert 'btn-primary' not in main_content
    # newspaper used 'card bg-dark', we check that specific combination is gone
    assert 'card bg-dark' not in main_content

@pytest.mark.asyncio
async def test_browse_files_invalid_folder_returns_400(client):
    await login(client)
    response = await client.get('/admin/browse/nonsense')
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_edit_file_invalid_folder_returns_400(client):
    await login(client)
    response = await client.get('/admin/edit/nonsense/monsters.json')
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_edit_file_path_traversal_filename_returns_400(client):
    # A bare ".." segment 404s at the routing layer before reaching the
    # handler (Werkzeug's default converter won't match a path separator),
    # so the handler's own "'..' in filename" guard is only reachable via a
    # filename that merely contains ".." as a substring.
    await login(client)
    response = await client.get('/admin/edit/infodata/..monsters.json')
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_file_invalid_folder_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/save/nonsense/monsters.json',
        json={"content": "{}"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_file_path_traversal_filename_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/save/infodata/..monsters.json',
        json={"content": "{}"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_file_invalid_json_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/save/infodata/monsters.json',
        json={"content": "{not valid json"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data['message'] == 'Invalid JSON format'
