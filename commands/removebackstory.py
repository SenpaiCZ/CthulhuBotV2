import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, save_player_stats
from commands._backstory_common import BackstoryView

class removebackstory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="removebackstory", description="Interactive wizard to remove items from your character's backstory.")
    async def removebackstory(self, interaction: discord.Interaction):
        """
        Interactive wizard to remove items from your character's backstory.
        """
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Check for DMs
        if not interaction.guild:
             await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)
             return

        player_stats = await load_player_stats()
        if user_id not in player_stats.get(server_id, {}):
            await interaction.response.send_message("You don't have an investigator.", ephemeral=True)
            return

        backstory = player_stats[server_id][user_id].get("Backstory", {})
        if not backstory:
            await interaction.response.send_message("Your backstory is empty.", ephemeral=True)
            return

        categories = list(backstory.keys())
        if not categories:
             await interaction.response.send_message("Your backstory is empty.", ephemeral=True)
             return

        category_view = BackstoryView(categories, interaction.user, placeholder="Select a category...")
        await interaction.response.send_message("Select a category from your backstory:", view=category_view, ephemeral=True)
        await category_view.wait()

        if category_view.selected_option:
            selected_category = category_view.selected_option
            items = backstory[selected_category]

            if not items:
                await interaction.edit_original_response(content=f"Category '{selected_category}' is empty.", view=None)
                return

            # Edit existing message to show next step
            item_view = BackstoryView(items, interaction.user, placeholder=f"Select item to remove from {selected_category}...")
            await interaction.edit_original_response(content=f"Select an item from '**{selected_category}**' to remove:", view=item_view)
            await item_view.wait()

            if item_view.selected_option:
                selected_item = item_view.selected_option

                try:
                    if selected_item in backstory[selected_category]:
                        backstory[selected_category].remove(selected_item)
                        await save_player_stats(player_stats)
                        await interaction.edit_original_response(content=f"✅ Item removed from '**{selected_category}**'.", view=None)
                    else:
                        await interaction.edit_original_response(content="Error: Item could not be found to remove.", view=None)
                except ValueError:
                    await interaction.edit_original_response(content="Error: Item could not be found to remove.", view=None)
            else:
                await interaction.edit_original_response(content="Item selection cancelled.", view=None)
        else:
            await interaction.edit_original_response(content="Category selection cancelled.", view=None)

async def setup(bot):
    await bot.add_cog(removebackstory(bot))
