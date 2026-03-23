import discord
from discord import app_commands
from discord.ext import commands
from models.database import SessionLocal
from services.settings_service import SettingsService

class ChangeLuck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="changeluck", description="🍀 Change the maximum luck players can spend.")
    @app_commands.describe(luck="The maximum luck points players can spend.")
    @app_commands.checks.has_permissions(administrator=True)
    async def changeluck(self, interaction: discord.Interaction, luck: int):
        """Update the server's luck threshold using SettingsService."""
        db = SessionLocal()
        try:
            guild_id = str(interaction.guild_id)
            SettingsService.set_setting(db, guild_id, "luck_threshold", luck)
            await interaction.response.send_message(f"✅ The server's luck threshold has been changed to `{luck}`.")
        finally:
            db.close()

    @app_commands.command(name="showluck", description="🍀 Show the luck threshold for the server.")
    async def showluck(self, interaction: discord.Interaction):
        """Display the current luck threshold using SettingsService."""
        db = SessionLocal()
        try:
            guild_id = str(interaction.guild_id)
            luck_value = SettingsService.get_setting(db, guild_id, "luck_threshold", 10)
            await interaction.response.send_message(f"The current luck threshold for this server is `{luck_value}`.")
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(ChangeLuck(bot))
