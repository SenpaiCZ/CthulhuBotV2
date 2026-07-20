import discord
from discord.ui import View, Modal, TextInput, UserSelect, Select
from emojis import get_emoji_for_item
from loadnsave import load_player_stats, save_player_stats


class AddItemModal(Modal, title="Add Inventory Item"):
    item_name = TextInput(label="Item Name", placeholder="e.g. .38 Revolver or Flashlight", max_length=100)
    details = TextInput(label="Details / Quantity", placeholder="e.g. [30/30] or 1x", required=False, max_length=50)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        item_str = self.item_name.value.strip()
        if self.details.value:
            item_str += f" {self.details.value.strip()}"

        # Default to "Gear and Possessions"
        target_key = "Gear and Possessions"
        if "Backstory" not in self.view.char_data:
            self.view.char_data["Backstory"] = {}

        backstory = self.view.char_data["Backstory"]
        if target_key not in backstory:
            backstory[target_key] = []

        # Ensure it's a list
        if not isinstance(backstory[target_key], list):
             backstory[target_key] = [str(backstory[target_key])]

        backstory[target_key].append(item_str)

        # Save
        try:
            player_stats = await load_player_stats()
            # Ensure structure exists
            if self.view.server_id not in player_stats:
                player_stats[self.view.server_id] = {}

            player_stats[self.view.server_id][self.view.owner_id] = self.view.char_data
            await save_player_stats(player_stats)

            await interaction.response.send_message(f"Added **{item_str}** to inventory.", ephemeral=True)
            await self.view.refresh_dashboard(interaction)
        except Exception as e:
            await interaction.response.send_message(f"Error saving item: {e}", ephemeral=True)

