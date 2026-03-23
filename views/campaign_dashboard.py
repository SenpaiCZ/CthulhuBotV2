import discord
from discord.ui import View, Button
from models.database import SessionLocal
from services.campaign_service import CampaignService
from services.character_service import CharacterService
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CampaignDashboardView(View):
    def __init__(self, guild_id: str, user_id: str, investigator_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user_id = user_id
        self.investigator_id = investigator_id
        self.current_tab = "Inventory"
        self.investigator = None
        
        # Initial data load
        db = SessionLocal()
        try:
            self.investigator = CharacterService.get_investigator(db, investigator_id)
        except Exception as e:
            logger.error(f"Error loading investigator {investigator_id}: {e}")
        finally:
            db.close()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This is not your campaign dashboard.", ephemeral=True)
            return False
        return True

    def get_embed(self) -> discord.Embed:
        db = SessionLocal()
        try:
            name = self.investigator.name if self.investigator else "Unknown Investigator"
            embed = discord.Embed(
                title=f"Campaign Dashboard: {name}",
                color=discord.Color.dark_red(),
                timestamp=datetime.utcnow()
            )
            
            if self.current_tab == "Inventory":
                self._render_inventory(db, embed)
            elif self.current_tab == "Handouts":
                self._render_handouts(db, embed)
            elif self.current_tab == "Journal":
                self._render_journal(db, embed)
                
            embed.set_footer(text=f"Tab: {self.current_tab} • Investigator ID: {self.investigator_id}")
            return embed
        finally:
            db.close()

    def _render_inventory(self, db, embed):
        items = CampaignService.get_investigator_inventory(db, self.investigator_id)
        embed.description = f"**Inventory for {self.investigator.name if self.investigator else 'Investigator'}**"
        
        if not items:
            embed.add_field(name="Empty", value="No items in inventory.", inline=False)
            return
        
        for item in items:
            macguffin_str = " (⭐ MacGuffin)" if item.is_macguffin else ""
            embed.add_field(
                name=f"{item.name} x{item.quantity}{macguffin_str}",
                value=item.description or "No description provided.",
                inline=False
            )

    def _render_handouts(self, db, embed):
        handouts = CampaignService.get_guild_handouts(db, self.guild_id)
        embed.description = "**Campaign Handouts**"
        
        if not handouts:
            embed.add_field(name="None", value="No handouts discovered yet.", inline=False)
            return
            
        for handout in handouts:
            # Shorten content for preview
            content_preview = handout.content[:100] + ("..." if len(handout.content) > 100 else "")
            embed.add_field(
                name=handout.title,
                value=content_preview or "No content.",
                inline=False
            )

    def _render_journal(self, db, embed):
        # Fetch both Personal entries for this user and Master entries for the guild
        personal_entries = CampaignService.get_journal_entries(db, self.guild_id, "Personal", owner_id=self.user_id)
        master_entries = CampaignService.get_journal_entries(db, self.guild_id, "Master")
        
        all_entries = sorted(personal_entries + master_entries, key=lambda x: x.timestamp, reverse=True)[:10]
        
        embed.description = "**Recent Journal Entries**"
        
        if not all_entries:
            embed.add_field(name="Empty", value="No journal entries found.", inline=False)
            return
            
        for entry in all_entries:
            type_prefix = "📓 [Personal]" if entry.journal_type == "Personal" else "📜 [Master]"
            date_str = entry.timestamp.strftime("%Y-%m-%d %H:%M")
            content_preview = entry.content[:100] + ("..." if len(entry.content) > 100 else "")
            embed.add_field(
                name=f"{type_prefix} {entry.title} ({date_str})",
                value=content_preview or "No content.",
                inline=False
            )

    @discord.ui.button(label="Inventory", style=discord.ButtonStyle.primary)
    async def inventory_tab(self, interaction: discord.Interaction, button: Button):
        self.current_tab = "Inventory"
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Handouts", style=discord.ButtonStyle.primary)
    async def handouts_tab(self, interaction: discord.Interaction, button: Button):
        self.current_tab = "Handouts"
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Journal", style=discord.ButtonStyle.primary)
    async def journal_tab(self, interaction: discord.Interaction, button: Button):
        self.current_tab = "Journal"
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
