import discord
from discord.ext import commands


class reportbug(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  async def reportbug(self, ctx, *, message: str):
      """
      `[p]reportbug message` - This sends a bug report message to the bot creator.
      Please write as many details about the bug as possible for easier replication and fixing.
      """
      user = self.bot.get_user(214351769243877376)  # Replace with your actual user ID
      if user:
          await user.send(f"Bug Report from {ctx.author} (Server: {ctx.guild}): {message}")
          await ctx.send("Bug report sent. Thank you!")
      else:
          await ctx.send("Bug report couldn't be sent. Please make sure the bot's creator's user ID is correct.")


async def setup(bot):
  await bot.add_cog(reportbug(bot))