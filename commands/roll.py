import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View
from loadnsave import load_player_stats, load_session_data, load_skill_sound_settings, load_server_volumes, load_skills_data
from support_functions import session_success, MockContext
from services.roll_service import RollService
from services.character_service import CharacterService
from views.roll_view import RollView
from views.dice_tray_view import DiceTrayView
from views.roll_utility_views import DisambiguationView, QuickSkillSelect
from schemas.roll import RollRequest, RollResult
from models.database import SessionLocal

class Roll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"
        self.ctx_menu = app_commands.ContextMenu(name='Quick Roll', callback=self.quick_roll_context)
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def quick_roll_context(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)
        stats = await load_player_stats()
        char_data = stats.get(str(interaction.guild_id), {}).get(str(member.id))
        if not char_data: return await interaction.followup.send(f"{member.display_name} has no investigator.", ephemeral=True)
        view = View(timeout=60); view.add_item(QuickSkillSelect(char_data, str(interaction.guild_id), str(member.id)))
        await interaction.followup.send(embed=discord.Embed(title=f"🎲 Quick Roll: {char_data.get('NAME', 'Unknown')}", description="Select a skill.", color=discord.Color.blue()), view=view, ephemeral=True)

    @app_commands.command(name="roll", description="🎲 Perform a dice roll or skill check.")
    @app_commands.describe(dice_expression="Dice (3d6) or skill (Spot Hidden)", bonus="Bonus (0-2)", penalty="Penalty (0-2)", secret="Hidden result", difficulty="Difficulty")
    @app_commands.choices(bonus=[app_commands.Choice(name=str(i), value=i) for i in range(3)], penalty=[app_commands.Choice(name=str(i), value=i) for i in range(3)], difficulty=[app_commands.Choice(name=d, value=d) for d in ["Regular", "Hard", "Extreme"]])
    async def roll(self, interaction: discord.Interaction, dice_expression: str = None, bonus: int = 0, penalty: int = 0, secret: bool = False, difficulty: str = "Regular"):
        if not interaction.response.is_done(): await interaction.response.defer(ephemeral=(secret or not dice_expression))
        if not dice_expression: return await interaction.followup.send(embed=DiceTrayView(self, interaction.user).get_embed(), view=DiceTrayView(self, interaction.user), ephemeral=True)
        await self._perform_roll(interaction, dice_expression, bonus, penalty, secret, difficulty)

    async def _perform_roll(self, interaction, dice_expression, bonus, penalty, secret, difficulty):
        try:
            res, det = RollService.evaluate_dice_expression(dice_expression)
            embed = discord.Embed(title="🎲 Dice Roll", description=f"{interaction.user.mention} rolling `{dice_expression}`", color=discord.Color.blue())
            embed.add_field(name="Detail", value=det); embed.add_field(name="Total", value=f"🎲 {res}")
            return await interaction.followup.send(embed=embed, ephemeral=secret)
        except: pass

        db = SessionLocal(); inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild_id), str(interaction.user.id))
        stats = {k: v for k, v in {"STR":inv.str,"CON":inv.con,"SIZ":inv.siz,"DEX":inv.dex,"APP":inv.app,"INT":inv.int,"POW":inv.pow,"EDU":inv.edu,"LUCK":inv.luck}.items()} if inv else (await load_player_stats()).get(str(interaction.guild_id), {}).get(str(interaction.user.id), {})
        if inv and inv.skills: stats.update(inv.skills)
        matches = RollService.resolve_skill(stats, dice_expression)
        if not matches: return await interaction.followup.send("No matching skill found.", ephemeral=secret)
        
        stat_name = matches[0]
        if len(matches) > 1:
            view = DisambiguationView(MockContext(interaction), matches); msg = await interaction.followup.send("Select a stat:", view=view, ephemeral=secret)
            await view.wait()
            if not view.selected_stat: return
            stat_name = view.selected_stat; await msg.delete()

        result = RollService.calculate_roll(RollRequest(stat_name=stat_name, bonus_dice=bonus, penalty_dice=penalty, difficulty=difficulty), stats[stat_name])
        await self._handle_sound(interaction, stat_name, result.result_level)
        
        async def on_done(res):
            if res.is_success and str(interaction.user.id) in await load_session_data(): await session_success(str(interaction.user.id), stat_name)

        view = RollView(interaction=interaction, roll_result=result, stat_name=stat_name, stat_value=stats[stat_name], difficulty=difficulty, investigator=inv, db=db, on_complete=on_done)
        desc = f"{interaction.user.mention} 🎲 **{('Bonus' if bonus>0 else 'Penalty' if penalty>0 else 'Normal')}** Check\nDice: {result.rolls} -> **{result.final_roll}**\n\n**{result.result_text}**\n\n**{stat_name}**: {stats[stat_name]} - {stats[stat_name]//2} - {stats[stat_name]//5}"
        if inv: desc += f"\n🍀 LUCK: {inv.luck}"
        await interaction.followup.send(embed=discord.Embed(description=desc, color=[0x992D22, 0xE74C3C, 0x2ECC71, 0x2ECC71, 0xF1C40F, 0xF1C40F][result.result_level]), view=view, ephemeral=secret)

    async def _handle_sound(self, interaction, stat_name, result_level):
        try:
            if not (interaction.guild and interaction.guild.voice_client): return
            settings = (await load_skill_sound_settings()).get(str(interaction.guild_id), {})
            key = {5:'critical', 4:'extreme', 3:'hard', 2:'regular', 1:'fail', 0:'fumble'}.get(result_level)
            sound = settings.get('skills', {}).get(stat_name, {}).get(key) or settings.get('default', {}).get(key)
            if sound:
                from dashboard.app import guild_mixers, SOUNDBOARD_FOLDER; import os; from dashboard.audio_mixer import MixingAudioSource
                mixer = guild_mixers.get(str(interaction.guild_id))
                if not mixer: mixer = MixingAudioSource(); guild_mixers[str(interaction.guild_id)] = mixer
                if not interaction.guild.voice_client.is_playing(): interaction.guild.voice_client.play(discord.PCMVolumeTransformer(mixer))
                vol = (await load_server_volumes()).get(str(interaction.guild_id), {}).get('soundboard', 0.5)
                mixer.add_track(os.path.join(SOUNDBOARD_FOLDER, sound), volume=vol)
        except: pass

    @roll.autocomplete('dice_expression')
    async def roll_autocomplete(self, interaction: discord.Interaction, current: str):
        stats = (await load_player_stats()).get(str(interaction.guild_id), {}).get(str(interaction.user.id), {})
        base = None if stats else sorted(list((await load_skills_data()).keys()))
        choices = RollService.get_autocomplete_choices(stats=stats, current=current, base_choices=base)
        return [app_commands.Choice(name=c[:100], value=c[:100]) for c in choices]

async def setup(bot): await bot.add_cog(Roll(bot))
