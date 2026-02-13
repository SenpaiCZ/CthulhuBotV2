import discord
import re
from discord.ext import commands
from discord import app_commands
from collections import OrderedDict
from loadnsave import load_player_stats, save_player_stats, load_server_stats
from rapidfuzz import process, fuzz


class renameskill(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.hybrid_command(aliases=["rskill"], description="Rename a skill on your character sheet.")
  @app_commands.describe(skill_name="The current name of the skill to rename", new_name="The new name for the skill")
  async def renameskill(self, ctx, skill_name: str, new_name: str):
      """
      Rename a skill on your character sheet.
      Usage: /renameskill skill_name: <old_name> new_name: <new_name>
      """
      server_id = str(ctx.guild.id)
      server_prefixes = await load_server_stats()
      prefix = server_prefixes.get(server_id, "!") if server_id else "!"

      # Restricted skills that cannot be renamed
      restricted_skills = {"NAME","STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN","HP", "MP", "LUCK", "MOV", "BUILD", "DAMAGE BONUS", "AGE", "DODGE"}

      if not isinstance(ctx.channel, discord.TextChannel):
          await ctx.send("This command is not allowed in DMs.")
          return
      
      user_id = str(ctx.author.id)
      player_stats = await load_player_stats()
  
      if user_id not in player_stats.get(server_id, {}):
          await ctx.send(
              f"{ctx.author.display_name} doesn't have an investigator. Use `{prefix}newInv` for creating a new investigator."
          )
          return

      # Clean up skill_name from autocomplete (e.g. "Spot Hidden (50)" -> "Spot Hidden")
      clean_skill_name = skill_name
      match = re.match(r"^(.*?)\s*\(\d+\)$", skill_name)
      if match:
          clean_skill_name = match.group(1)

      # 1. Exact match (case insensitive) search for the old skill
      user_skills = player_stats[server_id][user_id]
      target_skill_key = None

      for key in user_skills.keys():
          if key.lower() == clean_skill_name.lower():
              target_skill_key = key
              break

      # 2. Fuzzy match if no exact match found
      if not target_skill_key:
          choices = list(user_skills.keys())
          extract = process.extractOne(clean_skill_name, choices, scorer=fuzz.WRatio)
          if extract:
              match_key, score, _ = extract
              if score > 80:
                  target_skill_key = match_key

      if not target_skill_key:
          await ctx.send(f"Skill '{clean_skill_name}' not found in your skills list.")
          return

      # Check for restricted skills
      if target_skill_key.upper() in restricted_skills:
          await ctx.send(f"You cannot rename the skill '{target_skill_key}' as it's a restricted skill.")
          return

      # Check if new name already exists
      # We check case-insensitive match for new name to avoid duplicates like "jump" vs "Jump"
      for key in user_skills.keys():
          if key.lower() == new_name.lower():
               await ctx.send(f"Skill with the name '{key}' already exists. Choose a different name.")
               return

      # Proceed with rename
      new_skill_name_formatted = new_name.strip()

      try:
          # Create an ordered dictionary to maintain the skill order
          ordered_skills = OrderedDict()

          # Add skills to the ordered dictionary, replacing the old key with the new key
          for skill_key, skill_value in user_skills.items():
              if skill_key == target_skill_key:
                  ordered_skills[new_skill_name_formatted] = skill_value
              else:
                  ordered_skills[skill_key] = skill_value

          player_stats[server_id][user_id] = ordered_skills

          await save_player_stats(player_stats)
          await ctx.send(f"Your skill '{target_skill_key}' has been updated to '{new_skill_name_formatted}'.")

      except Exception:
          await ctx.send("An error occurred while updating the skill. Please try again.")

  @renameskill.autocomplete('skill_name')
  async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
      server_id = str(interaction.guild_id)
      user_id = str(interaction.user.id)
      player_stats = await load_player_stats()

      if server_id not in player_stats or user_id not in player_stats[server_id]:
          return []

      user_stats = player_stats[server_id][user_id]
      choices = [f"{k} ({v})" for k, v in user_stats.items()]

      if not current:
          return [app_commands.Choice(name=c, value=c) for c in sorted(choices)[:25]]

      matches = process.extract(current, choices, scorer=fuzz.WRatio, limit=25)
      return [app_commands.Choice(name=m[0], value=m[0]) for m in matches]


async def setup(bot):
  await bot.add_cog(renameskill(bot))
