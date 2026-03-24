import discord
from discord.ext import commands
from discord import app_commands
import traceback
from views.help_view import HelpView
from services.admin_service import AdminService

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Other"

    @app_commands.command(name="help", description="ℹ️ Show the interactive help dashboard.")
    async def help_command(self, interaction: discord.Interaction):
        """
        Shows the interactive help dashboard.
        """
        # Defer immediately ephemeral
        await interaction.response.defer(ephemeral=True)

        try:
            ctx = await self.bot.get_context(interaction)
            help_data = await AdminService.generate_help_data(self.bot, ctx)

            if not help_data:
                await interaction.followup.send("No commands available for you.")
                return

            view = HelpView(help_data, interaction.user, self.bot)
            embed = view.get_home_embed()

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            print(f"Error generating help menu: {e}")
            traceback.print_exc()
            await interaction.followup.send("An error occurred while accessing the archives.")

async def setup(bot):
    await bot.add_cog(Help(bot))
