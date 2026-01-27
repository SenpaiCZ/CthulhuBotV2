import discord
from discord.ext import commands
from loadnsave import load_inventions_data


class inventions(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["iinfo"])
  async def inventions(self, ctx, decade: str):
      """
      `[p]inventions decade` - Show inventions from selected decade (e.g. `[p]inventions 1920s`) 
      """
      # Define the inventions data as a dictionary
      inventions_data = await load_inventions_data()
      # Check if the provided decade exists in the inventions data
      if decade in inventions_data:
          # Retrieve the inventions for the specified decade
          inventions_list = inventions_data[decade]

          # Create an embed to display the inventions
          embed = discord.Embed(
              title=f"Inventions from the {decade}",
              description="\n".join(inventions_list),
              color=discord.Color.blue()  # You can customize the color
          )

          # Send the embed to the channel
          await ctx.send(embed=embed)
      else:
          await ctx.send("Decade not found in the inventions data.")


async def setup(bot):
  await bot.add_cog(inventions(bot))
