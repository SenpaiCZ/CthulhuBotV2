import discord
from discord.ext import commands
from loadnsave import load_firearms_data


class firearms(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["finfo"])
  async def firearms(self, ctx, *, weapon_name=None):
      """
      `[p]firearm name` - Get basic information about firearms. If you use just !firearm you will get list of firearms. (e.g. `[p]firearm m1911`)
      """
      firearms_data = await load_firearms_data()
      if weapon_name is None:
          weapons_list = "\n".join(f"• {weapon}" for weapon in firearms_data.keys())
          embed = discord.Embed(title="Available Firearms", description=weapons_list, color=discord.Color.blue())
      else:
          matching_weapons = [weapon for weapon in firearms_data.keys() if weapon_name.lower() in weapon.lower()]
  
          if not matching_weapons:
              embed = discord.Embed(description="No matching weapons found.", color=discord.Color.red())
          elif len(matching_weapons) == 1:
              weapon_name = matching_weapons[0]
              weapon_info = firearms_data[weapon_name]
              embed = discord.Embed(title=weapon_name, description=weapon_info["description"], color=discord.Color.green())
              embed.add_field(name="📅 Year", value=weapon_info["year"])
              embed.add_field(name="💰 Cost", value=weapon_info["cost"])
              embed.add_field(name="🎯 Range", value=weapon_info["range"])
              embed.add_field(name="🔫 Shots per Round", value=weapon_info["shots_per_round"])
              embed.add_field(name="📦 Capacity", value=weapon_info["capacity"])
              embed.add_field(name="⚔️ Damage", value=weapon_info["damage"])
              embed.add_field(name="🛠️ Malfunction", value=weapon_info["malfunction"])
          else:
              weapons_list = "\n".join(f"• {weapon}" for weapon in matching_weapons)
              embed = discord.Embed(title="Matching Weapons", description=weapons_list, color=discord.Color.blue())
  
      await ctx.send(embed=embed)


async def setup(bot):
  await bot.add_cog(firearms(bot))
