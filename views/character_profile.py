import discord
from discord.ui import View, Button, Modal, TextInput
from sqlalchemy.orm import Session
from models.database import SessionLocal
from services.character_service import CharacterService
from services.settings_service import SettingsService
from emojis import get_stat_emoji, get_health_bar
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class RenameModal(Modal, title="Rename Investigator"):
    name_input = TextInput(label="New Name", placeholder="Enter new name...", min_length=1, max_length=100)

    def __init__(self, view, current_name):
        super().__init__()
        self.view = view
        self.name_input.default = current_name

    async def on_submit(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            CharacterService.rename_investigator(db, self.view.investigator_id, self.name_input.value)
            self.view.investigator = CharacterService.get_investigator(db, self.view.investigator_id)
            await interaction.response.edit_message(embed=self.view.get_embed(), view=self.view)
        finally:
            db.close()

class BackstoryModal(Modal, title="Edit Backstory"):
    category_input = TextInput(label="Category", placeholder="e.g. Personal Description, Ideology/Beliefs...", min_length=1, max_length=100)
    entry_input = TextInput(label="Entry", placeholder="Enter backstory details...", style=discord.TextStyle.paragraph, min_length=1, max_length=1000)

    def __init__(self, view, category=None, entry=None):
        super().__init__()
        self.view = view
        if category:
            self.category_input.default = category
            # self.category_input.disabled = True # Modal TextInput doesn't have disabled
        if entry:
            self.entry_input.default = entry

    async def on_submit(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            CharacterService.manage_backstory(db, self.view.investigator_id, self.category_input.value, self.entry_input.value, "add")
            self.view.investigator = CharacterService.get_investigator(db, self.view.investigator_id)
            await interaction.response.edit_message(embed=self.view.get_embed(), view=self.view)
        finally:
            db.close()

class CharacterProfileView(View):
    def __init__(self, investigator_id: int, user: discord.User):
        super().__init__(timeout=180)
        self.investigator_id = investigator_id
        self.user = user
        self.current_tab = "Stats"
        self.investigator = None
        
        # Initial data load
        db = SessionLocal()
        try:
            self.investigator = CharacterService.get_investigator(db, investigator_id)
            # Add Print Sheet button as a link
            dashboard_url = SettingsService.get_setting(db, "global", "dashboard_url", "http://localhost:5000")
            print_url = f"{dashboard_url}/render/character/{self.investigator.guild_id}/{self.investigator.discord_user_id}"
            self.add_item(Button(label="Print Sheet", style=discord.ButtonStyle.link, url=print_url, emoji="🖨️"))
        finally:
            db.close()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your profile view.", ephemeral=True)
            return False
        return True

    def get_embed(self) -> discord.Embed:
        inv = self.investigator
        embed = discord.Embed(title=f"Character Profile: {inv.name}", color=discord.Color.blue())
        embed.set_author(name=inv.occupation or "Unknown Occupation")
        
        if self.current_tab == "Stats":
            self._render_stats(embed)
        elif self.current_tab == "Skills":
            self._render_skills(embed)
        elif self.current_tab == "Backstory":
            self._render_backstory(embed)
            
        last_played_str = inv.last_played.strftime('%Y-%m-%d') if inv.last_played else "Never"
        embed.set_footer(text=f"ID: {inv.id} • Last Played: {last_played_str}")
        return embed

    def _render_stats(self, embed):
        inv = self.investigator
        stats_text = (
            f"{get_stat_emoji('STR')} **STR**: {inv.str}  "
            f"{get_stat_emoji('DEX')} **DEX**: {inv.dex}  "
            f"{get_stat_emoji('CON')} **CON**: {inv.con}\n"
            f"{get_stat_emoji('SIZ')} **SIZ**: {inv.siz}  "
            f"{get_stat_emoji('APP')} **APP**: {inv.app}  "
            f"{get_stat_emoji('INT')} **INT**: {inv.int}\n"
            f"{get_stat_emoji('POW')} **POW**: {inv.pow}  "
            f"{get_stat_emoji('EDU')} **EDU**: {inv.edu}  "
            f"{get_stat_emoji('LUCK')} **LUCK**: {inv.luck}"
        )
        embed.add_field(name="Characteristics", value=stats_text, inline=False)
        
        derived = CharacterService.calculate_derived_stats({
            "str": inv.str, "con": inv.con, "siz": inv.siz, "dex": inv.dex, "pow": inv.pow, "app": inv.app
        })
        
        # Check for current values in skills
        skills = inv.skills or {}
        curr_hp = skills.get("HP", derived["hp"])
        curr_mp = skills.get("MP", derived["mp"])
        curr_san = skills.get("SAN", derived["san"])
        
        derived_text = (
            f"{get_stat_emoji('HP')} **HP**: {curr_hp}/{derived['hp']} {get_health_bar(curr_hp, derived['hp'])}\n"
            f"{get_stat_emoji('MP')} **MP**: {curr_mp}/{derived['mp']} {get_health_bar(curr_mp, derived['mp'])}\n"
            f"{get_stat_emoji('SAN')} **SAN**: {curr_san}/99 {get_health_bar(curr_san, 99)}\n"
            f"**DB**: {derived['damage_bonus']}  **Build**: {derived['build']}  **Move**: {derived['move']}"
        )
        embed.add_field(name="Derived Stats", value=derived_text, inline=False)

    def _render_skills(self, embed):
        inv = self.investigator
        if not inv.skills:
            embed.description = "No skills assigned."
            return
            
        sorted_skills = sorted(inv.skills.items())
        skill_lines = []
        for name, val in sorted_skills:
            emoji_str = get_stat_emoji(name)
            skill_lines.append(f"{emoji_str} **{name}**: {val}%")
            
        chunk_size = 15
        for i in range(0, len(skill_lines), chunk_size):
            chunk = skill_lines[i:i + chunk_size]
            embed.add_field(name="Skills" if i == 0 else "Skills (cont.)", value="\n".join(chunk), inline=True)

    def _render_backstory(self, embed):
        inv = self.investigator
        if not inv.backstory:
            embed.description = "No backstory entries."
            return
            
        for category, entries in inv.backstory.items():
            if isinstance(entries, list):
                val = "\n".join([f"• {e}" for e in entries])
            else:
                val = str(entries)
            embed.add_field(name=category, value=val or "None", inline=False)

    @discord.ui.button(label="Stats", style=discord.ButtonStyle.primary)
    async def stats_tab(self, interaction: discord.Interaction, button: Button):
        self.current_tab = "Stats"
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Skills", style=discord.ButtonStyle.primary)
    async def skills_tab(self, interaction: discord.Interaction, button: Button):
        self.current_tab = "Skills"
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Backstory", style=discord.ButtonStyle.primary)
    async def backstory_tab(self, interaction: discord.Interaction, button: Button):
        self.current_tab = "Backstory"
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, emoji="📝")
    async def edit_button(self, interaction: discord.Interaction, button: Button):
        if self.current_tab == "Stats":
            await interaction.response.send_modal(RenameModal(self, self.investigator.name))
        elif self.current_tab == "Backstory":
            await interaction.response.send_modal(BackstoryModal(self))
        else:
            await interaction.response.send_message("Editing not supported for this tab yet.", ephemeral=True)
