import discord
import re
import math
import asyncio
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, save_player_stats, load_server_stats, load_gamemode_stats
from emojis import get_stat_emoji
from rapidfuzz import process, fuzz


class stat(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(aliases=["cstat"], description="Change the value of a skill or stat for your character.")
    @app_commands.describe(stat_name="The name of the stat/skill (e.g. HP, STR, Spot Hidden)", value="The new value (e.g. 50) or change (e.g. +5, -5)")
    async def stat(self, ctx, stat_name: str, value: str):
        """
        Update your investigator's stats.
        Usage: /stat stat_name: <stat> value: <value>
        Example: /stat stat_name: HP value: +5
        """
        server_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        player_stats = await load_player_stats()
        server_prefixes = await load_server_stats()
        prefix = server_prefixes.get(server_id, "!") if server_id else "!"

        # Check if the command is used in a valid channel
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command is not allowed in DMs.")
            return

        # Check if the player has an investigator
        if user_id not in player_stats[server_id]:
            await ctx.send(
                f"{ctx.author.display_name} doesn't have an investigator. Use `{prefix}newInv` for creating a new investigator."
            )
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
            await ctx.send(f"Stat '{clean_stat_name}' not found.")
            return

        stat_key = matching_stats[0]
        current_value = user_stats[stat_key]

        # Parse the value
        # Check for relative change (+5, -5) or absolute set (50)
        value_match = re.match(r'^([+\-]?)(\d+)$', value.strip())
        if not value_match:
            await ctx.send("Invalid value format. Use numbers (e.g. 50) or relative changes (e.g. +5, -5).")
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
        # Loading game mode
        server_stats = await load_gamemode_stats()
        if server_id not in server_stats:
            server_stats[server_id] = {}
        if 'game_mode' not in server_stats[server_id]:
            server_stats[server_id]['game_mode'] = 'Call of Cthulhu'
        current_mode = server_stats[server_id]['game_mode']

        # Surpassing MAX_HP in Call of Cthulhu
        if current_mode == 'Call of Cthulhu' and stat_key == "HP" and new_value > (math.floor((user_stats["CON"] + user_stats["SIZ"]) / 10)):
            limit = math.floor((user_stats["CON"] + user_stats["SIZ"]) / 10)
            msg = await ctx.send(f"Are you sure you want to surpass your **HP**:heartpulse: limit ({limit})? \n ✅ - Go over the limit \n ❌ - Stop \n 📈 - Set to max")
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            await msg.add_reaction("📈")

            def check(reaction, user):
                return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["✅", "❌", "📈"]

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
                if str(reaction.emoji) == "✅":
                    pass
                elif str(reaction.emoji) == "📈":
                    new_value = limit
                    change_value = new_value - current_value
                elif str(reaction.emoji) == "❌":
                    await ctx.send("**HP**:heartpulse: will not be saved.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Timed out. **HP**:heartpulse: will not be saved.")
                return

        # Surpassing MAX_HP in Pulp of Cthulhu
        if current_mode == 'Pulp of Cthulhu' and stat_key == "HP" and new_value > (math.floor((user_stats["CON"] + user_stats["SIZ"]) / 5)):
            limit = math.floor((user_stats["CON"] + user_stats["SIZ"]) / 5)
            msg = await ctx.send(f"Are you sure you want to surpass your **HP**:heartpulse: limit ({limit})? \n ✅ - Go over the limit \n ❌ - Stop \n 📈 - Set to max")
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            await msg.add_reaction("📈")

            def check(reaction, user):
                return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["✅", "❌", "📈"]

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
                if str(reaction.emoji) == "✅":
                    pass
                elif str(reaction.emoji) == "📈":
                    new_value = limit
                    change_value = new_value - current_value
                elif str(reaction.emoji) == "❌":
                    await ctx.send("**HP**:heartpulse: will not be saved.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Timed out. **HP**:heartpulse: will not be saved.")
                return

        # Surpassing MAX_MP
        if stat_key == "MP" and new_value > (math.floor(user_stats["POW"] / 5)):
            limit = math.floor(user_stats["POW"] / 5)
            msg = await ctx.send(f"Are you sure you want to surpass your **MP**:sparkles: limit ({limit})? \n ✅ - Go over the limit \n ❌ - Stop \n 📈 - Set to max")
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            await msg.add_reaction("📈")

            def check(reaction, user):
                return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["✅", "❌", "📈"]

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
                if str(reaction.emoji) == "✅":
                    pass
                elif str(reaction.emoji) == "📈":
                    new_value = limit
                    change_value = new_value - current_value
                elif str(reaction.emoji) == "❌":
                    await ctx.send("**MP**:sparkles: will not be saved.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Timed out. **MP**:sparkles: will not be saved.")
                return

        # Surpassing MAX_SAN
        if stat_key == "SAN" and new_value > (99 - user_stats.get("Cthulhu Mythos", 0)):
            limit = 99 - user_stats.get("Cthulhu Mythos", 0)
            msg = await ctx.send(f"Are you sure you want to surpass your **SAN**:scales: limit ({limit})? \n ✅ - Go over the limit \n ❌ - Stop \n 📈 - Set to max")
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            await msg.add_reaction("📈")

            def check(reaction, user):
                return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["✅", "❌", "📈"]

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
                if str(reaction.emoji) == "✅":
                    pass
                elif str(reaction.emoji) == "📈":
                    new_value = limit
                    change_value = new_value - current_value
                elif str(reaction.emoji) == "❌":
                    await ctx.send("**SAN**:scales: will not be saved.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("Timed out. **SAN**:scales: will not be saved.")
                return

        # Update and Save
        player_stats[server_id][user_id][stat_key] = new_value
        await save_player_stats(player_stats)

        # Response
        color = discord.Color.green() if change_value >= 0 else discord.Color.red()
        stat_emoji = get_stat_emoji(stat_key)

        embed = discord.Embed(
            title=f"Stat Change - {stat_emoji} {stat_key}",
            description=f"**{ctx.author.display_name}**, you've updated your '{stat_key}' stat.",
            color=color
        )
        embed.add_field(name="Previous Value", value=str(current_value), inline=True)
        embed.add_field(name="Change", value=f"{change_value:+}", inline=True)
        embed.add_field(name="New Value", value=str(new_value), inline=True)

        await ctx.send(embed=embed)

        # Trigger auto-calcs (copied logic)
        # HP Calculation Trigger
        if stat_key in ["CON", "SIZ"]:
            if user_stats["CON"] != 0 and user_stats["SIZ"] != 0 and user_stats["HP"] == 0:
                 await self.prompt_calculation(ctx, "HP", math.floor((user_stats["CON"] + user_stats["SIZ"]) / 10), player_stats, server_id, user_id)

        # MP Calculation Trigger
        if stat_key == "POW":
            if user_stats["POW"] != 0 and user_stats["MP"] == 0:
                await self.prompt_calculation(ctx, "MP", math.floor(user_stats["POW"] / 5), player_stats, server_id, user_id)
            if user_stats["POW"] != 0 and user_stats["SAN"] == 0:
                await self.prompt_calculation(ctx, "SAN", user_stats["POW"], player_stats, server_id, user_id)

        # Dodge Calculation Trigger
        if stat_key == "DEX":
            if user_stats["DEX"] != 0 and user_stats["Dodge"] == 0:
                await self.prompt_calculation(ctx, "Dodge", math.floor(user_stats["DEX"] / 2), player_stats, server_id, user_id)

        # Language Own Calculation Trigger
        if stat_key == "EDU":
             if user_stats["EDU"] != 0 and user_stats.get("Language own", 0) == 0:
                 await self.prompt_calculation(ctx, "Language own", user_stats["EDU"], player_stats, server_id, user_id)

        # Age Warning
        if stat_key in ["STR", "DEX", "CON", "EDU", "APP", "SIZ", "LUCK"] and user_stats.get("Age", 0) == 0:
             # Check if all filled
             if all(user_stats.get(k, 0) != 0 for k in ["STR", "DEX", "CON", "EDU", "APP", "SIZ", "LUCK"]):
                 await ctx.send(f"{ctx.author.display_name} filled all stats affected by Age. Fill your age with `{prefix}stat Age <value>`")

        # Age specific advice
        if stat_key == "Age":
            age = user_stats["Age"]
            if age < 15: await ctx.send("Age Modifiers: No official rules for <15.")
            elif age < 20: await ctx.send("Age Modifiers (<20): Deduct 5 from STR/SIZ. Deduct 5 from EDU. Roll Luck twice (take high).")
            elif age < 40: await ctx.send("Age Modifiers (<40): Improvement check for EDU.")
            elif age < 50: await ctx.send("Age Modifiers (<50): 2 EDU checks. Deduct 5 from STR/CON/DEX. APP -5.")
            elif age < 60: await ctx.send("Age Modifiers (<60): 3 EDU checks. Deduct 10 from STR/CON/DEX. APP -10.")
            elif age < 70: await ctx.send("Age Modifiers (<70): 4 EDU checks. Deduct 20 from STR/CON/DEX. APP -15.")
            elif age < 80: await ctx.send("Age Modifiers (<80): 4 EDU checks. Deduct 40 from STR/CON/DEX. APP -20.")
            elif age < 90: await ctx.send("Age Modifiers (<90): 4 EDU checks. Deduct 80 from STR/CON/DEX. APP -25.")
            else: await ctx.send("Age Modifiers (90+): No official rules.")

    async def prompt_calculation(self, ctx, stat_name, calculated_value, player_stats, server_id, user_id):
        emoji = get_stat_emoji(stat_name)
        msg = await ctx.send(f"{ctx.author.display_name} filled all stats for **{stat_name}**{emoji}. Calculate it to **{calculated_value}**?")
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        def check(reaction, user):
            return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
            if str(reaction.emoji) == "✅":
                player_stats[server_id][user_id][stat_name] = calculated_value
                await save_player_stats(player_stats)
                await ctx.send(f"**{stat_name}** set to **{calculated_value}**.")
            else:
                await ctx.send(f"Calculation for **{stat_name}** skipped.")
        except asyncio.TimeoutError:
            await ctx.send(f"Timed out. Calculation for **{stat_name}** skipped.")

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
