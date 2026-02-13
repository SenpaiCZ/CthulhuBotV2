import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, save_player_stats, load_server_stats


class rename(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.hybrid_command(description="Change the name of your character.")
  @app_commands.describe(new_name="The new name for your character")
  async def rename(self, ctx, *, new_name: str):
      """
      Change the name of your character.
      Usage: /rename new_name: <New Name>
      """
      server_id = str(ctx.guild.id)
      server_prefixes = await load_server_stats()
      prefix = server_prefixes.get(server_id, "!") if server_id else "!"

      if not isinstance(ctx.channel, discord.TextChannel):
          await ctx.send("This command is not allowed in DMs.")
          return

      user_id = str(ctx.author.id)
      player_stats = await load_player_stats()

      if user_id in player_stats.get(server_id, {}):
          player_stats[server_id][user_id]["NAME"] = new_name
          await save_player_stats(player_stats)
          await ctx.send(f"Your character's name has been updated to `{new_name}`.")
      else:
          await ctx.send(
              f"{ctx.author.display_name} doesn't have an investigator. Use `{prefix}newInv` for creating a new investigator."
          )


async def setup(bot):
  await bot.add_cog(rename(bot))
