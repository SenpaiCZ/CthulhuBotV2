import discord
from discord.ext import commands
import os
import sys
import subprocess

class Restart(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='restartbot', aliases=['restart'], hidden=True)
    @commands.is_owner()
    async def restart_bot(self, ctx):
        """
        Restarts the bot.
        Only the bot owner can use this command.
        """
        await ctx.send("🔄 **Restarting bot...**")

        # Get the current process ID
        pid = os.getpid()

        # Prepare the restarter command
        python_exe = sys.executable
        restarter_script = "restarter.py"

        if not os.path.exists(restarter_script):
            await ctx.send(f"❌ Error: `{restarter_script}` not found in root directory.")
            return

        cmd = [python_exe, restarter_script, str(pid)]

        try:
            # Launch the restarter script
            if os.name == 'nt':
                # Windows
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # Linux/Unix
                subprocess.Popen(cmd)

            # Close the bot connection
            await self.bot.close()

        except Exception as e:
            await ctx.send(f"❌ Failed to start restarter: {e}")

async def setup(bot):
    await bot.add_cog(Restart(bot))
