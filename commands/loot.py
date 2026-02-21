import discord
import random
import re
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from loadnsave import load_loot_settings, load_player_stats, save_player_stats, load_weapons_data
from emojis import get_emoji_for_item

async def generate_random_loot():
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

    # Description
    flavor_texts = [
        "You pry open the dusty crate...",
        "You search the body...",
        "Hidden under the floorboards, you find...",
        "Inside the forgotten cabinet...",
        "Scattered on the table...",
        "In the pockets of the coat...",
        "Tucked away in a secret compartment..."
    ]
    desc = random.choice(flavor_texts)

    if not chosen_items and not money_str:
        desc = "You search thoroughly, but find nothing of value."

    return chosen_items, money_str, desc

class CapacityModal(Modal):
    def __init__(self, item_name, server_id, user_id, button_ref, view_ref, default_cap_str=""):
        super().__init__(title=f"Setup {item_name}"[:45])
        self.item_name = item_name
        self.server_id = server_id
        self.user_id = user_id
        self.button = button_ref
        self.view = view_ref

        self.capacity = TextInput(
            label="Ammo Capacity / Quantity",
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
             await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
             return

        # 2. Add Item to Inventory
        player_stats = await load_player_stats()
        if self.server_id not in player_stats: player_stats[self.server_id] = {}

        # Check user presence
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
            if hasattr(self.view, 'message') and self.view.message:
                 await self.view.message.edit(view=self.view)
        except Exception as e:
            pass

        await interaction.response.send_message(f"✅ Added **{full_name}** to your inventory.", ephemeral=True)


class LootItemButton(Button):
    def __init__(self, item_name, server_id, user_id=None):
        emoji = get_emoji_for_item(item_name)
        super().__init__(label=f"Take: {item_name}"[:80], style=discord.ButtonStyle.secondary, emoji=emoji)
        self.item_name = item_name
        self.server_id = str(server_id)
        # If user_id is provided, only that user can take. If None, anyone can.
        self.allowed_user_id = str(user_id) if user_id else None

    async def callback(self, interaction: discord.Interaction):
        if self.allowed_user_id and str(interaction.user.id) != self.allowed_user_id:
            await interaction.response.send_message("This loot stash belongs to someone else.", ephemeral=True)
            return

        weapon_db = await load_weapons_data()

        is_weapon = False
        w_data = {}

        if self.item_name in weapon_db:
            is_weapon = True
            w_data = weapon_db[self.item_name]

        if is_weapon:
            cap_str = str(w_data.get("capacity", "0"))
            needs_modal = False
            if "/" in cap_str or "or" in cap_str or not cap_str.isdigit():
                needs_modal = True

            if needs_modal:
                modal = CapacityModal(self.item_name, self.server_id, self.allowed_user_id, self, self.view, cap_str)
                await interaction.response.send_modal(modal)
                return

        player_stats = await load_player_stats()
        if self.server_id not in player_stats: player_stats[self.server_id] = {}

        if str(interaction.user.id) not in player_stats[self.server_id]:
             await interaction.response.send_message("You don't have an investigator. Use `/newinvestigator`.", ephemeral=True)
             return

        user_stats = player_stats[self.server_id][str(interaction.user.id)]
        if "Backstory" not in user_stats: user_stats["Backstory"] = {}
        if "Gear and Possessions" not in user_stats["Backstory"]:
            user_stats["Backstory"]["Gear and Possessions"] = []

        item_to_add = self.item_name
        if is_weapon:
            cap_str = str(w_data.get("capacity", "0"))
            if cap_str.isdigit():
                item_to_add = f"{self.item_name} [{cap_str}/{cap_str}]"

        user_stats["Backstory"]["Gear and Possessions"].append(item_to_add)
        await save_player_stats(player_stats)

        self.disabled = True
        self.label = f"Taken: {self.item_name}"[:80]
        self.style = discord.ButtonStyle.success

        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"✅ Added **{item_to_add}** to your inventory.", ephemeral=True)


class LootMoneyButton(Button):
    def __init__(self, amount_str, server_id, user_id):
        super().__init__(label=f"Take Money ({amount_str})", style=discord.ButtonStyle.success, emoji="💰", row=0)
        self.amount_str = amount_str
        self.server_id = str(server_id)
        self.allowed_user_id = str(user_id) if user_id else None

    async def callback(self, interaction: discord.Interaction):
        if self.allowed_user_id and str(interaction.user.id) != self.allowed_user_id:
            await interaction.response.send_message("This loot stash belongs to someone else.", ephemeral=True)
            return

        player_stats = await load_player_stats()
        if self.server_id not in player_stats: player_stats[self.server_id] = {}

        if str(interaction.user.id) not in player_stats[self.server_id]:
             await interaction.response.send_message("You don't have an investigator.", ephemeral=True)
             return

        user_stats = player_stats[self.server_id][str(interaction.user.id)]
        if "Backstory" not in user_stats: user_stats["Backstory"] = {}
        if "Cash" not in user_stats["Backstory"]: user_stats["Backstory"]["Cash"] = []

        user_stats["Backstory"]["Cash"].append(self.amount_str)
        await save_player_stats(player_stats)

        self.disabled = True
        self.label = f"Taken: {self.amount_str}"
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"✅ Added **{self.amount_str}** to your cash.", ephemeral=True)


