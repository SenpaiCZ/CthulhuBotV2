import json
import pytest
import loadnsave


ENTITY_CASES = [
    pytest.param(
        loadnsave.load_player_stats, loadnsave.save_player_stats,
        "player_stats.json", "_PLAYER_STATS_CACHE",
        {
            "123": {
                "456": {
                    "NAME": "Old Man Henderson",
                    "Backstory": {
                        "Personal Description": [],
                        "Ideology/Beliefs": [],
                        "Significant People": [],
                        "Meaningful Locations": [],
                        "Treasured Possessions": [],
                        "Traits": []
                    },
                    "Connections": []
                }
            }
        },
        id="player_stats",
    ),
    pytest.param(
        loadnsave.load_server_stats, loadnsave.save_server_stats,
        "server_stats.json", "_SERVER_STATS_CACHE",
        {"123": {"prefix": "!"}},
        id="server_stats",
    ),
    pytest.param(
        loadnsave.load_session_data, loadnsave.save_session_data,
        "session_data.json", "_SESSION_DATA_CACHE",
        {"123": {"456": {"skill_uses": 1}}},
        id="session_data",
    ),
    pytest.param(
        loadnsave.load_chase_data, loadnsave.save_chase_data,
        "chase_data.json", "_CHASE_DATA_CACHE",
        {"123": {"456": {"round_number": 2}}},
        id="chase_data",
    ),
    pytest.param(
        loadnsave.load_karma_stats, loadnsave.save_karma_stats,
        "karma_stats.json", None,
        {"123": {"456": 5}},
        id="karma_stats",
    ),
    pytest.param(
        loadnsave.load_retired_characters_data, loadnsave.save_retired_characters_data,
        "retired_characters_data.json", "_RETIRED_CHARACTERS_CACHE",
        {"123": [{"NAME": "Retired Guy"}]},
        id="retired_characters_data",
    ),
]


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "DATA_FOLDER", str(tmp_path))
    for cache_name in [
        "_PLAYER_STATS_CACHE", "_SERVER_STATS_CACHE", "_SESSION_DATA_CACHE",
        "_CHASE_DATA_CACHE", "_RETIRED_CHARACTERS_CACHE",
    ]:
        monkeypatch.setattr(loadnsave, cache_name, None)
    return tmp_path


@pytest.mark.asyncio
@pytest.mark.parametrize("load_fn,save_fn,filename,cache_attr,payload", ENTITY_CASES)
async def test_save_then_load_round_trips(
    isolated_data_dir, load_fn, save_fn, filename, cache_attr, payload
):
    await save_fn(payload)

    on_disk = json.loads((isolated_data_dir / filename).read_text(encoding="utf-8"))
    assert on_disk == payload

    if cache_attr is not None:
        setattr(loadnsave, cache_attr, None)

    reloaded = await load_fn()
    assert reloaded == payload


@pytest.mark.asyncio
async def test_load_player_stats_missing_file_returns_empty_dict(isolated_data_dir):
    result = await loadnsave.load_player_stats()
    assert result == {}


@pytest.mark.asyncio
async def test_load_json_file_backs_up_corrupt_file(isolated_data_dir):
    bad_file = isolated_data_dir / "server_stats.json"
    bad_file.write_text("{not valid json", encoding="utf-8")

    result = await loadnsave.load_server_stats()

    assert result == {}
    assert (isolated_data_dir / "server_stats.json.bak").exists()
