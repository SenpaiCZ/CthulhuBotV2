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


GRIMOIRE_CASES = [
    pytest.param('load_deities_data', '/deities', {"deities": [{"deity_entry": {"name": "Cthulhu"}}]}, "Cthulhu", id="deities"),
    pytest.param('load_archetype_data', '/archetypes', {"Adventurer": {"description": "A brave soul.", "adjustments": []}}, "Adventurer", id="archetypes"),
    pytest.param('load_pulp_talents_data', '/pulp_talents', {"Physical": ["**Keen Vision**: gain a bonus die to Spot Hidden rolls"]}, "Keen Vision", id="pulp_talents"),
    pytest.param('load_madness_insane_talent_data', '/insane_talents', {"Insane strength": "Gain a bonus die to a STR roll."}, "Insane strength", id="insane_talents"),
    pytest.param('load_manias_data', '/manias', {"Ablutomania": "Compulsion for washing oneself."}, "Ablutomania", id="manias"),
    pytest.param('load_phobias_data', '/phobias', {"Ablutophobia": "Fear of washing or bathing."}, "Ablutophobia", id="phobias"),
    pytest.param('load_poisons_data', '/poisons', {"Arsenic": {"Onset Time": "Minutes", "Symptoms": "Death", "Damage": "1D10", "Note": "Bad."}}, "Arsenic", id="poisons"),
    pytest.param('load_skills_data', '/skills', {"Accounting": "Understanding financial operations."}, "Accounting", id="skills"),
    pytest.param('load_inventions_data', '/inventions', {"1920s": ["The radio becomes popular."]}, "1920s", id="inventions"),
    pytest.param('load_years_data', '/years', {"1920": ["Prohibition begins."]}, "1920", id="years"),
    pytest.param('load_occupations_data', '/occupations', {"Antiquarian": {"description": "Old stuff.", "skills": "History"}}, "Antiquarian", id="occupations"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("loader_name,path,payload,expected_text", GRIMOIRE_CASES)
async def test_grimoire_reference_route_renders_data(client, loader_name, path, payload, expected_text):
    with patch(f'dashboard.blueprints.grimoire.{loader_name}', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = payload
        response = await client.get(path)
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert expected_text in html


@pytest.mark.asyncio
async def test_grimoire_deities_route_empty_data_renders_200(client):
    with patch('dashboard.blueprints.grimoire.load_deities_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"deities": []}
        response = await client.get('/deities')
        assert response.status_code == 200
