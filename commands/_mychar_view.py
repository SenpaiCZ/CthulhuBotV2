import discord
import math
import re
from discord.ui import View, Select, Button, Modal, TextInput, UserSelect
from emojis import get_stat_emoji, stat_emojis, get_emoji_for_item
from descriptions import get_description
import occupation_emoji
from commands._backstory_common import BackstoryCategorySelectView
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

            player_stats[self.view.server_id][str(self.view.user.id)] = self.view.char_data
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
                    player_stats[self.dashboard_view.server_id][str(self.dashboard_view.user.id)] = self.dashboard_view.char_data
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

        if target_user.id == interaction.user.id:
            return await interaction.response.send_message("You cannot give items to yourself.", ephemeral=True)

        if target_user.bot:
            return await interaction.response.send_message("You cannot give items to bots.", ephemeral=True)

        player_stats = await load_player_stats()
        server_id = str(interaction.guild_id)
        target_id = str(target_user.id)
        sender_id = str(interaction.user.id)

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
                     # Optimistic update - assume index matches because we validated against self.item_str above
                     # But local view might be stale, so verify content if possible.
                     # Since we are about to refresh, popping by index is risky if list shifted.
                     # But self.index came from the select menu which was built from current state.
                     # So it should be fine.
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
        self.add_item(GiveUserSelect(self, category, item_str, index))

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="✏️", row=1)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditItemModal(self.dashboard_view, self.category, self.index, self.item_str)
        await interaction.response.send_modal(modal)
        self.stop()

    @discord.ui.button(label="Discard", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def discard(self, interaction: discord.Interaction, button: discord.ui.Button):
        player_stats = await load_player_stats()
        server_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)

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


