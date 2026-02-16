import discord
import re
import math
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from loadnsave import load_player_stats, save_player_stats, load_gamemode_stats
from emojis import get_stat_emoji
from rapidfuzz import process, fuzz

class LimitCheckView(View):
    def __init__(self, user, limit):
        super().__init__(timeout=60)
        self.user = user
        self.limit = limit
        self.result = None # 'proceed', 'stop', 'max'

    @discord.ui.button(label="Go over limit", style=discord.ButtonStyle.danger, emoji="✅")
    async def proceed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
             return await interaction.response.send_message("Not your choice!", ephemeral=True)
        self.result = 'proceed'
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.secondary, emoji="❌")
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
             return await interaction.response.send_message("Not your choice!", ephemeral=True)
        self.result = 'stop'
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Set to Max", style=discord.ButtonStyle.success, emoji="📈")
    async def set_max(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
             return await interaction.response.send_message("Not your choice!", ephemeral=True)
        self.result = 'max'
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self):
        self.stop()

class CalculationView(View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user
        self.confirmed = None # True, False, None (timeout)

    @discord.ui.button(label="Calculate", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
             return await interaction.response.send_message("Not your choice!", ephemeral=True)
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
             return await interaction.response.send_message("Not your choice!", ephemeral=True)
        self.confirmed = False
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self):
        self.stop()

class stat(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def check_limit(self, interaction, stat_key, new_value, limit, emoji_key):
        view = LimitCheckView(interaction.user, limit)
        msg = await interaction.edit_original_response(content=f"Are you sure you want to surpass your **{stat_key}**:{emoji_key}: limit ({limit})?", view=view)
        await view.wait()

        if view.result is None:
             await msg.edit(content=f"Timed out. **{stat_key}**:{emoji_key}: will not be saved.", view=None)
             return None
        elif view.result == 'stop':
             await msg.edit(content=f"**{stat_key}**:{emoji_key}: will not be saved.", view=None)
             return None
        elif view.result == 'max':
             await msg.edit(content=f"Setting to limit {limit}...", view=None)
             return limit
        else: # proceed
             await msg.edit(content="Proceeding with over-limit value...", view=None)
             return new_value

    async def prompt_calculation(self, interaction, stat_name, calculated_value, player_stats, server_id, user_id):
        emoji = get_stat_emoji(stat_name)
        view = CalculationView(interaction.user)
        msg = await interaction.followup.send(f"{interaction.user.display_name} filled all stats for **{stat_name}**{emoji}. Calculate it to **{calculated_value}**?", view=view, ephemeral=True, wait=True)
        await view.wait()

        if view.confirmed:
            player_stats[server_id][user_id][stat_name] = calculated_value
            await save_player_stats(player_stats)
            await msg.edit(content=f"**{stat_name}** set to **{calculated_value}**.", view=None)
        else:
            if view.confirmed is False: # Cancelled explicitly
                await msg.edit(content=f"Calculation for **{stat_name}** skipped.", view=None)
            else: # Timeout
                await msg.edit(content=f"Timed out. Calculation for **{stat_name}** skipped.", view=None)

    @app_commands.command(description="Change the value of a skill or stat for your character.")
    @app_commands.describe(stat_name="The name of the stat/skill (e.g. HP, STR, Spot Hidden)", value="The new value (e.g. 50) or change (e.g. +5, -5)")
    async def stat(self, interaction: discord.Interaction, stat_name: str, value: str):
        """
        Update your investigator's stats.
        """
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild_id:
             await interaction.edit_original_response(content="This command must be used in a server.")
             return

        server_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        # Check if the player has an investigator
        if server_id not in player_stats or user_id not in player_stats[server_id]:
            await interaction.edit_original_response(content=f"{interaction.user.display_name} doesn't have an investigator. Use `/newinvestigator` for creating a new investigator.")
            return

        # Clean up stat_name from autocomplete (e.g. "Spot Hidden (50)" -> "Spot Hidden")
        clean_stat_name = stat_name
        match = re.match(r"^(.*?)\s*\(\d+\)$", stat_name)
        if match:
            clean_stat_name = match.group(1)

        # Find the stat
        matching_stats = []
        user_stats = player_stats[server_id][user_id]

        # 1. Exact match (case insensitive)
        for key in user_stats.keys():
            if key.lower() == clean_stat_name.lower():
                matching_stats.append(key)
                break

        # 2. Fuzzy match if no exact match
        if not matching_stats:
             # Use rapidfuzz to find best matches
            choices = list(user_stats.keys())
            extract = process.extractOne(clean_stat_name, choices, scorer=fuzz.WRatio)
            if extract:
                match_key, score, _ = extract
                if score > 80: # Threshold for confidence
                    matching_stats.append(match_key)

        if not matching_stats:
            await interaction.edit_original_response(content=f"Stat '{clean_stat_name}' not found.")
            return

        stat_key = matching_stats[0]
        current_value = user_stats[stat_key]

        # Parse the value
        # Check for relative change (+5, -5) or absolute set (50)
        value_match = re.match(r'^([+\-]?)(\d+)$', value.strip())
        if not value_match:
            await interaction.edit_original_response(content="Invalid value format. Use numbers (e.g. 50) or relative changes (e.g. +5, -5).")
            return

        sign = value_match.group(1)
        number = int(value_match.group(2))
        change_value = 0
        new_value = 0

        if sign == '+':
            change_value = number
            new_value = current_value + number
        elif sign == '-':
            change_value = -number
            new_value = current_value - number
        else:
            new_value = number
            change_value = new_value - current_value

        # Logic checks (Max HP, MP, SAN, etc.)
        server_stats = await load_gamemode_stats()
        if server_id not in server_stats:
            server_stats[server_id] = {}
        if 'game_mode' not in server_stats[server_id]:
            server_stats[server_id]['game_mode'] = 'Call of Cthulhu'
        current_mode = server_stats[server_id]['game_mode']

        # Determine limits
        limit = None
        emoji_key = None

        if stat_key == "HP":
             emoji_key = "heartpulse"
             con = user_stats.get("CON", 0)
             siz = user_stats.get("SIZ", 0)
             if current_mode == 'Call of Cthulhu':
                 limit = math.floor((con + siz) / 10)
             else: # Pulp
                 limit = math.floor((con + siz) / 5)
        elif stat_key == "MP":
             emoji_key = "sparkles"
             pow_stat = user_stats.get("POW", 0)
             limit = math.floor(pow_stat / 5)
        elif stat_key == "SAN":
             emoji_key = "scales"
             limit = 99 - user_stats.get("Cthulhu Mythos", 0)

        # Check limit
        limit_check_triggered = False
        if limit is not None and new_value > limit:
             limit_check_triggered = True
             result = await self.check_limit(interaction, stat_key, new_value, limit, emoji_key)
             if result is None: return # Stopped
             new_value = result
             # Recalculate change_value in case new_value changed (e.g. set to max)
             change_value = new_value - current_value

        # Update and Save
        player_stats[server_id][user_id][stat_key] = new_value
        await save_player_stats(player_stats)

        # Response
        color = discord.Color.green() if change_value >= 0 else discord.Color.red()
        stat_emoji = get_stat_emoji(stat_key)

        embed = discord.Embed(
            title=f"Stat Change - {stat_emoji} {stat_key}",
            description=f"**{interaction.user.display_name}**, you've updated your '{stat_key}' stat.",
            color=color
        )
        embed.add_field(name="Previous Value", value=str(current_value), inline=True)
        embed.add_field(name="Change", value=f"{change_value:+}", inline=True)
        embed.add_field(name="New Value", value=str(new_value), inline=True)

        if limit_check_triggered:
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.edit_original_response(content=None, embed=embed)

        # Trigger auto-calcs
        # HP Calculation Trigger
        if stat_key in ["CON", "SIZ"]:
            if user_stats.get("CON", 0) != 0 and user_stats.get("SIZ", 0) != 0 and user_stats.get("HP", 0) == 0:
                 hp_val = 0
                 if current_mode == 'Call of Cthulhu': hp_val = math.floor((user_stats["CON"] + user_stats["SIZ"]) / 10)
                 else: hp_val = math.floor((user_stats["CON"] + user_stats["SIZ"]) / 5)
                 await self.prompt_calculation(interaction, "HP", hp_val, player_stats, server_id, user_id)

        # MP Calculation Trigger
        if stat_key == "POW":
            if user_stats.get("POW", 0) != 0 and user_stats.get("MP", 0) == 0:
                await self.prompt_calculation(interaction, "MP", math.floor(user_stats["POW"] / 5), player_stats, server_id, user_id)
            if user_stats.get("POW", 0) != 0 and user_stats.get("SAN", 0) == 0:
                await self.prompt_calculation(interaction, "SAN", user_stats["POW"], player_stats, server_id, user_id)

        # Dodge Calculation Trigger
        if stat_key == "DEX":
            if user_stats.get("DEX", 0) != 0 and user_stats.get("Dodge", 0) == 0:
                await self.prompt_calculation(interaction, "Dodge", math.floor(user_stats["DEX"] / 2), player_stats, server_id, user_id)

        # Language Own Calculation Trigger
        if stat_key == "EDU":
             if user_stats.get("EDU", 0) != 0 and user_stats.get("Language own", 0) == 0:
                 await self.prompt_calculation(interaction, "Language own", user_stats["EDU"], player_stats, server_id, user_id)

        # Age Warning
        if stat_key in ["STR", "DEX", "CON", "EDU", "APP", "SIZ", "LUCK"] and user_stats.get("Age", 0) == 0:
             # Check if all filled
             if all(user_stats.get(k, 0) != 0 for k in ["STR", "DEX", "CON", "EDU", "APP", "SIZ", "LUCK"]):
                 await interaction.followup.send(f"{interaction.user.display_name} filled all stats affected by Age. Fill your age with `/stat stat_name: Age value: <value>`", ephemeral=True)

        # Age specific advice
        if stat_key == "Age":
            age = user_stats["Age"]
            if age < 15: await interaction.followup.send("Age Modifiers: No official rules for <15.", ephemeral=True)
            elif age < 20: await interaction.followup.send("Age Modifiers (<20): Deduct 5 from STR/SIZ. Deduct 5 from EDU. Roll Luck twice (take high).", ephemeral=True)
            elif age < 40: await interaction.followup.send("Age Modifiers (<40): Improvement check for EDU.", ephemeral=True)
            elif age < 50: await interaction.followup.send("Age Modifiers (<50): 2 EDU checks. Deduct 5 from STR/CON/DEX. APP -5.", ephemeral=True)
            elif age < 60: await interaction.followup.send("Age Modifiers (<60): 3 EDU checks. Deduct 10 from STR/CON/DEX. APP -10.", ephemeral=True)
            elif age < 70: await interaction.followup.send("Age Modifiers (<70): 4 EDU checks. Deduct 20 from STR/CON/DEX. APP -15.", ephemeral=True)
            elif age < 80: await interaction.followup.send("Age Modifiers (<80): 4 EDU checks. Deduct 40 from STR/CON/DEX. APP -20.", ephemeral=True)
            elif age < 90: await interaction.followup.send("Age Modifiers (<90): 4 EDU checks. Deduct 80 from STR/CON/DEX. APP -25.", ephemeral=True)
            else: await interaction.followup.send("Age Modifiers (90+): No official rules.", ephemeral=True)

    @stat.autocomplete('stat_name')
    async def stat_autocomplete(self, interaction: discord.Interaction, current: str):
        server_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        if server_id not in player_stats or user_id not in player_stats[server_id]:
            return []

        user_stats = player_stats[server_id][user_id]
        choices = [f"{k} ({v})" for k, v in user_stats.items()]

        if not current:
            return [app_commands.Choice(name=c, value=c) for c in sorted(choices)[:25]]

        matches = process.extract(current, choices, scorer=fuzz.WRatio, limit=25)
        return [app_commands.Choice(name=m[0], value=m[0]) for m in matches]


async def setup(bot):
    await bot.add_cog(stat(bot))
