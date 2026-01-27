import discord, random
from discord.ext import commands
from loadnsave import load_madness_group_data, load_madness_solo_data, load_madness_insane_talent_data, load_phobias_data, load_manias_data


class madness(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  async def madness(self, ctx, *, option=None):
    """
    `[p]madness` - outputs random madness.
    `[p]madness list` - will list all madness options
    """
    madness_list = await load_madness_group_data()
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

  @commands.command()
  async def madnessAlone(self, ctx, *, option=None):
    """
    `[p]madnessAlone` - outputs random madness.
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

  @commands.command()
  async def insaneTalents(self, ctx, *, option=None):
    """
    `[p]insaneTalents` - outputs random insane talent.
    `[p]insaneTalents list` - will list all insane talents.
    """
    madness_list = await load_madness_insane_talent_data()
    if option == 'list':
        # List all madness options
        madness_data = [f"**{name}**" for name, description in madness_list.items()]
        madness_all = '\n'.join(madness_data)
        embed = discord.Embed(title="Insane Talents Options", description=madness_all, color=0x00ff00)
        await ctx.send(embed=embed)
    else:
        # Output a random madness option
        random_madness = random.choice(list(madness_list.keys()))
        embed = discord.Embed(title="Random Insane Talent", description=f"{random_madness}\n\n{madness_list[random_madness]}", color=0xff0000)
        await ctx.send(embed=embed)

  @commands.command()
  async def phobia(self, ctx, *, option=None):
    """
    `[p]phobia` - outputs random phobia.
    `[p]phobia list` - will list all phobias
    """
    madness_list = await load_phobias_data()
    if option == 'list':
        # List all madness options
        madness_data = [f"**{name}**," for name, description in madness_list.items()]
        madness_all = ' '.join(madness_data)
        embed = discord.Embed(title="Phobias", description=madness_all, color=0x00ff00)
        await ctx.send(embed=embed)
    else:
        # Output a random madness option
        random_madness = random.choice(list(madness_list.keys()))
        embed = discord.Embed(title="Random Phobia", description=f"{random_madness}\n\n{madness_list[random_madness]}", color=0xff0000)
        await ctx.send(embed=embed)

  @commands.command()
  async def mania(self, ctx, *, option=None):
    """
    `[p]phobia` - outputs random phobia.
    `[p]phobia list` - will list all phobias
    """
    madness_list = await load_manias_data()
    if option == 'list':
        # List all madness options
        madness_data = [f"**{name}**," for name, description in madness_list.items()]
        madness_all = ' '.join(madness_data)
        embed = discord.Embed(title="Manias", description=madness_all, color=0x00ff00)
        await ctx.send(embed=embed)
    else:
        # Output a random madness option
        random_madness = random.choice(list(madness_list.keys()))
        embed = discord.Embed(title="Random Mania", description=f"{random_madness}\n\n{madness_list[random_madness]}", color=0xff0000)
        await ctx.send(embed=embed)

async def setup(bot):
  await bot.add_cog(madness(bot))
