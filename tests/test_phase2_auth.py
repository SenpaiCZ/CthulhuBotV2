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

@pytest.mark.asyncio
async def test_login_route_uses_design_system(client):
    """Test that /login uses new design system"""
    response = await client.get('/login')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    main_content = html.split('<main')[1]
    assert 'card-h' in main_content
    assert 'btn-eld' in main_content
    assert 'btn-primary' not in main_content

@pytest.mark.asyncio
async def test_karma_notification_uses_design_system(client):
    """Test that /render/karma uses modern cthulhu palette (oklch)"""
    # We mock bot.get_guild to avoid errors
    with patch('dashboard.app.app.bot', new_callable=AsyncMock) as mock_bot:
        mock_bot.get_guild.return_value = None
        response = await client.get('/render/karma/123/456')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        # Check for oklch or new void colors
        assert 'oklch' in html or '--void-0' in html
