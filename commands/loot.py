import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from models.database import SessionLocal
from services.campaign_service import CampaignService
from services.character_service import CharacterService
from schemas.campaign import InventoryItemCreate

class LootView(View):
    def __init__(self, items, money_str, guild_id, user_id=None):
        super().__init__(timeout=180)
        self.items = items
        self.money_str = money_str
        self.guild_id = guild_id
        self.user_id = user_id
        self._add_buttons()

    def _add_buttons(self):
        if self.money_str:
            btn = Button(label=f"Take {self.money_str}", style=discord.ButtonStyle.success, emoji="💰")
            btn.callback = self.take_money
            self.add_item(btn)
        
        for item in self.items:
            btn = Button(label=f"Take {item[:30]}", style=discord.ButtonStyle.secondary)
            btn.callback = self._make_take_callback(item)
            self.add_item(btn)

    def _make_take_callback(self, item_name):
        async def callback(interaction: discord.Interaction):
            await self.take_item(interaction, item_name)
        return callback

    async def take_item(self, interaction: discord.Interaction, item_name):
        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild_id), str(interaction.user.id))
            if not inv: return await interaction.response.send_message("❌ No active investigator.", ephemeral=True)
            
            CampaignService.add_inventory_item(db, InventoryItemCreate(investigator_id=inv.id, name=item_name))
            await interaction.response.send_message(f"✅ Added **{item_name}** to your inventory.", ephemeral=True)
        finally: db.close()

    async def take_money(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild_id), str(interaction.user.id))
            if not inv: return await interaction.response.send_message("❌ No active investigator.", ephemeral=True)
            
            CampaignService.add_inventory_item(db, InventoryItemCreate(investigator_id=inv.id, name=f"Cash: {self.money_str}"))
            await interaction.response.send_message(f"✅ Added **{self.money_str}** to your inventory.", ephemeral=True)
        finally: db.close()

class loot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    loot_group = app_commands.Group(name="loot", description="💰 Loot related commands")

    @loot_group.command(name="random", description="🎲 Generate random loot.")
    async def loot_random(self, interaction: discord.Interaction):
        await interaction.response.defer()
        items, money, desc = await CampaignService.generate_random_loot()
        embed = discord.Embed(title="Loot Found", description=desc, color=discord.Color.blue())
        if money: embed.add_field(name="Money", value=money)
        for item in items: embed.add_field(name="Item", value=item, inline=False)
        
        view = LootView(items, money, str(interaction.guild_id), str(interaction.user.id))
        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(loot(bot))
