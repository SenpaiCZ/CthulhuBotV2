import discord
from discord.ext import commands
from collections import OrderedDict
from loadnsave import load_player_stats, save_player_stats, load_server_stats


class renameskill(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["rskill"])
  async def renameskill(self, ctx, *, old_and_new_name):
      """
      `[p]rskill skill1 skill2` - Rename skill to your liking. (e.g. `[p]rskill Language other German`)
      """
      server_id = str(ctx.guild.id)  # Get the server's ID as a string
      server_prefixes = await load_server_stats()
      prefix = server_prefixes.get(server_id, "!") if server_id else "!"
      restricted_skills = {"NAME","STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN","HP", "MP", "LUCK", "MOV", "BUILD", "DAMAGE BONUS", "AGE", "DODGE"}
      if not isinstance(ctx.channel, discord.TextChannel):
          await ctx.send("This command is not allowed in DMs.")
          return
      user_id = str(ctx.author.id)  # Get the user's ID as a string
      
      player_stats = await load_player_stats()
  
      old_and_new_name = old_and_new_name.rsplit(maxsplit=1)
  
      if len(old_and_new_name) != 2:
          await ctx.send(
              "Invalid input. Please provide old skill name and new skill name.")
          return
  
      old_skill_name = old_and_new_name[0].title(
      )  # Convert the old skill name to title case
      new_skill_name = old_and_new_name[1].title(
      )  # Convert the new skill name to title case
  
      if old_skill_name.upper() in restricted_skills:
          await ctx.send(
              f"You cannot rename the skill '{old_skill_name}' as it's a restricted skill."
          )
          return
  
      if user_id in player_stats[server_id]:
          normalized_old_skill_name = old_skill_name.lower().replace(
              " ", "")  # Normalize old skill name to lowercase
          matching_skills = [
              s for s in player_stats[server_id][user_id]
              if s.lower().replace(" ", "") == normalized_old_skill_name
          ]
  
          if matching_skills:
              if new_skill_name.title() in player_stats[server_id][user_id]:
                  await ctx.send(
                      "Skill with the new name already exists. Choose a different name."
                  )
                  return
  
              try:
                  # Create an ordered dictionary to maintain the skill order
                  ordered_skills = OrderedDict()
  
                  # Add skills to the ordered dictionary, except the skill being renamed
                  for skill_name, skill_value in player_stats[server_id][user_id].items():
                      if skill_name.lower().replace(" ", "") == normalized_old_skill_name:
                          ordered_skills[new_skill_name] = skill_value
                      else:
                          ordered_skills[skill_name] = skill_value
  
                  player_stats[server_id][user_id] = ordered_skills
  
                  await save_player_stats(player_stats)  # Save the entire dictionary
                  await ctx.send(
                      f"Your skill '{matching_skills[0]}' has been updated to '{new_skill_name}'."
                  )
              except KeyError:
                  await ctx.send(
                      "An error occurred while updating the skill. Please try again.")
          else:
              await ctx.send("Skill not found in your skills list.")
      else:
          await ctx.send(
              f"{ctx.author.display_name} doesn't have an investigator. Use `{prefix}newInv` for creating a new investigator."
          )


async def setup(bot):
  await bot.add_cog(renameskill(bot))
