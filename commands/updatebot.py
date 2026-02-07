import discord
from discord.ext import commands
import os
import sys
import subprocess
import asyncio

class UpdateBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='updatebot', hidden=True)
    @commands.is_owner()
    async def update_bot(self, ctx):
        """
        Updates the bot from the GitHub repository (Master branch).
        Only the bot owner can use this command.
        """
        await ctx.send("🔄 **Updating Bot...**\n"
                       "Downloading latest version, installing dependencies, and restarting.\n"
                       "This may take a minute.")

        # Prepare the updater command
        # We pass the current PID so the updater can wait for us to exit
        pid = str(os.getpid())

        # Determine python executable
        python_exe = sys.executable

        updater_script = "updater.py"

        if not os.path.exists(updater_script):
            await ctx.send(f"❌ Error: `{updater_script}` not found in root directory.")
            return

        # Spawn the updater process
        # On Windows, we use creationflags to spawn a new console window (detached)
        # On Linux, we use start_new_session=True to detach
        try:
            if os.name == 'nt':
                subprocess.Popen([python_exe, updater_script, pid],
                                 creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen([python_exe, updater_script, pid],
                                 start_new_session=True)
        except Exception as e:
             await ctx.send(f"❌ Failed to start updater: {e}")
             return

        # Close the bot
        await self.bot.close()
        # Ensure process exits
        sys.exit(0)

    @update_bot.error
    async def update_bot_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("⛔ You do not have permission to run this command.")
        else:
            await ctx.send(f"❌ An error occurred: {str(error)}")

async def setup(bot):
    await bot.add_cog(UpdateBot(bot))
