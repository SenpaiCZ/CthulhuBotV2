import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
from loadnsave import load_player_stats, save_player_stats

class RenameCharacterModal(ui.Modal, title="Rename Character"):
    def __init__(self, bot, target_user, current_name):
        super().__init__()
        self.bot = bot
        self.target_user = target_user

        self.new_name = ui.TextInput(
            label="New Character Name",
            default=current_name,
            placeholder="Enter the new name here...",
            max_length=100,
            required=True
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        server_id = str(interaction.guild_id)
        user_id = str(self.target_user.id)
        new_name_val = self.new_name.value.strip()

        player_stats = await load_player_stats()

        if server_id in player_stats and user_id in player_stats[server_id]:
            old_name = player_stats[server_id][user_id].get("NAME", "Unknown")
            player_stats[server_id][user_id]["NAME"] = new_name_val
            await save_player_stats(player_stats)

            embed = discord.Embed(
                title="🏷️ Character Renamed",
                description=f"**{self.target_user.display_name}**'s character has been renamed.",
                color=discord.Color.green()
            )
            embed.add_field(name="Old Name", value=old_name, inline=True)
            embed.add_field(name="New Name", value=new_name_val, inline=True)

            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❌ Data for {self.target_user.display_name}'s investigator not found.",
                ephemeral=True
            )

class rename(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.help_category = "Player"

    self.ctx_menu = app_commands.ContextMenu(
        name='Rename Character',
        callback=self.rename_context,
    )
    self.ctx_menu.binding = self
    self.bot.tree.add_command(self.ctx_menu)

  def cog_unload(self):
    self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

  async def rename_context(self, interaction: discord.Interaction, member: discord.Member):
      # Permission check: You can rename yourself, or you can rename others if you're an Admin
      if interaction.user != member and not interaction.user.guild_permissions.administrator:
          return await interaction.response.send_message("❌ You can only rename your own character unless you're a Game Master (Admin).", ephemeral=True)

      server_id = str(interaction.guild.id)
      user_id = str(member.id)
      player_stats = await load_player_stats()

      if server_id in player_stats and user_id in player_stats[server_id]:
          current_name = player_stats[server_id][user_id].get("NAME", "")
          modal = RenameCharacterModal(self.bot, member, current_name)
          await interaction.response.send_modal(modal)
      else:
          await interaction.response.send_message(
              f"❌ {member.display_name} doesn't have an investigator.",
              ephemeral=True
          )

  @app_commands.command(description="🏷️ Change the name of your character via a popup.")
  async def rename(self, interaction: discord.Interaction):
      """
      Opens a form to change the name of your character.
      """
      server_id = str(interaction.guild.id)
      user_id = str(interaction.user.id)
      player_stats = await load_player_stats()

      if server_id in player_stats and user_id in player_stats[server_id]:
          current_name = player_stats[server_id][user_id].get("NAME", "")
          modal = RenameCharacterModal(self.bot, interaction.user, current_name)
          await interaction.response.send_modal(modal)
      else:
          await interaction.response.send_message(
              f"❌ You don't have an investigator. Use `/newinvestigator` to create one.",
              ephemeral=True
          )

async def setup(bot):
  await bot.add_cog(rename(bot))
