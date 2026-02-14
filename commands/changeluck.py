import discord
from discord import app_commands
from discord.ext import commands
from loadnsave import load_luck_stats, save_luck_stats

class ChangeLuck(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="changeluck", description="Change how much luck players can spend to make a successful roll.")
    @app_commands.describe(luck="The maximum luck points players can spend (0 to disable).")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def changeluck(self, interaction: discord.Interaction, luck: int):
        """
        Change how much luck players can spend to make a successful roll.
        If you set value to 0 you will disable spending luck for you players.
        """
        server_id = str(interaction.guild_id)
        server_stats = await load_luck_stats()

        # Set the custom luck for the server
        server_stats[server_id] = luck
        await save_luck_stats(server_stats)
        await interaction.response.send_message(f"The server's luck threshold has been changed to `{luck}`.")

    @changeluck.error
    async def changeluck_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("⛔ This command is limited to server administrators only.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {str(error)}", ephemeral=True)

    @app_commands.command(name="showluck", description="Show the luck threshold for the server.")
    @app_commands.guild_only()
    async def showluck(self, interaction: discord.Interaction):
        """
        Show the luck threshold for the server.
        """
        server_id = str(interaction.guild_id)
        server_stats = await load_luck_stats()

        # Check if the server has a custom luck setting; if not, use a default value of 10
        luck_value = server_stats.get(server_id, 10)

        await interaction.response.send_message(f"The current luck threshold for this server is `{luck_value}`.")

async def setup(bot):
    await bot.add_cog(ChangeLuck(bot))
