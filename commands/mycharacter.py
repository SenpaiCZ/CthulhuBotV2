import discord
from discord.ext import commands
from discord import app_commands
from models.database import SessionLocal
from services.character_service import CharacterService
from views.character_profile import CharacterProfileView

class mycharacter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"
        self.ctx_menu = app_commands.ContextMenu(
            name='Manage Character',
            callback=self.view_investigator_menu,
        )
        self.ctx_menu.description = "📊 View or manage this investigator's stats and bio."
        self.ctx_menu.binding = self
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def view_investigator_menu(self, interaction: discord.Interaction, member: discord.Member):
        await self._show_character(interaction, member)

    @app_commands.command(name="mycharacter", description="🕵️ Show your investigator's stats, skills, backstory and inventory.")
    @app_commands.describe(member="The member whose character you want to see")
    async def mycharacter(self, interaction: discord.Interaction, member: discord.Member = None):
        await self._show_character(interaction, member)

    async def _show_character(self, interaction: discord.Interaction, member: discord.Member = None):
        if interaction.guild is None:
            await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)
            return    
          
        target = member or interaction.user
        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild.id), str(target.id))
            if not inv:
                await interaction.response.send_message(
                    f"{target.display_name} doesn't have an active investigator. Use `/newinvestigator` to create one.",
                    ephemeral=True
                )
                return

            view = CharacterProfileView(inv.id, interaction.user)
            await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(mycharacter(bot))
