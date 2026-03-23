import discord
from discord.ext import commands
from discord import app_commands
from models.database import SessionLocal
from services.character_service import CharacterService
from services.roll_service import RollService
from schemas.roll import RollRequest
from views.roll_view import RollView

class Versus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"

    @app_commands.command(name="versus", description="⚔️ Start an opposed roll against another player.")
    @app_commands.describe(opponent="The player to challenge.", stat_name="The stat to roll (e.g. STR, DEX)")
    async def versus(self, interaction: discord.Interaction, opponent: discord.User, stat_name: str):
        """Perform an opposed roll against another player using RollService."""
        db = SessionLocal()
        try:
            guild_id = str(interaction.guild_id)
            
            # Get investigators
            author_inv = CharacterService.get_investigator_by_guild_and_user(db, guild_id, str(interaction.user.id))
            opp_inv = CharacterService.get_investigator_by_guild_and_user(db, guild_id, str(opponent.id))
            
            if not author_inv or not opp_inv:
                await interaction.response.send_message("Both players must have an active investigator.", ephemeral=True)
                return

            # Helper to get stat value
            def get_stat(inv, name):
                name_low = name.lower()
                if hasattr(inv, name_low):
                    return getattr(inv, name_low)
                return inv.skills.get(name, 0)

            author_val = get_stat(author_inv, stat_name)
            opp_val = get_stat(opp_inv, stat_name)

            # Perform rolls
            request = RollRequest(stat_name=stat_name)
            author_roll = RollService.calculate_roll(request, author_val)
            opp_roll = RollService.calculate_roll(request, opp_val)

            # Determine winner
            if author_roll.result_level > opp_roll.result_level:
                result_title = f"🏆 {interaction.user.display_name} Wins!"
            elif opp_roll.result_level > author_roll.result_level:
                result_title = f"🏆 {opponent.display_name} Wins!"
            else:
                if author_val > opp_val:
                    result_title = f"🏆 {interaction.user.display_name} Wins! (Higher Skill)"
                elif opp_val > author_val:
                    result_title = f"🏆 {opponent.display_name} Wins! (Higher Skill)"
                else:
                    result_title = "🤝 It's a Draw!"

            embed = discord.Embed(title="⚔️ Versus Roll Result", color=discord.Color.blue())
            embed.add_field(
                name=f"👤 {interaction.user.display_name}",
                value=f"**{stat_name}**: {author_val}\n🎲 Roll: **{author_roll.final_roll}**\n🔹 {author_roll.result_text}",
                inline=True
            )
            embed.add_field(name="VS", value="⚡", inline=True)
            embed.add_field(
                name=f"👤 {opponent.display_name}",
                value=f"**{stat_name}**: {opp_val}\n🎲 Roll: **{opp_roll.final_roll}**\n🔹 {opp_roll.result_text}",
                inline=True
            )
            embed.add_field(name="Result", value=f"### {result_title}", inline=False)

            await interaction.response.send_message(embed=embed)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(Versus(bot))
