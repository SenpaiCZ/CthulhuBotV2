import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, save_player_stats, load_server_stats

class RenameCharacterModal(discord.ui.Modal, title="Rename Character"):
    new_name = discord.ui.TextInput(
        label="New Character Name",
        placeholder="Enter the new name here...",
        min_length=1,
        max_length=100
    )

    def __init__(self, target_user_id: str, old_name: str):
        super().__init__()
        self.target_user_id = target_user_id
        self.new_name.default = old_name

    async def on_submit(self, interaction: discord.Interaction):
        server_id = str(interaction.guild.id)
        player_stats = await load_player_stats()

        if server_id in player_stats and self.target_user_id in player_stats[server_id]:
            old_name = player_stats[server_id][self.target_user_id].get("NAME", "Unknown")
            new_name_val = self.new_name.value.strip()
            player_stats[server_id][self.target_user_id]["NAME"] = new_name_val
            await save_player_stats(player_stats)

            embed = discord.Embed(
                title="🏷️ Character Renamed",
                description=f"Successfully renamed **{old_name}** to **{new_name_val}**.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Failed to find character data.", ephemeral=True)

class rename(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name='Rename Character',
            callback=self.rename_context_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def rename_context_menu(self, interaction: discord.Interaction, member: discord.Member):
        # Allow character owner or Administrators to rename
        is_owner = interaction.user.id == member.id
        is_admin = interaction.user.guild_permissions.administrator

        if not (is_owner or is_admin):
            await interaction.response.send_message("❌ Only the character owner or an Administrator can rename this character.", ephemeral=True)
            return

        server_id = str(interaction.guild.id)
        user_id = str(member.id)
        player_stats = await load_player_stats()

        if server_id in player_stats and user_id in player_stats[server_id]:
            old_name = player_stats[server_id][user_id].get("NAME", "")
            await interaction.response.send_modal(RenameCharacterModal(target_user_id=user_id, old_name=old_name))
        else:
            await interaction.response.send_message(f"❌ {member.display_name} doesn't have an investigator.", ephemeral=True)

    @app_commands.command(description="🏷️ Change the name of your character.")
    async def rename(self, interaction: discord.Interaction):
        """
        Change the name of your character using a pop-up form.
        """
        server_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        if user_id in player_stats.get(server_id, {}):
            old_name = player_stats[server_id][user_id].get("NAME", "")
            await interaction.response.send_modal(RenameCharacterModal(target_user_id=user_id, old_name=old_name))
        else:
            await interaction.response.send_message(
                f"{interaction.user.display_name} doesn't have an investigator. Use `/newinvestigator` for creating a new investigator.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(rename(bot))
