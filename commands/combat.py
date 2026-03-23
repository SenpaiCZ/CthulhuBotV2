import discord
from discord.ext import commands
from discord import app_commands
from models.database import SessionLocal
from services.combat_service import CombatService
from views.combat_tracker import CombatTrackerView

class Combat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="combat", description="⚔️ Opens the combat dashboard.")
    async def combat(self, interaction: discord.Interaction):
        """Starts a new combat session and displays the tracker."""
        db = SessionLocal()
        try:
            guild_id = str(interaction.guild_id)
            channel_id = str(interaction.channel_id)
            
            # Start a new combat session (or get existing active one)
            session = CombatService.get_active_session(db, guild_id, channel_id)
            if not session:
                session = CombatService.start_combat(db, guild_id, channel_id)
            
            view = CombatTrackerView(guild_id, channel_id)
            embed = view.get_embed(db)
            
            await interaction.response.send_message(embed=embed, view=view)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(Combat(bot))
