import discord
from discord.ext import commands
from discord import app_commands
from models.database import SessionLocal
from services.character_service import CharacterService
from views.character_profile import CharacterProfileView

class rename(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rename", description="🏷️ Change the name of your character.")
    @app_commands.describe(new_name="The new name for your character")
    async def rename(self, interaction: discord.Interaction, new_name: str):
        if not interaction.guild:
            await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)
            return

        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild.id), str(interaction.user.id))
            if not inv:
                await interaction.response.send_message("You don't have an active investigator.", ephemeral=True)
                return

            CharacterService.rename_investigator(db, inv.id, new_name)
            
            view = CharacterProfileView(inv.id, interaction.user)
            await interaction.response.send_message(f"Your character's name has been updated to `{new_name}`.", embed=view.get_embed(), view=view, ephemeral=True)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(rename(bot))
