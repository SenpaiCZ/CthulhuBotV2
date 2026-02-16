import discord
import asyncio
import random
import re
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
from loadnsave import (
    load_player_stats,
    save_player_stats,
    load_server_stats,
    load_session_data,
    save_session_data,
    load_luck_stats,
    load_skills_data
)
from emojis import get_stat_emoji
from support_functions import session_success
from rapidfuzz import process, fuzz

class DisambiguationSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="Select a skill...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_stat = self.values[0]
        await interaction.response.defer()
        self.view.stop()

class DisambiguationView(View):
    def __init__(self, ctx, matching_stats):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.selected_stat = None

        options = [
            discord.SelectOption(label=stat, value=stat)
            for stat in matching_stats[:25]
        ]
        self.add_item(DisambiguationSelect(options))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Not your session!", ephemeral=True)
            return False
        return True

class RollResultView(View):
    def __init__(self, ctx, cog, player_stats, server_id, user_id, stat_name, current_value,
                 ones_roll, tens_rolls, net_dice, result_tier, luck_threshold):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog
        self.player_stats = player_stats
        self.server_id = server_id
        self.user_id = user_id
        self.stat_name = stat_name
        self.current_value = current_value

        # Dice State
        self.ones_roll = ones_roll
        self.tens_rolls = tens_rolls # List of tens (0, 10, ... 90)
        self.net_dice = net_dice # >0 Bonus, <0 Penalty

        self.result_tier = result_tier
        self.luck_threshold = luck_threshold

        self.roll = self._calculate_current_roll() # Initial calculation
        self.success = False
        if self.result_tier >= 2:
            self.success = True

        self.update_buttons()

    def _calculate_current_roll(self):
        # Calculate roll based on current dice state
        # Determine how many dice to use based on net_dice
        num_to_use = 1 + abs(self.net_dice)

        # Ensure we have enough dice (safeguard, though buttons handle this)
        while len(self.tens_rolls) < num_to_use:
            self.tens_rolls.append(random.choice([0, 10, 20, 30, 40, 50, 60, 70, 80, 90]))

        # Use only the required number of dice from the history
        active_tens = self.tens_rolls[:num_to_use]

        possible_rolls = []
        for tens in active_tens:
            val = tens + self.ones_roll
            if val == 0: val = 100
            possible_rolls.append(val)

        if self.net_dice > 0:
            # Bonus: Take lowest
            return min(possible_rolls)
        elif self.net_dice < 0:
            # Penalty: Take highest
            return max(possible_rolls)
        else:
            # Normal: Use the single result
            return possible_rolls[0]

    def update_buttons(self):
        # LUCK Logic
        can_luck = False
        luck_cost = 0
        player_luck = self.player_stats[self.server_id][self.user_id]['LUCK']

        # Can only luck if Normal roll (net_dice == 0) and not LUCK roll itself
        if self.net_dice == 0 and self.stat_name != "LUCK" and self.result_tier != 0:
            target_val = 0
            if self.result_tier == 1: # Fail -> Regular
                target_val = self.current_value
            elif self.result_tier == 2: # Regular -> Hard
                target_val = self.current_value // 2
            elif self.result_tier == 3: # Hard -> Extreme
                target_val = self.current_value // 5

            if target_val > 0:
                cost = self.roll - target_val
                if player_luck >= cost and cost <= self.luck_threshold:
                    can_luck = True
                    luck_cost = cost

        self.luck_button.disabled = not can_luck
        if can_luck:
            self.luck_button.label = f"Use Luck (-{luck_cost})"
        else:
            self.luck_button.label = "Use Luck"

        # PUSH Logic (Only on Normal Fail)
        can_push = False
        if self.net_dice == 0 and self.stat_name != "LUCK" and self.result_tier == 1:
             can_push = True
        self.push_button.disabled = not can_push

        # Max Dice Limit (CoC doesn't specify hard limit, but UI should)
        # Limit to +/- 2 dice
        self.add_bonus_btn.disabled = self.net_dice >= 2
        self.add_penalty_btn.disabled = self.net_dice <= -2

    async def _update_state_and_embed(self, interaction):
        self.roll = self._calculate_current_roll()

        result_text, result_tier = self.cog.calculate_roll_result(self.roll, self.current_value)
        self.result_tier = result_tier
        self.success = result_tier >= 2

        self.update_buttons()

        # Rebuild Embed
        embed = interaction.message.embeds[0]

        # Determine Color
        color = discord.Color.green() # Default Regular/Hard
        if result_tier == 5 or result_tier == 4: color = 0xF1C40F # Gold
        elif result_tier == 3 or result_tier == 2: color = 0x2ECC71 # Green
        elif result_tier == 1: color = 0xE74C3C # Red
        elif result_tier == 0: color = 0x992D22 # Dark Red
        embed.color = color

        # Description
        num_to_use = 1 + abs(self.net_dice)
        active_tens = self.tens_rolls[:num_to_use]
        tens_str = ", ".join(str(t) if t != 0 else "00" for t in active_tens)
        ones_str = str(self.ones_roll)

        dice_text = "Normal"
        if self.net_dice > 0: dice_text = f"Bonus ({self.net_dice})"
        elif self.net_dice < 0: dice_text = f"Penalty ({abs(self.net_dice)})"

        description_roll_info = f"{self.ctx.author.mention} :game_die: **{dice_text}** Check\n"
        description_roll_info += f"Dice: [{tens_str}] + {ones_str} -> **{self.roll}**"

        formatted_luck = f":four_leaf_clover: LUCK: {self.player_stats[self.server_id][self.user_id]['LUCK']}"
        formatted_skill = f"**{self.stat_name}**: {self.current_value} - {self.current_value // 2} - {self.current_value // 5}"

        embed.description = f"{description_roll_info}\n\n**{result_text}**\n\n{formatted_skill}\n{formatted_luck}"

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Bonus Die", style=discord.ButtonStyle.success, emoji="🟢", row=0)
    async def add_bonus_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.net_dice += 1

        # Only add a new die if we don't have enough in history
        num_needed = 1 + abs(self.net_dice)
        while len(self.tens_rolls) < num_needed:
            self.tens_rolls.append(random.choice([0, 10, 20, 30, 40, 50, 60, 70, 80, 90]))

        await self._update_state_and_embed(interaction)

    @discord.ui.button(label="Penalty Die", style=discord.ButtonStyle.danger, emoji="🔴", row=0)
    async def add_penalty_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.net_dice -= 1

        # Only add a new die if we don't have enough in history
        num_needed = 1 + abs(self.net_dice)
        while len(self.tens_rolls) < num_needed:
            self.tens_rolls.append(random.choice([0, 10, 20, 30, 40, 50, 60, 70, 80, 90]))

        await self._update_state_and_embed(interaction)

    @discord.ui.button(label="Use Luck", style=discord.ButtonStyle.primary, emoji="🍀", row=1)
    async def luck_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_val = 0
        if self.result_tier == 1: target_val = self.current_value
        elif self.result_tier == 2: target_val = self.current_value // 2
        elif self.result_tier == 3: target_val = self.current_value // 5

        cost = self.roll - target_val

        self.player_stats[self.server_id][self.user_id]['LUCK'] -= cost
        self.roll = target_val
        self.result_tier += 1
        self.success = True

        # Visual Update
        result_text_map = {
            2: "Regular Success (LUCK Used) :heavy_check_mark:",
            3: "Hard Success (LUCK Used) :white_check_mark:",
            4: "Extreme Success (LUCK Used) :star:"
        }
        result_text = result_text_map.get(self.result_tier, "Success (LUCK Used)")

        # Disable stuff
        self.add_bonus_btn.disabled = True
        self.add_penalty_btn.disabled = True
        self.push_button.disabled = True
        self.luck_button.disabled = True

        embed = interaction.message.embeds[0]
        formatted_luck = f":four_leaf_clover: LUCK: {self.player_stats[self.server_id][self.user_id]['LUCK']}"
        formatted_skill = f"**{self.stat_name}**: {self.current_value} - {self.current_value // 2} - {self.current_value // 5}"

        # Reconstruct description with updated Luck
        desc_parts = embed.description.split("\n\n")
        # Keep roll info (part 0), update result (part 1), keep skill (part 2), update luck (part 3)
        if len(desc_parts) >= 1:
            embed.description = f"{desc_parts[0]}\n\n**{result_text}**\n\n{formatted_skill}\n{formatted_luck}"

        embed.color = 0x2ECC71 # Green
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Push Roll", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def push_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Pushing a roll is a completely new roll
        new_roll = random.randint(1, 100)
        result_text, new_tier = self.cog.calculate_roll_result(new_roll, self.current_value)

        msg = f"\n\n**PUSHED ROLL**: {new_roll}\nResult: {result_text}"
        if new_tier <= 1:
             msg += "\n:warning: **DIRE CONSEQUENCES!**"
             self.success = False
        else:
             self.success = True

        self.roll = new_roll
        self.result_tier = new_tier

        original_embed = interaction.message.embeds[0]
        original_embed.description += msg

        # Disable all
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=original_embed, view=None)

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=1)
    async def done_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()
        # Disable
        try:
            for child in self.children: child.disabled = True
            await interaction.message.edit(view=self)
        except: pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Not your session!", ephemeral=True)
            return False
        return True

