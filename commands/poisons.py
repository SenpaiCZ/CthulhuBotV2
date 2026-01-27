import discord
from discord.ext import commands
from loadnsave import load_poisons_data


class poisons(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["pinfo"])
  async def poisons(self, ctx, *, poison_name=None):
      """
      `[p]poison name` - Get basic information about poisons. If you use just !poison, you will get a list of poisons.
      (e.g., `[p]poison Amanita`)
      """
      poison_data = await load_poisons_data()
      if poison_name is None:
          poisons_list = "\n".join(f"• {poison}" for poison in poison_data.keys())
          embed = discord.Embed(title="Available Poisons", description=poisons_list, color=discord.Color.blue())
      else:
          matching_poisons = [poison for poison in poison_data.keys() if poison_name.lower() in poison.lower()]

          if not matching_poisons:
              embed = discord.Embed(description="No matching poisons found.", color=discord.Color.red())
          elif len(matching_poisons) == 1:
              poison_name = matching_poisons[0]
              poison_info = poison_data[poison_name]
              embed = discord.Embed(title=poison_name, description=poison_info["Symptoms"], color=discord.Color.red())
              embed.add_field(name="⏳ Onset Time", value=poison_info["Onset Time"])
              embed.add_field(name="⚔️ Damage", value=poison_info["Damage"])
              embed.add_field(name="📑 Note", value=poison_info["Note"])
          else:
              poisons_list = "\n".join(f"• {poison}" for poison in matching_poisons)
              embed = discord.Embed(title="Matching Poisons", description=poisons_list, color=discord.Color.blue())

      await ctx.send(embed=embed)


async def setup(bot):
  await bot.add_cog(poisons(bot))
