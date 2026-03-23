import discord
import random
from discord import app_commands
from discord.ext import commands
from loadnsave import load_macguffin_data
from models.database import SessionLocal
from services.campaign_service import CampaignService
from services.character_service import CharacterService
from schemas.campaign import InventoryItemCreate

class MacGuffin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="macguffin", description="🔮 Discover or lookup a MacGuffin.")
    @app_commands.describe(name="Specific MacGuffin to lookup")
    async def macguffin(self, interaction: discord.Interaction, name: str = None):
        data = await load_macguffin_data()
        if not name:
            name = random.choice(list(data.keys()))
        
        description = data.get(name, "No description found.")
        embed = discord.Embed(title=f"🔮 MacGuffin: {name}", description=description, color=discord.Color.purple())
        
        view = discord.ui.View()
        take_btn = discord.ui.Button(label="Take MacGuffin", style=discord.ButtonStyle.success)
        
        async def take_callback(inter):
            db = SessionLocal()
            try:
                inv = CharacterService.get_investigator_by_guild_and_user(db, str(inter.guild_id), str(inter.user.id))
                if not inv: return await inter.response.send_message("❌ No active investigator.", ephemeral=True)
                CampaignService.add_inventory_item(db, InventoryItemCreate(investigator_id=inv.id, name=name, description=description, is_macguffin=True))
                await inter.response.send_message(f"✅ Added **{name}** as a MacGuffin to your inventory.", ephemeral=True)
            finally: db.close()

        take_btn.callback = take_callback
        view.add_item(take_btn)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(MacGuffin(bot))
