import pytest
from commands.roll import Roll, SafeDiceParser


@pytest.fixture
def roll_cog():
    # Bypass Roll.__init__ (it registers a bot context-menu command) — the method
    # under test doesn't touch self, so an uninitialized instance is sufficient.
    return Roll.__new__(Roll)


@pytest.mark.parametrize(
    "roll,skill_value,expected_text,expected_tier",
    [
        (1, 50, "Critical Success :star2:", 5),
        (5, 50, "Extreme Success :star:", 4),
        (10, 50, "Extreme Success :star:", 4),
        (11, 50, "Hard Success :white_check_mark:", 3),
        (25, 50, "Hard Success :white_check_mark:", 3),
        (26, 50, "Regular Success :heavy_check_mark:", 2),
        (50, 50, "Regular Success :heavy_check_mark:", 2),
        (51, 50, "Fail :x:", 1),
        (95, 50, "Fail :x:", 1),
        (96, 50, "Fail :x:", 1),
        (100, 50, "Fumble :warning:", 0),
        (96, 49, "Fumble :warning:", 0),
        (99, 60, "Fail :x:", 1),
        (100, 60, "Fumble :warning:", 0),
    ],
)
def test_calculate_roll_result(roll_cog, roll, skill_value, expected_text, expected_tier):
    text, tier = roll_cog.calculate_roll_result(roll, skill_value)
    assert text == expected_text
    assert tier == expected_tier


def test_dice_parser_simple_addition():
    parser = SafeDiceParser()
    result, detail = parser.evaluate("1+2")
    assert result == 3
    assert detail == "1 + 2"


def test_dice_parser_rejects_power_operator():
    parser = SafeDiceParser()
    with pytest.raises(ValueError, match="Power operator not allowed"):
        parser.evaluate("2**3")


def test_dice_parser_rejects_oversized_dice_count():
    parser = SafeDiceParser()
    with pytest.raises(ValueError, match="Too many dice"):
        parser.evaluate("101d6")


def test_dice_parser_rejects_division_by_zero():
    parser = SafeDiceParser()
    with pytest.raises(ValueError, match="Division by zero"):
        parser.evaluate("1/0")


def test_dice_parser_dice_roll_within_bounds():
    parser = SafeDiceParser()
    result, detail = parser.evaluate("3d6")
    assert 3 <= result <= 18
    assert detail.startswith("[") and detail.endswith("]")
