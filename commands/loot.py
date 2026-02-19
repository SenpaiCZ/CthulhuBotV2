import discord
import random
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from loadnsave import load_loot_settings, load_player_stats, save_player_stats, load_weapons_data

class CapacityModal(discord.ui.Modal):
    def __init__(self, item_name, server_id, user_id, button_ref, view_ref, default_cap_str=""):
        super().__init__(title=f"Setup {item_name}"[:45])
        self.item_name = item_name
        self.server_id = server_id
        self.user_id = user_id
        self.button = button_ref
        self.view = view_ref

        self.capacity = discord.ui.TextInput(
            label="Ammo Capacity",
            placeholder=f"e.g. 30 (Default: {default_cap_str})",
            default=str(default_cap_str) if str(default_cap_str).isdigit() else "",
            required=True,
            max_length=10
        )
        self.add_item(self.capacity)

    async def on_submit(self, interaction: discord.Interaction):
        # 1. Validate Input
        cap_val = self.capacity.value.strip()
        if not cap_val.isdigit():
             await interaction.response.send_message("Please enter a valid number for capacity.", ephemeral=True)
             return

        # 2. Add Item to Inventory
        player_stats = await load_player_stats()
        if self.server_id not in player_stats: player_stats[self.server_id] = {}

        # Check user again (though button checked it)
        if str(interaction.user.id) != str(self.user_id) and self.user_id:
             await interaction.response.send_message("This loot is not for you!", ephemeral=True)
             return

        if str(interaction.user.id) not in player_stats[self.server_id]:
             await interaction.response.send_message("You don't have an investigator.", ephemeral=True)
             return

        user_stats = player_stats[self.server_id][str(interaction.user.id)]
        if "Backstory" not in user_stats: user_stats["Backstory"] = {}
        if "Gear and Possessions" not in user_stats["Backstory"]:
            user_stats["Backstory"]["Gear and Possessions"] = []

        # Format: Name [Cap/Cap]
        full_name = f"{self.item_name} [{cap_val}/{cap_val}]"
        user_stats["Backstory"]["Gear and Possessions"].append(full_name)

        await save_player_stats(player_stats)

        # 3. Update Button in Original View
        self.button.disabled = True
        self.button.label = f"Taken: {self.item_name}"[:80]
        self.button.style = discord.ButtonStyle.success

        # Update the message
        try:
            await self.view.message.edit(view=self.view)
        except Exception as e:
            # Message might be deleted or interaction expired
            pass

        await interaction.response.send_message(f"✅ Added **{full_name}** to your inventory.", ephemeral=True)


class LootItemButton(discord.ui.Button):
    def __init__(self, item_name, server_id, user_id=None):
        super().__init__(label=f"Take: {item_name}"[:80], style=discord.ButtonStyle.secondary, emoji="📥")
        self.item_name = item_name
        self.server_id = str(server_id)
        self.user_id = str(user_id) if user_id else None

    async def callback(self, interaction: discord.Interaction):
        # Verify user
        if self.user_id and str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This loot is not for you!", ephemeral=True)
            return

        # Load Weapons DB to check if it needs capacity
        weapon_db = await load_weapons_data()

        # Check if item is a weapon
        # Simple check: exact match or contained
        # The item_name from loot might match a key in weapon_db
        is_weapon = False
        w_data = {}

        if self.item_name in weapon_db:
            is_weapon = True
            w_data = weapon_db[self.item_name]

        if is_weapon:
            cap_str = str(w_data.get("capacity", "0"))
            # Check if complex (contains / or or) or user prompt required
            # If it's a simple number like "6", we can just assume 6/6
            # If it's "20/30", we ask.
            needs_modal = False
            if "/" in cap_str or "or" in cap_str or not cap_str.isdigit():
                needs_modal = True

            # Allow always setting capacity if desired?
            # The prompt implies "if its not just number, ask user".

            if needs_modal:
                modal = CapacityModal(self.item_name, self.server_id, self.user_id, self, self.view, cap_str)
                await interaction.response.send_modal(modal)
                return

        # Standard Add Logic (No Modal or Simple Weapon)
        player_stats = await load_player_stats()

        if self.server_id not in player_stats:
            player_stats[self.server_id] = {}

        current_user_id = str(interaction.user.id)
        if current_user_id not in player_stats[self.server_id]:
             await interaction.response.send_message("You don't have an investigator to give this to. Use `/newinvestigator` first.", ephemeral=True)
             return

        user_stats = player_stats[self.server_id][current_user_id]

        if "Backstory" not in user_stats:
            user_stats["Backstory"] = {}

        if "Gear and Possessions" not in user_stats["Backstory"]:
            user_stats["Backstory"]["Gear and Possessions"] = []

        # Add Item
        item_to_add = self.item_name

        # If it was a simple weapon, format it as [Cap/Cap] automatically
        if is_weapon:
            cap_str = str(w_data.get("capacity", "0"))
            if cap_str.isdigit():
                item_to_add = f"{self.item_name} [{cap_str}/{cap_str}]"
            # If it was complex but we skipped modal (logic error?), ensure we don't break.
            # But logic above handles complex cases.

        user_stats["Backstory"]["Gear and Possessions"].append(item_to_add)
        await save_player_stats(player_stats)

        # Disable button
        self.disabled = True
        self.label = f"Taken: {self.item_name}"[:80]
        self.style = discord.ButtonStyle.success

        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"✅ Added **{item_to_add}** to your inventory.", ephemeral=True)

