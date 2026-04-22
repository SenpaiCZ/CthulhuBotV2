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
async def test_render_character_uses_palette(client):
    """Test character render uses oklch palette"""
    with patch('dashboard.app.load_player_stats', new_callable=AsyncMock) as mock_stats:
        mock_stats.return_value = {"123": {"456": {"NAME": "Harvey Walters"}}}
        response = await client.get('/render/character/123/456')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        # Check for oklch colors in style
        assert 'oklch' in html or '--sigil' in html

@pytest.mark.asyncio
async def test_render_monster_uses_palette(client):
    """Test monster render uses oklch palette"""
    with patch('dashboard.app.load_monsters_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"monsters": [{
            "monster_entry": {
                "name": "Deep One",
                "derived_stats": {"hit_points": 10, "damage_bonus": "0", "build": 0, "magic_points": 10, "move": 8},
                "combat": {"attacks_per_round": 1, "dodge": {"success_chance": 30}}
            }
        }]}
        response = await client.get('/render/monster?name=Deep%20One')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'oklch' in html or '--sigil' in html

@pytest.mark.asyncio
async def test_render_archetype_uses_palette(client):
    """Test archetype render uses oklch palette"""
    with patch('dashboard.app.load_archetype_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Adventurer": {"description": "A brave soul.", "adjustments": []}}
        response = await client.get('/render/archetype?name=Adventurer')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'oklch' in html or '--sigil' in html

@pytest.mark.asyncio
async def test_render_occupation_uses_palette(client):
    """Test occupation render uses oklch palette"""
    with patch('dashboard.app.load_occupations_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Antiquarian": {"description": "Old stuff.", "skills": "History"}}
        response = await client.get('/render/occupation?name=Antiquarian')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'oklch' in html or '--sigil' in html

@pytest.mark.asyncio
async def test_render_poison_uses_palette(client):
    """Test poison render uses oklch palette"""
    with patch('dashboard.app.load_poisons_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Arsenic": {"Onset Time": "Minutes", "Symptoms": "Death", "Damage": "1D10", "Note": "Bad."}}
        response = await client.get('/render/poison?name=Arsenic')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'oklch' in html or '--sigil' in html
