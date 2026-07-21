import json

import pytest
from unittest.mock import patch

import loadnsave
from dashboard.app import app
import dashboard.blueprints.file_browser as file_browser


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture
def isolated_data_dir_as_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(file_browser, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_SERVER_STATS_CACHE", {"999": {"prefix": "OLD"}})
    with patch('dashboard.blueprints.file_browser.is_admin', return_value=True):
        yield tmp_path


async def login(client):
    async with client.session_transaction() as sess:
        sess['logged_in'] = True


@pytest.mark.asyncio
async def test_file_browser_save_invalidates_stale_data_cache(client, isolated_data_dir_as_admin):
    await login(client)
    new_content = {"999": {"prefix": "NEW"}}

    response = await client.post(
        '/api/save/data/server_stats.json',
        json={"content": json.dumps(new_content)},
        headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 200

    on_disk = json.loads((isolated_data_dir_as_admin / "server_stats.json").read_text(encoding="utf-8"))
    assert on_disk == new_content

    # The bug: save_file() writes via loadnsave._save_json_file() directly, which
    # only ever updates _INFODATA_CACHE (for infodata/ writes) -- it never resets
    # _SERVER_STATS_CACHE (a data/-folder entity cache). Without a fix,
    # load_server_stats() below would still return the stale {"999": {"prefix": "OLD"}}
    # set by the fixture, even though the file on disk now holds new_content.
    reloaded = await loadnsave.load_server_stats()
    assert reloaded == new_content
