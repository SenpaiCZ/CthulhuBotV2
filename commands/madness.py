import discord
from discord.ext import commands
from discord import app_commands
from commands._madness_view import MadnessMenuView, get_menu_embed

class madness(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Keeper"

    @app_commands.command(name="madness", description="🤪 Roll for a random madness effect.")
    async def madness(self, interaction: discord.Interaction):
        """Roll for a random madness effect by opening the madness menu."""
        embed = get_menu_embed()
        view = MadnessMenuView(interaction.user)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(madness(bot))
