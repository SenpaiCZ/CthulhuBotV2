import discord
import asyncio
from discord.ext import commands
from discord import app_commands, ui
from loadnsave import load_player_stats, save_player_stats


class DeleteInvestigatorModal(ui.Modal, title="Delete Investigator"):
    name_confirmation = ui.TextInput(label="Confirm Name", placeholder="Type the investigator's name to confirm")

    def __init__(self, cog, user_id, server_id, investigator_name, member):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.server_id = server_id
        self.investigator_name = investigator_name
        self.member = member
        self.name_confirmation.placeholder = f"Type '{investigator_name}' to confirm"

    async def on_submit(self, interaction: discord.Interaction):
        if self.name_confirmation.value.strip().lower() == self.investigator_name.strip().lower():
             player_stats = await load_player_stats()
             if self.server_id in player_stats and self.user_id in player_stats[self.server_id]:
                 del player_stats[self.server_id][self.user_id]
                 await save_player_stats(player_stats)
                 await interaction.response.send_message(
                     f"Investigator '{self.investigator_name}' for {self.member.display_name} has been deleted."
                 )
             else:
                 await interaction.response.send_message("Investigator data not found (maybe already deleted?).", ephemeral=True)
        else:
             await interaction.response.send_message("Confirmation name did not match. Deletion cancelled.", ephemeral=True)


class deleteinvestigator(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @app_commands.command(name="deleteinvestigator", description="Delete your investigator and all data.")
  @app_commands.describe(member="The member whose investigator you want to delete (Admin only)")
  async def deleteinvestigator(self, interaction: discord.Interaction, member: discord.Member = None):
    """
    Delete your investigator, all data, backstory and inventory. You will be prompted to write your investigators name to confirm deletion. Server owners can delete other players investigators.
    """
    user_id = str(interaction.user.id)
    server_id = str(interaction.guild.id)
    player_stats = await load_player_stats()

    if member is None:
      member = interaction.user

    # Check if the author is the server owner
    is_server_owner = interaction.user == interaction.guild.owner

    if is_server_owner or interaction.user == member:
      target_user_id = str(member.id)

      if server_id in player_stats and target_user_id in player_stats[server_id]:
        investigator_name = player_stats[server_id][target_user_id]["NAME"]

        modal = DeleteInvestigatorModal(self, target_user_id, server_id, investigator_name, member)
        await interaction.response.send_modal(modal)
      else:
        await interaction.response.send_message(f"{member.display_name} doesn't have an investigator.", ephemeral=True)
    else:
      await interaction.response.send_message(
          "Only the server owner or the user themselves can delete their investigator.",
          ephemeral=True
      )


async def setup(bot):
  await bot.add_cog(deleteinvestigator(bot))
