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
    load_session_data,
    save_session_data,
    load_luck_stats,
    load_skills_data,
    load_skill_sound_settings,
    load_server_volumes
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

class DamageSelect(Select):
    def __init__(self, damage_data, parent_view):
        self.parent_view = parent_view
        options = []
        for d in damage_data:
            lbl = d.get('label', 'Damage')
            val = d.get('value', '0')
            # Truncate if needed
            options.append(discord.SelectOption(label=lbl[:100], value=val, description=f"Rolls {val}"))
        super().__init__(placeholder="Select damage type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        chosen_formula = self.values[0]
        # Find label for display
        chosen_label = next((d['label'] for d in self.parent_view.damage_data if d['value'] == chosen_formula), "Damage")
        await self.parent_view.perform_damage_roll(interaction, chosen_formula, chosen_label)

class DamageSelectView(View):
    def __init__(self, damage_data, parent_view):
        super().__init__(timeout=60)
        self.damage_data = damage_data
        self.parent_view = parent_view
        self.add_item(DamageSelect(damage_data, parent_view))

class RollResultView(View):
    def __init__(self, ctx, cog, player_stats, server_id, user_id, stat_name, current_value,
                 ones_roll, tens_rolls, net_dice, result_tier, luck_threshold,
                 malfunction_threshold=None, on_complete=None,
                 damage_data=None, damage_bonus=None):
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

        self.malfunction_threshold = malfunction_threshold
        self.on_complete = on_complete
        self.is_malfunction = False

        self.damage_data = damage_data
        self.damage_bonus = damage_bonus
        self.luck_used = False

        self.roll = self._calculate_current_roll() # Initial calculation
        self.success = False
        if self.result_tier >= 2:
            self.success = True

        # Initial Malfunction Check
        if self.malfunction_threshold is not None:
            try:
                limit = int(self.malfunction_threshold)
                if self.roll >= limit:
                    self.is_malfunction = True
                    self.success = False # Malfunction overrides success usually
            except:
                pass

        # Cleanup Context: Remove Damage Button if irrelevant
        if not self.damage_data:
            to_remove = []
            for child in self.children:
                if isinstance(child, Button) and child.label == "Roll Damage":
                    to_remove.append(child)
            for child in to_remove:
                self.remove_item(child)

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
        # Locate buttons in children
        bonus_btn = None
        penalty_btn = None
        luck_btn = None
        push_btn = None
        damage_btn = None

        for child in self.children:
            if isinstance(child, Button):
                if child.label == "Bonus Die": bonus_btn = child
                elif child.label == "Penalty Die": penalty_btn = child
                elif "Use Luck" in (child.label or ""): luck_btn = child
                elif child.label == "Push Roll": push_btn = child
                elif child.label == "Roll Damage": damage_btn = child

        if self.luck_used:
            # If luck used, dice mods are locked
            if bonus_btn: bonus_btn.disabled = True
            if penalty_btn: penalty_btn.disabled = True
            if push_btn: push_btn.disabled = True
            if luck_btn: luck_btn.disabled = True

            # Damage is allowed if success
            if damage_btn:
                if self.success and not self.is_malfunction:
                    damage_btn.disabled = False
                else:
                    damage_btn.disabled = True
            return

        # --- Normal Logic (No Luck Used Yet) ---

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

        if luck_btn:
            luck_btn.disabled = not can_luck
            if can_luck:
                luck_btn.label = f"Use Luck (-{luck_cost})"
            else:
                luck_btn.label = "Use Luck"

        # PUSH Logic (Only on Normal Fail)
        can_push = False
        if self.net_dice == 0 and self.stat_name != "LUCK" and self.result_tier == 1:
             can_push = True

        if push_btn:
            push_btn.disabled = not can_push

        # Max Dice Limit (CoC doesn't specify hard limit, but UI should)
        # Limit to +/- 2 dice
        if bonus_btn: bonus_btn.disabled = self.net_dice >= 2
        if penalty_btn: penalty_btn.disabled = self.net_dice <= -2

        # Damage Button Logic
        if damage_btn:
            if self.success and self.damage_data and not self.is_malfunction:
                 damage_btn.disabled = False
            else:
                 damage_btn.disabled = True

    async def _update_state_and_embed(self, interaction):
        self.roll = self._calculate_current_roll()

        result_text, result_tier = self.cog.calculate_roll_result(self.roll, self.current_value)
        self.result_tier = result_tier
        self.success = result_tier >= 2

        # Malfunction Check
        self.is_malfunction = False
        if self.malfunction_threshold is not None:
            try:
                limit = int(self.malfunction_threshold)
                if self.roll >= limit:
                    self.is_malfunction = True
                    self.success = False
                    result_text = "🔫 MALFUNCTION! (Weapon Jammed)"
            except:
                pass

        self.update_buttons()

        # Rebuild Embed
        embed = interaction.message.embeds[0]

        # Determine Color
        color = discord.Color.green() # Default Regular/Hard
        if result_tier == 5 or result_tier == 4: color = 0xF1C40F # Gold
        elif result_tier == 3 or result_tier == 2: color = 0x2ECC71 # Green
        elif result_tier == 1: color = 0xE74C3C # Red
        elif result_tier == 0: color = 0x992D22 # Dark Red

        if self.is_malfunction:
            color = discord.Color.dark_red()

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
        self.luck_used = True

        # Visual Update
        result_text_map = {
            2: "Regular Success (LUCK Used) :heavy_check_mark:",
            3: "Hard Success (LUCK Used) :white_check_mark:",
            4: "Extreme Success (LUCK Used) :star:"
        }
        result_text = result_text_map.get(self.result_tier, "Success (LUCK Used)")

        # Update Buttons (Handles enabling Damage if valid)
        self.update_buttons()

        embed = interaction.message.embeds[0]
        formatted_luck = f":four_leaf_clover: LUCK: {self.player_stats[self.server_id][self.user_id]['LUCK']}"
        formatted_skill = f"**{self.stat_name}**: {self.current_value} - {self.current_value // 2} - {self.current_value // 5}"

        # Reconstruct description with updated Luck
        desc_parts = embed.description.split("\n\n")
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

        # Trigger Callback if exists
        if self.on_complete:
            try:
                if asyncio.iscoroutinefunction(self.on_complete):
                    await self.on_complete(self.roll, self.result_tier, self.is_malfunction)
                else:
                    self.on_complete(self.roll, self.result_tier, self.is_malfunction)
            except Exception as e:
                print(f"Error in on_complete callback: {e}")

        self.stop()
        # Disable
        try:
            for child in self.children: child.disabled = True
            await interaction.message.edit(view=self)
        except: pass

    @discord.ui.button(label="Roll Damage", style=discord.ButtonStyle.danger, emoji="⚔️", row=2, disabled=True)
    async def damage_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.damage_data: return

        if len(self.damage_data) == 1:
            # Direct Roll
            item = self.damage_data[0]
            await self.perform_damage_roll(interaction, item['value'], item['label'])
        else:
            # Selection
            view = DamageSelectView(self.damage_data, self)
            await interaction.response.send_message("Select damage type:", view=view, ephemeral=True)

    async def perform_damage_roll(self, interaction, formula, label):
        # Add DB if applicable
        final_formula = formula
        if self.damage_bonus and str(self.damage_bonus) not in ["0", "+0", "-0"]:
             final_formula += f" + {self.damage_bonus}"
             # Clean up " + -" -> " - "
             final_formula = final_formula.replace("+ -", "- ")

        try:
             result, detail = self.cog.evaluate_dice_expression(final_formula)

             # Construct Result Embed
             embed = discord.Embed(title=f"⚔️ Damage Roll: {label}", description=f"**{result}** Damage", color=discord.Color.dark_red())
             embed.add_field(name="Formula", value=f"`{final_formula}`")
             embed.add_field(name="Detail", value=detail, inline=False)
             embed.set_footer(text="Combat Log")

             if not interaction.response.is_done():
                 await interaction.response.send_message(embed=embed)
             else:
                 await interaction.followup.send(embed=embed)

        except Exception as e:
             if not interaction.response.is_done():
                 await interaction.response.send_message(f"Error rolling damage: {e}", ephemeral=True)
             else:
                 await interaction.followup.send(f"Error rolling damage: {e}", ephemeral=True)

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

            # Sound Logic
            try:
                if ctx.guild and ctx.guild.voice_client and ctx.guild.voice_client.is_connected():
                    # Check settings
                    sound_settings = await load_skill_sound_settings()
                    guild_settings = sound_settings.get(server_id, {})

                    tier_map = {
                        5: 'critical',
                        4: 'extreme',
                        3: 'hard',
                        2: 'regular',
                        1: 'fail',
                        0: 'fumble'
                    }
                    result_key = tier_map.get(result_tier)

                    if result_key:
                        sound_file = None
                        # 1. Check Specific Skill
                        if 'skills' in guild_settings and stat_name in guild_settings['skills']:
                             sound_file = guild_settings['skills'][stat_name].get(result_key)

                        # 2. Check Default
                        if not sound_file and 'default' in guild_settings:
                             sound_file = guild_settings['default'].get(result_key)

                        if sound_file:
                             # Import inside function to avoid potential circular dependency issues at top level if any
                             # though we already established it might be safe, being cautious.
                             from dashboard.app import guild_mixers, SOUNDBOARD_FOLDER
                             import os

                             mixer = guild_mixers.get(server_id)
                             # If no mixer exists for this guild yet, we should create one?
                             # Usually created by Music cog or Soundboard join.
                             # If user manually joined bot but didn't play anything, mixer might not exist.
                             if not mixer:
                                 from dashboard.audio_mixer import MixingAudioSource
                                 mixer = MixingAudioSource()
                                 guild_mixers[server_id] = mixer

                             full_path = os.path.join(SOUNDBOARD_FOLDER, sound_file)
                             if os.path.exists(full_path):
                                 # Check if voice_client is playing mixer
                                 vc = ctx.guild.voice_client
                                 is_playing_mixer = False
                                 if vc.is_playing() and isinstance(vc.source, discord.PCMVolumeTransformer):
                                     if vc.source.original == mixer:
                                         is_playing_mixer = True

                                 if not is_playing_mixer:
                                     # If not playing mixer, we should play it.
                                     # Stop whatever is playing (if anything)
                                     if vc.is_playing():
                                         vc.stop()

                                     source = discord.PCMVolumeTransformer(mixer, volume=1.0)
                                     vc.play(source)

                                 # Get Volume
                                 volumes = await load_server_volumes()
                                 vol_data = volumes.get(server_id, {'music': 1.0, 'soundboard': 0.5})
                                 sb_vol = vol_data.get('soundboard', 0.5)

                                 mixer.add_track(
                                     full_path,
                                     volume=sb_vol,
                                     loop=False,
                                     metadata={'type': 'soundboard', 'trigger': 'roll'}
                                 )
            except Exception as e:
                print(f"Error playing roll sound: {e}")

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
            stats = player_stats[server_id][user_id]
            valid_stats = []
            # Keys to exclude from rolling
            ignored_keys = [
                "NAME", "Name", "Residence", "Occupation", "Game Mode",
                "Archetype", "Archetype Info", "Backstory", "Custom Emojis",
                "Age", "Move", "Build", "Damage Bonus", "Bonus Damage",
                "CustomSkill", "CustomSkills", "CustomSkillss", "Occupation Info"
            ]

            for k, v in stats.items():
                if k in ignored_keys: continue
                # Only include numeric values (rolls need numbers)
                if isinstance(v, (int, float)):
                    valid_stats.append((k, v))

            # Sort by value descending (highest skill first)
            valid_stats.sort(key=lambda x: x[1], reverse=True)

            choices = [f"{k} ({v})" for k, v in valid_stats]
        else:
            skills_data = await load_skills_data()
            choices = sorted(list(skills_data.keys()))

        if not current:
            # Already sorted by value if we had stats
            return [app_commands.Choice(name=c[:100], value=c[:100]) for c in choices[:25]]

        matches = process.extract(current, choices, scorer=fuzz.WRatio, limit=25)
        results = []
        for m in matches:
            results.append(app_commands.Choice(name=m[0][:100], value=m[0][:100]))
        return results

async def setup(bot):
    await bot.add_cog(Roll(bot))
