import discord
from discord.ext import commands
from discord import app_commands
from models.database import SessionLocal
from services.character_service import CharacterService
from views.character_profile import CharacterProfileView

class removebackstory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="removebackstory", description="🗑️ Remove items from your character's backstory.")
    async def removebackstory(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)
            return

        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild.id), str(interaction.user.id))
            if not inv:
                await interaction.response.send_message("You don't have an investigator.", ephemeral=True)
                return

            view = CharacterProfileView(inv.id, interaction.user)
            view.current_tab = "Backstory"
            await interaction.response.send_message("Use the **Edit** button to manage your backstory.", embed=view.get_embed(), view=view, ephemeral=True)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(removebackstory(bot))
