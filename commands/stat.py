import discord
from discord.ext import commands
from discord import app_commands
from models.database import SessionLocal
from services.character_service import CharacterService
from emojis import get_stat_emoji

class stat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"

    @app_commands.command(description="📈 Change the value of a skill or stat for your character.")
    @app_commands.describe(stat_name="The name of the stat/skill (e.g. HP, STR, Spot Hidden)", value="The new value (e.g. 50)")
    async def stat(self, interaction: discord.Interaction, stat_name: str, value: int):
        """Update your investigator's stats using CharacterService."""
        db = SessionLocal()
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            
            investigator = CharacterService.get_investigator_by_guild_and_user(db, guild_id, user_id)
            if not investigator:
                await interaction.response.send_message("You don't have an investigator. Use `/newinvestigator`.", ephemeral=True)
                return

            # Determine if stat is a primary characteristic or a skill
            is_characteristic = hasattr(investigator, stat_name.lower())
            old_value = getattr(investigator, stat_name.lower()) if is_characteristic else investigator.skills.get(stat_name)
            
            if is_characteristic:
                CharacterService.update_investigator(db, investigator.id, {stat_name.lower(): value})
            else:
                CharacterService.add_skill(db, investigator.id, stat_name, value)
            
            stat_emoji = get_stat_emoji(stat_name)
            embed = discord.Embed(
                title=f"Stat Change - {stat_emoji} {stat_name}",
                description=f"**{interaction.user.display_name}**, you've updated your '{stat_name}' stat.",
                color=discord.Color.green()
            )
            embed.add_field(name="Old Value", value=str(old_value), inline=True)
            embed.add_field(name="New Value", value=str(value), inline=True)
            
            await interaction.response.send_message(embed=embed)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(stat(bot))
