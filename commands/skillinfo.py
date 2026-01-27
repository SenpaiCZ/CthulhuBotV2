import discord
from discord.ext import commands
from loadnsave import load_skills_data


class skillinfo(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["sinfo"])
  async def skillinfo(self, ctx, *, skill_name: str = None):
      """
      `[p]sinfo skill-name` - Get information about specific skill (without skill-name you will get list of skills). (e.g. `[p]sinfo Listen`)
      """
      # Zde můžete definovat informace o dovednostech (malá písmena)
      skills_info = await load_skills_data()
      if skill_name is None:
          skills_list = ", ".join(skills_info.keys())
          response = f":zap: List of skills: :zap: \n{skills_list}"
      else:
          matching_skills = [skill for skill in skills_info if skill_name.lower() in skill.lower()]
          if matching_skills:
              if len(matching_skills) > 1:
                  response = f"Found multiple matching skills: {', '.join(matching_skills)}. Please specify the skill name more clearly."
              else:
                  skill_description = skills_info.get(matching_skills[0], "Skill not found.")
                  response = f":zap: Skill Info: {matching_skills[0]}\n {skill_description}"
          else:
              response = f":zap: Skill Info: {skill_name}\n Skill not found."
              
      embed = discord.Embed(description=response, color=discord.Color.blue())
      await ctx.send(embed=embed)

async def setup(bot):
  await bot.add_cog(skillinfo(bot))
