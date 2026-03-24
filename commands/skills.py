import discord
from discord.ext import commands
from discord import app_commands
from rapidfuzz import process, fuzz
import re
from models.database import SessionLocal
from services.character_service import CharacterService
from views.character_profile import CharacterProfileView
from views.utility_views import AddSkillModal, RemoveSkillView

RESTRICTED_SKILLS = {"NAME", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN", "HP", "MP", "LUCK", "MOV", "BUILD", "DAMAGE BONUS", "AGE", "DODGE", "OCCUPATION", "RESIDENCE", "GAME MODE", "ARCHETYPE", "BACKSTORY", "CREDIT RATING", "TALENT", "ARCHETYPE INFO", "SEX", "BIRTHPLACE", "MOVE"}

class skills(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"

    @app_commands.command(name="skills", description="📜 View your character's skills.")
    async def skills_view(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild_id), str(interaction.user.id))
            if not inv: return await interaction.response.send_message("No investigator found.", ephemeral=True)
            view = CharacterProfileView(inv.id, interaction.user)
            view.current_tab = "Skills"
            await interaction.response.send_message(embed=view.get_embed(), view=view)
        finally: db.close()

    @app_commands.command(name="addskill", description="✨ Add a custom skill.")
    async def addskill(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild_id), str(interaction.user.id))
            if not inv: return await interaction.response.send_message("No investigator.", ephemeral=True)
            await interaction.response.send_modal(AddSkillModal(inv.id))
        finally: db.close()

    @app_commands.command(name="removeskill", description="❌ Remove a skill.")
    async def removeskill(self, interaction: discord.Interaction, skill_name: str):
        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild_id), str(interaction.user.id))
            if not inv: return await interaction.response.send_message("No investigator.", ephemeral=True)
            clean_name = re.match(r"^(.*?)\s*\(\d+\)$", skill_name).group(1) if "(" in skill_name else skill_name
            target = next((k for k in (inv.skills or {}).keys() if k.lower() == clean_name.lower()), None)
            if not target:
                match = process.extractOne(clean_name, list(inv.skills.keys()), scorer=fuzz.WRatio)
                if match and match[1] > 80: target = match[0]
            if not target: return await interaction.response.send_message("Skill not found.", ephemeral=True)
            if target.upper() in RESTRICTED_SKILLS: return await interaction.response.send_message("Cannot remove stat.", ephemeral=True)
            await interaction.response.send_message(f"Remove **{target}**?", view=RemoveSkillView(inv.id, target, interaction.user.id), ephemeral=True)
        finally: db.close()

    @removeskill.autocomplete('skill_name')
    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild_id), str(interaction.user.id))
            if not inv or not inv.skills: return []
            choices = [f"{k} ({v})" for k, v in inv.skills.items() if k.upper() not in RESTRICTED_SKILLS]
            if not current: return [app_commands.Choice(name=c, value=c) for c in sorted(choices)[:25]]
            matches = process.extract(current, choices, scorer=fuzz.WRatio, limit=25)
            return [app_commands.Choice(name=m[0], value=m[0]) for m in matches]
        finally: db.close()

async def setup(bot): await bot.add_cog(skills(bot))
