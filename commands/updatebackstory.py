import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, save_player_stats
from commands._backstory_common import BackstoryView

class UpdateBackstoryModal(discord.ui.Modal):
    def __init__(self, category, item_index, item_text, server_id, user_id, player_stats_ref):
        title = f"Update {category}"
        if len(title) > 45:
            title = title[:42] + "..."
        super().__init__(title=title)

        self.category = category
        self.item_index = item_index # Index in the list
        self.original_text = item_text
        self.server_id = server_id
        self.user_id = user_id
        self.player_stats = player_stats_ref

        self.new_text = discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            default=item_text[:4000],
            required=True,
            max_length=4000
        )
        self.add_item(discord.ui.Label(text="Edit content", component=self.new_text))

    async def on_submit(self, interaction: discord.Interaction):
        # Refresh stats to be safe? Or rely on ref.
        # Ideally we should reload but let's assume ref is valid for this short transaction.
        # But race conditions exist. Let's load fresh to be safe?
        # No, passing ref is standard here.

        backstory = self.player_stats.get(self.server_id, {}).get(self.user_id, {}).get("Backstory", {})
        if self.category not in backstory:
             await interaction.response.send_message("Error: Category not found (concurrent modification?)", ephemeral=True)
             return

        items = backstory[self.category]

        # Check if item still exists at index and matches text (optimistic lockingish)
        if self.item_index >= len(items) or items[self.item_index] != self.original_text:
             await interaction.response.send_message("Error: The item seems to have changed or moved. Please try again.", ephemeral=True)
             return

        # Update
        items[self.item_index] = self.new_text.value
        await save_player_stats(self.player_stats)

        await interaction.response.edit_message(content=f"✅ Updated item in **{self.category}**.", view=None)

class UpdateBackstorySelect(discord.ui.Select):
    def __init__(self, options, category, server_id, user_id, player_stats_ref):
        self.original_options = options
        self.category = category
        self.server_id = server_id
        self.user_id = user_id
        self.player_stats = player_stats_ref

        truncated_options = options
        if len(options) > 25:
             truncated_options = options[:25]

        select_options = []
        for i, opt in enumerate(truncated_options):
             label = str(opt)[:100]
             # Use index as value
             select_options.append(discord.SelectOption(label=label, value=str(i)))

        super().__init__(placeholder=f"Select item to update from {category}...", min_values=1, max_values=1, options=select_options)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if interaction.user != view.author:
            await interaction.response.send_message("This isn't your session!", ephemeral=True)
            return

        index = int(self.values[0])
        if 0 <= index < len(self.original_options):
            selected_text = self.original_options[index]
            modal = UpdateBackstoryModal(self.category, index, selected_text, self.server_id, self.user_id, self.player_stats)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("Error selecting item.", ephemeral=True)

class UpdateBackstoryView(discord.ui.View):
    def __init__(self, options, category, author, server_id, user_id, player_stats_ref, timeout=60):
        super().__init__(timeout=timeout)
        self.author = author
        self.add_item(UpdateBackstorySelect(options, category, server_id, user_id, player_stats_ref))

        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("This isn't your session!", ephemeral=True)
            return
        await interaction.response.edit_message(content="Update cancelled.", view=None)
        self.stop()

class updatebackstory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="updatebackstory", description="Interactive wizard to update your character's backstory elements.")
    async def updatebackstory(self, interaction: discord.Interaction):
        """
        Interactive wizard to update your character's backstory elements.
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

        # Step 1: Select Category
        category_view = BackstoryView(categories, interaction.user, placeholder="Select a category...")
        await interaction.response.send_message("Select a category from your backstory:", view=category_view, ephemeral=True)
        await category_view.wait()

        if category_view.selected_option:
            selected_category = category_view.selected_option
            items = backstory[selected_category]

            if not items:
                await interaction.edit_original_response(content=f"Category '{selected_category}' is empty.", view=None)
                return

            # Step 2: Select Item (triggers Modal)
            update_view = UpdateBackstoryView(items, selected_category, interaction.user, server_id, user_id, player_stats)
            await interaction.edit_original_response(content=f"Select an item from '**{selected_category}**' to update:", view=update_view)

            # We don't wait() here because the view handles the modal interaction flow.
        else:
            await interaction.edit_original_response(content="Category selection cancelled.", view=None)

async def setup(bot):
    await bot.add_cog(updatebackstory(bot))