class LootMoneyButton(discord.ui.Button):
    def __init__(self, amount_str, server_id, user_id):
        super().__init__(label=f"Take Money ({amount_str})", style=discord.ButtonStyle.success, emoji="💰")
        self.amount_str = amount_str
        self.server_id = str(server_id)
        self.user_id = str(user_id)

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This loot is not for you!", ephemeral=True)
            return

        player_stats = await load_player_stats()
        if self.server_id not in player_stats or self.user_id not in player_stats[self.server_id]:
             await interaction.response.send_message("You don't have an investigator.", ephemeral=True)
             return

        user_stats = player_stats[self.server_id][self.user_id]
        if "Backstory" not in user_stats: user_stats["Backstory"] = {}
        if "Cash" not in user_stats["Backstory"]: user_stats["Backstory"]["Cash"] = []

        user_stats["Backstory"]["Cash"].append(self.amount_str)
        await save_player_stats(player_stats)

        self.disabled = True
        self.label = f"Taken: {self.amount_str}"
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"✅ Added **{self.amount_str}** to your cash.", ephemeral=True)

class TakeAllButton(discord.ui.Button):
    def __init__(self, server_id, user_id):
        super().__init__(label="Take All", style=discord.ButtonStyle.primary, emoji="🎒", row=0)
        self.server_id = str(server_id)
        self.user_id = str(user_id)

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This loot is not for you!", ephemeral=True)

        # Collect items to add
        items_to_add = []
        money_to_add = None

        # Load Weapons DB for auto-formatting simple weapons
        weapon_db = await load_weapons_data()

        # Iterate through view children to find untaken loot
        # WARNING: Take All will skip Modals for complex weapons and just add them as-is?
        # Or should it trigger modals? Triggering multiple modals is impossible.
        # Decision: "Take All" adds items raw, or tries to apply defaults.
        # If capacity is complex, it just adds the name. User can edit later.
        # Or better: "Take All" formats simple ones, leaves complex ones raw.

        for child in self.view.children:
            if child.disabled:
                continue

            if isinstance(child, LootItemButton):
                # Logic to format name
                final_name = child.item_name
                if child.item_name in weapon_db:
                    cap_str = str(weapon_db[child.item_name].get("capacity", "0"))
                    if cap_str.isdigit():
                        final_name = f"{child.item_name} [{cap_str}/{cap_str}]"
                    # Complex ones added raw

                items_to_add.append(final_name)
                # Mark as taken for UI update
                child.disabled = True
                child.style = discord.ButtonStyle.success
                child.label = f"Taken: {child.item_name}"[:80]

            elif isinstance(child, LootMoneyButton):
                money_to_add = child.amount_str
                # Mark as taken
                child.disabled = True
                child.style = discord.ButtonStyle.success
                child.label = f"Taken: {child.amount_str}"

        if not items_to_add and not money_to_add:
             return await interaction.response.send_message("Everything has already been taken!", ephemeral=True)

        player_stats = await load_player_stats()
        if self.server_id not in player_stats or self.user_id not in player_stats[self.server_id]:
             return await interaction.response.send_message("You don't have an investigator.", ephemeral=True)

        user_stats = player_stats[self.server_id][self.user_id]
        if "Backstory" not in user_stats: user_stats["Backstory"] = {}

        # Add Items
        if items_to_add:
            if "Gear and Possessions" not in user_stats["Backstory"]:
                user_stats["Backstory"]["Gear and Possessions"] = []
            for item in items_to_add:
                user_stats["Backstory"]["Gear and Possessions"].append(item)

        # Add Money
        if money_to_add:
            if "Cash" not in user_stats["Backstory"]: user_stats["Backstory"]["Cash"] = []
            user_stats["Backstory"]["Cash"].append(money_to_add)

        await save_player_stats(player_stats)

        # Update TakeAllButton itself
        self.disabled = True
        self.label = "All Taken"
        self.style = discord.ButtonStyle.success

        await interaction.response.edit_message(view=self.view)

        msg_parts = []
        if items_to_add: msg_parts.append(f"{len(items_to_add)} items")
        if money_to_add: msg_parts.append(f"{money_to_add}")
        msg = f"✅ Taken {' and '.join(msg_parts)}."

        await interaction.followup.send(msg, ephemeral=True)

