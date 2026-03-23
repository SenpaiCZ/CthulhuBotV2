import random
from typing import Optional, Tuple, List
from schemas.roll import RollRequest, RollResult

class SafeDiceParser:
    def __init__(self):
        self.max_dice_count = 100
        self.max_sides = 1000
        self.max_result = 1000000 # 1 million limit

    def evaluate(self, expression: str) -> Tuple[int, str]:
        expression = str(expression).replace(" ", "")

        if "**" in expression: raise ValueError("Power operator not allowed")
        if "//" in expression: raise ValueError("Floor division not allowed")

        tokens = self._tokenize(expression)
        result_val, detail_str = self._parse_expression(tokens)

        if result_val > self.max_result:
            raise ValueError(f"Result too large (max {self.max_result})")

        return result_val, detail_str

    def _tokenize(self, expr):
        tokens = []
        i = 0
        while i < len(expr):
            char = expr[i]
            if char.isdigit():
                num_str = char
                i += 1
                while i < len(expr) and expr[i].isdigit():
                    num_str += expr[i]
                    i += 1
                tokens.append(('NUM', int(num_str)))
                continue
            elif char.lower() in "+-*/()d":
                if char.lower() == 'd':
                    tokens.append(('OP', 'd'))
                else:
                    tokens.append(('OP', char))
                i += 1
                continue
            else:
                raise ValueError(f"Invalid character: {char}")
        return tokens

    def _parse_expression(self, tokens):
        val, det = self._parse_term(tokens)
        while tokens and tokens[0][0] == 'OP' and tokens[0][1] in "+-":
            op = tokens.pop(0)[1]
            right_val, right_det = self._parse_term(tokens)
            if op == '+':
                val += right_val
                if right_det: det += f" + {right_det}"
            else:
                val -= right_val
                if right_det: det += f" - {right_det}"
        return val, det

    def _parse_term(self, tokens):
        val, det = self._parse_factor(tokens)
        while tokens and tokens[0][0] == 'OP' and tokens[0][1] in "*/":
            op = tokens.pop(0)[1]
            right_val, right_det = self._parse_factor(tokens)
            if op == '*':
                val *= right_val
                if right_det: det += f" * {right_det}"
            else:
                if right_val == 0: raise ValueError("Division by zero")
                val //= right_val
                if right_det: det += f" / {right_det}"
        return val, det

    def _parse_factor(self, tokens):
        if not tokens: raise ValueError("Unexpected end of expression")
        token = tokens.pop(0)

        if token[0] == 'NUM':
            val = token[1]
            if tokens and tokens[0][0] == 'OP' and tokens[0][1] == 'd':
                tokens.pop(0)
                if not tokens or tokens[0][0] != 'NUM': raise ValueError("Expected number after 'd'")
                sides = tokens.pop(0)[1]
                return self._roll_dice(val, sides)
            return val, str(val)

        elif token[0] == 'OP' and token[1] == '(':
            val, det = self._parse_expression(tokens)
            if not tokens or tokens[0][1] != ')': raise ValueError("Missing closing parenthesis")
            tokens.pop(0)
            return val, f"({det})"

        elif token[0] == 'OP' and token[1] == 'd':
            if not tokens or tokens[0][0] != 'NUM': raise ValueError("Expected number after 'd'")
            sides = tokens.pop(0)[1]
            return self._roll_dice(1, sides)

        else:
            raise ValueError(f"Unexpected token: {token}")

    def _roll_dice(self, count, sides):
        if count > self.max_dice_count: raise ValueError(f"Too many dice (max {self.max_dice_count})")
        if sides > self.max_sides: raise ValueError(f"Too many sides (max {self.max_sides})")
        if count <= 0 or sides <= 0: return 0, "0"

        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        rolls_str = ', '.join(map(str, rolls))
        if len(rolls_str) > 50: rolls_str = rolls_str[:50] + "..."

        detail = f"[{rolls_str}]"
        return total, detail

class RollService:
    @staticmethod
    def evaluate_dice_expression(expression: str) -> Tuple[int, str]:
        """
        Evaluates a standard dice expression like '3d6 + 4'.
        """
        parser = SafeDiceParser()
        return parser.evaluate(expression)

    @staticmethod
    def calculate_roll_result_tier(roll: int, skill_value: int) -> Tuple[str, int]:
        """
        Calculates the success tier for a CoC skill check (0=Fumble to 5=Critical).
        """
        is_fumble = False
        if skill_value < 50:
            if roll >= 96: is_fumble = True
        else:
            if roll == 100: is_fumble = True

        if is_fumble: return "Fumble", 0
        if roll == 1: return "Critical Success", 5
        elif roll <= skill_value // 5: return "Extreme Success", 4
        elif roll <= skill_value // 2: return "Hard Success", 3
        elif roll <= skill_value: return "Regular Success", 2
        return "Fail", 1

    @staticmethod
    def calculate_roll(request: RollRequest, stat_value: int) -> RollResult:
        """
        Perform a CoC skill check roll including bonus/penalty dice and difficulty logic.
        """
        net_dice = request.bonus_dice - request.penalty_dice
        ones_roll = random.randint(0, 9)
        num_tens = 1 + abs(net_dice)
        tens_options = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
        tens_rolls = [random.choice(tens_options) for _ in range(num_tens)]
        
        possible_rolls = []
        for t in tens_rolls:
            val = t + ones_roll
            if val == 0: val = 100
            possible_rolls.append(val)

        if net_dice > 0:
            final_roll = min(possible_rolls)
        elif net_dice < 0:
            final_roll = max(possible_rolls)
        else:
            final_roll = possible_rolls[0]

        result_text, result_tier = RollService.calculate_roll_result_tier(final_roll, stat_value)

        # Difficulty Check Logic
        target_tier = 2 # Default Regular
        if request.difficulty == "Hard": target_tier = 3
        elif request.difficulty == "Extreme": target_tier = 4

        is_success = result_tier >= target_tier
        is_failure = result_tier == 1 or (result_tier < target_tier and result_tier > 0)
        is_fumble = result_tier == 0
        is_critical = result_tier == 5

        if request.difficulty != "Regular":
            if is_success:
                result_text += f" (Passed {request.difficulty})"
            elif not is_fumble and not is_critical:
                result_text += f" (Failed {request.difficulty})"

        return RollResult(
            final_roll=final_roll,
            result_level=result_tier,
            result_text=result_text,
            is_success=is_success,
            is_failure=is_failure,
            is_fumble=is_fumble,
            is_critical=is_critical,
            rolls=possible_rolls,
            net_dice=net_dice
        )
