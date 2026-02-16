import discord
from loadnsave import load_player_stats, save_player_stats

CATEGORIES = [
    'My Story', 'Personal Description', 'Ideology and Beliefs', 'Significant People',
    'Meaningful Locations', 'Treasured Possessions', 'Traits', 'Injuries and Scars',
    'Phobias and Manias', 'Arcane Tome and Spells', 'Encounters with Strange Entities',
    'Fellow Investigators', 'Gear and Possessions', 'Spending Level', 'Cash', 'Assets'
]

class BackstorySelect(discord.ui.Select):
    def __init__(self, options, placeholder="Select an option..."):
        # Discord select menus can only have 25 options.
        # We store options to map back from index
        self.original_options = options

        truncated_options = options
        if len(options) > 25:
            truncated_options = options[:25] # Truncate for now

        select_options = []
        for i, opt in enumerate(truncated_options):
            label = str(opt)[:100]
            # Use index as value to avoid truncation issues and collisions
            select_options.append(discord.SelectOption(label=label, value=str(i)))

        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=select_options)

    async def callback(self, interaction: discord.Interaction):
        # We need access to the view to verify the author and store the result
        view: BackstoryView = self.view
        if interaction.user != view.author:
            await interaction.response.send_message("You are not the author of this command!", ephemeral=True)
            return

        index = int(self.values[0])
        if 0 <= index < len(self.original_options):
            view.selected_option = self.original_options[index]
        else:
            # Should not happen
            view.selected_option = None

        view.stop()
        await interaction.response.defer()

class BackstoryView(discord.ui.View):
    def __init__(self, options, author, placeholder="Select an option...", timeout=60):
        super().__init__(timeout=timeout)
        self.author = author
        self.selected_option = None

        self.add_item(BackstorySelect(options, placeholder))

        # Add cancel button
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("You are not the author of this command!", ephemeral=True)
            return
        self.selected_option = None
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self):
        self.stop()

# --- Interactive Dashboard Components ---

class BackstoryAddModal(discord.ui.Modal):
    def __init__(self, category, server_id, user_id, callback=None):
        title = f"Add to {category}"
        if len(title) > 45:
            title = title[:42] + "..."
        super().__init__(title=title)
        self.category = category
        self.server_id = server_id
        self.user_id = user_id
        self.callback_func = callback

        self.entry = discord.ui.TextInput(
            label=f"New entry for {category}"[:45],
            style=discord.TextStyle.paragraph,
            placeholder="Type your backstory/item details here...",
            required=True,
            max_length=4000
        )
        self.add_item(self.entry)

    async def on_submit(self, interaction: discord.Interaction):
        # Load stats (ensuring we have latest)
        player_stats = await load_player_stats()

        if self.server_id not in player_stats:
            player_stats[self.server_id] = {}

        if self.user_id not in player_stats[self.server_id]:
            await interaction.response.send_message("Error: Investigator not found.", ephemeral=True)
            return

        if "Backstory" not in player_stats[self.server_id][self.user_id]:
            player_stats[self.server_id][self.user_id]["Backstory"] = {}

        if self.category not in player_stats[self.server_id][self.user_id]["Backstory"]:
            player_stats[self.server_id][self.user_id]["Backstory"][self.category] = []

        entry_text = self.entry.value
        player_stats[self.server_id][self.user_id]["Backstory"][self.category].append(entry_text)

        await save_player_stats(player_stats)

        msg = f"✅ Added to **{self.category}**:\n>>> {entry_text}"
        await interaction.response.send_message(msg, ephemeral=True)

        if self.callback_func:
            await self.callback_func(interaction)

class BackstoryCategorySelectView(discord.ui.View):
    def __init__(self, author, server_id, user_id, mode="add", callback=None):
        super().__init__(timeout=60)
        self.author = author
        self.server_id = server_id
        self.user_id = user_id
        self.mode = mode # "add" or "remove"
        self.callback_func = callback

        # Build options
        self.categories = CATEGORIES

        self.select_menu = discord.ui.Select(placeholder="Select a category...", min_values=1, max_values=1)

        for cat in self.categories[:25]: # Limit to 25
            self.select_menu.add_option(label=cat[:100], value=cat)

        self.select_menu.callback = self.select_callback
        self.add_item(self.select_menu)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return

        category = self.select_menu.values[0]

        if self.mode == "add":
            modal = BackstoryAddModal(category, self.server_id, self.user_id, self.callback_func)
            await interaction.response.send_modal(modal)

        elif self.mode == "remove":
            # Launch Item Select View
            # We need to fetch items first
            player_stats = await load_player_stats()
            items = player_stats.get(self.server_id, {}).get(self.user_id, {}).get("Backstory", {}).get(category, [])

            if not items:
                await interaction.response.send_message(f"No items in **{category}** to remove.", ephemeral=True)
                return

            view = BackstoryItemSelectView(self.author, self.server_id, self.user_id, category, items, self.callback_func)
            await interaction.response.send_message(f"Select an item from **{category}** to remove:", view=view, ephemeral=True)

class BackstoryItemSelectView(discord.ui.View):
    def __init__(self, author, server_id, user_id, category, items, callback=None):
        super().__init__(timeout=60)
        self.author = author
        self.server_id = server_id
        self.user_id = user_id
        self.category = category
        self.items = items
        self.callback_func = callback

        self.select_menu = discord.ui.Select(placeholder="Select an item to remove...", min_values=1, max_values=1)

        # Limit items to 25
        for i, item in enumerate(items[:25]):
            # Use index as value to identify item uniquely (handling duplicates)
            label = str(item)[:100]
            self.select_menu.add_option(label=label, value=str(i))

        self.select_menu.callback = self.select_callback
        self.add_item(self.select_menu)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return

        index = int(self.select_menu.values[0])
        if index < 0 or index >= len(self.items):
             await interaction.response.send_message("Error: Item not found.", ephemeral=True)
             return

        item_to_remove = self.items[index]

        # Perform removal
        player_stats = await load_player_stats()
        # Re-fetch list to be safe
        current_list = player_stats.get(self.server_id, {}).get(self.user_id, {}).get("Backstory", {}).get(self.category, [])

        try:
            # Re-verify item exists
            if item_to_remove in current_list:
                current_list.remove(item_to_remove)
                await save_player_stats(player_stats)

                msg = f"✅ Removed from **{self.category}**:\n>>> {item_to_remove}"
                await interaction.response.send_message(msg, ephemeral=True)

                if self.callback_func:
                    await self.callback_func(interaction)
            else:
                await interaction.response.send_message("Error: Item not found (maybe already removed?).", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error removing item: {e}", ephemeral=True)

        # Disable buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        self.stop()
