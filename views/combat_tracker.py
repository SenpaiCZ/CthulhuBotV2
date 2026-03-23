import discord
from discord.ui import View, Button, Modal, TextInput, Select
from sqlalchemy.orm import Session
from models.database import SessionLocal
from services.combat_service import CombatService
from services.character_service import CharacterService
from models.game_state import CombatSession, CombatParticipant
from models.investigator import Investigator
from emojis import get_health_bar, get_stat_emoji
import logging

logger = logging.getLogger(__name__)

class DamageModal(Modal, title="Apply Damage/Healing"):
    amount = TextInput(label="Amount", placeholder="Positive for damage, negative for healing", min_length=1, max_length=5)
    target_name = TextInput(label="Target Name (Optional)", placeholder="Leave blank for active participant", required=False)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            try:
                dmg_amount = int(self.amount.value)
            except ValueError:
                await interaction.response.send_message("Invalid amount. Please enter a number.", ephemeral=True)
                return

            session = CombatService.get_active_session(db, str(interaction.guild_id), str(interaction.channel_id))
            if not session:
                await interaction.response.send_message("No active combat session found.", ephemeral=True)
                return

            participants = db.query(CombatParticipant).filter(CombatParticipant.session_id == session.id).all()
            target = None
            
            if self.target_name.value:
                # Find by name
                for p in participants:
                    if self.target_name.value.lower() in p.name.lower():
                        target = p
                        break
                if not target:
                    await interaction.response.send_message(f"Could not find participant matching '{self.target_name.value}'", ephemeral=True)
                    return
            else:
                # Use active participant
                if session.current_turn > 0 and session.current_turn <= len(participants):
                    # Need to sort them same way as next_turn to find active
                    sorted_participants = sorted(participants, key=lambda x: (x.initiative, -x.id), reverse=True)
                    target = sorted_participants[session.current_turn - 1]
                else:
                    await interaction.response.send_message("No active participant. Please specify a name or start combat.", ephemeral=True)
                    return

            CombatService.apply_damage(db, target.id, dmg_amount)
            await interaction.response.edit_message(embed=self.view.get_embed(db), view=self.view)
        except Exception as e:
            logger.error(f"Error applying damage: {e}")
            await interaction.response.send_message("An error occurred while applying damage.", ephemeral=True)
        finally:
            db.close()

class CombatTrackerView(View):
    def __init__(self, guild_id: str, channel_id: str):
        super().__init__(timeout=None) # Combat can last a long time
        self.guild_id = guild_id
        self.channel_id = channel_id

    def get_embed(self, db: Session) -> discord.Embed:
        session = CombatService.get_active_session(db, self.guild_id, self.channel_id)
        if not session:
            return discord.Embed(title="Combat Tracker", description="No active combat session.", color=discord.Color.red())

        participants = db.query(CombatParticipant).filter(
            CombatParticipant.session_id == session.id
        ).order_by(CombatParticipant.initiative.desc(), CombatParticipant.id.asc()).all()

        embed = discord.Embed(title="⚔️ Combat Tracker", color=discord.Color.dark_red())
        
        if not participants:
            embed.description = "No participants added to combat."
            return embed

        status_lines = []
        for i, p in enumerate(participants):
            is_active = (session.current_turn == i + 1)
            prefix = "➡️ " if is_active else "   "
            
            # Try to get max HP
            max_hp = 10 # Default
            if p.investigator_id:
                inv = db.query(Investigator).filter(Investigator.id == p.investigator_id).first()
                if inv:
                    derived = CharacterService.calculate_derived_stats({
                        "con": inv.con, "siz": inv.siz
                    })
                    max_hp = derived.get("hp", 10)
            else:
                # If NPC, we don't have max_hp stored, assume current is max if we don't know better
                # or maybe just don't show the bar if we can't determine it accurately.
                # For now, let's assume NPCs have at least current_hp as max if we just started.
                # Actually, let's just use a reasonable default or the current HP if it's the first time.
                max_hp = max(p.current_hp, 10) # Fallback

            hp_bar = get_health_bar(p.current_hp, max_hp)
            line = f"{prefix}**{p.initiative}** | {p.name}: {p.current_hp} HP {hp_bar}"
            if is_active:
                line = f"__**{line}**__"
            status_lines.append(line)

        embed.description = "\n".join(status_lines)
        
        active_p = None
        if 0 < session.current_turn <= len(participants):
            active_p = participants[session.current_turn - 1]
            embed.set_footer(text=f"Active: {active_p.name} • Turn {session.current_turn}")
        else:
            embed.set_footer(text="Combat started. Waiting for first turn.")

        return embed

    @discord.ui.button(label="Next Turn", style=discord.ButtonStyle.green, emoji="⏭️")
    async def next_turn(self, interaction: discord.Interaction, button: Button):
        db = SessionLocal()
        try:
            session = CombatService.get_active_session(db, self.guild_id, self.channel_id)
            if not session:
                await interaction.response.send_message("Combat session ended.", ephemeral=True)
                return
            
            CombatService.next_turn(db, session.id)
            await interaction.response.edit_message(embed=self.get_embed(db), view=self)
        finally:
            db.close()

    @discord.ui.button(label="Damage", style=discord.ButtonStyle.danger, emoji="💥")
    async def damage(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(DamageModal(self))

    @discord.ui.button(label="End Combat", style=discord.ButtonStyle.grey, emoji="⏹️")
    async def end_combat(self, interaction: discord.Interaction, button: Button):
        db = SessionLocal()
        try:
            session = CombatService.get_active_session(db, self.guild_id, self.channel_id)
            if session:
                CombatService.end_combat(db, session.id)
            
            embed = discord.Embed(title="Combat Ended", color=discord.Color.greyple())
            await interaction.response.edit_message(embed=embed, view=None)
        finally:
            db.close()
