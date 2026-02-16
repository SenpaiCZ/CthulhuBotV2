import discord
import random
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from loadnsave import load_loot_settings, load_player_stats, save_player_stats

class LootItemButton(discord.ui.Button):
    def __init__(self, item_name, server_id, user_id):
        super().__init__(label=f"Take: {item_name}"[:80], style=discord.ButtonStyle.secondary, emoji="📥")
        self.item_name = item_name
        self.server_id = str(server_id)
        self.user_id = str(user_id)

    async def callback(self, interaction: discord.Interaction):
        # Verify user
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This loot is not for you!", ephemeral=True)
            return

        # Load Stats
        player_stats = await load_player_stats()

        if self.server_id not in player_stats:
            player_stats[self.server_id] = {}

        if self.user_id not in player_stats[self.server_id]:
             # Create basic structure if missing (though usually user should have character)
             # But let's fail gracefully if no character
             await interaction.response.send_message("You don't have an investigator to give this to. Use `/newinvestigator` first.", ephemeral=True)
             return

        user_stats = player_stats[self.server_id][self.user_id]

        if "Backstory" not in user_stats:
            user_stats["Backstory"] = {}

        if "Gear and Possessions" not in user_stats["Backstory"]:
            user_stats["Backstory"]["Gear and Possessions"] = []

        # Add Item
        user_stats["Backstory"]["Gear and Possessions"].append(self.item_name)
        await save_player_stats(player_stats)

        # Disable button
        self.disabled = True
        self.label = f"Taken: {self.item_name}"[:80]
        self.style = discord.ButtonStyle.success

        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"✅ Added **{self.item_name}** to your inventory.", ephemeral=True)

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

        # Iterate through view children to find untaken loot
        for child in self.view.children:
            if child.disabled:
                continue

            if isinstance(child, LootItemButton):
                items_to_add.append(child.item_name)
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

class loot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="loot", description="Generate random loot from the 1920s.")
    async def loot(self, interaction: discord.Interaction):
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

async def setup(bot):
    await bot.add_cog(loot(bot))