class LootView(discord.ui.View):
    def __init__(self, items, money_str, server_id, user_id):
        super().__init__(timeout=180)
        self.items = items
        self.money_str = money_str
        self.server_id = str(server_id)
        self.user_id = str(user_id)
        self.message = None

        # Add Take All Button
        self.add_item(TakeAllButton(server_id, user_id))

        # Add Money Button if exists
        if money_str:
            self.add_item(LootMoneyButton(money_str, server_id, user_id))

        # Add Item Buttons
        for item in items:
            self.add_item(LootItemButton(item, server_id, user_id))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass

class LootCustomView(discord.ui.View):
    def __init__(self, items, server_id):
        super().__init__(timeout=None)
        self.items = items
        self.server_id = str(server_id)
        # Fix: passing None as user_id to allow anyone to take custom loot?
        # Or assume creator? The original code had user_id=None for CustomView buttons.
        for item in items:
            self.add_item(LootItemButton(item, server_id, user_id=None))

class LootCustomModal(discord.ui.Modal, title="Create Custom Loot"):
    items = discord.ui.TextInput(
        label="Items (one per line)",
        style=discord.TextStyle.paragraph,
        placeholder="A Mysterious Sword\nHealing Potion\nOld Map",
        required=True,
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Parse items
        items_text = self.items.value
        items = [line.strip() for line in items_text.split('\n') if line.strip()]

        if not items:
            await interaction.response.send_message("You must provide at least one item.", ephemeral=True)
            return

        # Create View
        view = LootCustomView(items, interaction.guild.id)

        # Create Embed
        embed = discord.Embed(title="Custom Loot Available", color=discord.Color.gold())
        embed.description = "Items available for taking:"

        for item in items:
            embed.add_field(name=f"📦 {item}", value="\u200b", inline=False)

        await interaction.response.send_message(embed=embed, view=view)

class loot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    loot_group = app_commands.Group(name="loot", description="Loot related commands")

    @loot_group.command(name="random", description="Generate random loot from the 1920s.")
    async def loot_random(self, interaction: discord.Interaction):
        """
        Generate random loot from 1920s.
        """
        await interaction.response.defer() # Thinking...

        settings = await load_loot_settings()

        items_pool = settings.get("items", [])
        if not items_pool:
            items_pool = ["Nothing found."]

        money_chance = settings.get("money_chance", 25)
        money_min = settings.get("money_min", 0.01)
        money_max = settings.get("money_max", 5.00)
        currency_symbol = settings.get("currency_symbol", "$")
        min_items = settings.get("num_items_min", 1)
        max_items = settings.get("num_items_max", 5)

        if max_items < min_items: max_items = min_items

        # Money
        has_money = random.randint(1, 100) <= money_chance
        money_str = None
        if has_money:
            money_val = random.uniform(money_min, money_max)
            money_str = f"{currency_symbol}{money_val:.2f}"

        # Items
        available_count = len(items_pool)
        actual_max = min(max_items, available_count)
        actual_min = min(min_items, actual_max)

        chosen_items = []
        if available_count > 0:
            num_items = random.randint(actual_min, actual_max)
            chosen_items = random.sample(items_pool, num_items)

        # Embed
        embed = discord.Embed(title="Random Loot Found", color=discord.Color.blue())
        # embed.set_thumbnail(url="https://i.imgur.com/8p5T0lC.png")

        desc = "You search the area and find..."
        embed.description = desc

        for item in chosen_items:
            embed.add_field(name=f"📦 {item}", value="\u200b", inline=False)

        if money_str:
            embed.add_field(name=f"💰 Money", value=f"**{money_str}**", inline=False)

        if not chosen_items and not money_str:
            embed.description = "You search thoroughly, but find nothing of value."
            await interaction.followup.send(embed=embed)
            return

        view = LootView(chosen_items, money_str, interaction.guild.id, interaction.user.id)
        msg = await interaction.followup.send(embed=embed, view=view)
        view.message = msg

    @loot_group.command(name="custom", description="Create custom loot distribution.")
    async def loot_custom(self, interaction: discord.Interaction):
        """
        Create a custom loot drop via a modal.
        """
        await interaction.response.send_modal(LootCustomModal())

async def setup(bot):
    await bot.add_cog(loot(bot))
