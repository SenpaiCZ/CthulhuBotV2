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
