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
)
from emojis import get_stat_emoji
from support_functions import session_success

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

class RollTypeView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.roll_type = None

    @discord.ui.button(label="Normal", style=discord.ButtonStyle.primary, emoji="🎲")
    async def normal(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.roll_type = "normal"
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Bonus", style=discord.ButtonStyle.success, emoji="🟢")
    async def bonus(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.roll_type = "bonus"
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Penalty", style=discord.ButtonStyle.danger, emoji="🔴")
    async def penalty(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.roll_type = "penalty"
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Not your session!", ephemeral=True)
            return False
        return True

class PostRollView(View):
    def __init__(self, ctx, cog, player_stats, server_id, user_id, stat_name, current_value,
                 initial_roll, initial_tier, roll_type, luck_threshold):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog
        self.player_stats = player_stats
        self.server_id = server_id
        self.user_id = user_id
        self.stat_name = stat_name
        self.current_value = current_value
        self.roll = initial_roll
        self.result_tier = initial_tier
        self.roll_type = roll_type
        self.luck_threshold = luck_threshold

        self.message = None
        self.success = False

        if self.result_tier >= 2:
            self.success = True

        self.update_buttons()

    def update_buttons(self):
        can_luck = False
        luck_cost = 0
        player_luck = self.player_stats[self.server_id][self.user_id]['LUCK']

        if self.roll_type == "normal" and self.stat_name != "LUCK" and self.result_tier != 0:
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

        can_push = False
        if self.roll_type == "normal" and self.stat_name != "LUCK" and self.result_tier == 1:
             can_push = True

        self.push_button.disabled = not can_push

    @discord.ui.button(label="Use Luck", style=discord.ButtonStyle.success, emoji="🍀")
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

        result_text_map = {
            2: "Regular Success (LUCK Used) :heavy_check_mark:",
            3: "Hard Success (LUCK Used) :white_check_mark:",
            4: "Extreme Success (LUCK Used) :star:"
        }
        result_text = result_text_map.get(self.result_tier, "Success (LUCK Used)")

        await self.update_embed(interaction, result_text)

        self.update_buttons()
        self.push_button.disabled = True

        await interaction.message.edit(view=self)

    @discord.ui.button(label="Push Roll", style=discord.ButtonStyle.danger, emoji="🔄")
    async def push_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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

        self.luck_button.disabled = True
        self.push_button.disabled = True
        self.stop()

        await interaction.response.edit_message(embed=original_embed, view=None)

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary)
    async def done_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()

    async def update_embed(self, interaction, result_text):
        embed = interaction.message.embeds[0]
        formatted_luck = f":four_leaf_clover: LUCK: {self.player_stats[self.server_id][self.user_id]['LUCK']}"
        formatted_skill = f"**{self.stat_name}**: {self.current_value} - {self.current_value // 2} - {self.current_value // 5}"

        description_roll_info = f"{self.ctx.author.mention} :game_die: Rolled: {self.roll}"

        embed.description = f"{description_roll_info}\n{result_text}\n{formatted_skill}\n{formatted_luck}"

        await interaction.response.edit_message(embed=embed)

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

class newroll(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def evaluate_dice_expression(self, expression):
        # Replace D with 'd' and remove spaces
        expression = expression.replace('D', 'd').replace(' ', '')
        detail_parts = []

        # Define a function to handle dice rolls
        def roll_dice(match):
            num, size = map(int, match.groups())
            rolls = [random.randint(1, size) for _ in range(num)]
            detail_parts.append(f":game_die: {num}d{size}: {' + '.join(map(str, rolls))} = {sum(rolls)}")
            return sum(rolls)

        # Replace dice roll expressions with their results
        dice_pattern = re.compile(r'(\d+)d(\d+)')
        expression = dice_pattern.sub(lambda m: str(roll_dice(m)), expression)

        # Evaluate the expression
        # Only allow safe characters
        if not re.match(r'^[\d+\-*/().]+$', expression):
            raise ValueError("Invalid dice expression")

        result = eval(expression, {"__builtins__": None})
        detail = "\n".join(detail_parts) + f"\nExpression: {expression}"
        return result, detail

    def calculate_roll_result(self, roll, skill_value):
        # Fumble Logic - Check first because 100 is always Fumble/Fail
        is_fumble = False
        if skill_value < 50:
            if roll >= 96:
                is_fumble = True
        else:
            if roll == 100:
                is_fumble = True

        if is_fumble:
            return "Fumble :warning:", 0

        # Success Logic
        if roll == 1:
            return "Critical Success :star2:", 5
        elif roll <= skill_value // 5:
            return "Extreme Success :star:", 4
        elif roll <= skill_value // 2:
            return "Hard Success :white_check_mark:", 3
        elif roll <= skill_value:
            return "Regular Success :heavy_check_mark:", 2

        # If not Success and not Fumble, it is Fail
        return "Fail :x:", 1

    @commands.hybrid_command(name="newroll", aliases=["roll", "diceroll", "d", "nd"], guild_only=True, description="Perform a dice roll or skill check.")
    @app_commands.describe(dice_expression="The dice expression (e.g. 3d6) or skill name (e.g. Spot Hidden)")
    async def newroll(self, ctx, *, dice_expression: str):
        """
        🎲 Perform a dice roll or skill check.
        Interactive interface allows for Bonus/Penalty dice and Luck spending.
        """
        server_prefixes = await load_server_stats()
        server_id = str(ctx.guild.id)
        prefix = server_prefixes.get(server_id, "!") if server_id else "!"

        luck_stats = await load_luck_stats()
        luck_threshold = luck_stats.get(server_id, 10)

        # 1. Try to evaluate as dice expression (e.g. 3d6)
        try:
            result, detail = self.evaluate_dice_expression(dice_expression)
            embed = discord.Embed(
                title=f":game_die: Dice Roll Result",
                description=f"{ctx.author.mention} :game_die: Rolling: `{dice_expression}`",
                color=discord.Color.blue()
            )
            embed.add_field(name="Detail", value=detail, inline=False)
            embed.add_field(name="Total", value=f":game_die: {result}", inline=False)
            await ctx.send(embed=embed)
            return
        except Exception:
            # Not a valid dice expression, assume it is a Skill Check
            pass

        # 2. Skill Check Logic
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command is not allowed in DMs.")
            return
        user_id = str(ctx.author.id)

        player_stats = await load_player_stats()

        if user_id not in player_stats[server_id]:
            await ctx.send(
                f"{ctx.author.display_name} doesn't have an investigator. Use `{prefix}newInv` for creating a new investigator."
            )
            return

        try:
            normalized_dice_expression = dice_expression.lower()
            matching_stats = []

            # Exact match
            for stat_key, stat_value in player_stats[server_id][user_id].items():
                if any(word.lower() == stat_key.lower() for word in normalized_dice_expression.split()):
                    matching_stats.append(stat_key)
                    break

            # Partial match if no exact match
            if not matching_stats:
                for stat_key, stat_value in player_stats[server_id][user_id].items():
                    if any(word.lower() in stat_key.lower() for word in normalized_dice_expression.split()):
                        matching_stats.append(stat_key)

            if not matching_stats:
                await ctx.send("No matching stat found and invalid dice expression.")
                return

            stat_name = matching_stats[0]
            current_value = player_stats[server_id][user_id][stat_name]

            if len(matching_stats) > 1:
                # Use DisambiguationView
                view = DisambiguationView(ctx, matching_stats)
                msg = await ctx.send("Multiple matching stats found. Please select one:", view=view)
                await view.wait()

                if view.selected_stat:
                    stat_name = view.selected_stat
                    current_value = player_stats[server_id][user_id][stat_name]
                    await msg.delete()
                else:
                    await msg.edit(content="Selection timed out or cancelled.", view=None)
                    return

            # Ask for Roll Type
            view = RollTypeView(ctx)
            embed = discord.Embed(
                title=f"Select Roll Type for {stat_name}",
                description="Choose the type of roll:",
                color=discord.Color.blue()
            )
            msg = await ctx.send(embed=embed, view=view)
            await view.wait()

            if view.roll_type:
                roll_type = view.roll_type
                await msg.delete()
            else:
                await msg.edit(content="Roll cancelled.", view=None, embed=None)
                return

            # Perform the Roll
            ASKFORSESSION = 0
            SUCCESSFULLROLL = 0
            session_data = await load_session_data()
            if user_id not in session_data:
                ASKFORSESSION = 1

            roll = 0
            tens_rolls = []
            ones_roll = 0

            if roll_type == "normal":
                roll = random.randint(1, 100)
            else:
                tens_rolls = [random.randint(0, 9) * 10 for _ in range(2)]
                ones_roll = random.randint(1, 10)
                if roll_type == "bonus":
                    lower_tens_roll = min(tens_rolls)
                    roll = lower_tens_roll + ones_roll
                else: # penalty
                    higher_tens_roll = max(tens_rolls)
                    roll = higher_tens_roll + ones_roll

            result_text, result_tier = self.calculate_roll_result(roll, current_value)

            # Post Roll Interaction (Luck/Push)
            post_roll_view = PostRollView(
                ctx=ctx,
                cog=self,
                player_stats=player_stats,
                server_id=server_id,
                user_id=user_id,
                stat_name=stat_name,
                current_value=current_value,
                initial_roll=roll,
                initial_tier=result_tier,
                roll_type=roll_type,
                luck_threshold=luck_threshold
            )

            # Initial Embed construction
            formatted_luck = f":four_leaf_clover: LUCK: {player_stats[server_id][user_id]['LUCK']}"
            formatted_skill = f"**{stat_name}**: {current_value} - {current_value // 2} - {current_value // 5}"

            description_roll_info = f"{ctx.author.mention} :game_die: Rolled: {roll}"
            if roll_type != "normal":
                description_roll_info = f"{ctx.author.mention} :game_die: Rolled: {tens_rolls[0]}|{tens_rolls[1]} + {ones_roll} = {roll}"

            embed = discord.Embed(
                title=f"{ctx.author.display_name}'s {roll_type.capitalize()} Check for '{stat_name}{get_stat_emoji(stat_name)}'",
                description=f"{description_roll_info}\n{result_text}\n{formatted_skill}\n{formatted_luck}",
                color=discord.Color.green(),
            )

            post_roll_view.message = await ctx.send(embed=embed, view=post_roll_view)
            await post_roll_view.wait()

            # After interaction, save stats (Luck might have changed)
            await save_player_stats(player_stats)

            # Disable buttons on final message
            if post_roll_view.message:
                try:
                    for child in post_roll_view.children:
                        child.disabled = True
                    await post_roll_view.message.edit(view=post_roll_view)
                except:
                    pass

            if post_roll_view.success:
                SUCCESSFULLROLL = 1
            else:
                SUCCESSFULLROLL = 0

            # Session Recording
            if SUCCESSFULLROLL == 1 and ASKFORSESSION == 1:
                view = SessionView(ctx)
                msg = await ctx.send(
                    "**Do you want to create a gaming session?**\n\nGaming session will record all your successful rolls for the character development phase.",
                    view=view
                )
                await view.wait()

                if view.create_session:
                    session_data[user_id] = []
                    await save_session_data(session_data)
                    await ctx.send("Session started! The first successful rolls have been recorded!")
                    await session_success(user_id, stat_name)
                else:
                    await ctx.send("Session creation canceled.")

                try: await msg.edit(view=None)
                except: pass

            elif SUCCESSFULLROLL == 1 and ASKFORSESSION == 0:
                await session_success(user_id, stat_name)

        except ValueError:
            embed = discord.Embed(
                title="Invalid Input",
                description=f"Use format {prefix}d <skill_name> or {prefix}d <expression>",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(newroll(bot))
