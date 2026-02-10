import discord
import asyncio
import random
import re
from discord.ext import commands
from loadnsave import (
    load_player_stats,
    save_player_stats,
    load_server_stats,
    load_session_data,
    save_session_data,
    load_luck_stats,
)
from emojis import get_stat_emoji
from support_functions import session_success


class newroll(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def evaluate_dice_expression(self, expression):
        # Replace D with 'd' and remove spaces
        expression = expression.replace('D', 'd').replace(' ', '')
        detail_parts = []

        # Define a function to handle dice rolls
        def roll_dice(match):
            num, size = map(int, match.groups())
            rolls = [random.randint(1, size) for _ in range(num)]
            detail_parts.append(f":game_die: {num}d{size}: {' + '.join(map(str, rolls))} = {sum(rolls)}")
            return sum(rolls)

        # Replace dice roll expressions with their results
        dice_pattern = re.compile(r'(\d+)d(\d+)')
        expression = dice_pattern.sub(lambda m: str(roll_dice(m)), expression)

        # Evaluate the expression
        # Only allow safe characters
        if not re.match(r'^[\d+\-*/().]+$', expression):
            raise ValueError("Invalid dice expression")

        result = eval(expression, {"__builtins__": None})
        detail = "\n".join(detail_parts) + f"\nExpression: {expression}"
        return result, detail

    def calculate_roll_result(self, roll, skill_value):
        # Fumble Logic - Check first because 100 is always Fumble/Fail
        is_fumble = False
        if skill_value < 50:
            if roll >= 96:
                is_fumble = True
        else:
            if roll == 100:
                is_fumble = True

        if is_fumble:
            return "Fumble :warning:", 0

        # Success Logic
        if roll == 1:
            return "Critical Success :star2:", 5
        elif roll <= skill_value // 5:
            return "Extreme Success :star:", 4
        elif roll <= skill_value // 2:
            return "Hard Success :white_check_mark:", 3
        elif roll <= skill_value:
            return "Regular Success :heavy_check_mark:", 2

        # If not Success and not Fumble, it is Fail
        return "Fail :x:", 1

    @commands.command(aliases=["roll", "diceroll", "d", "nd"], guild_only=True)
    async def newroll(self, ctx, *, dice_expression):
        """
        🎲 Perform a dice roll or skill check.
        Interactive interface allows for Bonus/Penalty dice and Luck spending.
        """
        server_prefixes = await load_server_stats()
        server_id = str(ctx.guild.id)
        prefix = server_prefixes.get(server_id, "!") if server_id else "!"

        luck_stats = await load_luck_stats()
        luck_threshold = luck_stats.get(server_id, 10)

        # 1. Try to evaluate as dice expression (e.g. 3d6)
        try:
            result, detail = self.evaluate_dice_expression(dice_expression)
            embed = discord.Embed(
                title=f":game_die: Dice Roll Result",
                description=f"{ctx.author.mention} :game_die: Rolling: `{dice_expression}`",
                color=discord.Color.blue()
            )
            embed.add_field(name="Detail", value=detail, inline=False)
            embed.add_field(name="Total", value=f":game_die: {result}", inline=False)
            await ctx.send(embed=embed)
            return
        except Exception:
            # Not a valid dice expression, assume it is a Skill Check
            pass

        # 2. Skill Check Logic
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command is not allowed in DMs.")
            return
        user_id = str(ctx.author.id)

        player_stats = await load_player_stats()

        if user_id not in player_stats[server_id]:
            await ctx.send(
                f"{ctx.author.display_name} doesn't have an investigator. Use `{prefix}newInv` for creating a new investigator."
            )
            return

        try:
            normalized_dice_expression = dice_expression.lower()
            matching_stats = []

            # Exact match
            for stat_key, stat_value in player_stats[server_id][user_id].items():
                if any(word.lower() == stat_key.lower() for word in normalized_dice_expression.split()):
                    matching_stats.append(stat_key)
                    break

            # Partial match if no exact match
            if not matching_stats:
                for stat_key, stat_value in player_stats[server_id][user_id].items():
                    if any(word.lower() in stat_key.lower() for word in normalized_dice_expression.split()):
                        matching_stats.append(stat_key)

            if not matching_stats:
                await ctx.send("No matching stat found and invalid dice expression.")
                return

            stat_name = matching_stats[0]
            current_value = player_stats[server_id][user_id][stat_name]

            if len(matching_stats) > 1:
                if len(matching_stats) <= 10:
                    matching_stats_str = "\n".join([f"{i+1}. {stat}" for i, stat in enumerate(matching_stats)])
                    embed = discord.Embed(
                        title="Multiple Matching Stats Found",
                        description=f"Your input matches multiple stats. Please specify one of the following:\n\n{matching_stats_str}",
                        color=discord.Color.red(),
                    )
                    message = await ctx.send(embed=embed)
                    emoji_list = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
                    for emoji in emoji_list[:len(matching_stats)]:
                        await message.add_reaction(emoji)

                    def check(reaction, user):
                        return user == ctx.author and str(reaction.emoji) in emoji_list

                    try:
                        reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
                        selected_stat_index = emoji_list.index(reaction.emoji)
                        stat_name = matching_stats[selected_stat_index]
                        current_value = player_stats[server_id][user_id][stat_name]
                        await message.delete()
                    except asyncio.TimeoutError:
                        await ctx.send("You took too long to react. Please run the command again.")
                        return
                    except Exception as e:
                        print(f"An error occurred: {e}")
                        return
                else:
                    await ctx.send(f"Found {len(matching_stats)} matching stats. Please specify more to narrow it down.")
                    return

            # Ask for Roll Type: Normal, Bonus, Penalty
            roll_type_embed = discord.Embed(
                title=f"Select Roll Type for {stat_name}",
                description="Choose the type of roll:\n🎲 **Normal Roll**\n🟢 **Bonus Die**\n🔴 **Penalty Die**",
                color=discord.Color.blue()
            )
            roll_type_message = await ctx.send(embed=roll_type_embed)
            await roll_type_message.add_reaction("🎲")
            await roll_type_message.add_reaction("🟢")
            await roll_type_message.add_reaction("🔴")

            def roll_type_check(reaction, user):
                return user == ctx.author and reaction.message.id == roll_type_message.id and str(reaction.emoji) in ["🎲", "🟢", "🔴"]

            roll_type = "normal"
            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=roll_type_check)
                if str(reaction.emoji) == "🟢":
                    roll_type = "bonus"
                elif str(reaction.emoji) == "🔴":
                    roll_type = "penalty"
                await roll_type_message.delete()
            except asyncio.TimeoutError:
                await ctx.send("Selection timed out. Cancelling roll.")
                await roll_type_message.delete()
                return

            # Perform the Roll
            ASKFORSESSION = 0
            SUCCESSFULLROLL = 0
            session_data = await load_session_data()
            if user_id not in session_data:
                ASKFORSESSION = 1

            roll = 0
            tens_rolls = []
            ones_roll = 0

            if roll_type == "normal":
                roll = random.randint(1, 100)
            else:
                tens_rolls = [random.randint(0, 9) * 10 for _ in range(2)]
                ones_roll = random.randint(1, 10)
                if roll_type == "bonus":
                    lower_tens_roll = min(tens_rolls)
                    roll = lower_tens_roll + ones_roll
                else: # penalty
                    higher_tens_roll = max(tens_rolls)
                    roll = higher_tens_roll + ones_roll

            result_text, result_tier = self.calculate_roll_result(roll, current_value)
            if result_tier >= 2:
                SUCCESSFULLROLL = 1

            formatted_luck = f":four_leaf_clover: LUCK: {player_stats[server_id][user_id]['LUCK']}"
            formatted_skill = f"**{stat_name}**: {current_value} - {current_value // 2} - {current_value // 5}"

            description_roll_info = f"{ctx.author.mention} :game_die: Rolled: {roll}"
            if roll_type != "normal":
                description_roll_info = f"{ctx.author.mention} :game_die: Rolled: {tens_rolls[0]}|{tens_rolls[1]} + {ones_roll} = {roll}"

            embed = discord.Embed(
                title=f"{ctx.author.display_name}'s {roll_type.capitalize()} Check for '{stat_name}{get_stat_emoji(stat_name)}'",
                description=f"{description_roll_info}\n{result_text}\n{formatted_skill}\n{formatted_luck}",
                color=discord.Color.green(),
            )

            # Interactions (Luck/Push) - ONLY for Normal Rolls
            can_push = False
            can_luck = False
            luck_target_tier = 0
            luck_cost = 0
            player_luck = player_stats[server_id][user_id]['LUCK']

            if roll_type == "normal":
                def update_luck_availability():
                    nonlocal can_luck, luck_target_tier, luck_cost
                    can_luck = False
                    if stat_name != "LUCK" and result_tier != 0: # Not Luck skill, Not Fumble
                        if result_tier == 1: # Fail -> Regular
                            target_val = current_value
                            luck_cost_temp = roll - target_val
                            if player_luck >= luck_cost_temp and luck_cost_temp <= luck_threshold:
                                can_luck = True
                                luck_target_tier = 2
                                luck_cost = luck_cost_temp
                        elif result_tier == 2: # Regular -> Hard
                            target_val = current_value // 2
                            luck_cost_temp = roll - target_val
                            if player_luck >= luck_cost_temp and luck_cost_temp <= luck_threshold:
                                can_luck = True
                                luck_target_tier = 3
                                luck_cost = luck_cost_temp
                        elif result_tier == 3: # Hard -> Extreme
                            target_val = current_value // 5
                            luck_cost_temp = roll - target_val
                            if player_luck >= luck_cost_temp and luck_cost_temp <= luck_threshold:
                                can_luck = True
                                luck_target_tier = 4
                                luck_cost = luck_cost_temp

                update_luck_availability()
                if stat_name != "LUCK" and result_tier == 1:
                     can_push = True

            # Send initial message
            if can_luck or can_push:
                instructions = "\n\nReact within 180s:"
                if can_luck:
                    instructions += "\n🍀 Use LUCK to improve success level"
                if can_push:
                    instructions += "\n🔄 PUSH the roll (Risk of Dire Consequences!)"
                embed.description += instructions

            message = await ctx.send(embed=embed)

            if can_luck: await message.add_reaction("🍀")
            if can_push: await message.add_reaction("🔄")

            loop = True
            while loop and (can_luck or can_push):
                def interaction_check(reaction, user):
                    return user == ctx.author and reaction.message.id == message.id and str(reaction.emoji) in ["🍀", "🔄"]

                try:
                    reaction, _ = await self.bot.wait_for("reaction_add", timeout=180, check=interaction_check)

                    if str(reaction.emoji) == "🍀" and can_luck:
                        # Apply Luck
                        player_stats[server_id][user_id]['LUCK'] -= luck_cost
                        player_luck = player_stats[server_id][user_id]['LUCK']

                        # Upgrade Result
                        if result_tier == 1:
                            result_tier = 2
                            result_text = "Regular Success (LUCK Used) :heavy_check_mark:"
                            SUCCESSFULLROLL = 1
                        elif result_tier == 2:
                            result_tier = 3
                            result_text = "Hard Success (LUCK Used) :white_check_mark:"
                        elif result_tier == 3:
                            result_tier = 4
                            result_text = "Extreme Success (LUCK Used) :star:"

                        roll -= luck_cost
                        formatted_luck = f":four_leaf_clover: LUCK: {player_luck}"
                        embed.description = f"{ctx.author.mention} :game_die: Rolled: {roll}\n{result_text}\n{formatted_skill}\n{formatted_luck}"

                        can_push = False
                        update_luck_availability()

                        instructions = ""
                        if can_luck:
                            instructions += "\n\nReact within 180s:\n🍀 Improve success level further"
                        embed.description += instructions

                        await message.edit(embed=embed)
                        await message.remove_reaction(reaction.emoji, ctx.author)

                        if not can_luck:
                            try: await message.clear_reactions()
                            except: pass
                            loop = False
                        else:
                            try: await message.clear_reaction("🔄")
                            except: pass

                    elif str(reaction.emoji) == "🔄" and can_push:
                        # Push Roll
                        roll = random.randint(1, 100)
                        result_text, result_tier = self.calculate_roll_result(roll, current_value)
                        description_add = f"\n\n**PUSHED ROLL**: {roll}\nResult: {result_text}"

                        if result_tier <= 1:
                            description_add += "\n:warning: **DIRE CONSEQUENCES!**"
                            SUCCESSFULLROLL = 0
                        else:
                            SUCCESSFULLROLL = 1

                        embed.description = f"{ctx.author.mention} :game_die: Original Roll Pushed.\n{formatted_skill}\n{formatted_luck}" + description_add
                        await message.edit(embed=embed)
                        try: await message.clear_reactions()
                        except: pass
                        loop = False

                except asyncio.TimeoutError:
                    try: await message.clear_reactions()
                    except: pass
                    loop = False

            await save_player_stats(player_stats)

            # Session Recording
            if SUCCESSFULLROLL == 1 and ASKFORSESSION == 1:
                session_message = await ctx.send(
                    "**Do you want to create a gaming session?**\n\nGaming session will record all your successful rolls for the character development phase."
                )
                await session_message.add_reaction("✅")
                await session_message.add_reaction("❌")

                def session_check(reaction, user):
                    return (user == ctx.author and str(reaction.emoji) in ["✅", "❌"])

                try:
                    reaction, _ = await self.bot.wait_for("reaction_add", timeout=30, check=session_check)
                    if str(reaction.emoji) == "✅":
                        session_data[user_id] = []
                        await save_session_data(session_data)
                        await ctx.send("Session started! The first successful roll has been recorded!")
                        await session_success(user_id, stat_name)
                    else:
                        await ctx.send("Session creation canceled.")
                except asyncio.TimeoutError:
                    await ctx.send("You took too long to react. The session will not be recorded.")

            elif SUCCESSFULLROLL == 1 and ASKFORSESSION == 0:
                await session_success(user_id, stat_name)
            else:
                pass

        except ValueError:
            embed = discord.Embed(
                title="Invalid Input",
                description=f"Use format {prefix}d <skill_name> or {prefix}d <expression>",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(newroll(bot))
