import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, load_gamemode_stats
from commands._mychar_view import CharacterDashboardView

class mycharacter(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    
  @app_commands.command(name="mycharacter", description="Show your investigator's stats, skills, backstory and inventory.")
  @app_commands.describe(member="The member whose character you want to see")
  async def mycharacter(self, interaction: discord.Interaction, member: discord.Member = None):

    if interaction.guild is None:
      await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)
      return    
      
    if member is None:
      user_id = str(interaction.user.id)
      member = interaction.user
    else:
      user_id = str(member.id)
    
    server_id = str(interaction.guild.id)
    player_stats = await load_player_stats()
    
    # Check if server exists in stats, if not handle gracefully or rely on it returning empty dict
    if server_id not in player_stats or user_id not in player_stats[server_id]:
        await interaction.response.send_message(f"{member.display_name} doesn't have an investigator. Use `/newinvestigator` for creating a new investigator.", ephemeral=True)
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
    # Pass interaction.user so the dashboard is interactive for the caller
    view = CharacterDashboardView(interaction.user, char_data, mode_label, current_mode, server_id)
    
    # Send message with the initial Embed (Stats)
    await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)
    view.message = await interaction.original_response()

async def setup(bot):
  await bot.add_cog(mycharacter(bot))
