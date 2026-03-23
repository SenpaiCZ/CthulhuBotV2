import discord
import asyncio
import random
import re
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
from loadnsave import (
    load_player_stats,
    save_player_stats,
    load_session_data,
    save_session_data,
    load_luck_stats,
    load_skills_data,
    load_skill_sound_settings,
    load_server_volumes
)
from emojis import get_stat_emoji, get_health_bar
from support_functions import session_success, MockContext
from rapidfuzz import process, fuzz
from services.roll_service import RollService
from services.character_service import CharacterService
from views.roll_view import RollView
from schemas.roll import RollRequest, RollResult
from models.database import SessionLocal

class SessionView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.create_session = False
        self.message = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        self.create_session = True
        self.stop()
        # Disable buttons
        for child in self.children: child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except:
            pass

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        self.create_session = False
        self.stop()
        # Disable buttons
        for child in self.children: child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except:
            pass

class DisambiguationSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="Select a skill...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_stat = self.values[0]
        await interaction.response.defer()
        self.view.stop()

class DisambiguationView(View):
    def __init__(self, ctx, matching_stats):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.selected_stat = None

        options = [
            discord.SelectOption(label=stat, value=stat)
            for stat in matching_stats[:25]
        ]
        self.add_item(DisambiguationSelect(options))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Not your session!", ephemeral=True)
            return False
        return True

