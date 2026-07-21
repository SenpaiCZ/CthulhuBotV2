import json
import pytest
from dashboard.app import app
from unittest.mock import AsyncMock, MagicMock, patch


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
async def test_admin_enroll_redirects_if_not_logged_in(client):
    response = await client.get('/admin/enroll')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


@pytest.mark.asyncio
async def test_admin_enroll_authenticated_renders_dashboard(client):
    await login(client)
    response = await client.get('/admin/enroll')
    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert '<title>' in html


@pytest.mark.asyncio
async def test_enroll_data_unauthorized_without_session(client):
    response = await client.get('/api/enroll/data')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_enroll_data_no_bot_returns_empty_guilds(client):
    await login(client)
    with patch('dashboard.blueprints.enroll.app') as mock_app:
        mock_app.bot = None
        response = await client.get('/api/enroll/data')
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"guilds": []}


@pytest.mark.asyncio
async def test_enroll_data_authenticated_lists_guilds_and_roles(client):
    await login(client)

    mock_role_default = MagicMock()
    mock_role_default.is_default.return_value = True
    mock_role_default.managed = False

    mock_role_managed = MagicMock()
    mock_role_managed.is_default.return_value = False
    mock_role_managed.managed = True

    mock_role_normal = MagicMock()
    mock_role_normal.is_default.return_value = False
    mock_role_normal.managed = False
    mock_role_normal.id = 555
    mock_role_normal.name = "Investigator"
    mock_role_normal.color = "#ff0000"

    mock_guild = MagicMock()
    mock_guild.id = 123
    mock_guild.name = "Arkham Society"
    mock_guild.roles = [mock_role_default, mock_role_managed, mock_role_normal]

    with patch('dashboard.blueprints.enroll.app') as mock_app, \
         patch('dashboard.blueprints.enroll.load_enroll_settings', new_callable=AsyncMock) as mock_settings:
        mock_app.bot.guilds = [mock_guild]
        mock_settings.return_value = {
            "123": {"enabled": True, "final_message": "Welcome!", "pages": [{"title": "Intro"}]}
        }

        response = await client.get('/api/enroll/data')
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert len(data["guilds"]) == 1
        guild_data = data["guilds"][0]
        assert guild_data["id"] == "123"
        assert guild_data["name"] == "Arkham Society"
        assert guild_data["roles"] == [{"id": "555", "name": "Investigator", "color": "#ff0000"}]
        assert guild_data["config"] == {
            "enabled": True, "final_message": "Welcome!", "pages": [{"title": "Intro"}]
        }


@pytest.mark.asyncio
async def test_enroll_save_unauthorized_without_session(client):
    response = await client.post(
        '/api/enroll/save',
        json={'guild_id': '123'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_enroll_save_missing_guild_id_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/enroll/save',
        json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_enroll_save_authenticated_persists_settings(client):
    await login(client)
    with patch('dashboard.blueprints.enroll.load_enroll_settings', new_callable=AsyncMock) as mock_load, \
         patch('dashboard.blueprints.enroll.save_enroll_settings', new_callable=AsyncMock) as mock_save:
        mock_load.return_value = {}
        response = await client.post(
            '/api/enroll/save',
            json={
                'guild_id': '123',
                'enabled': True,
                'final_message': 'Thanks for joining!',
                'pages': [{"title": "Intro"}],
            },
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"status": "success"}
        mock_save.assert_awaited_once_with({
            "123": {
                "enabled": True,
                "final_message": "Thanks for joining!",
                "pages": [{"title": "Intro"}],
            }
        })
