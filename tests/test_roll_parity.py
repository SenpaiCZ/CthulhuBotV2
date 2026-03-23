import pytest
import random
from unittest.mock import MagicMock
from services.roll_service import RollService
from schemas.roll import RollRequest
from commands.roll import Roll

def get_mock_cog():
    mock_bot = MagicMock()
    # Mocking self.bot.tree.add_command
    mock_bot.tree = MagicMock()
    cog = Roll(mock_bot)
    return cog

def legacy_roll_logic(skill_value, bonus=0, penalty=0, difficulty="Regular"):
    """Replicated legacy roll logic from commands/roll.py"""
    net_dice = bonus - penalty
    ones_roll = random.randint(0, 9)
    num_tens = 1 + abs(net_dice)
    tens_options = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
    tens_rolls = [random.choice(tens_options) for _ in range(num_tens)]
    possible_rolls = []
    for t in tens_rolls:
        val = t + ones_roll
        if val == 0: val = 100
        possible_rolls.append(val)

    final_roll = 0
    if net_dice > 0:
        final_roll = min(possible_rolls)
    elif net_dice < 0:
        final_roll = max(possible_rolls)
    else:
        final_roll = possible_rolls[0]

    # Instantiate Cog with mock bot
    cog = get_mock_cog()
    result_text, result_tier = cog.calculate_roll_result(final_roll, skill_value)
    
    return final_roll, result_tier

@pytest.mark.parametrize("skill_value", [10, 50, 90])
@pytest.mark.parametrize("bonus", [0, 1, 2])
@pytest.mark.parametrize("penalty", [0, 1, 2])
@pytest.mark.parametrize("difficulty", ["Regular", "Hard", "Extreme"])
def test_roll_parity(skill_value, bonus, penalty, difficulty):
    seed = 42
    
    # 1. Run legacy logic
    random.seed(seed)
    legacy_roll, legacy_tier = legacy_roll_logic(skill_value, bonus, penalty, difficulty)
    
    # 2. Run new service
    random.seed(seed)
    request = RollRequest(
        stat_name="Test Skill",
        bonus_dice=bonus,
        penalty_dice=penalty,
        difficulty=difficulty
    )
    service_result = RollService.calculate_roll(request, skill_value)
    
    # 3. Compare
    assert service_result.final_roll == legacy_roll, f"Roll mismatch for skill={skill_value}, bonus={bonus}, penalty={penalty}"
    assert service_result.result_level == legacy_tier, f"Tier mismatch for skill={skill_value}, bonus={bonus}, penalty={penalty}"

def test_critical_and_fumble_parity():
    # Test specific known cases or many random cases to find criticals/fumbles
    cog = get_mock_cog()
    
    test_cases = [
        (1, 50),   # Critical
        (100, 50), # Fumble (skill >= 50)
        (96, 40),  # Fumble (skill < 50)
        (50, 50),  # Regular Success
        (25, 50),  # Hard Success
        (10, 50),  # Extreme Success
        (51, 50),  # Fail
    ]
    
    for roll, skill in test_cases:
        legacy_text, legacy_tier = cog.calculate_roll_result(roll, skill)
        service_text, service_tier = RollService.calculate_roll_result_tier(roll, skill)
        
        assert legacy_tier == service_tier, f"Tier mismatch for roll={roll}, skill={skill}"
