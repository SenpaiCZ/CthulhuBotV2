import discord, random
from discord.ext import commands
#from names import get_male_name, get_female_name, get_lastname
from loadnsave import load_names_male_data, load_names_female_data, load_names_last_data


class randomname(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["rname"])
  async def randomname(self, ctx, gender=None):
    """
        `[p]randomname gender` - Generate random name form 1920s era. (e.g. `[p]randomname female`)
        """
    if gender == None:
      await ctx.send("Missing gender. Use 'male' or 'female'.")
      return

    gender = gender.lower()
    if gender not in ["male", "female"]:
      await ctx.send("Invalid gender. Use 'male' or 'female'.")
      return
      
    last_names = await load_names_last_data()
    male_names = await load_names_male_data()
    female_names = await load_names_female_data()
    
    if gender == "male":
      name = random.choice(male_names)
      if random.random() < 0.3:
        name += " " + random.choice(male_names)
      name += " " + random.choice(last_names)
      if random.random() < 0.5:
        name += "-" + random.choice(last_names)
    else:
      name = random.choice(female_names)
      if random.random() < 0.3:
        name += " " + random.choice(female_names)
      name += " " + random.choice(last_names)
      if random.random() < 0.5:
        name += "-" + random.choice(last_names)

    embed = discord.Embed(title="Random name for Call of Cthulhu",
                          description=f":game_die: **{name}** :game_die:",
                          color=discord.Color.blue())
    await ctx.send(embed=embed)


async def setup(bot):
  await bot.add_cog(randomname(bot))
