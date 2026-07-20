import discord
import random
import re
from discord.ext import commands
from discord import app_commands
from discord.ui import View
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
from emojis import get_health_bar
from support_functions import session_success, MockContext
from rapidfuzz import process, fuzz
from commands._roll_views import SessionView, DisambiguationView, RollResultView, QuickSkillSelect, DiceTrayView

class SafeDiceParser:
    def __init__(self):
        self.max_dice_count = 100
        self.max_sides = 1000
        self.max_result = 1000000 # 1 million limit

    def evaluate(self, expression):
        expression = str(expression).replace(" ", "")

        if "**" in expression: raise ValueError("Power operator not allowed")
        if "//" in expression: raise ValueError("Floor division not allowed")

        tokens = self._tokenize(expression)
        result_val, detail_str = self._parse_expression(tokens)

        if result_val > self.max_result:
            raise ValueError(f"Result too large (max {self.max_result})")

        return result_val, detail_str

    def _tokenize(self, expr):
        tokens = []
        i = 0
        while i < len(expr):
            char = expr[i]
            if char.isdigit():
                num_str = char
                i += 1
                while i < len(expr) and expr[i].isdigit():
                    num_str += expr[i]
                    i += 1
                tokens.append(('NUM', int(num_str)))
                continue
            elif char.lower() in "+-*/()d":
                if char.lower() == 'd':
                    tokens.append(('OP', 'd'))
                else:
                    tokens.append(('OP', char))
                i += 1
                continue
            else:
                raise ValueError(f"Invalid character: {char}")
        return tokens

    def _parse_expression(self, tokens):
        val, det = self._parse_term(tokens)
        while tokens and tokens[0][0] == 'OP' and tokens[0][1] in "+-":
            op = tokens.pop(0)[1]
            right_val, right_det = self._parse_term(tokens)
            if op == '+':
                val += right_val
                if right_det: det += f" + {right_det}"
            else:
                val -= right_val
                if right_det: det += f" - {right_det}" # Logic check: 1d6 - 1d6? Detail needs parenthesis maybe?
                # For simplicity, we just append details. The math is correct.
        return val, det

    def _parse_term(self, tokens):
        val, det = self._parse_factor(tokens)
        while tokens and tokens[0][0] == 'OP' and tokens[0][1] in "*/":
            op = tokens.pop(0)[1]
            right_val, right_det = self._parse_factor(tokens)
            if op == '*':
                val *= right_val
                if right_det: det += f" * {right_det}"
            else:
                if right_val == 0: raise ValueError("Division by zero")
                val //= right_val
                if right_det: det += f" / {right_det}"
        return val, det

    def _parse_factor(self, tokens):
        if not tokens: raise ValueError("Unexpected end of expression")
        token = tokens.pop(0)

        if token[0] == 'NUM':
            val = token[1]
            if tokens and tokens[0][0] == 'OP' and tokens[0][1] == 'd':
                tokens.pop(0)
                if not tokens or tokens[0][0] != 'NUM': raise ValueError("Expected number after 'd'")
                sides = tokens.pop(0)[1]
                return self._roll_dice(val, sides)
            return val, str(val)

        elif token[0] == 'OP' and token[1] == '(':
            val, det = self._parse_expression(tokens)
            if not tokens or tokens[0][1] != ')': raise ValueError("Missing closing parenthesis")
            tokens.pop(0)
            return val, f"({det})"

        elif token[0] == 'OP' and token[1] == 'd':
            if not tokens or tokens[0][0] != 'NUM': raise ValueError("Expected number after 'd'")
            sides = tokens.pop(0)[1]
            return self._roll_dice(1, sides)

        else:
            raise ValueError(f"Unexpected token: {token}")

    def _roll_dice(self, count, sides):
        if count > self.max_dice_count: raise ValueError(f"Too many dice (max {self.max_dice_count})")
        if sides > self.max_sides: raise ValueError(f"Too many sides (max {self.max_sides})")
        if count <= 0 or sides <= 0: return 0, "0"

        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        rolls_str = ', '.join(map(str, rolls))
        if len(rolls_str) > 50: rolls_str = rolls_str[:50] + "..."

        # Format: [6, 2]
        detail = f"[{rolls_str}]"
        return total, detail

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

    def evaluate_dice_expression(self, expression):
        # Use SafeDiceParser
        parser = SafeDiceParser()
        result, detail = parser.evaluate(expression)
        return result, detail

    def calculate_roll_result(self, roll, skill_value):
        is_fumble = False
        if skill_value < 50:
            if roll >= 96: is_fumble = True
        else:
            if roll == 100: is_fumble = True

        if is_fumble: return "Fumble :warning:", 0
        if roll == 1: return "Critical Success :star2:", 5
        elif roll <= skill_value // 5: return "Extreme Success :star:", 4
        elif roll <= skill_value // 2: return "Hard Success :white_check_mark:", 3
        elif roll <= skill_value: return "Regular Success :heavy_check_mark:", 2
        return "Fail :x:", 1

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
        skill="Pick a skill from your character sheet (autocomplete)",
        dice_expression="Dice expression (e.g. 3d6) or skill name typed manually",
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
    async def roll(self, interaction: discord.Interaction, skill: str = None, dice_expression: str = None, bonus: int = 0, penalty: int = 0, secret: bool = False, difficulty: str = "Regular"):
        """
        🎲 Perform a dice roll or skill check.
        """
        # skill takes priority over dice_expression
        target = skill or dice_expression

        ephemeral = secret
        if target is None:
            ephemeral = True

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)

        if not target:
            view = DiceTrayView(self, interaction.user)
            await interaction.followup.send(embed=view.get_embed(), view=view, ephemeral=True)
            return

        await self._perform_roll(interaction, target, bonus, penalty, secret, difficulty)

    async def _perform_roll(self, interaction, dice_expression, bonus, penalty, secret, difficulty):
        ephemeral = secret
        async def send_msg(content=None, embed=None, view=None):
             return await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral, wait=True)

        # Create Mock Context for Compatibility
        ctx = MockContext(interaction)

        server_id = str(interaction.guild_id)
        # 1. Dice Expression (e.g. 3d6)
        try:
            result, detail = self.evaluate_dice_expression(dice_expression)
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
        user_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        if user_id not in player_stats.get(server_id, {}):
            await send_msg(content=f"{interaction.user.display_name} doesn't have an investigator. Use `/newinvestigator`.")
            return

        try:
            stats = player_stats[server_id][user_id]
            matching_stats = self._resolve_skill(stats, dice_expression)

            if not matching_stats:
                await send_msg(content="No matching skill found.")
                return

            stat_name = matching_stats[0]
            current_value = stats[stat_name]
            if not isinstance(current_value, (int, float)):
                await send_msg(content=f"**{stat_name}** is not a numeric stat and can't be rolled.")
                return

            if len(matching_stats) > 1:
                view = DisambiguationView(ctx, matching_stats)
                msg = await send_msg(content="Multiple matching stats found. Please select one:", view=view)
                await view.wait()
                if view.selected_stat:
                    stat_name = view.selected_stat
                    current_value = stats[stat_name]
                    if not isinstance(current_value, (int, float)):
                        await send_msg(content=f"**{stat_name}** is not a numeric stat and can't be rolled.")
                        return
                    try: await msg.delete()
                    except: pass
                else:
                    try: await msg.edit(content="Selection cancelled.", view=None)
                    except: pass
                    return

            # ROLL LOGIC
            net_dice = bonus - penalty
            ones_roll = random.randint(0, 9)
            num_tens = 1 + abs(net_dice)
            tens_options = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
            tens_rolls = [random.choice(tens_options) for _ in range(num_tens)]
            possible_rolls = []
            for t in tens_rolls:
                val = t + ones_roll
                if val == 0: val = 100
                possible_rolls.append(val)

            final_roll = 0
            if net_dice > 0: final_roll = min(possible_rolls)
            elif net_dice < 0: final_roll = max(possible_rolls)
            else: final_roll = possible_rolls[0]

            result_text, result_tier = self.calculate_roll_result(final_roll, current_value)

            # Difficulty Check Logic
            target_tier = 2
            if difficulty == "Hard": target_tier = 3
            elif difficulty == "Extreme": target_tier = 4

            color = discord.Color.green()
            if result_tier == 5 or result_tier == 4: color = 0xF1C40F
            elif result_tier == 3 or result_tier == 2: color = 0x2ECC71
            elif result_tier == 1: color = 0xE74C3C
            elif result_tier == 0: color = 0x992D22

            if difficulty != "Regular":
                if result_tier >= target_tier:
                    result_text += f"\n✅ **Passed {difficulty} Difficulty**"
                elif result_tier > 1: # Passed Regular but not High enough
                    result_text += f"\n❌ **Failed {difficulty} Difficulty**"
                    color = 0xE74C3C

            # Sound Logic (Preserved from original)
            try:
                if interaction.guild and interaction.guild.voice_client and interaction.guild.voice_client.is_connected():
                    sound_settings = await load_skill_sound_settings()
                    guild_settings = sound_settings.get(server_id, {})
                    tier_map = {5: 'critical', 4: 'extreme', 3: 'hard', 2: 'regular', 1: 'fail', 0: 'fumble'}
                    result_key = tier_map.get(result_tier)
                    if result_key:
                        sound_file = None
                        if 'skills' in guild_settings and stat_name in guild_settings['skills']:
                             sound_file = guild_settings['skills'][stat_name].get(result_key)
                        if not sound_file and 'default' in guild_settings:
                             sound_file = guild_settings['default'].get(result_key)
                        if sound_file:
                             from dashboard.state import guild_mixers, SOUNDBOARD_FOLDER
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

            luck_threshold = (await load_luck_stats()).get(server_id, 10)

            view = RollResultView(
                ctx=ctx,
                cog=self,
                player_stats=player_stats,
                server_id=server_id,
                user_id=user_id,
                stat_name=stat_name,
                current_value=current_value,
                ones_roll=ones_roll,
                tens_rolls=tens_rolls,
                net_dice=net_dice,
                result_tier=result_tier,
                luck_threshold=luck_threshold
            )

            tens_str = ", ".join(str(t) if t != 0 else "00" for t in tens_rolls)
            dice_text = "Normal"
            if net_dice > 0: dice_text = f"Bonus ({net_dice})"
            elif net_dice < 0: dice_text = f"Penalty ({abs(net_dice)})"

            description = f"{interaction.user.mention} :game_die: **{dice_text}** Check\n"
            description += f"Dice: [{tens_str}] + {ones_roll} -> **{final_roll}**\n\n"
            description += f"**{result_text}**\n\n"
            description += f"**{stat_name}**: {current_value} - {current_value // 2} - {current_value // 5}\n"
            description += f":four_leaf_clover: LUCK: {player_stats[server_id][user_id].get('LUCK', 0)}"

            embed = discord.Embed(description=description, color=color)
            view.message = await send_msg(embed=embed, view=view)
            await view.wait()
            await save_player_stats(player_stats)

            if view.success:
                 session_data = await load_session_data()
                 if user_id not in session_data:
                     sess_view = SessionView(ctx)
                     msg = await send_msg(content="**Start a gaming session to record this success?**", view=sess_view)
                     await sess_view.wait()
                     if sess_view.create_session:
                         session_data[user_id] = []
                         await save_session_data(session_data)
                         await session_success(user_id, stat_name)
                         await msg.edit(content="Session started!", view=None)
                     else:
                         await msg.delete()
                 else:
                     await session_success(user_id, stat_name)

        except Exception as e:
            import traceback
            traceback.print_exc()
            await send_msg(content=f"An error occurred: {e}")

    @roll.autocomplete('skill')
    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        server_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        if server_id not in player_stats or user_id not in player_stats[server_id]:
            return [app_commands.Choice(name="No character found — use /newinvestigator", value="")]

        stats = player_stats[server_id][user_id]
        ignored_keys = {
            "NAME", "Name", "Residence", "Occupation", "Game Mode",
            "Archetype", "Archetype Info", "Backstory", "Custom Emojis",
            "Age", "Move", "Build", "Damage Bonus", "Bonus Damage",
            "CustomSkill", "CustomSkills", "CustomSkillss", "Occupation Info"
        }
        valid_stats = [(k, v) for k, v in stats.items() if k not in ignored_keys and isinstance(v, (int, float))]
        valid_stats.sort(key=lambda x: x[1], reverse=True)

        # Format: "Spot Hidden — 60%"
        choices = [(f"{k} — {v}%", k) for k, v in valid_stats]  # (display, value)

        if not current:
            return [app_commands.Choice(name=name[:100], value=val[:100]) for name, val in choices[:25]]

        # Fuzzy match against skill names, preserve score order (best match first)
        skill_keys = [val for _, val in choices]
        display_map = {val: name for name, val in choices}
        matches = process.extract(current, skill_keys, scorer=fuzz.WRatio, limit=25, score_cutoff=30)
        return [
            app_commands.Choice(name=display_map[m[0]][:100], value=m[0][:100])
            for m in matches  # already sorted best→worst by rapidfuzz
        ]

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
