import pytest
from commands.combat import CombatView


def make_view(backstory_items, weapon_db):
    view = CombatView.__new__(CombatView)
    view.char_data = {"Backstory": {"Gear and Possessions": backstory_items}}
    view.weapon_db = weapon_db
    return view


def test_parse_weapons_exact_match_with_ammo():
    view = make_view(
        ["Shotgun [2/2]"],
        {"Shotgun": {"capacity": "2"}},
    )
    weapons = view._parse_weapons()
    assert len(weapons) == 1
    w = weapons[0]
    assert w["key"] == "Shotgun"
    assert w["ammo"] == 2
    assert w["cap"] == 2
    assert w["is_jammed"] is False


def test_parse_weapons_jammed_suffix_detected():
    view = make_view(
        ["Shotgun [1/2] (JAMMED)"],
        {"Shotgun": {"capacity": "2"}},
    )
    weapons = view._parse_weapons()
    assert weapons[0]["is_jammed"] is True
    assert weapons[0]["ammo"] == 1


def test_parse_weapons_strips_article_prefix_for_fuzzy_match():
    view = make_view(
        ["A Shotgun [2/2]"],
        {"Shotgun": {"capacity": "2"}},
    )
    weapons = view._parse_weapons()
    assert weapons[0]["key"] == "Shotgun"


def test_parse_weapons_no_bracket_defaults_to_db_capacity():
    view = make_view(
        ["Shotgun"],
        {"Shotgun": {"capacity": "2"}},
    )
    weapons = view._parse_weapons()
    assert weapons[0]["ammo"] == 2
    assert weapons[0]["cap"] == 2


def test_parse_weapons_ignores_non_weapon_inventory_items():
    view = make_view(
        ["A Mysterious Journal", "Shotgun [2/2]"],
        {"Shotgun": {"capacity": "2"}},
    )
    weapons = view._parse_weapons()
    assert len(weapons) == 1
    assert weapons[0]["key"] == "Shotgun"


def test_parse_weapons_empty_inventory_returns_empty_list():
    view = make_view([], {"Shotgun": {"capacity": "2"}})
    assert view._parse_weapons() == []
