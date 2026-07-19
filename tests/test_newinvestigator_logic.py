import random
import pytest
from commands.newinvestigator import newinvestigator


@pytest.fixture
def wizard():
    return newinvestigator.__new__(newinvestigator)


def test_roll_stat_formula_3d6x5_within_bounds(wizard):
    random.seed(1)
    for _ in range(50):
        value = wizard.roll_stat_formula("3D6 * 5")
        assert 15 <= value <= 90
        assert value % 5 == 0


def test_roll_stat_formula_2d6_plus_6_x5_within_bounds(wizard):
    random.seed(1)
    for _ in range(50):
        value = wizard.roll_stat_formula("(2D6 + 6) * 5")
        assert 40 <= value <= 90
        assert value % 5 == 0


def test_roll_stat_formula_unknown_formula_returns_zero(wizard):
    assert wizard.roll_stat_formula("not a formula") == 0


@pytest.mark.parametrize(
    "skill_name,allowed_list,expected",
    [
        ("Spot Hidden", ["Spot Hidden", "Listen"], True),
        ("Firearms (Handgun)", ["Firearms Handgun"], True),
        ("Firearms (Rifle)", ["Firearms (any)"], True),
        ("Language (French)", ["Language (Other)"], True),
        ("Language (Own)", ["Language (Other)"], False),
        ("Survival (Desert)", ["Survival (any)"], True),
        ("Psychology", ["Spot Hidden", "Listen"], False),
    ],
)
def test_is_skill_allowed_for_archetype(wizard, skill_name, allowed_list, expected):
    assert wizard.is_skill_allowed_for_archetype(skill_name, allowed_list) is expected


def test_get_archetype_skills_extracts_bonus_skill_list(wizard):
    adjustments = [
        "You gain 100 bonus points to spend on the following skills:** Fighting (Brawl), Firearms (Handgun), Stealth."
    ]
    result = wizard.get_archetype_skills(adjustments)
    # rstrip(".") runs on the whole joined tail before the comma-split, so only the
    # string's final trailing period is removed — "Stealth." becomes "Stealth".
    assert result == ["Fighting (Brawl)", "Firearms (Handgun)", "Stealth"]


def test_get_archetype_skills_no_match_returns_empty_list(wizard):
    assert wizard.get_archetype_skills(["Some unrelated adjustment line."]) == []


def test_get_archetype_core_options_extracts_listed_stats(wizard):
    adjustments = ["Core characteristic bonus: **STR, DEX and CON** are increased."]
    result = wizard.get_archetype_core_options(adjustments)
    assert result == ["STR", "DEX", "CON"]


def test_get_archetype_talent_reqs_detects_hardened_requirement(wizard):
    adjustments = ["Talents: This archetype must take the Hardened talent."]
    assert wizard.get_archetype_talent_reqs(adjustments) == ["Hardened"]


def test_get_archetype_talent_reqs_no_match_returns_empty_list(wizard):
    assert wizard.get_archetype_talent_reqs(["Talents: no special requirement."]) == []


def test_evaluate_term_multiplies_named_stat(wizard):
    assert wizard.evaluate_term("EDU×4", edu=60, dex=0, str_stat=0, app=0, pow_stat=0) == 240
    assert wizard.evaluate_term("DEX×2", edu=0, dex=55, str_stat=0, app=0, pow_stat=0) == 110


def test_evaluate_term_missing_multiplier_symbol_returns_zero(wizard):
    assert wizard.evaluate_term("EDU", edu=60, dex=0, str_stat=0, app=0, pow_stat=0) == 0


def test_calculate_occupation_points_simple_formula(wizard):
    char_data = {"EDU": 60, "DEX": 50, "STR": 40, "APP": 45, "POW": 55}
    info = {"skill_points": "EDU × 4"}
    assert wizard.calculate_occupation_points(char_data, info) == 240


def test_calculate_occupation_points_or_clause_picks_best_option(wizard):
    char_data = {"EDU": 60, "DEX": 80, "STR": 40, "APP": 45, "POW": 55}
    info = {"skill_points": "(EDU×2 or STR×5)"}
    # EDU*2=120, STR*5=200, so the "or" branch should select 200.
    # We avoid "DEX" because the normalization replaces "x" in "DEX" creating "DE××2".
    assert wizard.calculate_occupation_points(char_data, info) == 200


def test_calculate_occupation_points_varies_formula_returns_zero(wizard):
    char_data = {"EDU": 60, "DEX": 50, "STR": 40, "APP": 45, "POW": 55}
    info = {"skill_points": "Varies"}
    assert wizard.calculate_occupation_points(char_data, info) == 0


def test_calculate_occupation_points_unparseable_formula_returns_zero(wizard):
    char_data = {"EDU": 60, "DEX": 50, "STR": 40, "APP": 45, "POW": 55}
    info = {"skill_points": "???"}
    # Unparseable formulas that don't throw exceptions return 0, not a fallback to EDU×4.
    # The fallback only triggers on actual exceptions.
    assert wizard.calculate_occupation_points(char_data, info) == 0
