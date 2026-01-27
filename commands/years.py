import discord
from discord.ext import commands
from loadnsave import load_years_data


class years(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["yinfo"])
  async def year(self, ctx, year: int):
      """
      `[p]year number` - Get basic information about events in a year (1590-2012) (e.g., `[p]year 1920`)
      """
      # Check if the provided year is within the specified range
      if year < 1590 or year > 2012:
          await ctx.send("Please provide a year between 1590 and 2012.")
          return
  
      years_data = await load_years_data()
  
      event_info = years_data.get(str(year), [])
  
      if not event_info:
          await ctx.send("No historical events found for the specified year.")
          return
  
      # Format historical events as bullet points
      events_formatted = "\n".join([f"• {event}" for event in event_info])
  
      year_embed = discord.Embed(
          title=f"Historical Events in {year}",
          description=events_formatted,
          color=discord.Color.blue()
      )
  
      await ctx.send(embed=year_embed)


async def setup(bot):
  await bot.add_cog(years(bot))
