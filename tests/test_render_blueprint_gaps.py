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


NAME_REQUIRED_ROUTES = [
    '/render/deity', '/render/spell', '/render/weapon', '/render/pulp_talent',
    '/render/insane_talent', '/render/mania', '/render/phobia', '/render/skill',
    '/render/invention', '/render/year',
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", NAME_REQUIRED_ROUTES)
async def test_render_routes_missing_name_param_returns_400(client, path):
    response = await client.get(path)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_render_deity_known_name_returns_200(client):
    with patch('dashboard.blueprints.render.load_deities_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"deities": [{"deity_entry": {"name": "Cthulhu", "classification": "Great Old One"}}]}
        response = await client.get('/render/deity?name=Cthulhu')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'Cthulhu' in html


@pytest.mark.asyncio
async def test_render_deity_unknown_name_returns_404(client):
    with patch('dashboard.blueprints.render.load_deities_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"deities": []}
        response = await client.get('/render/deity?name=Nobody')
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_render_spell_known_name_returns_200(client):
    with patch('dashboard.blueprints.render.load_spells_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"spells": [{"spell_entry": {"name": "Wither Limb", "category": "Contact"}}]}
        response = await client.get('/render/spell?name=Wither+Limb')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'Wither Limb' in html


@pytest.mark.asyncio
async def test_render_spell_unknown_name_returns_404(client):
    with patch('dashboard.blueprints.render.load_spells_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"spells": []}
        response = await client.get('/render/spell?name=Nobody')
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_render_weapon_known_name_returns_200(client):
    with patch('dashboard.blueprints.render.load_weapons_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Knife": {"damage": "1D4", "range": "Touch"}}
        response = await client.get('/render/weapon?name=Knife')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'Knife' in html


@pytest.mark.asyncio
async def test_render_weapon_case_insensitive_lookup(client):
    with patch('dashboard.blueprints.render.load_weapons_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Knife": {"damage": "1D4", "range": "Touch"}}
        response = await client.get('/render/weapon?name=KNIFE')
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_render_weapon_unknown_name_returns_404(client):
    with patch('dashboard.blueprints.render.load_weapons_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Knife": {"damage": "1D4"}}
        response = await client.get('/render/weapon?name=Nonexistent')
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_render_pulp_talent_known_name_returns_200(client):
    with patch('dashboard.blueprints.render.load_pulp_talents_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Physical": ["**Keen Vision**: gain a bonus die to Spot Hidden rolls"]}
        response = await client.get('/render/pulp_talent?name=Keen+Vision')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'Keen Vision' in html
        assert 'bonus die to Spot Hidden' in html


@pytest.mark.asyncio
async def test_render_pulp_talent_unknown_name_returns_404(client):
    with patch('dashboard.blueprints.render.load_pulp_talents_data', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {"Physical": ["**Keen Vision**: gain a bonus die to Spot Hidden rolls"]}
        response = await client.get('/render/pulp_talent?name=Nonexistent')
        assert response.status_code == 404


SIMPLE_ENTRY_CASES = [
    pytest.param('load_madness_insane_talent_data', '/render/insane_talent', "Insane strength", id="insane_talent"),
    pytest.param('load_manias_data', '/render/mania', "Ablutomania", id="mania"),
    pytest.param('load_phobias_data', '/render/phobia', "Ablutophobia", id="phobia"),
    pytest.param('load_skills_data', '/render/skill', "Accounting", id="skill"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("loader_name,path,key", SIMPLE_ENTRY_CASES)
async def test_render_simple_entry_routes_known_name_returns_200(client, loader_name, path, key):
    # NOTE: render_simple_entry.html renders `{{ content }}`, but these routes pass
    # `description=` (not `content=`) -- so only the title/type render; the description
    # text itself is silently dropped. This test asserts current behavior, not intent.
    with patch(f'dashboard.blueprints.render.{loader_name}', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {key: "Some description text."}
        response = await client.get(f'{path}?name={key}')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert key in html


@pytest.mark.asyncio
@pytest.mark.parametrize("loader_name,path,key", SIMPLE_ENTRY_CASES)
async def test_render_simple_entry_routes_unknown_name_returns_404(client, loader_name, path, key):
    with patch(f'dashboard.blueprints.render.{loader_name}', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {key: "Some description text."}
        response = await client.get(f'{path}?name=Nonexistent')
        assert response.status_code == 404


TIMELINE_CASES = [
    pytest.param('load_inventions_data', '/render/invention', "1920s", ["The radio becomes popular."], id="invention"),
    pytest.param('load_years_data', '/render/year', "1920", ["Prohibition begins in the United States."], id="year"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("loader_name,path,key,events", TIMELINE_CASES)
async def test_render_timeline_routes_known_key_returns_200(client, loader_name, path, key, events):
    with patch(f'dashboard.blueprints.render.{loader_name}', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {key: events}
        response = await client.get(f'{path}?name={key}')
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert key in html
        assert events[0] in html


@pytest.mark.asyncio
@pytest.mark.parametrize("loader_name,path,key,events", TIMELINE_CASES)
async def test_render_timeline_routes_unknown_key_returns_404(client, loader_name, path, key, events):
    with patch(f'dashboard.blueprints.render.{loader_name}', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {key: events}
        response = await client.get(f'{path}?name=Nonexistent')
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_render_morse_default_encodes_sos(client):
    response = await client.get('/render/morse')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '.../---/...' in html


@pytest.mark.asyncio
async def test_render_morse_custom_text(client):
    response = await client.get('/render/morse?text=HI')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '..../..' in html


@pytest.mark.asyncio
async def test_render_newspaper_defaults(client):
    response = await client.get('/render/newspaper')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'Arkham' in html
    assert 'The Arkham Advertiser' in html


@pytest.mark.asyncio
async def test_render_newspaper_custom_params(client):
    response = await client.get('/render/newspaper?headline=Doom&body=It+happened&city=Innsmouth')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'DOOM' in html.upper()
    assert 'Innsmouth' in html


@pytest.mark.asyncio
async def test_render_telegram_defaults(client):
    response = await client.get('/render/telegram')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'STOP' in html


@pytest.mark.asyncio
async def test_render_telegram_custom_params(client):
    response = await client.get('/render/telegram?body=help&sender=investigator')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'HELP' in html
    assert 'INVESTIGATOR' in html


@pytest.mark.asyncio
async def test_render_letter_defaults(client):
    response = await client.get('/render/letter')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'Dearest Friend' in html


@pytest.mark.asyncio
async def test_render_letter_custom_params(client):
    response = await client.get('/render/letter?body=Come+quickly&signature=Yours')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'Come quickly' in html
    assert 'Yours' in html


@pytest.mark.asyncio
async def test_render_script_default_text(client):
    response = await client.get('/render/script')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    # apostrophes are HTML-escaped by the template, so match substrings without them
    assert "nglui mglw" in html
    assert "Cthulhu R" in html


@pytest.mark.asyncio
async def test_render_script_custom_text(client):
    response = await client.get('/render/script?text=Iaaaa')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert 'Iaaaa' in html
