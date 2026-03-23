import discord
import re
from discord.ext import commands
from discord import app_commands
from rapidfuzz import process, fuzz
from models.database import SessionLocal
from services.character_service import CharacterService

class renameskill(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(description="✏️ Rename a skill on your character sheet.")
    @app_commands.describe(skill_name="The current name of the skill to rename", new_name="The new name for the skill")
    async def renameskill(self, interaction: discord.Interaction, skill_name: str, new_name: str):
        """
        Rename a skill on your character sheet.
        """
        # Restricted skills that cannot be renamed
        restricted_skills = {
            "NAME", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", 
            "SAN", "HP", "MP", "LUCK", "MOV", "BUILD", "DAMAGE BONUS", "AGE", "DODGE"
        }

        db = SessionLocal()
        try:
            investigator = CharacterService.get_investigator_by_guild_and_user(
                db, str(interaction.guild_id), str(interaction.user.id)
            )

            if not investigator:
                await interaction.response.send_message(
                    f"{interaction.user.display_name} doesn't have an investigator. Use `/newinvestigator` for creating a new investigator.",
                    ephemeral=True
                )
                return

            # Clean up skill_name from autocomplete (e.g. "Spot Hidden (50)" -> "Spot Hidden")
            clean_skill_name = skill_name
            match = re.match(r"^(.*?)\s*\(\d+\)$", skill_name)
            if match:
                clean_skill_name = match.group(1)

            user_skills = investigator.skills or {}
            target_skill_key = None

            # 1. Exact match (case insensitive) search for the old skill
            for key in user_skills.keys():
                if key.lower() == clean_skill_name.lower():
                    target_skill_key = key
                    break

            # 2. Fuzzy match if no exact match found
            if not target_skill_key:
                choices = list(user_skills.keys())
                extract = process.extractOne(clean_skill_name, choices, scorer=fuzz.WRatio)
                if extract:
                    match_key, score, _ = extract
                    if score > 80:
                        target_skill_key = match_key

            if not target_skill_key:
                await interaction.response.send_message(f"Skill '{clean_skill_name}' not found in your skills list.", ephemeral=True)
                return

            # Check for restricted skills
            if target_skill_key.upper() in restricted_skills:
                await interaction.response.send_message(f"You cannot rename the skill '{target_skill_key}' as it's a restricted skill.", ephemeral=True)
                return

            # Check if new name already exists
            for key in user_skills.keys():
                if key.lower() == new_name.lower():
                    await interaction.response.send_message(f"Skill with the name '{key}' already exists. Choose a different name.", ephemeral=True)
                    return

            # Proceed with rename
            new_skill_name_formatted = new_name.strip()
            CharacterService.rename_skill(db, investigator.id, target_skill_key, new_skill_name_formatted)
            
            await interaction.response.send_message(f"Your skill '{target_skill_key}' has been updated to '{new_skill_name_formatted}'.")

        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
        finally:
            db.close()

    @renameskill.autocomplete('skill_name')
    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        db = SessionLocal()
        try:
            investigator = CharacterService.get_investigator_by_guild_and_user(
                db, str(interaction.guild_id), str(interaction.user.id)
            )
            if not investigator or not investigator.skills:
                return []

            choices = [f"{k} ({v})" for k, v in investigator.skills.items()]
            if not current:
                return [app_commands.Choice(name=c, value=c) for c in sorted(choices)[:25]]

            matches = process.extract(current, choices, scorer=fuzz.WRatio, limit=25)
            return [app_commands.Choice(name=m[0], value=m[0]) for m in matches]
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(renameskill(bot))
