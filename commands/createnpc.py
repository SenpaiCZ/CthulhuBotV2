import discord, random
from discord.ext import commands
#from names import get_male_name, get_female_name, get_lastname
from loadnsave import load_names_male_data, load_names_female_data, load_names_last_data


class createnpc(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["cNPC"])
  async def createnpc(self, ctx, gender=None):
    """
    `[p]cNPC gender` - Generate NPC with random name and stats. (e.g. `[p]cNPC male`)
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

    def get_stat_emoji(stat_name):
      stat_emojis = {
          "STR": ":muscle:",
          "DEX": ":runner:",
          "CON": ":heart:",
          "INT": ":brain:",
          "POW": ":zap:",
          "APP": ":heart_eyes:",
          "EDU": ":mortar_board:",
          "SIZ": ":bust_in_silhouette:",
          "HP": ":heartpulse:",
          "LUCK": ":four_leaf_clover:",
      }
      return stat_emojis.get(stat_name, "")

    # Generate stats
    STR = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
    CON = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
    SIZ = 5 * (sum(sorted([random.randint(1, 6) for _ in range(2)])) + 6)
    DEX = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
    APP = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
    INT = 5 * (sum(sorted([random.randint(1, 6) for _ in range(2)])) + 6)
    POW = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
    EDU = 5 * (sum(sorted([random.randint(1, 6) for _ in range(2)])) + 6)
    LUCK = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
    HP = (CON + SIZ) // 10

    stats = {
        "STR": STR,
        "DEX": DEX,
        "CON": CON,
        "INT": INT,
        "POW": POW,
        "APP": APP,
        "EDU": EDU,
        "SIZ": SIZ,
        "HP": HP,
        "LUCK": LUCK,
    }

    stats_embed = "\n".join([
        f"{get_stat_emoji(stat)} {stat}: {value}"
        for stat, value in stats.items()
    ])

    embed = discord.Embed(
        title="NPC Character Sheet",
        description=f":game_die: **Name:** {name}\n\n{stats_embed}",
        color=discord.Color.gold())

    await ctx.send(embed=embed)


async def setup(bot):
  await bot.add_cog(createnpc(bot))
