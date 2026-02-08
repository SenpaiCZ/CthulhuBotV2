import discord, random
from discord.ext import commands
from loadnsave import load_madness_group_data, load_madness_solo_data


class madness(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  async def madness(self, ctx, *, option=None):
    """
    `[p]madness` - outputs random madness (Group).
    `[p]madness list` - will list all madness options
    """
    madness_list = await load_madness_group_data()
    if option == 'list':
        # List all madness options
        madness_data = [f"**{name}**: {description}" for name, description in madness_list.items()]
        madness_all = '\n\n'.join(madness_data)
        # Split if too long? For now assuming it fits or user accepts truncation/split handling by discord lib if implemented,
        # but typically this might fail if too long.
        # Existing code didn't handle it, so leaving as is.
        embed = discord.Embed(title="Madness Options", description=madness_all, color=0x00ff00)
        await ctx.send(embed=embed)
    else:
        # Output a random madness option
        random_madness = random.choice(list(madness_list.keys()))
        embed = discord.Embed(title="Random Madness", description=f"{random_madness}\n\n{madness_list[random_madness]}", color=0xff0000)
        await ctx.send(embed=embed)

  @commands.command()
  async def madnessAlone(self, ctx, *, option=None):
    """
    `[p]madnessAlone` - outputs random madness (Solo).
    `[p]madnessAlone list` - will list all madness options
    """
    madness_list = await load_madness_solo_data()
    if option == 'list':
        # List all madness options
        madness_data = [f"**{name}**: {description}" for name, description in madness_list.items()]
        madness_all = '\n\n'.join(madness_data)
        embed = discord.Embed(title="Madness Options", description=madness_all, color=0x00ff00)
        await ctx.send(embed=embed)
    else:
        # Output a random madness option
        random_madness = random.choice(list(madness_list.keys()))
        embed = discord.Embed(title="Random Madness", description=f"{random_madness}\n\n{madness_list[random_madness]}", color=0xff0000)
        await ctx.send(embed=embed)

async def setup(bot):
  await bot.add_cog(madness(bot))
