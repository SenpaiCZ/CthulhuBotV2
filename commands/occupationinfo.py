import discord
from discord.ext import commands
from loadnsave import load_occupations_data


class occupationinfo(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["cocc","oinfo"])
  async def occupationinfo(self, ctx, *, occupation_name: str = None):
      """
      `[p]oinfo occupation-name` - Get information about occupation (without occupation-name you will get list of occupations). (e.g. `[p]oinfo bartender`)
      """
      occupations_info = await load_occupations_data()
      
      image_url = ""


      if occupation_name is None:
          occupations_list = ", ".join(occupations_info.keys())
          response = f"List of occupations:\n{occupations_list}"
          embed_title = "Occupations List"
      else:
          matching_occupations = [
              name for name in occupations_info.keys() if occupation_name.lower() in name.lower()
          ]
          if not matching_occupations:
              response = (
                  f"No matching occupations found for '{occupation_name}'.\n"
                  f"Please choose an occupation from the list or check your spelling."
              )
              embed_title = "No Matching Occupations"
          elif len(matching_occupations) == 1:
              occupation_name = matching_occupations[0]
              occupation_info = occupations_info[occupation_name]
              embed_title = occupation_name.capitalize()
              description = occupation_info["description"]
              era = occupation_info["era"]
              skill_points = occupation_info["skill_points"]
              credit_rating = occupation_info["credit_rating"]
              suggested_contacts = occupation_info.get("suggested_contacts", "None")
              skills = occupation_info["skills"]
              image_url = occupation_info["link"]
              response = (
                  f":clipboard: Description: {description}\n"
                  f":clock: Era: {era}\n"
                  f":black_joker: Occupation Skill Points: {skill_points}\n"
                  f":moneybag: Credit Rating: {credit_rating}\n"
                  f":telephone: Suggested Contacts: {suggested_contacts}\n"
                  f":zap: Skills: {skills}"
              )
          else:
              matching_occupations_list = ", ".join(matching_occupations)
              response = (
                  f"Multiple matching occupations found for '{occupation_name}':\n"
                  f"{matching_occupations_list}"
              )
              embed_title = "Multiple Matching Occupations"

      embed = discord.Embed(title=embed_title, description=response, color=discord.Color.green())
      embed.set_image(url=image_url)
      await ctx.send(embed=embed)
      
async def setup(bot):
  await bot.add_cog(occupationinfo(bot))
