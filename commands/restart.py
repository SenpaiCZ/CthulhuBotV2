import discord
from discord.ext import commands
import os
from services.admin_service import AdminService

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
        
        # Get current process ID
        pid = os.getpid()
        
        # Call service to trigger restart
        if AdminService.trigger_restart(pid):
            await self.bot.close()
        else:
            await ctx.send("❌ Failed to start restarter. Please check logs.")

async def setup(bot):
    await bot.add_cog(Restart(bot))