class TakeAllButton(Button):
    def __init__(self, server_id, user_id):
        super().__init__(label="Take All", style=discord.ButtonStyle.primary, emoji="🎒", row=0)
        self.server_id = str(server_id)
        self.allowed_user_id = str(user_id) if user_id else None

    async def callback(self, interaction: discord.Interaction):
        if self.allowed_user_id and str(interaction.user.id) != self.allowed_user_id:
            return await interaction.response.send_message("This loot stash belongs to someone else.", ephemeral=True)

        items_to_add = []
        money_to_add = None

        weapon_db = await load_weapons_data()

        for child in self.view.children:
            if child.disabled or child is self:
                continue

            if isinstance(child, LootItemButton):
                final_name = child.item_name
                if child.item_name in weapon_db:
                    cap_str = str(weapon_db[child.item_name].get("capacity", "0"))
                    if cap_str.isdigit():
                        final_name = f"{child.item_name} [{cap_str}/{cap_str}]"

                items_to_add.append(final_name)
                child.disabled = True
                child.style = discord.ButtonStyle.success
                child.label = f"Taken: {child.item_name}"[:80]

            elif isinstance(child, LootMoneyButton):
                money_to_add = child.amount_str
                child.disabled = True
                child.style = discord.ButtonStyle.success
                child.label = f"Taken: {child.amount_str}"

        if not items_to_add and not money_to_add:
             return await interaction.response.send_message("Everything has already been taken!", ephemeral=True)

        player_stats = await load_player_stats()
        if self.server_id not in player_stats: player_stats[self.server_id] = {}

        if str(interaction.user.id) not in player_stats[self.server_id]:
             return await interaction.response.send_message("You don't have an investigator.", ephemeral=True)

        user_stats = player_stats[self.server_id][str(interaction.user.id)]
        if "Backstory" not in user_stats: user_stats["Backstory"] = {}

        if items_to_add:
            if "Gear and Possessions" not in user_stats["Backstory"]:
                user_stats["Backstory"]["Gear and Possessions"] = []
            user_stats["Backstory"]["Gear and Possessions"].extend(items_to_add)

        if money_to_add:
            if "Cash" not in user_stats["Backstory"]: user_stats["Backstory"]["Cash"] = []
            user_stats["Backstory"]["Cash"].append(money_to_add)

        await save_player_stats(player_stats)

        self.disabled = True
        self.label = "All Taken"
        self.style = discord.ButtonStyle.success

        await interaction.response.edit_message(view=self.view)

        summary = []
        if items_to_add: summary.append(f"{len(items_to_add)} items")
        if money_to_add: summary.append(f"{money_to_add}")

        await interaction.followup.send(f"✅ Taken {' and '.join(summary)}.", ephemeral=True)


class RerollButton(Button):
    def __init__(self, user_id):
        super().__init__(label="Reroll", style=discord.ButtonStyle.secondary, emoji="🎲", row=0)
        self.allowed_user_id = str(user_id)

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.allowed_user_id:
            return await interaction.response.send_message("Only the person who found this loot can reroll it.", ephemeral=True)

        await interaction.response.defer()
        await self.view.reroll(interaction)


class LootView(View):
    def __init__(self, items, money_str, server_id, user_id, rerollable=False):
        super().__init__(timeout=180)
        self.items = items
        self.money_str = money_str
        self.server_id = str(server_id)
        self.user_id = str(user_id) if user_id else None
        self.rerollable = rerollable
        self.message = None

        self.update_components()

    def update_components(self):
        self.clear_items()

        self.add_item(TakeAllButton(self.server_id, self.user_id))

        if self.rerollable and self.user_id:
            self.add_item(RerollButton(self.user_id))

        if self.money_str:
            self.add_item(LootMoneyButton(self.money_str, self.server_id, self.user_id))

        for item in self.items:
            self.add_item(LootItemButton(item, self.server_id, self.user_id))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass

    async def reroll(self, interaction: discord.Interaction):
        new_items, new_money, new_desc = await generate_random_loot()

        self.items = new_items
        self.money_str = new_money

        embed = discord.Embed(title="Random Loot Found", description=new_desc, color=discord.Color.blue())
        for item in self.items:
            embed.add_field(name=f"{get_emoji_for_item(item)} {item}", value="\u200b", inline=False)
        if self.money_str:
            embed.add_field(name="💰 Money", value=f"**{self.money_str}**", inline=False)

        self.update_components()

        await interaction.edit_original_response(embed=embed, view=self)


class LootCustomModal(Modal, title="Create Custom Loot"):
    items = TextInput(
        label="Items (one per line)",
        style=discord.TextStyle.paragraph,
        placeholder="A Mysterious Sword\nHealing Potion\nOld Map",
        required=True,
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        items_text = self.items.value
        items = [line.strip() for line in items_text.split('\n') if line.strip()]

        if not items:
            await interaction.response.send_message("You must provide at least one item.", ephemeral=True)
            return

        view = LootView(items, None, interaction.guild.id, None, rerollable=False)

        embed = discord.Embed(title="Custom Loot Available", color=discord.Color.gold())
        embed.description = "Items available for taking:"

        for item in items:
            embed.add_field(name=f"{get_emoji_for_item(item)} {item}", value="\u200b", inline=False)

        await interaction.response.send_message(embed=embed, view=view)

        msg = await interaction.original_response()
        view.message = msg


class loot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    loot_group = app_commands.Group(name="loot", description="Loot related commands")

    @loot_group.command(name="random", description="Generate random loot from the 1920s.")
    async def loot_random(self, interaction: discord.Interaction):
        """
        Generate random loot from 1920s.
        """
        await interaction.response.defer()

        items, money_str, desc = await generate_random_loot()

        embed = discord.Embed(title="Random Loot Found", description=desc, color=discord.Color.blue())

        for item in items:
            embed.add_field(name=f"{get_emoji_for_item(item)} {item}", value="\u200b", inline=False)

        if money_str:
            embed.add_field(name=f"💰 Money", value=f"**{money_str}**", inline=False)

        if not items and not money_str:
             await interaction.followup.send(embed=embed)
             return

        view = LootView(items, money_str, interaction.guild.id, interaction.user.id, rerollable=True)
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
