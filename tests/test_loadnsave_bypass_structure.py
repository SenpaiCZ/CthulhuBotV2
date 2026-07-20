import dashboard.blueprints.grimoire as grimoire_module


def test_grimoire_does_not_import_private_load_json_file_bypass():
    """grimoire.py must read infodata via loadnsave's cached load_X() functions,
    not the private _load_json_file() helper directly -- a direct call always
    re-reads disk and ignores _INFODATA_CACHE, silently diverging from every
    other infodata route in this file (archetypes, pulp_talents, etc. already
    do it correctly via load_archetype_data() and friends)."""
    assert not hasattr(grimoire_module, "_load_json_file"), (
        "grimoire.py imports loadnsave._load_json_file directly -- this bypasses "
        "the infodata cache. Use the corresponding load_X_data() function instead."
    )
