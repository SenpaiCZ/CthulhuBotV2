import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, save_player_stats


class RenameCharacterModal(discord.ui.Modal, title="Rename Character"):
    new_name = discord.ui.TextInput(
        label="New Character Name",
        style=discord.TextStyle.short,
        placeholder="Enter the new name here...",
        required=True,
        max_length=100
    )

    def __init__(self, user_id: str, server_id: str, old_name: str):
        super().__init__()
        self.user_id = user_id
        self.server_id = server_id
        self.new_name.default = old_name

    async def on_submit(self, interaction: discord.Interaction):
        player_stats = await load_player_stats()
        if self.server_id in player_stats and self.user_id in player_stats[self.server_id]:
            player_stats[self.server_id][self.user_id]["NAME"] = self.new_name.value
            await save_player_stats(player_stats)
            await interaction.response.send_message(f"✅ Character name updated to **{self.new_name.value}**.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Investigator not found.", ephemeral=True)


class rename(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name='Rename Character',
            callback=self.rename_character_context,
        )
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def rename_character_context(self, interaction: discord.Interaction, member: discord.Member):
        server_id = str(interaction.guild.id)
        user_id = str(member.id)

        # Check permissions: GM or Owner
        is_gm = interaction.user.guild_permissions.administrator
        is_owner = interaction.user.id == member.id

        if not (is_gm or is_owner):
            return await interaction.response.send_message("❌ You do not have permission to rename this character.", ephemeral=True)

        player_stats = await load_player_stats()
        if server_id in player_stats and user_id in player_stats[server_id]:
            old_name = player_stats[server_id][user_id].get("NAME", "Unknown")
            await interaction.response.send_modal(RenameCharacterModal(user_id, server_id, old_name))
        else:
            await interaction.response.send_message(f"❌ {member.display_name} doesn't have an investigator.", ephemeral=True)

    @app_commands.command(name="rename", description="🏷️ Change the name of your character interactively.")
    async def rename_command(self, interaction: discord.Interaction):
        """
        Change the name of your character interactively.
        """
        server_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        player_stats = await load_player_stats()
        if server_id in player_stats and user_id in player_stats[server_id]:
            old_name = player_stats[server_id][user_id].get("NAME", "Unknown")
            await interaction.response.send_modal(RenameCharacterModal(user_id, server_id, old_name))
        else:
            await interaction.response.send_message(
                f"❌ {interaction.user.display_name} doesn't have an investigator. Use `/newinvestigator` for creating a new investigator.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(rename(bot))