class CharacterDashboardView(View):
    def __init__(self, user, char_data, mode_label, current_mode, server_id):
        super().__init__(timeout=300) # 5 minute timeout
        self.user = user
        self.char_data = char_data
        self.mode_label = mode_label
        self.current_mode = current_mode
        self.server_id = server_id
        self.current_section = "stats"
        self.page = 0
        self.inventory_page = 0
        self.items_per_page = 24
        self.message = None

        # Build the initial Select Menu
        self.update_components()

    def update_components(self):
        self.clear_items()

        # Section Selector
        select = Select(
            placeholder="Navigate Character Sheet",
            options=[
                discord.SelectOption(label="📊 Attributes & Bio", value="stats", description="Core stats, HP, SAN, Move, etc.", emoji="📊", default=(self.current_section == "stats")),
                discord.SelectOption(label="🛠️ Skills", value="skills", description="List of all skills and probabilities", emoji="🛠️", default=(self.current_section == "skills")),
                discord.SelectOption(label="📜 Backstory & Inventory", value="backstory", description="History, Ideology, Assets, Gear", emoji="📜", default=(self.current_section == "backstory"))
            ],
            row=0
        )
        select.callback = self.select_callback
        self.add_item(select)

        # Pagination Buttons (Only for Skills/Backstory if needed)
        if self.current_section == "skills":
            skill_list = self._get_skill_list()
            max_pages = math.ceil(len(skill_list) / self.items_per_page)

            if max_pages > 1:
                prev_btn = Button(label="Previous", style=discord.ButtonStyle.secondary, row=1, disabled=(self.page == 0))
                prev_btn.callback = self.prev_page_callback
                self.add_item(prev_btn)

                indicator = Button(label=f"Page {self.page + 1}/{max_pages}", style=discord.ButtonStyle.secondary, disabled=True, row=1)
                self.add_item(indicator)

                next_btn = Button(label="Next", style=discord.ButtonStyle.secondary, row=1, disabled=(self.page >= max_pages - 1))
                next_btn.callback = self.next_page_callback
                self.add_item(next_btn)

        # Interactive Buttons for Backstory
        if self.current_section == "backstory":
             # 1. Inventory Select Menu
             inventory_items = self._get_inventory_items()
             if inventory_items:
                 self.add_item(InventorySelect(self, inventory_items, self.inventory_page))

             # Check for empty inventory logic
             if not inventory_items:
                 add_item_btn = Button(label="Add Item", style=discord.ButtonStyle.primary, row=2, emoji="🎒")
                 add_item_btn.callback = self.add_item_callback
                 self.add_item(add_item_btn)
             else:
                  # If we have items, we still want add item button, but maybe in row 2
                  add_item_btn = Button(label="Add Item", style=discord.ButtonStyle.primary, row=2, emoji="🎒")
                  add_item_btn.callback = self.add_item_callback
                  self.add_item(add_item_btn)

             # Standard Buttons
             add_btn = Button(label="Add Entry", style=discord.ButtonStyle.success, row=2, emoji="➕")
             add_btn.callback = self.add_entry_callback
             self.add_item(add_btn)

             remove_btn = Button(label="Remove Entry", style=discord.ButtonStyle.danger, row=2, emoji="➖")
             remove_btn.callback = self.remove_entry_callback
             self.add_item(remove_btn)

        # Dismiss Button (Always available)
        dismiss_btn = Button(label="Dismiss", style=discord.ButtonStyle.danger, row=3)
        dismiss_btn.callback = self.dismiss_callback
        self.add_item(dismiss_btn)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This dashboard is not for you!", ephemeral=True)
            return

        self.current_section = interaction.data["values"][0]
        self.page = 0 # Reset page on section change
        self.inventory_page = 0
        self.update_components()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
        self.message = interaction.message

    async def prev_page_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user: return
        if self.page > 0:
            self.page -= 1
            self.update_components()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
            self.message = interaction.message

    async def next_page_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user: return
        self.page += 1
        self.update_components()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
        self.message = interaction.message

    async def dismiss_callback(self, interaction: discord.Interaction):
        if interaction.user == self.user:
            await interaction.response.edit_message(content="Dashboard dismissed.", embed=None, view=None)
        else:
            await interaction.response.send_message("You cannot dismiss this.", ephemeral=True)

    async def refresh_dashboard(self, interaction: discord.Interaction):
        # Refresh dashboard view
        if not self.message:
            return

        try:
            # Re-fetch data to ensure we have the latest updates
            player_stats = await load_player_stats()
            # server_id and user.id are used to get the specific char_data
            if self.server_id in player_stats and str(self.user.id) in player_stats[self.server_id]:
                self.char_data = player_stats[self.server_id][str(self.user.id)]

            self.update_components()
            await self.message.edit(embed=self.get_embed(), view=self)
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"Error refreshing dashboard: {e}")

    async def add_entry_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not your dashboard!", ephemeral=True)

        view = BackstoryCategorySelectView(self.user, self.server_id, str(self.user.id), mode="add", callback=self.refresh_dashboard)
        await interaction.response.send_message("Select a category to add to:", view=view, ephemeral=True)

    async def remove_entry_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not your dashboard!", ephemeral=True)

        view = BackstoryCategorySelectView(self.user, self.server_id, str(self.user.id), mode="remove", callback=self.refresh_dashboard)
        await interaction.response.send_message("Select a category to remove from:", view=view, ephemeral=True)

    async def add_item_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not your dashboard!", ephemeral=True)
        await interaction.response.send_modal(AddItemModal(self))

    async def launch_item_actions(self, interaction, category, item_str, index):
        view = ItemActionsView(self, category, item_str, index)
        embed = discord.Embed(title="Item Actions", description=f"**Item:** {get_emoji_for_item(item_str)} {item_str}\n**Category:** {category}", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    def _get_inventory_items(self):
        inventory_keys = ["Gear and Possessions", "Assets", "Equipment", "Weapons"]
        backstory = self.char_data.get("Backstory", {})

        items = []
        for key in inventory_keys:
            if key in backstory and isinstance(backstory[key], list):
                for item in backstory[key]:
                    items.append((key, item))
        return items

    def get_embed(self):
        if self.current_section == "stats":
            return self._get_stats_embed()
        elif self.current_section == "skills":
            return self._get_skills_embed()
        elif self.current_section == "backstory":
            return self._get_backstory_embed()
        return discord.Embed(title="Error", description="Unknown section")

    def _get_stats_embed(self):
        embed = discord.Embed(
            title=f"{self.char_data.get('NAME', 'Unknown')}",
            description=f"**{self.mode_label}**",
            color=discord.Color.dark_teal()
        )

        # --- 1. Bio Section ---
        occupation = self.char_data.get("Occupation", "Unknown")
        occ_emoji = occupation_emoji.get_occupation_emoji(occupation)
        residence = self.char_data.get("Residence", "Unknown")
        age = self.char_data.get("Age", "Unknown")
        archetype = self.char_data.get("Archetype", None)

        bio_desc = f"**Occupation:** {occupation} {occ_emoji}\n**Age:** {age}\n**Residence:** {residence}"
        if archetype:
            bio_desc += f"\n**Archetype:** {archetype}"

        embed.add_field(name="📜 Biography", value=bio_desc, inline=False)

        # --- 2. Attributes (STR, DEX, etc.) ---
        # We want a nice grid.
        attributes = ["STR", "DEX", "INT", "CON", "APP", "POW", "SIZ", "EDU", "LUCK"]

        attr_text = ""
        for attr in attributes:
            val = self.char_data.get(attr, 0)
            emoji = get_stat_emoji(attr)
            # Format: **STR** 50 (25/10)
            attr_text += f"{emoji} **{attr}:** {val} ({val//2}/{val//5})\n"

        embed.add_field(name="📊 Characteristics", value=attr_text, inline=True)

        # --- 3. Derived Stats (HP, MP, SAN, Move, Build, DB) ---
        derived_text = ""

        # HP
        hp = self.char_data.get("HP", 0)
        con = self.char_data.get("CON", 0)
        siz = self.char_data.get("SIZ", 0)
        max_hp = (con + siz) // 10 if self.current_mode == "Call of Cthulhu" else (con + siz) // 5
        derived_text += f"❤️ **HP:** {hp}/{max_hp}\n"

        # MP
        mp = self.char_data.get("MP", 0)
        pow_stat = self.char_data.get("POW", 0)
        max_mp = pow_stat // 5
        derived_text += f"✨ **MP:** {mp}/{max_mp}\n"

        # SAN
        san = self.char_data.get("SAN", 0)
        start_san = pow_stat
        mythos = self.char_data.get("Cthulhu Mythos", 0)
        max_san = 99 - mythos
        derived_text += f"🧠 **SAN:** {san}/{max_san}\n"

        # Move
        move = self._calculate_move()
        derived_text += f"🏃 **Move:** {move}\n"

        # Build & DB
        build, db = self._calculate_build_db()
        derived_text += f"💪 **Build:** {build}\n💥 **DB:** {db}\n"

        # Dodge (Often considered a core combat stat)
        dodge = self.char_data.get("Dodge", 0)
        derived_text += f"💨 **Dodge:** {dodge} ({dodge//2}/{dodge//5})\n"

        embed.add_field(name="⚖️ Derived Stats", value=derived_text, inline=True)

        return embed

    def _get_skills_embed(self):
        embed = discord.Embed(
            title=f"🛠️ Skills - {self.char_data.get('NAME', 'Unknown')}",
            color=discord.Color.dark_green()
        )

        all_skills = self._get_skill_list()

        # Pagination logic
        start_idx = self.page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        current_page_skills = all_skills[start_idx:end_idx]

        if not current_page_skills:
            embed.description = "No skills found."
            return embed

        for skill, val in current_page_skills:
            # Format: Value (Hard/Extreme)
            val_text = f"**{val}** ({val//2}/{val//5})"
            emoji = self._get_skill_emoji(skill)
            embed.add_field(name=f"{emoji} {skill}", value=val_text, inline=True)

        embed.set_footer(text=f"Page {self.page + 1}/{math.ceil(len(all_skills)/self.items_per_page)}")
        return embed

    def _get_backstory_embed(self):
        embed = discord.Embed(
            title=f"📜 Backstory & Inventory - {self.char_data.get('NAME', 'Unknown')}",
            color=discord.Color.gold()
        )

        backstory = self.char_data.get("Backstory", {})

        # Helper to format list entries
        def format_entries(entries):
            if isinstance(entries, list):
                if not entries: return "None"
                return "\n".join([f"• {entry}" for entry in entries])
            return str(entries)

        # Inventory / Assets specific handling
        # Usually keys like "Assets", "Gear", "Possessions", "Cash"
        # We will try to group them or highlight them.

        inventory_keys = ["Assets", "Gear", "Possessions", "Cash", "Equipment", "Weapons"]
        inventory_text = ""

        for key, value in backstory.items():
            if key in inventory_keys:
                inventory_text += f"**{key}:**\n{format_entries(value)}\n\n"

        if inventory_text:
            embed.add_field(name="🎒 Inventory & Assets", value=inventory_text, inline=False)
        else:
            embed.add_field(name="🎒 Inventory & Assets", value="Empty. Use 'Add Item' to start!", inline=False)

        # Other Backstory elements
        for key, value in backstory.items():
            if key in inventory_keys or key == "Pulp Talents": continue
            # Pulp talents handled separately or just skipped if standard mode

            content = format_entries(value)
            # Truncate if too long
            if len(content) > 1000:
                content = content[:1000] + "..."

            embed.add_field(name=key, value=content, inline=False)

        # Pulp Talents if applicable
        if "Pulp Talents" in backstory and self.current_mode == "Pulp of Cthulhu":
            embed.add_field(name="🦸 Pulp Talents", value=format_entries(backstory["Pulp Talents"]), inline=False)

        return embed

    def _get_skill_list(self):
        # Filters out core stats and returns a list of (Name, Value) tuples sorted alphabetically
        ignored = [
            "Residence", "Game Mode", "Archetype", "NAME", "Occupation",
            "Age", "HP", "MP", "SAN", "LUCK", "Build", "Damage Bonus", "Move",
            "STR", "DEX", "INT", "CON", "APP", "POW", "SIZ", "EDU", "Dodge",
            "Backstory"
        ]

        skills = []
        for key, val in self.char_data.items():
            if key in ignored: continue
            if isinstance(val, dict): continue # Skip nested dicts if any
            if isinstance(val, str): continue # Skip string fields that aren't stats

            skills.append((key, val))

        return sorted(skills, key=lambda item: item[0])

    def _get_skill_emoji(self, skill_name):
        custom_emojis = self.char_data.get("Custom Emojis", {})
        if skill_name in custom_emojis:
            return custom_emojis[skill_name]

        if skill_name in stat_emojis:
            return stat_emojis[skill_name]

        # Normalized Match (strip parens and extra spaces)
        normalized_skill = skill_name.replace("(", " ").replace(")", " ").replace("/", " ").strip()
        # Collapse multiple spaces
        normalized_skill = re.sub(r'\s+', ' ', normalized_skill)

        if normalized_skill in stat_emojis:
            return stat_emojis[normalized_skill]

        # Partial Match
        sorted_keys = sorted(stat_emojis.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key.lower() in skill_name.lower():
                return stat_emojis[key]

        return "❓"

    def _calculate_move(self):
        dex = self.char_data.get("DEX", 0)
        siz = self.char_data.get("SIZ", 0)
        str_stat = self.char_data.get("STR", 0)
        age = self.char_data.get("Age", 0)

        if dex == 0 or siz == 0 or str_stat == 0 or age == 0:
            return "N/A"

        if dex < siz and str_stat < siz:
            mov = 7
        elif dex < siz or str_stat < siz:
            mov = 8
        elif dex == siz and str_stat == siz:
            mov = 8
        else:
            mov = 9

        if 40 <= age < 50: mov -= 1
        elif 50 <= age < 60: mov -= 2
        elif 60 <= age < 70: mov -= 3
        elif 70 <= age < 80: mov -= 4
        elif age >= 80: mov -= 5

        return max(0, mov)

    def _calculate_build_db(self):
        str_stat = self.char_data.get("STR", 0)
        siz = self.char_data.get("SIZ", 0)

        if str_stat == 0 or siz == 0:
            return "N/A", "N/A"

        str_siz = str_stat + siz

        if 2 <= str_siz <= 64: return -2, "-2"
        elif 65 <= str_siz <= 84: return -1, "-1"
        elif 85 <= str_siz <= 124: return 0, "0"
        elif 125 <= str_siz <= 164: return 1, "1D4"
        elif 165 <= str_siz <= 204: return 2, "1D6"
        elif 205 <= str_siz <= 284: return 3, "2D6"
        elif 285 <= str_siz <= 364: return 4, "3D6"
        elif 365 <= str_siz <= 444: return 5, "4D6"
        elif 445 <= str_siz <= 524: return 6, "5D6"
        else: return "7+", "6D6+" # Simplified for >524