class QuickSkillSelect(Select):
    def __init__(self, char_data, server_id, user_id):
        self.char_data = char_data
        self.server_id = server_id
        self.user_id = user_id

        # Get Skills and Sort
        ignored = [
            "Residence", "Game Mode", "Archetype", "NAME", "Occupation",
            "Age", "HP", "MP", "SAN", "LUCK", "Build", "Damage Bonus", "Move",
            "STR", "DEX", "INT", "CON", "APP", "POW", "SIZ", "EDU", "Dodge",
            "Backstory"
        ]
        skills = []
        for key, val in char_data.items():
            if key in ignored: continue
            if isinstance(val, (int, float)):
                skills.append((key, val))

        skills.sort(key=lambda x: x[1], reverse=True)
        top_skills = skills[:25]

        options = []
        for name, val in top_skills:
            emoji = get_stat_emoji(name)
            options.append(discord.SelectOption(label=f"{name} ({val}%)", value=name, emoji=emoji))

        super().__init__(placeholder="🎲 Quick Roll...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        skill_name = self.values[0]
        current_val = self.char_data.get(skill_name, 0)

        # Roll using service
        request = RollRequest(stat_name=skill_name, bonus_dice=0, penalty_dice=0, difficulty="Regular")
        roll_result = RollService.calculate_roll(request, current_val)
        
        db = SessionLocal()
        investigator = CharacterService.get_investigator_by_guild_and_user(db, self.server_id, self.user_id)

        view = RollView(
            interaction=interaction,
            roll_result=roll_result,
            stat_name=skill_name,
            stat_value=current_val,
            investigator=investigator,
            db=db
        )

        color = discord.Color.green()
        if roll_result.result_level <= 1: color = discord.Color.red()
        elif roll_result.result_level >= 4: color = discord.Color.gold()

        desc = f"{interaction.user.mention} rolled **{skill_name}**!\n"
        desc += f"Dice: [{', '.join(map(str, roll_result.rolls))}] -> **{roll_result.final_roll}**\n\n"
        desc += f"**{roll_result.result_text}**\n\n"
        desc += f"**{skill_name}**: {current_val} - {current_val//2} - {current_val//5}\n"

        embed = discord.Embed(description=desc, color=color)

        # Public
        msg = await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Rolled **{skill_name}** in channel.", ephemeral=True)


class DiceTrayView(View):
    def __init__(self, cog, user):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.expression = ""
        self.update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("This dice tray is not for you!", ephemeral=True)
            return False
        return True

    def update_buttons(self):
        # We don't need to rebuild buttons every time, just update embed via callback
        pass

    def get_embed(self):
        desc = "Click buttons to build your dice pool."
        if self.expression:
            desc = f"```\n{self.expression}\n```"

        embed = discord.Embed(title="🎲 Dice Tray", description=desc, color=discord.Color.gold())
        return embed

    async def update_display(self, interaction):
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def add_term(self, interaction, term):
        if self.expression:
            self.expression += f" + {term}"
        else:
            self.expression = term
        await self.update_display(interaction)

    @discord.ui.button(label="D4", style=discord.ButtonStyle.secondary, row=0)
    async def d4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d4")

    @discord.ui.button(label="D6", style=discord.ButtonStyle.secondary, row=0)
    async def d6(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d6")

    @discord.ui.button(label="D8", style=discord.ButtonStyle.secondary, row=0)
    async def d8(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d8")

    @discord.ui.button(label="D10", style=discord.ButtonStyle.secondary, row=0)
    async def d10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d10")

    @discord.ui.button(label="D12", style=discord.ButtonStyle.secondary, row=0)
    async def d12(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d12")

    @discord.ui.button(label="D20", style=discord.ButtonStyle.secondary, row=1)
    async def d20(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d20")

    @discord.ui.button(label="D100", style=discord.ButtonStyle.secondary, row=1)
    async def d100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d100")

    @discord.ui.button(label="+1", style=discord.ButtonStyle.secondary, row=1)
    async def plus1(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += " + 1"
        await self.update_display(interaction)

    @discord.ui.button(label="+5", style=discord.ButtonStyle.secondary, row=1)
    async def plus5(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += " + 5"
        await self.update_display(interaction)

    @discord.ui.button(label="Clear", style=discord.ButtonStyle.danger, row=1)
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression = ""
        await self.update_display(interaction)

    @discord.ui.button(label="ROLL!", style=discord.ButtonStyle.success, row=2, emoji="🎲")
    async def roll_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.expression:
            return await interaction.response.send_message("Add dice first!", ephemeral=True)

        await interaction.response.defer()
        await interaction.delete_original_response()

        # Tray rolls are always private
        await self.cog._perform_roll(interaction, self.expression, 0, 0, True, "Regular")

class Roll(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"
        self.ctx_menu = app_commands.ContextMenu(
            name='Quick Roll',
            callback=self.quick_roll_context,
        )
        self.ctx_menu.description = "🎲 Quickly roll a skill for this character."
        self.ctx_menu.binding = self
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def quick_roll_context(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)

        server_id = str(interaction.guild_id)
        target_id = str(member.id)

        player_stats = await load_player_stats()

        if server_id not in player_stats or target_id not in player_stats[server_id]:
            return await interaction.followup.send(f"{member.display_name} has no investigator.", ephemeral=True)

        char_data = player_stats[server_id][target_id]

        view = View(timeout=60)
        view.add_item(QuickSkillSelect(char_data, server_id, target_id))

        embed = discord.Embed(
            title=f"🎲 Quick Roll: {char_data.get('NAME', 'Unknown')}",
            description="Select a skill to roll immediately.",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    def _resolve_skill(self, stats, skill_name_input):
        match = re.match(r"^(.*?)\s*\(\d+\)$", skill_name_input)
        clean_expression = match.group(1) if match else skill_name_input

        choices = list(stats.keys())

        # 1. Exact Match (Case Insensitive)
        exact_matches = []
        clean_lower = clean_expression.lower()
        for k in choices:
            if k.lower() == clean_lower:
                exact_matches.append(k)

        if exact_matches:
            return exact_matches

        # 2. Fuzzy Match
        results = process.extract(clean_expression, choices, scorer=fuzz.WRatio, limit=5, score_cutoff=60)
        return [res[0] for res in results]

    @app_commands.command(name="roll", description="🎲 Perform a dice roll or skill check.")
    @app_commands.describe(
        dice_expression="The dice expression (e.g. 3d6) or skill name (e.g. Spot Hidden)",
        bonus="Number of Bonus Dice (0-2)",
        penalty="Number of Penalty Dice (0-2)",
        secret="Make the result ephemeral (hidden)",
        difficulty="The difficulty level required."
    )
    @app_commands.choices(
        bonus=[app_commands.Choice(name="0", value=0), app_commands.Choice(name="1", value=1), app_commands.Choice(name="2", value=2)],
        penalty=[app_commands.Choice(name="0", value=0), app_commands.Choice(name="1", value=1), app_commands.Choice(name="2", value=2)],
        difficulty=[app_commands.Choice(name="Regular", value="Regular"), app_commands.Choice(name="Hard", value="Hard"), app_commands.Choice(name="Extreme", value="Extreme")]
    )
    async def roll(self, interaction: discord.Interaction, dice_expression: str = None, bonus: int = 0, penalty: int = 0, secret: bool = False, difficulty: str = "Regular"):
        """
        🎲 Perform a dice roll or skill check.
        """
        ephemeral = secret
        if dice_expression is None:
            ephemeral = True

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)

        if not dice_expression:
            view = DiceTrayView(self, interaction.user)
            await interaction.followup.send(embed=view.get_embed(), view=view, ephemeral=True)
            return

        await self._perform_roll(interaction, dice_expression, bonus, penalty, secret, difficulty)

    async def _perform_roll(self, interaction, dice_expression, bonus, penalty, secret, difficulty):
        ephemeral = secret
        async def send_msg(content=None, embed=None, view=None):
             return await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral, wait=True)

        # 1. Dice Expression (e.g. 3d6)
        try:
            result, detail = RollService.evaluate_dice_expression(dice_expression)
            embed = discord.Embed(
                title=f":game_die: Dice Roll Result",
                description=f"{interaction.user.mention} :game_die: Rolling: `{dice_expression}`",
                color=discord.Color.blue()
            )
            embed.add_field(name="Detail", value=detail, inline=False)
            embed.add_field(name="Total", value=f":game_die: {result}", inline=False)
            await send_msg(embed=embed)
            return
        except Exception:
            pass

        # 2. Skill Check Logic
        server_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        db = SessionLocal()
        investigator = CharacterService.get_investigator_by_guild_and_user(db, server_id, user_id)

        if not investigator:
            # Fallback to legacy player_stats if investigator not in DB yet
            player_stats = await load_player_stats()
            if user_id not in player_stats.get(server_id, {}):
                await send_msg(content=f"{interaction.user.display_name} doesn't have an investigator. Use `/newinvestigator`.")
                return
            stats = player_stats[server_id][user_id]
        else:
            # Combine core stats and skills from investigator model
            stats = {
                "STR": investigator.str, "CON": investigator.con, "SIZ": investigator.siz,
                "DEX": investigator.dex, "APP": investigator.app, "INT": investigator.int,
                "POW": investigator.pow, "EDU": investigator.edu, "LUCK": investigator.luck
            }
            if investigator.skills:
                stats.update(investigator.skills)

        matching_stats = self._resolve_skill(stats, dice_expression)

        if not matching_stats:
            await send_msg(content="No matching skill found.")
            return

        stat_name = matching_stats[0]
        current_value = stats[stat_name]

        if len(matching_stats) > 1:
            # Disambiguation needed
            ctx = MockContext(interaction)
            view = DisambiguationView(ctx, matching_stats)
            msg = await send_msg(content="Multiple matching stats found. Please select one:", view=view)
            await view.wait()
            if view.selected_stat:
                stat_name = view.selected_stat
                current_value = stats[stat_name]
                try: await msg.delete()
                except: pass
            else:
                try: await msg.edit(content="Selection cancelled.", view=None)
                except: pass
                return

        # ROLL LOGIC via Service
        request = RollRequest(
            stat_name=stat_name,
            bonus_dice=bonus,
            penalty_dice=penalty,
            difficulty=difficulty
        )
        roll_result = RollService.calculate_roll(request, current_value)

        # Sound Logic
        try:
            if interaction.guild and interaction.guild.voice_client and interaction.guild.voice_client.is_connected():
                sound_settings = await load_skill_sound_settings()
                guild_settings = sound_settings.get(server_id, {})
                tier_map = {5: 'critical', 4: 'extreme', 3: 'hard', 2: 'regular', 1: 'fail', 0: 'fumble'}
                result_key = tier_map.get(roll_result.result_level)
                if result_key:
                    sound_file = None
                    if 'skills' in guild_settings and stat_name in guild_settings['skills']:
                         sound_file = guild_settings['skills'][stat_name].get(result_key)
                    if not sound_file and 'default' in guild_settings:
                         sound_file = guild_settings['default'].get(result_key)
                    if sound_file:
                         from dashboard.app import guild_mixers, SOUNDBOARD_FOLDER
                         import os
                         mixer = guild_mixers.get(server_id)
                         if not mixer:
                             from dashboard.audio_mixer import MixingAudioSource
                             mixer = MixingAudioSource()
                             guild_mixers[server_id] = mixer
                         full_path = os.path.join(SOUNDBOARD_FOLDER, sound_file)
                         if os.path.exists(full_path):
                             vc = interaction.guild.voice_client
                             is_playing_mixer = False
                             if vc.is_playing() and isinstance(vc.source, discord.PCMVolumeTransformer):
                                 if vc.source.original == mixer: is_playing_mixer = True
                             if not is_playing_mixer:
                                 if vc.is_playing(): vc.stop()
                                 source = discord.PCMVolumeTransformer(mixer, volume=1.0)
                                 vc.play(source)
                             volumes = await load_server_volumes()
                             vol_data = volumes.get(server_id, {'music': 1.0, 'soundboard': 0.5})
                             sb_vol = vol_data.get('soundboard', 0.5)
                             mixer.add_track(full_path, volume=sb_vol, loop=False, metadata={'type': 'soundboard', 'trigger': 'roll'})
        except Exception as e:
            print(f"Error playing roll sound: {e}")

        async def handle_roll_complete(result: RollResult):
            if result.is_success:
                session_data = await load_session_data()
                if user_id not in session_data:
                    # We can't easily show another view here without more complexity,
                    # but we can at least record it if session exists.
                    # For now, let's just use session_success if they have a session.
                    pass
                else:
                    await session_success(user_id, stat_name)

        view = RollView(
            interaction=interaction,
            roll_result=roll_result,
            stat_name=stat_name,
            stat_value=current_value,
            difficulty=difficulty,
            investigator=investigator,
            db=db,
            on_complete=handle_roll_complete
        )

        rolls_str = ", ".join(map(str, roll_result.rolls))
        dice_text = "Normal"
        if bonus > 0: dice_text = f"Bonus ({bonus})"
        elif penalty > 0: dice_text = f"Penalty ({penalty})"

        description = f"{interaction.user.mention} :game_die: **{dice_text}** Check\n"
        description += f"Dice: [{rolls_str}] -> **{roll_result.final_roll}**\n\n"
        description += f"**{roll_result.result_text}**\n\n"
        description += f"**{stat_name}**: {current_value} - {current_value // 2} - {current_value // 5}\n"
        
        if investigator:
            description += f":four_leaf_clover: LUCK: {investigator.luck}"

        color = discord.Color.green()
        if roll_result.result_level >= 4: color = 0xF1C40F
        elif roll_result.result_level >= 2: color = 0x2ECC71
        elif roll_result.result_level == 1: color = 0xE74C3C
        elif roll_result.result_level == 0: color = 0x992D22

        embed = discord.Embed(description=description, color=color)
        await send_msg(embed=embed, view=view)

    @roll.autocomplete('dice_expression')
    async def roll_autocomplete(self, interaction: discord.Interaction, current: str):
        server_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        choices = []
        if server_id in player_stats and user_id in player_stats[server_id]:
            stats = player_stats[server_id][user_id]
            valid_stats = []
            # Keys to exclude from rolling
            ignored_keys = [
                "NAME", "Name", "Residence", "Occupation", "Game Mode",
                "Archetype", "Archetype Info", "Backstory", "Custom Emojis",
                "Age", "Move", "Build", "Damage Bonus", "Bonus Damage",
                "CustomSkill", "CustomSkills", "CustomSkillss", "Occupation Info"
            ]

            for k, v in stats.items():
                if k in ignored_keys: continue
                # Only include numeric values (rolls need numbers)
                if isinstance(v, (int, float)):
                    valid_stats.append((k, v))

            # Sort by value descending (highest skill first)
            valid_stats.sort(key=lambda x: x[1], reverse=True)

            choices = [f"{k} ({v})" for k, v in valid_stats]
        else:
            skills_data = await load_skills_data()
            choices = sorted(list(skills_data.keys()))

        if not current:
            # Already sorted by value if we had stats
            return [app_commands.Choice(name=c[:100], value=c[:100]) for c in choices[:25]]

        matches = process.extract(current, choices, scorer=fuzz.WRatio, limit=25)
        results = []
        for m in matches:
            results.append(app_commands.Choice(name=m[0][:100], value=m[0][:100]))
        return results

async def setup(bot):
    await bot.add_cog(Roll(bot))
