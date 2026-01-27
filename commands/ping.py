import discord
from discord.ext import commands


class ping(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  async def ping(self, ctx):
    """
    `[p]ping` - Just a simple ping pong command for testing.
    """
    await ctx.send("Pong!")


async def setup(bot):
  await bot.add_cog(ping(bot))
