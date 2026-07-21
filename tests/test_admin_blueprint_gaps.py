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
async def test_admin_design_redirects_if_not_logged_in(client):
    response = await client.get('/admin/design')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_admin_design_authenticated_renders_dashboard(client):
    await login(client)
    with patch('dashboard.blueprints.admin.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {
            'dashboard_theme': 'cthulhu',
            'dashboard_fonts': {'headers': 'Arial', 'body': '', 'special': ''},
            'origin_fonts': {},
        }
        response = await client.get('/admin/design')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert '<title>' in html


@pytest.mark.asyncio
async def test_save_fonts_unauthorized_without_session(client):
    response = await client.post(
        '/api/design/save_fonts',
        json={'headers': 'Arial', 'body': 'Georgia', 'special': 'Cinzel'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_save_fonts_authenticated_persists_settings(client):
    await login(client)
    with patch('dashboard.blueprints.admin.load_settings_async', new_callable=AsyncMock) as mock_load, \
         patch('dashboard.blueprints.admin.save_settings', new_callable=AsyncMock) as mock_save:
        mock_load.return_value = {}
        response = await client.post(
            '/api/design/save_fonts',
            json={'headers': 'Arial', 'body': 'Georgia', 'special': 'Cinzel'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        mock_save.assert_awaited_once()
        saved_settings = mock_save.await_args.args[0]
        assert saved_settings['dashboard_fonts'] == {'headers': 'Arial', 'body': 'Georgia', 'special': 'Cinzel'}


@pytest.mark.asyncio
async def test_save_origin_fonts_unauthorized_without_session(client):
    response = await client.post(
        '/api/design/save_origin_fonts',
        json={'headers': 'Arial', 'body': 'Georgia', 'special': 'Cinzel'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_save_origin_fonts_authenticated_persists_settings(client):
    await login(client)
    with patch('dashboard.blueprints.admin.load_settings_async', new_callable=AsyncMock) as mock_load, \
         patch('dashboard.blueprints.admin.save_settings', new_callable=AsyncMock) as mock_save:
        mock_load.return_value = {}
        response = await client.post(
            '/api/design/save_origin_fonts',
            json={'headers': 'Special Elite', 'body': 'Nanum Myeongjo', 'special': 'Dancing Script'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        saved_settings = mock_save.await_args.args[0]
        assert saved_settings['origin_fonts'] == {
            'headers': 'Special Elite', 'body': 'Nanum Myeongjo', 'special': 'Dancing Script'
        }


@pytest.mark.asyncio
async def test_save_design_unauthorized_without_session(client):
    response = await client.post(
        '/api/design/save',
        json={'theme': 'cthulhu'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_save_design_missing_theme_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/design/save',
        json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data['status'] == 'error'


@pytest.mark.asyncio
async def test_save_design_authenticated_persists_theme(client):
    await login(client)
    with patch('dashboard.blueprints.admin.load_settings_async', new_callable=AsyncMock) as mock_load, \
         patch('dashboard.blueprints.admin.save_settings', new_callable=AsyncMock) as mock_save:
        mock_load.return_value = {}
        response = await client.post(
            '/api/design/save',
            json={'theme': 'delta_green'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        saved_settings = mock_save.await_args.args[0]
        assert saved_settings['dashboard_theme'] == 'delta_green'
