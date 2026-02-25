import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, save_player_stats, load_server_stats


class rename(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @app_commands.command(description="Change the name of your character.")
  @app_commands.describe(new_name="The new name for your character")
  async def rename(self, interaction: discord.Interaction, new_name: str):
      """
      Change the name of your character.
      """
      server_id = str(interaction.guild.id)
      server_prefixes = await load_server_stats()
      prefix = server_prefixes.get(server_id, "!") if server_id else "!"

      user_id = str(interaction.user.id)
      player_stats = await load_player_stats()

      if user_id in player_stats.get(server_id, {}):
          player_stats[server_id][user_id]["NAME"] = new_name
          await save_player_stats(player_stats)
          await interaction.response.send_message(f"Your character's name has been updated to `{new_name}`.")
      else:
          await interaction.response.send_message(
              f"{interaction.user.display_name} doesn't have an investigator. Use `/newinvestigator` for creating a new investigator.",
              ephemeral=True
          )


async def setup(bot):
  await bot.add_cog(rename(bot))
