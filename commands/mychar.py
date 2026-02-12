import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, load_gamemode_stats
from commands._mychar_view import CharacterDashboardView

class mychar(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    
  @commands.hybrid_command(aliases=["mcs", "char", "inv"], description="Show your investigator's stats, skills, backstory and inventory.")
  @app_commands.describe(member="The member whose character you want to see")
  async def mychar(self, ctx, *, member: discord.Member = None):
    """
    📜 Show your investigator's stats, skills, backstory and inventory.
    Usage: `[p]mychar` or `[p]mychar @User` to see others.
    """
    if ctx.guild is None:
      await ctx.send("This command is not allowed in DMs.")
      return    
      
    if member is None:
      user_id = str(ctx.author.id)
      member = ctx.author
    else:
      user_id = str(member.id)
    
    server_id = str(ctx.guild.id)
    player_stats = await load_player_stats()
    
    # Check if server exists in stats, if not handle gracefully or rely on it returning empty dict
    if server_id not in player_stats or user_id not in player_stats[server_id]:
        await ctx.send(f"{member.display_name} doesn't have an investigator. Use `!newInv` for creating a new investigator.", ephemeral=True)
        return
      
    # Loading game mode
    server_stats = await load_gamemode_stats()
    # Ensure nested dict exists
    if server_id not in server_stats:
        server_stats[server_id] = {}
    if 'game_mode' not in server_stats[server_id]:
        server_stats[server_id]['game_mode'] = 'Call of Cthulhu'

    # Determine Character Game Mode
    char_data = player_stats[server_id][user_id]
    current_mode = char_data.get("Game Mode", server_stats[server_id]['game_mode'])

    # Normalize mode string just in case
    if "pulp" in current_mode.lower():
        current_mode = "Pulp of Cthulhu"
        mode_label = "Pulp of Cthulhu character"
    else:
        current_mode = "Call of Cthulhu"
        mode_label = "Call of Cthulhu character"

    # Instantiate View
    view = CharacterDashboardView(ctx, char_data, mode_label, current_mode)
    
    # Send message with the initial Embed (Stats)
    await ctx.send(embed=view.get_embed(), view=view)

async def setup(bot):
  await bot.add_cog(mychar(bot))
