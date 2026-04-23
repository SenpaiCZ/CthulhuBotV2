import pytest
import re
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

EMOJI_PATTERN = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map symbols
    "\U0001f1e0-\U0001f1ff"  # flags (iOS)
    "\U00002702-\U000027b0"
    "\U000024c2-\U0001f251"
    "]+", flags=re.UNICODE
)

def filter_allowed(emojis):
    allowed = ['⚙', '⚖']
    return [e for e in emojis if e not in allowed]

@pytest.mark.asyncio
async def test_monsters_page_no_emojis(client):
    await login(client)
    response = await client.get('/monsters')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    content_only = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
    content_only = re.sub(r'<style.*?</style>', '', content_only, flags=re.DOTALL)
    
    emojis = EMOJI_PATTERN.findall(content_only)
    emojis = filter_allowed(emojis)
    assert not emojis, f"Found emojis in monsters page: {emojis}"

@pytest.mark.asyncio
async def test_spells_page_no_emojis(client):
    await login(client)
    response = await client.get('/spells')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    content_only = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
    emojis = EMOJI_PATTERN.findall(content_only)
    emojis = filter_allowed(emojis)
    assert not emojis, f"Found emojis in spells page: {emojis}"

@pytest.mark.asyncio
async def test_weapons_page_no_emojis(client):
    await login(client)
    response = await client.get('/weapons')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    content_only = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
    emojis = EMOJI_PATTERN.findall(content_only)
    emojis = filter_allowed(emojis)
    assert not emojis, f"Found emojis in weapons page: {emojis}"
