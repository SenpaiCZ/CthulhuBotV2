import discord, random
from discord.ext import commands
from loadnsave import load_macguffin_data


class macguffin(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  async def macguffin(self, ctx, *, option=None):
    """
    `[p]macguffin` - outputs random macguffin.
    `[p]macguffin list` - will list all macguffin options
    """
    macguffin_list = await load_macguffin_data()
    if option == 'list':
        # List all macguffin options
        macguffin_data = [f"**{name}**: {description}" for name, description in macguffin_list.items()]
        macguffin_all = '\n\n'.join(macguffin_data)
        embed = discord.Embed(title="MacGuffin Options", description=macguffin_all, color=0x00ff00)
        await ctx.send(embed=embed)
    else:
        # Output a random macguffin option
        random_macguffin = random.choice(list(macguffin_list.keys()))
        embed = discord.Embed(title="Random MacGuffin", description=f"{random_macguffin}\n\n{macguffin_list[random_macguffin]}", color=0xff0000)
        await ctx.send(embed=embed)

async def setup(bot):
  await bot.add_cog(macguffin(bot))