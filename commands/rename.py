import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, TextInput
from loadnsave import load_player_stats, save_player_stats


class RenameCharacterModal(Modal, title="Rename Character"):
    def __init__(self, current_name: str, target_user_id: str, server_id: str):
        super().__init__()
        self.target_user_id = target_user_id
        self.server_id = server_id

        self.new_name = TextInput(
            label="New Character Name",
            style=discord.TextStyle.short,
            placeholder="Enter new character name...",
            default=current_name,
            required=True,
            max_length=100
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        new_name_val = self.new_name.value.strip()

        player_stats = await load_player_stats()

        if self.server_id in player_stats and self.target_user_id in player_stats[self.server_id]:
            old_name = player_stats[self.server_id][self.target_user_id].get("NAME", "Unknown")
            player_stats[self.server_id][self.target_user_id]["NAME"] = new_name_val
            await save_player_stats(player_stats)
            await interaction.response.send_message(f"Character successfully renamed from **{old_name}** to **{new_name_val}**.", ephemeral=True)
        else:
            await interaction.response.send_message("Could not find the investigator to rename.", ephemeral=True)


class rename(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"
        self.ctx_menu = app_commands.ContextMenu(
            name='Rename Character',
            callback=self.rename_character_menu,
        )
        self.ctx_menu.description = "🏷️ Rename this user's character."
        self.ctx_menu.binding = self
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def rename_character_menu(self, interaction: discord.Interaction, user: discord.Member):
        server_id = str(interaction.guild_id)
        target_user_id = str(user.id)
        requester_id = str(interaction.user.id)

        if not interaction.guild:
            return await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)

        # Check permissions: must be the character owner OR an administrator
        if target_user_id != requester_id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You do not have permission to rename this character.", ephemeral=True)

        player_stats = await load_player_stats()

        if target_user_id in player_stats.get(server_id, {}):
            current_name = player_stats[server_id][target_user_id].get("NAME", "Unknown")
            modal = RenameCharacterModal(current_name, target_user_id, server_id)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message(
                f"{user.display_name} doesn't have an investigator.",
                ephemeral=True
            )

    @app_commands.command(description="🏷️ Change the name of your character.")
    async def rename(self, interaction: discord.Interaction):
        """
        Change the name of your character.
        """
        server_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)

        if not interaction.guild:
            return await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)

        player_stats = await load_player_stats()

        if user_id in player_stats.get(server_id, {}):
            current_name = player_stats[server_id][user_id].get("NAME", "Unknown")
            modal = RenameCharacterModal(current_name, user_id, server_id)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message(
                f"{interaction.user.display_name} doesn't have an investigator. Use `/newinvestigator` for creating a new investigator.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(rename(bot))
