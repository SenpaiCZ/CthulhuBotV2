import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
from loadnsave import load_player_stats, save_player_stats


class RenameCharacterModal(ui.Modal, title="Rename Character"):
    new_name = ui.TextInput(label="New Character Name", placeholder="Enter the new name here...", style=discord.TextStyle.short, required=True, max_length=100)

    def __init__(self, target_user_id):
        super().__init__()
        self.target_user_id = str(target_user_id)

    async def on_submit(self, interaction: discord.Interaction):
        server_id = str(interaction.guild_id)
        player_stats = await load_player_stats()

        if server_id in player_stats and self.target_user_id in player_stats[server_id]:
            player_stats[server_id][self.target_user_id]["NAME"] = self.new_name.value
            await save_player_stats(player_stats)
            await interaction.response.send_message(f"Character's name has been updated to `{self.new_name.value}`.", ephemeral=True)
        else:
            await interaction.response.send_message("Character not found.", ephemeral=True)


class rename(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.ctx_menu = app_commands.ContextMenu(
        name='Rename Character',
        callback=self.rename_character_context,
    )
    self.ctx_menu.description = "🏷️ Change the name of this character."
    self.ctx_menu.binding = self
    self.bot.tree.add_command(self.ctx_menu)

  def cog_unload(self):
    self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

  async def rename_character_context(self, interaction: discord.Interaction, member: discord.Member):
      if interaction.user != member and not interaction.user.guild_permissions.administrator:
          await interaction.response.send_message("❌ Only Game Masters (Admins) can rename other players' characters.", ephemeral=True)
          return

      server_id = str(interaction.guild_id)
      user_id = str(member.id)
      player_stats = await load_player_stats()

      if server_id not in player_stats or user_id not in player_stats[server_id]:
          await interaction.response.send_message(f"❌ {member.display_name} doesn't have an investigator.", ephemeral=True)
          return

      modal = RenameCharacterModal(member.id)
      await interaction.response.send_modal(modal)

  @app_commands.command(description="🏷️ Change the name of your character.")
  async def rename(self, interaction: discord.Interaction):
      """
      Change the name of your character.
      """
      server_id = str(interaction.guild.id)
      user_id = str(interaction.user.id)
      player_stats = await load_player_stats()

      if server_id in player_stats and user_id in player_stats[server_id]:
          modal = RenameCharacterModal(interaction.user.id)
          await interaction.response.send_modal(modal)
      else:
          await interaction.response.send_message(
              f"{interaction.user.display_name} doesn't have an investigator. Use `/newinvestigator` for creating a new investigator.",
              ephemeral=True
          )


async def setup(bot):
  await bot.add_cog(rename(bot))
