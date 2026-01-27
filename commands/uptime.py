import discord
from discord.ext import commands
import datetime

class uptime(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.datetime.now()

    @commands.command()
    async def uptime(self, ctx):
        """
        `[p]uptime` - Returns how long the bot has been online.
        """
        now = datetime.datetime.now()
        uptime_delta = now - self.start_time
        days = uptime_delta.days
        seconds = uptime_delta.seconds
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        
        uptime_str = f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"
        
        await ctx.send(f"Bot has been online for {uptime_str}.\n We need to restart bot for every update we push.")

async def setup(bot):
  await bot.add_cog(uptime(bot))
