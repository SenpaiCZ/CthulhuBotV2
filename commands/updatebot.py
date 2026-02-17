import discord
from discord import app_commands
from discord.ext import commands
import os
import sys
import subprocess
import asyncio

class UpdateBotView(discord.ui.View):
    def __init__(self, user, bot):
        super().__init__(timeout=60)
        self.user = user
        self.bot = bot

    async def _run_updater(self, interaction: discord.Interaction, update_infodata=False):
        await interaction.response.edit_message(content="🔄 **Starting Update...**\nBot is restarting.", view=None)

        # Prepare the updater command
        pid = str(os.getpid())
        python_exe = sys.executable
        updater_script = "updater.py"

        if not os.path.exists(updater_script):
            await interaction.followup.send(f"❌ Error: `{updater_script}` not found in root directory.", ephemeral=True)
            return

        cmd = [python_exe, updater_script, pid]
        if update_infodata:
            cmd.append("--update-infodata")

        try:
            if os.name == 'nt':
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
             await interaction.followup.send(f"❌ Failed to start updater: {e}", ephemeral=True)
             return

        # Close the bot
        await self.bot.close()

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

    @app_commands.command(name='updatebot', description="Updates the bot from the GitHub repository (Master branch). Owner only.")
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
