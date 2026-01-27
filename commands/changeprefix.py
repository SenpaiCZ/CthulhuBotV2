import discord, json, aiofiles
from discord.ext import commands
from loadnsave import load_server_stats, save_server_stats

class changeprefix(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  async def changeprefix(self, ctx, prefix=None):
    """
    `[p]changeprefix newprefix` - command for server owners to change prefix for this bot.
    """
    if ctx.author != ctx.guild.owner:
      await ctx.send("This command is limited for server owner only.")
      return
    if not isinstance(ctx.channel, discord.TextChannel):
      await ctx.send("This command is not allowed in DMs.")
      return

    if prefix is None:
      await ctx.send("Please add prefix, that will be used on this server.")
      return
  
    server_id = str(ctx.guild.id)  # Get the server's ID as a string
    server_stats = await load_server_stats()


    # Check if the user is the server owner
    if ctx.author == ctx.guild.owner:
        # Set the custom prefix for the server
        server_stats[server_id] = prefix
        await save_server_stats(server_stats)
        await ctx.send(f"The server's prefix has been changed to `{prefix}`.")
    else:
        await ctx.send("You must be the server owner to use this command.")    


async def setup(bot):
  await bot.add_cog(changeprefix(bot))
