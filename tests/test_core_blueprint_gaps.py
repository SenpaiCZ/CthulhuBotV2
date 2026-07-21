import io
import json
import pytest
from dashboard.app import app
from unittest.mock import AsyncMock, patch
from werkzeug.datastructures import FileStorage


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
async def test_login_post_correct_password_redirects_to_admin(client):
    # core.py imports load_settings_async directly (`from loadnsave import
    # load_settings_async`), so the autouse mock_dependencies fixture -- which
    # only patches dashboard.app.load_settings_async -- does not cover this
    # module's own binding. It must be patched separately here.
    with patch('dashboard.blueprints.core.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {'admin_password': 'testpassword'}
        response = await client.post(
            '/login',
            form={'password': 'testpassword'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 302
        assert '/admin' in response.headers['Location']
        async with client.session_transaction() as sess:
            assert sess.get('logged_in') is True


@pytest.mark.asyncio
async def test_login_post_wrong_password_renders_error(client):
    with patch('dashboard.blueprints.core.load_settings_async', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = {'admin_password': 'testpassword'}
        response = await client.post(
            '/login',
            form={'password': 'wrongpassword'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        html = await response.get_data(as_text=True)
        assert 'Invalid Password' in html
        async with client.session_transaction() as sess:
            assert not sess.get('logged_in')


@pytest.mark.asyncio
async def test_api_images_check_missing_args_returns_400(client):
    # /api/images/check is not in _PUBLIC_API, so it needs a session even
    # though the handler itself does not call is_admin().
    await login(client)
    response = await client.get('/api/images/check')
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data['found'] is False


@pytest.mark.asyncio
async def test_api_images_check_found(client):
    await login(client)
    with patch('dashboard.blueprints.core.get_image_url', return_value='/images/monster/deep_one.png') as mock_url:
        response = await client.get('/api/images/check?type_slug=monster&name=Deep+One')
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"found": True, "url": "/images/monster/deep_one.png"}
        mock_url.assert_called_once_with('monster', 'Deep One')


@pytest.mark.asyncio
async def test_api_images_check_not_found(client):
    await login(client)
    with patch('dashboard.blueprints.core.get_image_url', return_value=None):
        response = await client.get('/api/images/check?type_slug=monster&name=Nonexistent')
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data == {"found": False}


@pytest.mark.asyncio
async def test_api_images_upload_unauthorized_without_session(client):
    response = await client.post(
        '/api/images/upload',
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_images_upload_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/images/upload',
        form={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data['status'] == 'error'


@pytest.mark.asyncio
async def test_api_images_upload_success(client, tmp_path):
    await login(client)
    upload = FileStorage(stream=io.BytesIO(b'fake-image-bytes'), filename='deepone.png')
    with patch('dashboard.blueprints.core.IMAGES_FOLDER', str(tmp_path)):
        response = await client.post(
            '/api/images/upload',
            form={'type_slug': 'monster', 'name': 'Deep One'},
            files={'file': upload},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data['status'] == 'success'
        assert data['url'].startswith('/images/monster/')
        assert (tmp_path / 'monster').exists()


@pytest.mark.asyncio
async def test_api_images_delete_unauthorized_without_session(client):
    response = await client.post(
        '/api/images/delete',
        json={'type_slug': 'monster', 'name': 'Deep One'},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_images_delete_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/images/delete',
        json={},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_api_images_delete_not_found_returns_404(client, tmp_path):
    await login(client)
    with patch('dashboard.blueprints.core.IMAGES_FOLDER', str(tmp_path)):
        response = await client.post(
            '/api/images/delete',
            json={'type_slug': 'monster', 'name': 'Nonexistent'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_images_delete_success(client, tmp_path):
    await login(client)
    target_dir = tmp_path / 'monster'
    target_dir.mkdir()
    (target_dir / 'Deep_One.png').write_bytes(b'fake')
    with patch('dashboard.blueprints.core.IMAGES_FOLDER', str(tmp_path)), \
         patch('dashboard.blueprints.core.sanitize_filename', side_effect=lambda x: x.replace(' ', '_')):
        response = await client.post(
            '/api/images/delete',
            json={'type_slug': 'monster', 'name': 'Deep One'},
            headers={"Origin": "http://localhost"},
        )
        assert response.status_code == 200
        data = json.loads(await response.get_data(as_text=True))
        assert data['status'] == 'success'
        assert not (target_dir / 'Deep_One.png').exists()
