import discord
from discord.ext import commands
from discord import app_commands
from services.roll_service import RollService
from views.dice_tray_view import DiceTrayView
from views.roll_view import RollView
from views.roll_utility_views import SessionView, QuickSkillSelect

class Roll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"
        self.quick_roll_menu = app_commands.ContextMenu(name='🎲 Quick Roll', callback=self.quick_roll_context)
        self.bot.tree.add_command(self.quick_roll_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.quick_roll_menu.name, type=self.quick_roll_menu.type)

    async def quick_roll_context(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id != member.id: return await interaction.response.send_message("Only for you.", ephemeral=True)
        await interaction.response.send_message("Select a skill to roll:", view=QuickSkillSelect(member.id), ephemeral=True)

    @app_commands.command(name="roll", description="🎲 Interactive dice roll.")
    async def roll(self, interaction: discord.Interaction, stat: str = None, bonus: int = 0, penalty: int = 0):
        if not stat: return await interaction.response.send_message("Dice Tray:", view=DiceTrayView(interaction.user.id), ephemeral=True)
        await interaction.response.defer()
        from models.database import SessionLocal
        from services.character_service import CharacterService
        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild_id), str(interaction.user.id))
            res = RollService.perform_stat_roll(inv, stat, bonus, penalty)
            await interaction.followup.send(embed=res.create_embed(), view=RollView(res))
        finally: db.close()

    @roll.autocomplete('stat')
    async def roll_auto(self, it: discord.Interaction, cur: str):
        return await RollService.get_autocomplete_choices(str(it.guild_id), str(it.user.id), cur)

async def setup(bot): await bot.add_cog(Roll(bot))