class EditItemModal(Modal, title="Edit Item"):
    def __init__(self, view, category, index, original_text):
        super().__init__()
        self.dashboard_view = view
        self.category = category
        self.index = index
        self.item_input = TextInput(label="Item Details", default=original_text, max_length=100)
        self.add_item(self.item_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_text = self.item_input.value.strip()

        # Update Data
        backstory = self.dashboard_view.char_data.get("Backstory", {})
        if self.category in backstory and isinstance(backstory[self.category], list):
            if 0 <= self.index < len(backstory[self.category]):
                backstory[self.category][self.index] = new_text

                # Save
                try:
                    player_stats = await load_player_stats()
                    player_stats[self.dashboard_view.server_id][self.dashboard_view.owner_id] = self.dashboard_view.char_data
                    await save_player_stats(player_stats)

                    await interaction.response.send_message(f"✅ Item updated to: **{new_text}**", ephemeral=True)
                    await self.dashboard_view.refresh_dashboard(interaction)
                except Exception as e:
                    await interaction.response.send_message(f"Error saving update: {e}", ephemeral=True)
            else:
                await interaction.response.send_message("Error: Item index out of bounds.", ephemeral=True)
        else:
            await interaction.response.send_message("Error: Category not found.", ephemeral=True)

class GiveUserSelect(UserSelect):
    def __init__(self, view, category, item_str, index):
        super().__init__(placeholder="🎁 Give to player...", min_values=1, max_values=1, row=0)
        self.action_view = view
        self.category = category
        self.item_str = item_str
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        target_user = self.values[0] # discord.Member or User

        # Sender ID is the character owner, not necessarily the interactor (if GM)
        sender_id = self.action_view.dashboard_view.owner_id

        if str(target_user.id) == sender_id:
            return await interaction.response.send_message("You cannot give items to yourself.", ephemeral=True)

        if target_user.bot:
            return await interaction.response.send_message("You cannot give items to bots.", ephemeral=True)

        player_stats = await load_player_stats()
        server_id = str(interaction.guild_id)
        target_id = str(target_user.id)

        # 1. Validate Target has Investigator
        if server_id not in player_stats or target_id not in player_stats[server_id]:
            return await interaction.response.send_message(f"❌ {target_user.display_name} does not have an active investigator.", ephemeral=True)

        target_char = player_stats[server_id][target_id]
        sender_char = player_stats[server_id][sender_id]

        # 2. Transfer Logic
        # Remove from Sender
        backstory = sender_char.get("Backstory", {})
        item_removed = False
        if self.category in backstory and isinstance(backstory[self.category], list):
            if 0 <= self.index < len(backstory[self.category]):
                # Verify item matches (race condition check)
                if backstory[self.category][self.index] != self.item_str:
                     return await interaction.response.send_message("❌ Item state changed. Please refresh.", ephemeral=True)

                # Remove
                backstory[self.category].pop(self.index)
                item_removed = True
            else:
                 return await interaction.response.send_message("❌ Item not found.", ephemeral=True)
        else:
             return await interaction.response.send_message("❌ Category not found.", ephemeral=True)

        # Add to Target
        if "Backstory" not in target_char: target_char["Backstory"] = {}
        # We add to "Gear and Possessions" by default for transfers, or keep category?
        # Keeping category is safer contextually.
        target_cat = self.category
        if target_cat not in target_char["Backstory"]:
            target_char["Backstory"][target_cat] = []

        if not isinstance(target_char["Backstory"][target_cat], list):
             target_char["Backstory"][target_cat] = [str(target_char["Backstory"][target_cat])]

        target_char["Backstory"][target_cat].append(self.item_str)

        # Save
        await save_player_stats(player_stats)

        # Update Local View State to avoid desync
        if item_removed:
            local_backstory = self.action_view.dashboard_view.char_data.get("Backstory", {})
            if self.category in local_backstory and isinstance(local_backstory[self.category], list):
                 if 0 <= self.index < len(local_backstory[self.category]):
                     local_backstory[self.category].pop(self.index)

        # 3. Feedback
        await interaction.response.send_message(f"🎁 Given **{self.item_str}** to {target_user.mention}.", ephemeral=True)

        # Refresh Sender Dashboard
        await self.action_view.dashboard_view.refresh_dashboard(interaction)
        self.action_view.stop()


class ItemActionsView(View):
    def __init__(self, view, category, item_str, index):
        super().__init__(timeout=60)
        self.dashboard_view = view
        self.category = category
        self.item_str = item_str
        self.index = index
        # Give button is available if user has edit permissions
        if self.dashboard_view.can_edit:
            self.add_item(GiveUserSelect(self, category, item_str, index))

    @discord.ui.button(label="Show", style=discord.ButtonStyle.secondary, emoji="👁️", row=1)
    async def show_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            description=f"🕵️ {interaction.user.mention} reveals an item:\n\n**{get_emoji_for_item(self.item_str)} {self.item_str}**\n*({self.category})*",
            color=discord.Color.gold()
        )
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Item shown to chat.", ephemeral=True)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="✏️", row=1)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.dashboard_view.can_edit:
             return await interaction.response.send_message("You cannot edit this.", ephemeral=True)
        modal = EditItemModal(self.dashboard_view, self.category, self.index, self.item_str)
        await interaction.response.send_modal(modal)
        self.stop()

    @discord.ui.button(label="Discard", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def discard(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.dashboard_view.can_edit:
             return await interaction.response.send_message("You cannot discard this.", ephemeral=True)

        player_stats = await load_player_stats()
        server_id = str(interaction.guild_id)
        user_id = self.dashboard_view.owner_id

        char_data = player_stats.get(server_id, {}).get(user_id, {})
        backstory = char_data.get("Backstory", {})

        if self.category in backstory and isinstance(backstory[self.category], list):
             if 0 <= self.index < len(backstory[self.category]):
                 removed = backstory[self.category].pop(self.index)
                 await save_player_stats(player_stats)

                 # Update Local View State
                 local_backstory = self.dashboard_view.char_data.get("Backstory", {})
                 if self.category in local_backstory and isinstance(local_backstory[self.category], list):
                     if 0 <= self.index < len(local_backstory[self.category]):
                         local_backstory[self.category].pop(self.index)

                 await interaction.response.send_message(f"🗑️ Discarded **{removed}**.", ephemeral=True)
                 await self.dashboard_view.refresh_dashboard(interaction)
                 self.stop()
             else:
                 await interaction.response.send_message("Item not found.", ephemeral=True)
        else:
             await interaction.response.send_message("Category not found.", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

class InventorySelect(Select):
    def __init__(self, view, items, page=0):
        self.dashboard_view = view
        self.all_items = items
        self.page = page
        self.items_per_page = 24 # Reserve 1 spot for pagination if needed

        options = []

        # Calculate slice
        start = page * self.items_per_page
        end = start + self.items_per_page
        current_items = items[start:end]

        for i, (category, item_str) in enumerate(current_items):
            # Value needs to be unique and reconstructable. Index in all_items is best.
            real_index = start + i

            # Truncate label
            label = item_str[:100]
            desc = category[:100]
            emoji = get_emoji_for_item(item_str)

            options.append(discord.SelectOption(
                label=label,
                value=str(real_index),
                description=desc,
                emoji=emoji
            ))

        # Pagination Logic
        if len(items) > end:
            options.append(discord.SelectOption(
                label="Next Page >>",
                value="next_page",
                description="View more items",
                emoji="➡️"
            ))

        if page > 0:
            options.append(discord.SelectOption(
                label="<< Previous Page",
                value="prev_page",
                description="Go back",
                emoji="⬅️"
            ))

        super().__init__(
            placeholder=f"📦 Manage Items ({len(items)} total)...",
            min_values=1,
            max_values=1,
            options=options,
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.dashboard_view.user:
            return await interaction.response.send_message("Not your dashboard!", ephemeral=True)

        selected = self.values[0]

        if selected == "next_page":
            self.dashboard_view.inventory_page += 1
            self.dashboard_view.update_components()
            await interaction.response.edit_message(view=self.dashboard_view)
        elif selected == "prev_page":
            self.dashboard_view.inventory_page = max(0, self.dashboard_view.inventory_page - 1)
            self.dashboard_view.update_components()
            await interaction.response.edit_message(view=self.dashboard_view)
        else:
            # Item Selected
            index = int(selected)
            if 0 <= index < len(self.all_items):
                category, item_str = self.all_items[index]
                # Launch Item Actions View
                await self.dashboard_view.launch_item_actions(interaction, category, item_str, index)
            else:
                await interaction.response.send_message("Item selection error.", ephemeral=True)
