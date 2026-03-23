import discord
from discord.ext import commands
from discord import app_commands
from models.database import SessionLocal
from services.character_service import CharacterService
from services.settings_service import SettingsService

class PrintCharacter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"

    @app_commands.command(name="printcharacter", description="🖨️ Get a link to your character sheet for printing.")
    @app_commands.describe(user="The user whose character you want to print (defaults to you)")
    async def printcharacter(self, interaction: discord.Interaction, user: discord.Member = None):
        """
        Provides a link to the character sheet for printing.
        """
        if user is None:
            user = interaction.user

        db = SessionLocal()
        try:
            investigator = CharacterService.get_investigator_by_guild_and_user(
                db, str(interaction.guild_id), str(user.id)
            )

            if not investigator:
                 await interaction.response.send_message(f"No active character found for {user.display_name}.", ephemeral=True)
                 return

            dashboard_url = SettingsService.get_setting(db, "global", "dashboard_url", "http://localhost:5000")
            print_url = f"{dashboard_url}/render/character/{investigator.guild_id}/{investigator.discord_user_id}"
            
            embed = discord.Embed(
                title=f"Character Sheet: {investigator.name}",
                description=f"You can view and print the character sheet for **{investigator.name}** at the link below:",
                color=discord.Color.blue()
            )
            embed.add_field(name="Dashboard Link", value=f"[Click here to view character sheet]({print_url})")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(PrintCharacter(bot))
