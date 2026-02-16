import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_skill_settings, save_skill_settings

class GameSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    gamesettings_group = app_commands.Group(name="gamesettings", description="Manage game settings")

    @gamesettings_group.command(name="maxskill", description="Set the maximum starting skill points for new investigators.")
    @app_commands.describe(value="The maximum skill points (1-99)")
    @app_commands.checks.has_permissions(administrator=True)
    async def maxskill(self, interaction: discord.Interaction, value: int):
        if value < 1 or value > 99:
            await interaction.response.send_message("Please enter a value between 1 and 99.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        settings = await load_skill_settings()

        if guild_id not in settings:
            settings[guild_id] = {}

        settings[guild_id]["max_starting_skill"] = value
        await save_skill_settings(settings)

        await interaction.response.send_message(f"Max starting skill points set to **{value}** for this server.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(GameSettings(bot))
