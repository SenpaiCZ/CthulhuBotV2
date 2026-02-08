import discord
from discord.ext import commands


class ping(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  async def ping(self, ctx):
    """
    `[p]ping` - Basic check to see if the bot is responsive.
    """
    await ctx.send("Pong!")


async def setup(bot):
  await bot.add_cog(ping(bot))
