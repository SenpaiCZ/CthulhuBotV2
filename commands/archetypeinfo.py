import discord
from discord.ext import commands
from loadnsave import load_archetype_data


class archetypeinfo(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["cArchetype", "ainfo"])
  async def archetypeinfo(self, ctx, *, archetype_name: str = None):
    """
      `[p]cArchetype name` - Get information about archetypes from Pulp of Cthulhu (e.g. `[p]cArchetype Adventurer`)
      """
    image_url = ""
    archetypes_info = await load_archetype_data()
    if archetype_name is None:
      archetypes_list = ", ".join(archetypes_info.keys())
      response = f"Archetypes are used only in Pulp of Cthulhu \n\n List of archetypes:\n{archetypes_list}"
      embed_title = "Archetypes List"
      image_url = ""
    else:
      matching_archetypes = [
          archetype for archetype in archetypes_info.keys()
          if archetype_name.lower() in archetype.lower()
      ]
      if not matching_archetypes:
        response = (
            f"Archetype '{archetype_name}' not found.\n"
            f"Please choose an archetype from the list or check your spelling."
        )
        embed_title = "Invalid Archetype"
      elif len(matching_archetypes) > 1:
        response = f"Multiple archetypes found matching '{archetype_name}': {', '.join(matching_archetypes)}"
        embed_title = "Multiple Archetypes Found"
      else:
        matched_archetype = matching_archetypes[0]
        archetype_info = archetypes_info[matched_archetype]
        embed_title = matched_archetype.capitalize()
        description = archetype_info["description"]
        image_url = archetype_info["link"]
        adjustments = "\n".join(archetype_info["adjustments"])
        response = f"Archetypes are used only in Pulp of Cthulhu \n\n :scroll: **Description:** {description}\n\n:gear: **Adjustments:**\n\n{adjustments}"
    embed = discord.Embed(title=embed_title,
                          description=response,
                          color=discord.Color.green())
    embed.set_image(url=image_url)
    await ctx.send(embed=embed)


async def setup(bot):
  await bot.add_cog(archetypeinfo(bot))
