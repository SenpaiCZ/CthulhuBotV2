import discord
from discord import app_commands
from discord.ext import commands
import os
from services.admin_service import AdminService

class UpdateBotView(discord.ui.View):
    def __init__(self, user, bot):
        super().__init__(timeout=60)
        self.user = user
        self.bot = bot

    async def _run_updater(self, interaction: discord.Interaction, update_infodata=False):
        await interaction.response.edit_message(content="🔄 **Starting Update...**\nBot is restarting.", view=None)
        
        # Get current process ID
        pid = os.getpid()
        
        # Call service to trigger update
        if AdminService.trigger_update(pid, update_infodata=update_infodata):
            await self.bot.close()
        else:
            await interaction.followup.send("❌ Failed to start updater. Please check logs.", ephemeral=True)

    @discord.ui.button(label="Update System Only", style=discord.ButtonStyle.success)
    async def update_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Only the command invoker can use this.", ephemeral=True)
        await self._run_updater(interaction, update_infodata=False)

    @discord.ui.button(label="Update System & Infodata", style=discord.ButtonStyle.danger)
    async def update_full(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Only the command invoker can use this.", ephemeral=True)
        await self._run_updater(interaction, update_infodata=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Only the command invoker can use this.", ephemeral=True)
        await interaction.response.edit_message(content="❌ Update cancelled.", view=None)
        self.stop()

class UpdateBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='updatebot', description="🔄 Updates the bot from the GitHub repository (Master branch). Owner only.")
    async def update_bot(self, interaction: discord.Interaction):
        """
        Updates the bot from the GitHub repository (Master branch).
        Only the bot owner can use this command.
        """
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("⛔ You do not have permission to run this command.", ephemeral=True)
            return

        view = UpdateBotView(interaction.user, self.bot)
        await interaction.response.send_message(
            "⚠️ **System Update**\n\nSelect update mode:\n"
            "• **Update System Only**: Updates bot code but keeps `infodata` (default).\n"
            "• **Update System & Infodata**: Updates bot code AND `infodata` (overwrites local changes).\n",
            view=view,
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(UpdateBot(bot))
