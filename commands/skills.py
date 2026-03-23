import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
from rapidfuzz import process, fuzz
import re
from models.database import SessionLocal
from services.character_service import CharacterService
from views.character_profile import CharacterProfileView

# Restricted skills that cannot be removed
RESTRICTED_SKILLS = {
    "NAME", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP",
    "SAN", "HP", "MP", "LUCK", "MOV", "BUILD", "DAMAGE BONUS",
    "AGE", "DODGE", "OCCUPATION", "RESIDENCE", "GAME MODE",
    "ARCHETYPE", "BACKSTORY", "CREDIT RATING", "TALENT",
    "ARCHETYPE INFO", "SEX", "BIRTHPLACE", "MOVE"
}

class AddSkillModal(ui.Modal, title="Add Custom Skill"):
    skill_name_input = ui.TextInput(label="Skill Name", placeholder="e.g. Drive (Tank)", min_length=1, max_length=100)
    skill_value_input = ui.TextInput(label="Starting Value", placeholder="e.g. 40", min_length=1, max_length=3)
    # emoji_input = ui.TextInput(label="Emoji (Optional)", placeholder="Paste emoji here", required=False, max_length=5)

    def __init__(self, investigator_id):
        super().__init__()
        self.investigator_id = investigator_id

    async def on_submit(self, interaction: discord.Interaction):
        skill_name = self.skill_name_input.value.strip()
        skill_value_str = self.skill_value_input.value.strip()

        if not skill_value_str.isdigit():
             await interaction.response.send_message("Skill value must be a number (0-100).", ephemeral=True)
             return

        skill_value = int(skill_value_str)
        if skill_value < 0:
             await interaction.response.send_message("Skill value cannot be negative.", ephemeral=True)
             return

        db = SessionLocal()
        try:
            investigator = CharacterService.get_investigator(db, self.investigator_id)
            user_skills = investigator.skills or {}

            # Check if skill exists (case-insensitive)
            existing_skill = next((k for k in user_skills.keys() if k.lower() == skill_name.lower()), None)

            if existing_skill:
                await interaction.response.send_message(f"Skill '{existing_skill}' already exists with value {user_skills[existing_skill]}. Use `/stat` to update it.", ephemeral=True)
                return

            CharacterService.add_skill(db, self.investigator_id, skill_name, skill_value)
            await interaction.response.send_message(f"Added skill **{skill_name}** with value **{skill_value}**.", ephemeral=True)
        finally:
            db.close()

class RemoveSkillView(ui.View):
    def __init__(self, investigator_id, skill_name, user_id):
        super().__init__(timeout=60)
        self.investigator_id = investigator_id
        self.skill_name = skill_name
        self.user_id = user_id

    @ui.button(label="Yes, Remove Skill", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return
        
        db = SessionLocal()
        try:
            CharacterService.remove_skill(db, self.investigator_id, self.skill_name)
            await interaction.response.edit_message(content=f"Removed skill **{self.skill_name}**.", view=None)
        finally:
            db.close()
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return
        await interaction.response.edit_message(content="Action cancelled.", view=None)
        self.stop()

class skills(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"

    @app_commands.command(name="skills", description="📜 View your character's skills.")
    async def skills_view(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            investigator = CharacterService.get_investigator_by_guild_and_user(
                db, str(interaction.guild_id), str(interaction.user.id)
            )
            if not investigator:
                await interaction.response.send_message("You don't have an investigator.", ephemeral=True)
                return

            view = CharacterProfileView(investigator.id, interaction.user)
            view.current_tab = "Skills"
            await interaction.response.send_message(embed=view.get_embed(), view=view)
        finally:
            db.close()

    @app_commands.command(name="addskill", description="✨ Add a new custom skill to your character sheet.")
    async def addskill(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            investigator = CharacterService.get_investigator_by_guild_and_user(
                db, str(interaction.guild_id), str(interaction.user.id)
            )
            if not investigator:
                await interaction.response.send_message("You don't have an investigator. Use `/newinvestigator` first.", ephemeral=True)
                return
            await interaction.response.send_modal(AddSkillModal(investigator.id))
        finally:
            db.close()

    @app_commands.command(name="removeskill", description="❌ Remove a skill from your character sheet.")
    @app_commands.describe(skill_name="The name of the skill to remove")
    async def removeskill(self, interaction: discord.Interaction, skill_name: str):
        db = SessionLocal()
        try:
            investigator = CharacterService.get_investigator_by_guild_and_user(
                db, str(interaction.guild_id), str(interaction.user.id)
            )
            if not investigator:
                await interaction.response.send_message("You don't have an investigator.", ephemeral=True)
                return

            # Clean up skill_name input
            clean_skill_name = skill_name
            match = re.match(r"^(.*?)\s*\(\d+\)$", skill_name)
            if match:
                clean_skill_name = match.group(1)

            user_skills = investigator.skills or {}
            target_skill = None
            for key in user_skills.keys():
                if key.lower() == clean_skill_name.lower():
                    target_skill = key
                    break

            if not target_skill:
                 choices = list(user_skills.keys())
                 extract = process.extractOne(clean_skill_name, choices, scorer=fuzz.WRatio)
                 if extract:
                     match_key, score, _ = extract
                     if score > 80:
                         target_skill = match_key

            if not target_skill:
                 await interaction.response.send_message(f"Skill '{clean_skill_name}' not found.", ephemeral=True)
                 return

            if target_skill.upper() in RESTRICTED_SKILLS:
                 await interaction.response.send_message(f"Cannot remove restricted skill/stat **{target_skill}**.", ephemeral=True)
                 return

            view = RemoveSkillView(investigator.id, target_skill, interaction.user.id)
            await interaction.response.send_message(f"Are you sure you want to remove **{target_skill}**? This cannot be undone.", view=view, ephemeral=True)
        finally:
            db.close()

    @removeskill.autocomplete('skill_name')
    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        db = SessionLocal()
        try:
            investigator = CharacterService.get_investigator_by_guild_and_user(
                db, str(interaction.guild_id), str(interaction.user.id)
            )
            if not investigator or not investigator.skills:
                return []

            choices = [f"{k} ({v})" for k, v in investigator.skills.items() if k.upper() not in RESTRICTED_SKILLS]
            if not current:
                return [app_commands.Choice(name=c, value=c) for c in sorted(choices)[:25]]

            matches = process.extract(current, choices, scorer=fuzz.WRatio, limit=25)
            return [app_commands.Choice(name=m[0], value=m[0]) for m in matches]
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(skills(bot))
