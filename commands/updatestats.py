import discord, asyncio, re, math
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats, load_server_stats
from emojis import get_stat_emoji


class updatestats(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
  
  @commands.command(aliases=["ustat","updatestat","ustats"])
  async def updatestats(self, ctx, stat_name: str, change_value: int):
      """
      `[p]updatestats stat-name value` - Update your investigator's stats by adding or subtracting a value.
      Example usage:
      `[p]updatestats STR +4` - Add 4 to your Strength (STR) stat.
      `[p]ustats con -2` - Subtract 2 from your Constitution (CON) stat.
      """
      server_id = str(ctx.guild.id)  # Get the server's ID as a string
      server_prefixes = await load_server_stats()
      prefix = server_prefixes.get(server_id, "!") if server_id else "!"
      if not isinstance(ctx.channel, discord.TextChannel):
          await ctx.send("This command is not allowed in DMs.")
          return
  
      user_id = str(ctx.author.id)  # Get the user's ID as a string
      player_stats = await load_player_stats()
  
      if user_id not in player_stats[server_id]:
          await ctx.send(
              f"{ctx.author.display_name} doesn't have an investigator. Use `{prefix}newInv` for creating a new investigator."
          )
          return
  
      # Adjust the stat name to start with an uppercase letter
      stat_name = stat_name.capitalize()
  
      matching_stats = [
          stat for stat in player_stats[server_id][user_id]
          if stat_name.lower() in stat.lower()
      ]
  
      if not matching_stats:
          await ctx.send(f"Invalid stat name: {stat_name}. Please provide a valid stat name.")
          return
  
      exact_match = None
  
      for stat in matching_stats:
          if stat_name.lower() == stat.lower():
              exact_match = stat
              break
  
      if exact_match:
          matching_stat = exact_match
      elif len(matching_stats) > 1:
          matching_stats_str = ", ".join(matching_stats)
          await ctx.send(
              f"Multiple matching stats found: {matching_stats_str}. Please specify the stat name more clearly."
          )
          return
      else:
          matching_stat = matching_stats[0]
  
      current_value = player_stats[server_id][user_id][matching_stat]
  
      # Determine the operation (addition or subtraction)
      if change_value > 0:
          player_stats[server_id][user_id][matching_stat] = current_value + change_value
          action = "added to"
      elif change_value < 0:
          # Ensure that stats cannot go below 0
          new_value = max(current_value + change_value, 0)
          player_stats[server_id][user_id][matching_stat] = new_value
          action = "subtracted from"
      else:
          await ctx.send("Change value should be a non-zero number.")
          return
  
      await save_player_stats(player_stats)  # Save the data to the JSON file
  
      emoji = get_stat_emoji(matching_stat)
      await ctx.send(
          f"{ctx.author.display_name}'s **{matching_stat}**{emoji} has been {action} to **{player_stats[server_id][user_id][matching_stat]}**."
      )
  

  


async def setup(bot):
  await bot.add_cog(updatestats(bot))
