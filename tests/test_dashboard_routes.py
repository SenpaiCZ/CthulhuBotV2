import pytest
from dashboard.app import app
import json
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

@pytest.mark.asyncio
async def test_index_route(client):
    """Test that the index route returns 200 OK and uses index.html"""
    response = await client.get('/')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '<title>' in html  # Basic check for HTML content

@pytest.mark.asyncio
async def test_login_route_get(client):
    """Test that the login route GET returns 200 OK"""
    response = await client.get('/login')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'Password' in html

@pytest.mark.asyncio
async def test_admin_dashboard_redirects_if_not_logged_in(client):
    """Test that admin dashboard redirects to login if not authenticated"""
    response = await client.get('/admin')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

@pytest.mark.asyncio
async def test_api_status_route_returns_json(client):
    """Public route (in _PUBLIC_API) — must work with no session."""
    response = await client.get('/api/status')
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert "is_ready" in data or "status" in data


@pytest.mark.asyncio
async def test_monsters_route_renders_reference_data(client):
    """Public reference page reading infodata/monsters.json via loadnsave."""
    response = await client.get('/monsters')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '<title>' in html


@pytest.mark.asyncio
async def test_render_monster_missing_name_param_returns_400(client):
    response = await client.get('/render/monster')
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_render_monster_known_name_returns_200(client):
    response = await client.get('/render/monster?name=Spawn+of+Abhoth')
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_fonts_redirects_if_not_logged_in(client):
    response = await client.get('/admin/fonts')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_api_fonts_list_unauthorized_without_session(client):
    """/api/* routes require session login except _PUBLIC_API entries."""
    response = await client.get('/api/fonts/list')
    assert response.status_code == 401
