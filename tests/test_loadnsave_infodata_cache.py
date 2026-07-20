import json

import pytest

import loadnsave


INFODATA_CASES = [
    pytest.param(loadnsave.load_monsters_data, "monsters.json", {"Deep One": {"HP": 8}}, id="monsters"),
    pytest.param(loadnsave.load_deities_data, "deities.json", {"Cthulhu": {"HP": 100}}, id="deities"),
    pytest.param(loadnsave.load_spells_data, "spells.json", {"Wither Limb": {"cost": "1D6"}}, id="spells"),
    pytest.param(loadnsave.load_weapons_data, "weapons.json", {"Knife": {"damage": "1D4"}}, id="weapons"),
]


@pytest.fixture
def isolated_infodata_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(loadnsave, "INFODATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(loadnsave, "_INFODATA_CACHE", {})
    return tmp_path


@pytest.mark.asyncio
@pytest.mark.parametrize("load_fn,filename,payload", INFODATA_CASES)
async def test_infodata_loader_serves_cached_value_after_first_read(
    isolated_infodata_dir, load_fn, filename, payload
):
    (isolated_infodata_dir / filename).write_text(json.dumps(payload), encoding="utf-8")

    first = await load_fn()
    assert first == payload

    # Mutate the on-disk file directly (simulating an external change) without
    # touching the cache. A correctly-cached loader must keep returning the
    # value it already cached, not re-read disk on every call.
    (isolated_infodata_dir / filename).write_text(json.dumps({"changed": True}), encoding="utf-8")

    second = await load_fn()
    assert second == payload