class SessionView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.create_session = False

    @discord.ui.button(label="Record Session", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.create_session = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.create_session = False
        await interaction.response.defer()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Not your session!", ephemeral=True)
            return False
        return True

class Roll(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def evaluate_dice_expression(self, expression):
        expression = expression.replace('D', 'd').replace(' ', '')
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

    def calculate_roll_result(self, roll, skill_value):
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

    @commands.hybrid_command(name="roll", aliases=["newroll", "diceroll", "d", "nd"], guild_only=True, description="Perform a dice roll or skill check.")
    @app_commands.describe(
        dice_expression="The dice expression (e.g. 3d6) or skill name (e.g. Spot Hidden)",
        bonus="Number of Bonus Dice (0-2)",
        penalty="Number of Penalty Dice (0-2)",
        secret="Make the result ephemeral (hidden)"
    )
    @app_commands.choices(
        bonus=[app_commands.Choice(name="0", value=0), app_commands.Choice(name="1", value=1), app_commands.Choice(name="2", value=2)],
        penalty=[app_commands.Choice(name="0", value=0), app_commands.Choice(name="1", value=1), app_commands.Choice(name="2", value=2)]
    )
    async def roll(self, ctx, *, dice_expression: str, bonus: int = 0, penalty: int = 0, secret: bool = False):
        """
        🎲 Perform a dice roll or skill check.
        """
        if not ctx.interaction:
             # Prevent legacy use if possible, or just fail gracefully.
             # The user asked to remove legacy prefix commands, so we can just return or send a message.
             # Hybrid command might still trigger on !roll.
             await ctx.send("Please use the slash command `/roll`.")
             return

        ephemeral = secret

        async def send_msg(content=None, embed=None, view=None):
            if not ctx.interaction.response.is_done():
                await ctx.interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
                return await ctx.interaction.original_response()
            else:
                return await ctx.interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral, wait=True)

        server_id = str(ctx.guild.id)
        # 1. Dice Expression (e.g. 3d6)
        try:
            result, detail = self.evaluate_dice_expression(dice_expression)
            embed = discord.Embed(
                title=f":game_die: Dice Roll Result",
                description=f"{ctx.author.mention} :game_die: Rolling: `{dice_expression}`",
                color=discord.Color.blue()
            )
            embed.add_field(name="Detail", value=detail, inline=False)
            embed.add_field(name="Total", value=f":game_die: {result}", inline=False)
            await send_msg(embed=embed)
            return
        except Exception:
            pass

        # 2. Skill Check Logic
        user_id = str(ctx.author.id)
        player_stats = await load_player_stats()

        if user_id not in player_stats.get(server_id, {}):
            await send_msg(content=f"{ctx.author.display_name} doesn't have an investigator. Use `/newinvestigator`.")
            return

        try:
            # Skill Matching Logic
            clean_expression = dice_expression
            match = re.match(r"^(.*?)\s*\(\d+\)$", dice_expression)
            if match: clean_expression = match.group(1)

            normalized_input = clean_expression.lower()
            matching_stats = []

            stats = player_stats[server_id][user_id]

            # 1. Exact Key Match
            for k in stats.keys():
                if k.lower() == normalized_input:
                    matching_stats.append(k)
                    break

            # 2. Word Match
            if not matching_stats:
                for k in stats.keys():
                    if any(word.lower() == k.lower() for word in normalized_input.split()):
                        matching_stats.append(k)
                        break

            # 3. Partial Match
            if not matching_stats:
                for k in stats.keys():
                    if any(word.lower() in k.lower() for word in normalized_input.split()):
                        matching_stats.append(k)

            if not matching_stats:
                await send_msg(content="No matching skill found.")
                return

            stat_name = matching_stats[0]
            current_value = stats[stat_name]

            if len(matching_stats) > 1:
                view = DisambiguationView(ctx, matching_stats)
                msg = await send_msg(content="Multiple matching stats found. Please select one:", view=view)
                await view.wait()
                if view.selected_stat:
                    stat_name = view.selected_stat
                    current_value = stats[stat_name]
                    try: await msg.delete()
                    except: pass
                else:
                    try: await msg.edit(content="Selection cancelled.", view=None)
                    except: pass
                    return

            # ROLL LOGIC
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
            else: final_roll = possible_rolls[0] # Should only be 1

            result_text, result_tier = self.calculate_roll_result(final_roll, current_value)

            luck_threshold = (await load_luck_stats()).get(server_id, 10)

            # View
            view = RollResultView(
                ctx=ctx,
                cog=self,
                player_stats=player_stats,
                server_id=server_id,
                user_id=user_id,
                stat_name=stat_name,
                current_value=current_value,
                ones_roll=ones_roll,
                tens_rolls=tens_rolls,
                net_dice=net_dice,
                result_tier=result_tier,
                luck_threshold=luck_threshold
            )

            # Embed
            color = discord.Color.green()
            if result_tier == 5 or result_tier == 4: color = 0xF1C40F
            elif result_tier == 3 or result_tier == 2: color = 0x2ECC71
            elif result_tier == 1: color = 0xE74C3C
            elif result_tier == 0: color = 0x992D22

            tens_str = ", ".join(str(t) if t != 0 else "00" for t in tens_rolls)
            dice_text = "Normal"
            if net_dice > 0: dice_text = f"Bonus ({net_dice})"
            elif net_dice < 0: dice_text = f"Penalty ({abs(net_dice)})"

            description = f"{ctx.author.mention} :game_die: **{dice_text}** Check\n"
            description += f"Dice: [{tens_str}] + {ones_roll} -> **{final_roll}**\n\n"
            description += f"**{result_text}**\n\n"
            description += f"**{stat_name}**: {current_value} - {current_value // 2} - {current_value // 5}\n"
            description += f":four_leaf_clover: LUCK: {player_stats[server_id][user_id]['LUCK']}"

            embed = discord.Embed(description=description, color=color)
            view.message = await send_msg(embed=embed, view=view)
            await view.wait()

            await save_player_stats(player_stats)

            # Session Check
            if view.success:
                 session_data = await load_session_data()
                 if user_id not in session_data:
                     # Ask
                     sess_view = SessionView(ctx)
                     msg = await send_msg(content="**Start a gaming session to record this success?**", view=sess_view)
                     await sess_view.wait()
                     if sess_view.create_session:
                         session_data[user_id] = []
                         await save_session_data(session_data)
                         await session_success(user_id, stat_name)
                         await msg.edit(content="Session started!", view=None)
                     else:
                         await msg.delete()
                 else:
                     await session_success(user_id, stat_name)

        except Exception as e:
            import traceback
            traceback.print_exc()
            await send_msg(content=f"An error occurred: {e}")

    @roll.autocomplete('dice_expression')
    async def roll_autocomplete(self, interaction: discord.Interaction, current: str):
        server_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        choices = []
        if server_id in player_stats and user_id in player_stats[server_id]:
            for stat, value in player_stats[server_id][user_id].items():
                choices.append(f"{stat} ({value})")
        else:
            skills_data = await load_skills_data()
            choices = list(skills_data.keys())

        if not current:
            sorted_choices = sorted(choices)[:25]
            return [app_commands.Choice(name=c[:100], value=c[:100]) for c in sorted_choices]

        matches = process.extract(current, choices, scorer=fuzz.WRatio, limit=25)
        results = []
        for m in matches:
            results.append(app_commands.Choice(name=m[0][:100], value=m[0][:100]))
        return results

async def setup(bot):
    await bot.add_cog(Roll(bot))
