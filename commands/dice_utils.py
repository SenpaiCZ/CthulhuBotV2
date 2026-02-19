import random
import re

class DiceUtils:
    @staticmethod
    def evaluate_dice_expression(expression):
        """
        Evaluates a standard dice expression (e.g., 2d6+5).
        Returns result (int) and detail string.
        """
        expression = str(expression).replace('D', 'd').replace(' ', '')
        detail_parts = []

        def roll_dice(match):
            num, size = map(int, match.groups())
            rolls = [random.randint(1, size) for _ in range(num)]
            detail_parts.append(f":game_die: {num}d{size}: {' + '.join(map(str, rolls))} = {sum(rolls)}")
            return sum(rolls)

        dice_pattern = re.compile(r'(\d+)d(\d+)')
        expression = dice_pattern.sub(lambda m: str(roll_dice(m)), expression)

        if not re.match(r'^[\d+\-*/().]+$', expression):
            raise ValueError("Invalid dice expression")

        result = eval(expression, {"__builtins__": None})
        detail = "\n".join(detail_parts) + f"\nExpression: {expression}"
        return result, detail

    @staticmethod
    def calculate_roll_result(roll, skill_value):
        """
        Determines the success tier of a CoC skill roll.
        Returns text description and integer tier.
        Tier: 0=Fumble, 1=Fail, 2=Regular, 3=Hard, 4=Extreme, 5=Critical
        """
        is_fumble = False
        if skill_value < 50:
            if roll >= 96: is_fumble = True
        else:
            if roll == 100: is_fumble = True

        if is_fumble: return "Fumble :warning:", 0
        if roll == 1: return "Critical Success :star2:", 5
        elif roll <= skill_value // 5: return "Extreme Success :star:", 4
        elif roll <= skill_value // 2: return "Hard Success :white_check_mark:", 3
        elif roll <= skill_value: return "Regular Success :heavy_check_mark:", 2
        return "Fail :x:", 1

    @staticmethod
    def perform_skill_roll(skill_value, bonus=0, penalty=0):
        """
        Performs a full CoC skill roll with bonus/penalty dice.
        Returns:
            final_roll (int),
            result_tier (int),
            result_text (str),
            ones_roll (int),
            tens_rolls (list of int),
            net_dice (int)
        """
        net_dice = bonus - penalty

        # Roll Ones (0-9)
        ones_roll = random.randint(0, 9)

        # Roll Tens (00-90)
        # Need 1 + abs(net_dice) tens rolls initially
        num_tens = 1 + abs(net_dice)
        tens_options = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
        tens_rolls = [random.choice(tens_options) for _ in range(num_tens)]

        # Calculate Result
        possible_rolls = []
        for t in tens_rolls:
            val = t + ones_roll
            if val == 0: val = 100
            possible_rolls.append(val)

        final_roll = 0
        if net_dice > 0: final_roll = min(possible_rolls)
        elif net_dice < 0: final_roll = max(possible_rolls)
        else: final_roll = possible_rolls[0]

        result_text, result_tier = DiceUtils.calculate_roll_result(final_roll, skill_value)

        return {
            "final_roll": final_roll,
            "result_tier": result_tier,
            "result_text": result_text,
            "ones_roll": ones_roll,
            "tens_rolls": tens_rolls,
            "net_dice": net_dice
        }
