import discord, random
from discord.ext import commands
from loadnsave import load_pulp_talents_data


class talents(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["cTalents","tinfo"])
  async def talents(self, ctx, category: str = None):
      """
      `[p]cTalents` - Generate two random talents or get a list of talents. You can get list of tallent if you chose category (physical, mental, combat or miscellaneous) (e. g. `[p]cTalents mental`)
      """
      pulp_talents = await load_pulp_talents_data()
      
      physical_talents = pulp_talents.get("physical", [])
      mental_talents = pulp_talents.get("mental", [])
      combat_talents = pulp_talents.get("combat", [])
      miscellaneous_talents = pulp_talents.get("miscellaneous", [])

      if not category:
          # Pokud hráč neposkytne žádnou kategorii, vrátíme dvě náhodné položky.
          all_talents = physical_talents + mental_talents + combat_talents + miscellaneous_talents
          if not all_talents:
              await ctx.send("No talents found in database.")
              return
          selected_talents = random.sample(all_talents, 2)
          category = "Random Talents"
      else:
          # Jinak vybereme položky z dané kategorie.
          category = category.lower()
          if category == "physical":
              selected_talents = physical_talents
              category = "Physical Talents"
          elif category == "mental":
              selected_talents = mental_talents
              category = "Mental Talents"
          elif category == "combat":
              selected_talents = combat_talents
              category = "Combat Talents"
          elif category == "miscellaneous":
              selected_talents = miscellaneous_talents
              category = "Miscellaneous Talents"
          else:
              await ctx.send("Invalid category. Available categories: Physical, Mental, Combat, Miscellaneous")
              return

          if not selected_talents:
               await ctx.send(f"No talents found for category {category}.")
               return

      # Nyní můžeme sestavit výstupní embed.
      embed = discord.Embed(title=f"{category}", color=discord.Color.blue())
      for index, talent in enumerate(selected_talents, 1):
          embed.add_field(name=f"Talent {index}", value=talent, inline=False)

      await ctx.send(embed=embed)


async def setup(bot):
  await bot.add_cog(talents(bot))
