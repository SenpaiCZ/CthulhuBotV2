import discord
from discord import app_commands
from discord.ext import commands
import os
import sys
import subprocess

from dashboard.state import BACKUP_FOLDER
from backup_utils import get_system_backups


class BackupSelect(discord.ui.Select):
    def __init__(self, backups: list[dict]):
        options = [
            discord.SelectOption(
                label=b["name"],
                description=f"{b['created']} · {b['size'] // 1024} KB",
            )
            for b in backups
        ]
        super().__init__(placeholder="Choose a backup to restore...", options=options)

    async def callback(self, interaction: discord.Interaction):
        filename = self.values[0]
        await interaction.response.edit_message(
            content=f"🔄 **Restoring `{filename}`...**\nBot is restarting.", view=None
        )

        pid = str(os.getpid())
        python_exe = sys.executable
        cmd = [python_exe, "updater.py", pid, "--restore", filename]

        try:
            if os.name == 'nt':
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to start restore: {e}", ephemeral=True)
            return

        await interaction.client.close()


class BackupSelectView(discord.ui.View):
    def __init__(self, backups: list[dict]):
        super().__init__(timeout=60)
        self.add_item(BackupSelect(backups))


class Rollback(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='rollback', description="⏪ Restore the bot from a previous backup. Owner only.")
    async def rollback(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("⛔ You do not have permission to run this command.", ephemeral=True)
            return

        backups = get_system_backups(BACKUP_FOLDER)
        if not backups:
            await interaction.response.send_message("No backups available to restore.", ephemeral=True)
            return

        view = BackupSelectView(backups[:25])
        await interaction.response.send_message(
            "⚠️ **Rollback**\n\nSelect a backup to restore. The bot will restart after applying it.",
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Rollback(bot))
