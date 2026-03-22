import discord
from discord import app_commands
from discord.ext import commands
from views.investigator_wizard import InvestigatorWizardView

class newinvestigator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"

    @app_commands.command(name="newinvestigator", description="🆕 Starts the character creation wizard.")
    async def newinvestigator(self, interaction: discord.Interaction):
        """
        Starts the multi-step character creation wizard using specialized Discord Views.
        """
        wizard = InvestigatorWizardView(interaction.user, interaction.guild)
        await wizard.start(interaction)

async def setup(bot):
    await bot.add_cog(newinvestigator(bot))
