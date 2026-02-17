import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
from loadnsave import load_player_stats, save_player_stats
from rapidfuzz import process, fuzz
import re

# Restricted skills that cannot be removed
RESTRICTED_SKILLS = {
    "NAME", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP",
    "SAN", "HP", "MP", "LUCK", "MOV", "BUILD", "DAMAGE BONUS",
    "AGE", "DODGE", "OCCUPATION", "RESIDENCE", "GAME MODE",
    "ARCHETYPE", "BACKSTORY", "CREDIT RATING", "TALENT",
    "ARCHETYPE INFO", "SEX", "BIRTHPLACE", "MOVE"
}

class AddSkillModal(ui.Modal, title="Add Custom Skill"):
    skill_name = ui.Label(text="Skill Name", component=ui.TextInput(placeholder="e.g. Drive (Tank)", min_length=1, max_length=100))
    skill_value = ui.Label(text="Starting Value", component=ui.TextInput(placeholder="e.g. 40", min_length=1, max_length=3))
    emoji_input = ui.Label(text="Emoji (Optional)", component=ui.TextInput(placeholder="Paste emoji here", required=False, max_length=5))

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)
            return

        skill_name = self.skill_name.component.value.strip()
        skill_value_str = self.skill_value.component.value.strip()

        # Validate Value
        if not skill_value_str.isdigit():
             await interaction.response.send_message("Skill value must be a number (0-100).", ephemeral=True)
             return

        skill_value = int(skill_value_str)
        # Allow >100? CoC skills can go above 100.
        # But "Starting Value" usually implies base.
        # Let's trust user, but maybe warn if excessive.
        # Keeping it simple for now, maybe just check non-negative.
        if skill_value < 0:
             await interaction.response.send_message("Skill value cannot be negative.", ephemeral=True)
             return

        server_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        if server_id not in player_stats or user_id not in player_stats[server_id]:
             await interaction.response.send_message("You don't have an investigator. Use `/newinvestigator` first.", ephemeral=True)
             return

        user_stats = player_stats[server_id][user_id]

        # Check if skill exists (case-insensitive)
        existing_skill = next((k for k in user_stats.keys() if k.lower() == skill_name.lower()), None)

        if existing_skill:
            await interaction.response.send_message(f"Skill '{existing_skill}' already exists with value {user_stats[existing_skill]}. Use `/stat` to update it.", ephemeral=True)
            return

        # Add Skill
        player_stats[server_id][user_id][skill_name] = skill_value

        # Handle Emoji
        emoji_char = self.emoji_input.component.value.strip()
        if emoji_char:
            if "Custom Emojis" not in user_stats:
                player_stats[server_id][user_id]["Custom Emojis"] = {}
            player_stats[server_id][user_id]["Custom Emojis"][skill_name] = emoji_char

        await save_player_stats(player_stats)

        msg = f"Added skill **{skill_name}** with value **{skill_value}**."
        if emoji_char:
            msg += f" Emoji: {emoji_char}"

        await interaction.response.send_message(msg, ephemeral=True)

class RemoveSkillView(ui.View):
    def __init__(self, skill_name, user_id, confirm_callback):
        super().__init__(timeout=60)
        self.skill_name = skill_name
        self.user_id = user_id
        self.confirm_callback = confirm_callback

    @ui.button(label="Yes, Remove Skill", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return
        await self.confirm_callback(interaction)
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

    @app_commands.command(name="addskill", description="Add a new custom skill to your character sheet.")
    async def addskill(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)
            return
        await interaction.response.send_modal(AddSkillModal(self.bot))

    @app_commands.command(name="removeskill", description="Remove a skill from your character sheet.")
    @app_commands.describe(skill_name="The name of the skill to remove")
    async def removeskill(self, interaction: discord.Interaction, skill_name: str):
        if interaction.guild is None:
            await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)
            return

        server_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        if server_id not in player_stats or user_id not in player_stats[server_id]:
             await interaction.response.send_message("You don't have an investigator.", ephemeral=True)
             return

        user_stats = player_stats[server_id][user_id]

        # Clean up skill_name input
        clean_skill_name = skill_name
        match = re.match(r"^(.*?)\s*\(\d+\)$", skill_name)
        if match:
            clean_skill_name = match.group(1)

        # Find the skill
        target_skill = None
        # Exact match
        for key in user_stats.keys():
            if key.lower() == clean_skill_name.lower():
                target_skill = key
                break

        # Fuzzy match
        if not target_skill:
             choices = list(user_stats.keys())
             extract = process.extractOne(clean_skill_name, choices, scorer=fuzz.WRatio)
             if extract:
                 match_key, score, _ = extract
                 if score > 80:
                     target_skill = match_key

        if not target_skill:
             await interaction.response.send_message(f"Skill '{clean_skill_name}' not found.", ephemeral=True)
             return

        # Check Restricted
        if target_skill.upper() in RESTRICTED_SKILLS:
             await interaction.response.send_message(f"Cannot remove restricted skill/stat **{target_skill}**.", ephemeral=True)
             return

        # Callback for confirmation
        async def delete_callback(intx: discord.Interaction):
            # Re-fetch stats to be safe? Or assume consistency.
            # In async environment, it's possible it changed, but unlikely for this use case.
            # Using the reference we have.
            try:
                del player_stats[server_id][user_id][target_skill]
                await save_player_stats(player_stats)
                await intx.response.edit_message(content=f"Removed skill **{target_skill}**.", view=None)
            except KeyError:
                await intx.response.edit_message(content=f"Skill **{target_skill}** was already removed or not found.", view=None)

        view = RemoveSkillView(target_skill, interaction.user.id, delete_callback)
        await interaction.response.send_message(f"Are you sure you want to remove **{target_skill}**? This cannot be undone.", view=view, ephemeral=True)

    @removeskill.autocomplete('skill_name')
    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        if interaction.guild is None:
            return []

        server_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        if server_id not in player_stats or user_id not in player_stats[server_id]:
            return []

        user_stats = player_stats[server_id][user_id]

        # Filter out restricted skills from autocomplete
        choices = [f"{k} ({v})" for k, v in user_stats.items() if k.upper() not in RESTRICTED_SKILLS]

        if not current:
            return [app_commands.Choice(name=c, value=c) for c in sorted(choices)[:25]]

        matches = process.extract(current, choices, scorer=fuzz.WRatio, limit=25)
        return [app_commands.Choice(name=m[0], value=m[0]) for m in matches]

async def setup(bot):
    await bot.add_cog(skills(bot))
