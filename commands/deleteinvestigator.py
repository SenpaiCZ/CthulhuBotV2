import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, save_player_stats


class deleteinvestigator(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.hybrid_command(aliases=["delInv", "delinv"], description="Delete your investigator and all data.")
  @app_commands.describe(member="The member whose investigator you want to delete (Admin only)")
  async def deleteinvestigator(self, ctx, member: discord.Member = None):
    """
    `[p]deleteInvestigator` - Delete your investigator, all data, backstory and inventory. You will be promptet to write your investigators name to confirm deletion. Server owners can delete other players investigators with @.
    """
    if not isinstance(ctx.channel, discord.TextChannel):
      await ctx.send("This command is not allowed in DMs.")
      return
      
    user_id = str(ctx.author.id)  # Get the user's ID as a string
    server_id = str(ctx.guild.id)  # Get the server's ID as a string
    player_stats = await load_player_stats()

    if member is None:
      member = ctx.author  # If no member is mentioned, use the author of the message

    # Check if the author is the server owner
    is_server_owner = ctx.author == ctx.guild.owner

    if is_server_owner or ctx.author == member:
      user_id = str(
          member.id
      )  # Get the ID of the user whose investigator you want to delete

      if server_id in player_stats and user_id in player_stats[server_id]:
        investigator_name = player_stats[server_id][user_id]["NAME"]
        await ctx.send(
            f"Are you sure you want to delete investigator '{investigator_name}' for {member.display_name}? "
            f"Type '{investigator_name}' to confirm or anything else to cancel."
        )

        def check(message):
          return message.author == ctx.author and message.content.strip(
          ).title() == investigator_name

        try:
          confirmation_msg = await self.bot.wait_for("message",
                                                     timeout=30.0,
                                                     check=check)
        except asyncio.TimeoutError:
          await ctx.send(
              "Confirmation timed out. Investigator was not deleted.")
        else:
          del player_stats[server_id][user_id]  # Remove the investigator data
          await ctx.send(
              f"Investigator '{investigator_name}' for {member.display_name} has been deleted."
          )
          await save_player_stats(player_stats
                                  )  # Save the updated data to the JSON file
      else:
        await ctx.send(f"{member.display_name} doesn't have an investigator.")
    else:
      await ctx.send(
          "Only the server owner or the user themselves can delete their investigator."
      )


async def setup(bot):
  await bot.add_cog(deleteinvestigator(bot))
