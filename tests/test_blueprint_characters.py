import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import loadnsave
from dashboard.app import app


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


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_PLAYER_STATS_CACHE", None)
    monkeypatch.setattr(loadnsave, "_RETIRED_CHARACTERS_CACHE", None)
    return tmp_path


CHAR_TEMPLATE = {
    "NAME": "Old Man Henderson",
    "Backstory": {
        "Personal Description": [], "Ideology/Beliefs": [], "Significant People": [],
        "Meaningful Locations": [], "Treasured Possessions": [], "Traits": []
    },
    "Connections": []
}


@pytest.mark.asyncio
async def test_characters_route_is_public_and_resolves_user_names(client, isolated_data_dir):
    await loadnsave.save_player_stats({"123": {"456": dict(CHAR_TEMPLATE)}})

    mock_user = MagicMock()
    mock_user.display_name = "PlayerOne"
    mock_bot = MagicMock()
    mock_bot.get_user.side_effect = lambda uid: mock_user if uid == 456 else None

    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/characters')

    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert "PlayerOne" in html


@pytest.mark.asyncio
async def test_characters_route_falls_back_to_user_id_when_unresolvable(client, isolated_data_dir):
    await loadnsave.save_player_stats({"123": {"456": dict(CHAR_TEMPLATE)}})
    mock_bot = MagicMock()
    mock_bot.get_user.return_value = None

    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/characters')

    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert "User 456" in html


@pytest.mark.asyncio
async def test_characters_route_skips_name_resolution_when_bot_not_initialized(client, isolated_data_dir):
    await loadnsave.save_player_stats({"123": {"456": dict(CHAR_TEMPLATE)}})

    with patch('dashboard.app.app.bot', None):
        response = await client.get('/characters')

    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert "Old Man Henderson" in html


@pytest.mark.asyncio
async def test_characters_route_handles_non_numeric_user_id_gracefully(client, isolated_data_dir):
    await loadnsave.save_player_stats({"123": {"not-a-number": dict(CHAR_TEMPLATE)}})
    mock_bot = MagicMock()
    mock_bot.get_user.side_effect = lambda uid: None

    with patch('dashboard.app.app.bot', mock_bot):
        response = await client.get('/characters')

    assert response.status_code == 200
    html = await response.get_data(as_text=True)
    assert "User not-a-number" in html


@pytest.mark.asyncio
async def test_retired_route_is_public(client, isolated_data_dir):
    await loadnsave.save_retired_characters_data({"456": [dict(CHAR_TEMPLATE)]})
    with patch('dashboard.app.app.bot', None):
        response = await client.get('/retired')
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_character_unauthorized_without_session(client):
    response = await client.post(
        '/api/character/delete', json={"type": "active", "name": "x"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_character_missing_arguments_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/character/delete', json={"type": "active"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_active_character_missing_ids_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/character/delete',
        json={"type": "active", "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_active_character_name_mismatch_returns_400(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_player_stats({"123": {"456": dict(CHAR_TEMPLATE)}})

    response = await client.post(
        '/api/character/delete',
        json={"type": "active", "server_id": "123", "user_id": "456", "name": "Wrong Name"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert "do not match" in data["message"]

    remaining = await loadnsave.load_player_stats()
    assert "456" in remaining["123"]


@pytest.mark.asyncio
async def test_delete_active_character_not_found_returns_404(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_player_stats({})
    response = await client.post(
        '/api/character/delete',
        json={"type": "active", "server_id": "123", "user_id": "456", "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_active_character_success_cleans_empty_guild(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_player_stats({"123": {"456": dict(CHAR_TEMPLATE)}})

    response = await client.post(
        '/api/character/delete',
        json={"type": "active", "server_id": "123", "user_id": "456", "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    remaining = await loadnsave.load_player_stats()
    assert "123" not in remaining


@pytest.mark.asyncio
async def test_delete_active_character_success_keeps_other_characters_in_guild(client, isolated_data_dir):
    await login(client)
    other_char = dict(CHAR_TEMPLATE)
    other_char["NAME"] = "Someone Else"
    await loadnsave.save_player_stats({
        "123": {"456": dict(CHAR_TEMPLATE), "789": other_char}
    })

    response = await client.post(
        '/api/character/delete',
        json={"type": "active", "server_id": "123", "user_id": "456", "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200

    remaining = await loadnsave.load_player_stats()
    assert "123" in remaining
    assert "456" not in remaining["123"]
    assert "789" in remaining["123"]


@pytest.mark.asyncio
async def test_delete_retired_character_missing_ids_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_retired_character_invalid_index_returns_400(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_retired_characters_data({"456": [dict(CHAR_TEMPLATE)]})

    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "user_id": "456", "index": 5, "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Invalid index"


@pytest.mark.asyncio
async def test_delete_retired_character_negative_index_returns_400(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_retired_characters_data({"456": [dict(CHAR_TEMPLATE)]})

    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "user_id": "456", "index": -1, "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
    data = json.loads(await response.get_data(as_text=True))
    assert data["message"] == "Invalid index"


@pytest.mark.asyncio
async def test_delete_retired_character_name_mismatch_returns_400(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_retired_characters_data({"456": [dict(CHAR_TEMPLATE)]})

    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "user_id": "456", "index": 0, "name": "Wrong Name"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_retired_character_user_not_found_returns_404(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_retired_characters_data({})

    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "user_id": "999", "index": 0, "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_retired_character_success_cleans_empty_list(client, isolated_data_dir):
    await login(client)
    await loadnsave.save_retired_characters_data({"456": [dict(CHAR_TEMPLATE)]})

    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "user_id": "456", "index": 0, "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    data = json.loads(await response.get_data(as_text=True))
    assert data == {"status": "success"}

    remaining = await loadnsave.load_retired_characters_data()
    assert "456" not in remaining


@pytest.mark.asyncio
async def test_delete_retired_character_success_keeps_other_entries(client, isolated_data_dir):
    await login(client)
    second_char = dict(CHAR_TEMPLATE)
    second_char["NAME"] = "Someone Else"
    await loadnsave.save_retired_characters_data({"456": [dict(CHAR_TEMPLATE), second_char]})

    response = await client.post(
        '/api/character/delete',
        json={"type": "retired", "user_id": "456", "index": 0, "name": "Old Man Henderson"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200

    remaining = await loadnsave.load_retired_characters_data()
    assert len(remaining["456"]) == 1
    assert remaining["456"][0]["NAME"] == "Someone Else"


@pytest.mark.asyncio
async def test_delete_character_invalid_type_returns_400(client):
    await login(client)
    response = await client.post(
        '/api/character/delete',
        json={"type": "bogus", "name": "x"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400
