import discord
from discord.ext import commands
from discord import app_commands
from services.settings_service import SettingsService
from schemas.settings import GuildSettingsUpdate
from models.database import SessionLocal

class GameSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Admin"

    gamesettings_group = app_commands.Group(name="gamesettings", description="⚙️ Manage game settings")

    @gamesettings_group.command(name="maxskill", description="📈 Set the maximum starting skill points for new investigators.")
    @app_commands.describe(value="The maximum skill points (1-99)")
    @app_commands.checks.has_permissions(administrator=True)
    async def maxskill(self, interaction: discord.Interaction, value: int):
        if value < 1 or value > 99:
            await interaction.response.send_message("Please enter a value between 1 and 99.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        db = SessionLocal()
        
        try:
            update_data = GuildSettingsUpdate(max_starting_skill=value)
            SettingsService.update_guild_settings(db, guild_id, update_data)
            await interaction.response.send_message(f"Max starting skill points set to **{value}** for this server.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error updating settings: {e}", ephemeral=True)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(GameSettings(bot))
