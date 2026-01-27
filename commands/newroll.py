import discord
import asyncio
import random
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

    @commands.command(aliases=["ND", "nd", "s"], guild_only=True)
    async def newroll(self, ctx, *, dice_expression):
        server_prefixes = await load_server_stats()
        server_id = str(ctx.guild.id)
        prefix = server_prefixes.get(server_id, "!") if server_id else "!"
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command is not allowed in DMs.")
            return
        user_id = str(ctx.author.id)

        player_stats = await load_player_stats()

        if user_id not in player_stats[server_id]:
            await ctx.send(
                f"{ctx.author.display_name} doesn't have an investigator. Use `{prefix}newInv` for creating a new investigator."
            )
        else:
            try:
                normalized_dice_expression = dice_expression.lower()
                matching_stats = []

                # Hledáme statistiky s dokonalým matchem
                for stat_key, stat_value in player_stats[server_id][
                        user_id].items():
                    if any(word.lower() == stat_key.lower()
                           for word in normalized_dice_expression.split()):
                        matching_stats.append(stat_key)
                        current_value = stat_value
                        break  # Ukončíme smyčku po prvním nalezeném dokonalém matchi

                # Pokud nemáme dokonalý match, použijeme druhý for loop
                if not matching_stats:
                    for stat_key, stat_value in player_stats[server_id][
                            user_id].items():
                        if any(word.lower() in stat_key.lower()
                               for word in normalized_dice_expression.split()):
                            matching_stats.append(stat_key)
                            current_value = stat_value

                print(len(matching_stats))
                if not matching_stats:
                    await ctx.send("No matching stat found.")
                    return

                stat_name = matching_stats[0]

                if len(matching_stats) > 1:
                    if len(matching_stats) <= 10:
                        matching_stats_str = "\n".join([
                            f"{i+1}. {stat}"
                            for i, stat in enumerate(matching_stats)
                        ])
                        embed = discord.Embed(
                            title="Multiple Matching Stats Found",
                            description=
                            f"Your input matches multiple stats. Please specify one of the following:\n\n{matching_stats_str}",
                            color=discord.Color.red(),
                        )

                        message = await ctx.send(embed=embed)

                        emoji_list = [
                            "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣",
                            "8️⃣", "9️⃣", "🔟"
                        ]
                        for emoji in emoji_list[:len(matching_stats)]:
                            await message.add_reaction(emoji)

                        # Čeká na reakci od původního autora zprávy
                        def check(reaction, user):
                            return (user == ctx.author
                                    and str(reaction.emoji) in emoji_list)

                        try:
                            reaction, _ = await self.bot.wait_for(
                                "reaction_add", timeout=60, check=check)

                            # Zpracuje reakci
                            selected_stat_index = emoji_list.index(
                                reaction.emoji)
                            stat_name = matching_stats[selected_stat_index]
                            current_value = player_stats[server_id][user_id][stat_name]
                            await message.delete()

                        except asyncio.TimeoutError:
                            await ctx.send(
                                "You took too long to react. Please run the command again."
                            )
                        except Exception as e:
                            print(f"An error occurred: {e}")

                    else:
                        await ctx.send(
                            f"Found {len(matching_stats)} matching stats. Please specify more to narrow it down."
                        )
                        return

                print(len(matching_stats))
                print(stat_name)

                ASKFORSESSION = 0
                SUCCESSFULLROLL = 0

                session_data = await load_session_data()
                if user_id not in session_data:
                    ASKFORSESSION = 1

                roll = random.randint(1, 100)

                if roll == 1:
                    result = "CRITICAL! :star2:"
                    SUCCESSFULLROLL = 1
                elif roll <= current_value // 5:
                    result = "Extreme Success :star:"
                    SUCCESSFULLROLL = 1
                elif roll <= current_value // 2:
                    result = "Hard Success :white_check_mark:"
                    SUCCESSFULLROLL = 1
                elif roll <= current_value:
                    result = "Regular Success :heavy_check_mark:"
                    SUCCESSFULLROLL = 1
                elif roll > 95:
                    result = "Fumble :warning:"
                else:
                    result = "Fail :x:"

                formatted_luck = f":four_leaf_clover: LUCK: {player_stats[server_id][user_id]['LUCK']}"
                formatted_skill = f"**{stat_name}**: {current_value} - {current_value // 2} - {current_value // 5}"

                embed = discord.Embed(
                    title=
                    f"{ctx.author.display_name}'s Skill Check for '{stat_name}{get_stat_emoji(stat_name)}'",
                    description=
                    f"{ctx.author.mention} :game_die: Rolled: {roll}\n{result}\n{formatted_skill}\n{formatted_luck}",
                    color=discord.Color.green(),
                )

                luck_stats = await load_luck_stats()
                LUCKTHR = luck_stats[
                    server_id] if server_id in luck_stats else 10
                if (roll > current_value and roll <= current_value + LUCKTHR
                        and player_stats[server_id][user_id]['LUCK']
                        >= roll - current_value and stat_name != "LUCK"):
                    difference = roll - current_value
                    prompt_embed = discord.Embed(
                        title="Use LUCK?",
                        description=
                        f"{ctx.author.mention} :game_die: Rolled: {roll}\n{result}\n{formatted_skill}\n{formatted_luck}\n\nYour roll is close to your skill (**{difference}**). Do you want to use LUCK to turn it into a Regular Success?\n"
                        "Reply with ✅ to use LUCK or ❌ to skip within 1 minute.",
                        color=discord.Color.orange(),
                    )
                    prompt_message = await ctx.send(embed=prompt_embed)
                    await prompt_message.add_reaction("✅")
                    await prompt_message.add_reaction("❌")

                    def check(reaction, user):
                        return user == ctx.author and reaction.message.id == prompt_message.id and str(
                            reaction.emoji) in ["✅", "❌"]

                    try:
                        reaction, _ = await self.bot.wait_for("reaction_add",
                                                              timeout=60,
                                                              check=check)
                        await prompt_message.delete()

                        if str(reaction.emoji) == "✅":
                            luck_used = min(
                                player_stats[server_id][user_id]['LUCK'],
                                difference)
                            player_stats[server_id][user_id][
                                'LUCK'] -= luck_used
                            formatted_luck = f":four_leaf_clover: LUCK: {player_stats[server_id][user_id]['LUCK']}"
                            result = "Regular Success (LUCK Used) :heavy_check_mark:"
                            current_value += luck_used
                            formatted_skill = f"**{stat_name}**: {current_value} - {current_value // 2} - {current_value // 5}"
                            SUCCESSFULLROLL = 1

                        else:
                            result = "Fail :x:"

                        embed = discord.Embed(
                            title=
                            f"{ctx.author.display_name}'s Skill Check for '{stat_name}'",
                            description=
                            f"{ctx.author.mention} :game_die: Rolled: {roll}\n{result}\n{formatted_skill}\n{formatted_luck}",
                            color=discord.Color.green(),
                        )
                    except asyncio.TimeoutError:
                        await prompt_message.delete()
                    except Exception as e:
                        print(f"An error occurred: {e}")
                await ctx.send(embed=embed)
                await save_player_stats(player_stats)
                if SUCCESSFULLROLL == 1 and ASKFORSESSION == 1:
                    session_message = await ctx.send(
                        "**Do you want to create a gaming session?**\n\nGaming session will record all your successful rolls for the character development phase."
                    )
                    await session_message.add_reaction("✅"
                                                       )  # Add checkmark emoji
                    await session_message.add_reaction("❌")  # Add X emoji

                    def check(reaction, user):
                        return (user == ctx.author
                                and str(reaction.emoji) in ["✅", "❌"])

                    try:
                        reaction, _ = await self.bot.wait_for("reaction_add",
                                                              timeout=30,
                                                              check=check)
                        if str(reaction.emoji) == "✅":
                            session_data[user_id] = []
                            await save_session_data(session_data)
                            await ctx.send(
                                "Session started! The first successful rolls have been recorded!"
                            )
                            await session_success(user_id, stat_name)
                        else:
                            await ctx.send("Session creation canceled.")
                    except asyncio.TimeoutError:
                        await ctx.send(
                            "You took too long to react. The session will not be recorded."
                        )

                elif SUCCESSFULLROLL == 1 and ASKFORSESSION == 0:
                    await session_success(user_id, stat_name)
                else:
                    pass

            except ValueError:
                embed = discord.Embed(
                    title="Invalid Input",
                    description=f"Use format {prefix}d <skill_name>",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(newroll(bot))
