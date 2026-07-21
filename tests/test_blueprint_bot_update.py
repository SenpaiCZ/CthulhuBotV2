import os
import sys
import subprocess

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from dashboard.app import app
import dashboard.blueprints.bot_update as bot_update


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


@pytest.fixture(autouse=True)
def reset_bot(monkeypatch):
    # admin_update_bot() touches app.bot; keep it None unless a test opts in.
    monkeypatch.setattr(app, "bot", None)


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.mark.asyncio
async def test_admin_update_unauthorized_without_login(client):
    """Not logged in -> rejected before the destructive logic ever runs."""
    response = await client.post('/api/admin/update', json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_update_missing_updater_script_returns_500(client):
    await login(client)
    with patch('dashboard.blueprints.bot_update.os.path.exists', return_value=False), \
         patch('dashboard.blueprints.bot_update.subprocess.Popen') as mock_popen:
        response = await client.post(
            '/api/admin/update', json={}, headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 500
        data = await response.get_json()
        assert data == {"status": "error", "message": "Updater script not found"}
        mock_popen.assert_not_called()


@pytest.mark.asyncio
async def test_admin_update_success_spawns_updater_without_infodata_flag(client):
    """
    subprocess.Popen and app.add_background_task (which schedules sys.exit via
    shutdown_process) are mocked so the test process is never actually killed or
    replaced -- we only verify the *decision logic*: the right command is built
    and the right shutdown hook is registered, not that a restart truly happens.
    """
    await login(client)
    with patch('dashboard.blueprints.bot_update.os.path.exists', return_value=True), \
         patch('dashboard.blueprints.bot_update.subprocess.Popen') as mock_popen, \
         patch.object(app, 'add_background_task') as mock_add_bg:
        response = await client.post(
            '/api/admin/update', json={}, headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert data == {"status": "success", "message": "Update started. Bot is restarting..."}

        expected_cmd = [sys.executable, "updater.py", str(os.getpid())]
        assert mock_popen.call_count == 1
        called_cmd = mock_popen.call_args[0][0]
        assert called_cmd == expected_cmd
        if os.name == 'nt':
            assert mock_popen.call_args.kwargs.get('creationflags') == subprocess.CREATE_NEW_CONSOLE
        else:
            assert mock_popen.call_args.kwargs.get('start_new_session') is True

        mock_add_bg.assert_called_once_with(bot_update.shutdown_process)


@pytest.mark.asyncio
async def test_admin_update_appends_infodata_flag_when_requested(client):
    await login(client)
    with patch('dashboard.blueprints.bot_update.os.path.exists', return_value=True), \
         patch('dashboard.blueprints.bot_update.subprocess.Popen') as mock_popen, \
         patch.object(app, 'add_background_task'):
        response = await client.post(
            '/api/admin/update',
            json={"update_infodata": True},
            headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 200
        called_cmd = mock_popen.call_args[0][0]
        assert called_cmd == [sys.executable, "updater.py", str(os.getpid()), "--update-infodata"]


@pytest.mark.asyncio
async def test_admin_update_closes_bot_when_present(client, monkeypatch):
    await login(client)
    fake_bot = AsyncMock()
    monkeypatch.setattr(app, "bot", fake_bot)

    with patch('dashboard.blueprints.bot_update.os.path.exists', return_value=True), \
         patch('dashboard.blueprints.bot_update.subprocess.Popen'), \
         patch.object(app, 'add_background_task'):
        response = await client.post(
            '/api/admin/update', json={}, headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 200
        fake_bot.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_update_popen_failure_returns_500_with_error_message(client):
    await login(client)
    with patch('dashboard.blueprints.bot_update.os.path.exists', return_value=True), \
         patch('dashboard.blueprints.bot_update.subprocess.Popen', side_effect=OSError("spawn failed")), \
         patch.object(app, 'add_background_task') as mock_add_bg:
        response = await client.post(
            '/api/admin/update', json={}, headers={"Origin": "http://localhost"}
        )
        assert response.status_code == 500
        data = await response.get_json()
        assert data == {"status": "error", "message": "spawn failed"}
        # Must not proceed to schedule a shutdown if the updater never launched.
        mock_add_bg.assert_not_called()
