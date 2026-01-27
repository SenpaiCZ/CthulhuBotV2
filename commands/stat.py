import discord
import re
import math
import asyncio
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats, load_server_stats, load_gamemode_stats
from emojis import get_stat_emoji


class stat(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["cstat"])
    async def stat(self, ctx, *args):
        """
        `[p]stat stat_name value_expression` - Change the value of a skill for your character.
        """
        server_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        player_stats = await load_player_stats()
        server_prefixes = await load_server_stats()
        prefix = server_prefixes.get(server_id, "!") if server_id else "!"

        # Kontrola, zda je příkaz používán ve správném kanálu
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command is not allowed in DMs.")
            return

        # Kontrola, zda jsou zadány argumenty
        if not args:
            await ctx.send(
                f"`{prefix}cstat stat-name` - Edit your investigators stats. (e.g. `{prefix}cstat STR 50` or `{prefix}cstat HP +1` or `{prefix}cstat SAN -5`)"
            )
            return

        # Kontrola, zda má hráč vytvořeného investigátora
        if user_id not in player_stats[server_id]:
            await ctx.send(
                f"{ctx.author.display_name} doesn't have an investigator. Use `{prefix}newInv` for creating a new investigator."
            )
            return

        # Získání hodnoty ze vstupního výrazu
        match = re.match(r'([+\-]?\d+)$', args[-1])

        if match:
            # Získání aktuální hodnoty statistiky
            current_value = 0
            matching_stats = []

            # Slova z poslední části příkazu (mimo posledního argumentu, což je hodnota)
            stat_name_words = args[:-1]

            # Hledáme statistiky s dokonalým matchem
            for stat_key, stat_value in player_stats[server_id][user_id].items(
            ):
                if all(word.lower() == stat_key.lower()
                       for word in stat_name_words):
                    matching_stats.append(stat_key)
                    current_value = stat_value
                    break  # Ukončíme smyčku po prvním nalezeném dokonalém matchi

            # Pokud nemáme dokonalý match, použijeme druhý for loop
            if not matching_stats:
                for stat_key, stat_value in player_stats[server_id][
                        user_id].items():
                    if any(word.lower() in stat_key.lower()
                           for word in stat_name_words):
                        matching_stats.append(stat_key)
                        current_value = stat_value

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
                        "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣",
                        "9️⃣", "🔟"
                    ]
                    for emoji in emoji_list[:len(matching_stats)]:
                        await message.add_reaction(emoji)

                    # Čeká na reakci od původního autora zprávy
                    def check(reaction, user):
                        return (user == ctx.author
                                and str(reaction.emoji) in emoji_list)

                    try:
                        reaction, _ = await self.bot.wait_for("reaction_add",
                                                              timeout=60,
                                                              check=check)

                        # Zpracuje reakci
                        selected_stat_index = emoji_list.index(reaction.emoji)
                        selected_stat = matching_stats[selected_stat_index]
                        matching_stats = [selected_stat]
                        #await message.delete()

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

            if len(matching_stats) == 1:
                # Zabránení změny jména na číslo
                if matching_stats[0] == "NAME":
                    await ctx.send(
                        f"You can not change your name with this command. Please, use `{prefix}rename` instead."
                    )
                    return

                # Získání hodnoty, kterou chceme přidat nebo odečíst
                change_value = int(match.group(1))

                stat_name = matching_stats[0]

                # Výpočet nové hodnoty podle předchozí logiky
                if args[-1].startswith('+') or args[-1].startswith('-'):
                    new_value = current_value + change_value
                else:
                    new_value = change_value
                    change_value = change_value - current_value

                stat_name = matching_stats[0]

                #loading game mode
                server_id = str(
                    ctx.guild.id)  # Get the server's ID as a string
                server_stats = await load_gamemode_stats()

                if server_id not in server_stats:
                    server_stats[server_id] = {}

                if 'game_mode' not in server_stats[server_id]:
                    server_stats[server_id][
                        'game_mode'] = 'Call of Cthulhu'  # Default to Call of Cthulhu

                current_mode = server_stats[server_id]['game_mode']

                #Surpassing MAX_HP in Call of Cthulhu
                if current_mode == 'Call of Cthulhu' and stat_name == "HP" and new_value > (
                        math.floor(
                            (player_stats[server_id][user_id]["CON"] +
                             player_stats[server_id][user_id]["SIZ"]) / 10)):
                    maxhp_message = await ctx.send(
                        f"Are you sure you want to surpass your **HP**:heartpulse: limit? \n ✅ - Go over the limit \n ❌ - Stop writing new value \n 📈 - Set value on your max"
                    )
                    await maxhp_message.add_reaction("✅")
                    await maxhp_message.add_reaction("❌")
                    await maxhp_message.add_reaction("📈")

                    def check(reaction, user):
                        return user == ctx.author and reaction.message.id == maxhp_message.id and str(
                            reaction.emoji) in ["✅", "❌", "📈"]

                    try:
                        reaction, _ = await self.bot.wait_for("reaction_add",
                                                              timeout=60,
                                                              check=check)
                        if str(reaction.emoji) == "✅":
                            #await ctx.send(f"✅")
                            pass
                        elif str(reaction.emoji) == "📈":
                            new_value = math.floor(
                                (player_stats[server_id][user_id]["CON"] +
                                 player_stats[server_id][user_id]["SIZ"]) / 10)
                            change_value = new_value - current_value
                            pass

                        elif str(reaction.emoji) == "❌":
                            await ctx.send(
                                f"**HP**:heartpulse: will not be saved.")
                            return
                    except asyncio.TimeoutError:
                        await ctx.send(
                            f"{ctx.author.display_name} took too long to react. **HP**:heartpulse: will not be saved."
                        )

                #Surpassing MAX_HP in Pulp of Cthulhu
                if current_mode == 'Pulp of Cthulhu' and stat_name == "HP" and new_value > (
                        math.floor(
                            (player_stats[server_id][user_id]["CON"] +
                             player_stats[server_id][user_id]["SIZ"]) / 5)):
                    maxhp_message = await ctx.send(
                        f"Are you sure you want to surpass your **HP**:heartpulse: limit? \n ✅ - Go over the limit \n ❌ - Stop writing new value \n 📈 - Set value on your max"
                    )
                    await maxhp_message.add_reaction("✅")
                    await maxhp_message.add_reaction("❌")
                    await maxhp_message.add_reaction("📈")

                    def check(reaction, user):
                        return user == ctx.author and reaction.message.id == maxhp_message.id and str(
                            reaction.emoji) in ["✅", "❌", "📈"]

                    try:
                        reaction, _ = await self.bot.wait_for("reaction_add",
                                                              timeout=60,
                                                              check=check)
                        if str(reaction.emoji) == "✅":
                            #await ctx.send(f"✅")
                            pass
                        elif str(reaction.emoji) == "📈":
                            new_value = math.floor(
                                (player_stats[server_id][user_id]["CON"] +
                                 player_stats[server_id][user_id]["SIZ"]) / 5)
                            change_value = new_value - current_value
                            pass

                        elif str(reaction.emoji) == "❌":
                            await ctx.send(
                                f"**HP**:heartpulse: will not be saved.")
                            return
                    except asyncio.TimeoutError:
                        await ctx.send(
                            f"{ctx.author.display_name} took too long to react. **HP**:heartpulse: will not be saved."
                        )

                #Surpassing MAX_MP
                if stat_name == "MP" and new_value > (math.floor(
                        player_stats[server_id][user_id]["POW"] / 5)):
                    maxmp_message = await ctx.send(
                        f"Are you sure you want to surpass your **MP**:sparkles: limit? \n ✅ - Confirm and exceed the limit \n ❌ - Cancel and keep the current value\n 📈 - Set the value to the maximum allowed"
                    )
                    await maxmp_message.add_reaction("✅")
                    await maxmp_message.add_reaction("❌")
                    await maxmp_message.add_reaction("📈")

                    def check(reaction, user):
                        return user == ctx.author and reaction.message.id == maxmp_message.id and str(
                            reaction.emoji) in ["✅", "❌", "📈"]

                    try:
                        reaction, _ = await self.bot.wait_for("reaction_add",
                                                              timeout=60,
                                                              check=check)
                        if str(reaction.emoji) == "✅":
                            # await ctx.send(f"✅")
                            pass
                        elif str(reaction.emoji) == "📈":
                            new_value = math.floor(
                                player_stats[server_id][user_id]["POW"] / 5)
                            change_value = new_value - current_value
                            pass

                        elif str(reaction.emoji) == "❌":
                            await ctx.send(
                                f"**MP**:sparkles: will not be saved.")
                            return
                    except asyncio.TimeoutError:
                        await ctx.send(
                            f"{ctx.author.display_name} took too long to react. **MP**:sparkles: will not be saved."
                        )

                #Surpassing MAX_SAN
                if stat_name == "SAN" and new_value > (
                        99 -
                        player_stats[server_id][user_id]["Cthulhu Mythos"]):
                    maxsan_message = await ctx.send(
                        f"Are you sure you want to surpass your **SAN**:scales: limit? \n ✅ - Confirm and exceed the limit \n ❌ - Cancel and keep the current value\n 📈 - Set the value to the maximum allowed"
                    )
                    await maxsan_message.add_reaction("✅")
                    await maxsan_message.add_reaction("❌")
                    await maxsan_message.add_reaction("📈")

                    def check(reaction, user):
                        return user == ctx.author and reaction.message.id == maxsan_message.id and str(
                            reaction.emoji) in ["✅", "❌", "📈"]

                    try:
                        reaction, _ = await self.bot.wait_for("reaction_add",
                                                              timeout=60,
                                                              check=check)
                        if str(reaction.emoji) == "✅":
                            # await ctx.send(f"✅")
                            pass
                        elif str(reaction.emoji) == "📈":
                            new_value = player_stats[server_id][user_id][
                                "POW"] - player_stats[server_id][user_id][
                                    "Cthulhu Mythos"]
                            change_value = new_value - current_value
                            pass

                        elif str(reaction.emoji) == "❌":
                            await ctx.send(
                                f"**SAN**:scales: will not be saved.")
                            return
                    except asyncio.TimeoutError:
                        await ctx.send(
                            f"{ctx.author.display_name} took too long to react. **SAN**:scales: will not be saved."
                        )

                # Aktualizace hodnoty v player_stats
                player_stats[server_id][user_id][matching_stats[0]] = new_value

                # Uložení změn
                await save_player_stats(player_stats)

                # Příprava barvy pro Embed
                color = discord.Color.green(
                ) if change_value >= 0 else discord.Color.red()

                # Příprava jména statu s emodži
                stat_name_with_emoji = f"{get_stat_emoji(matching_stats[0])} {matching_stats[0]}"

                # Příprava Embedu
                embed = discord.Embed(
                    title=f"Stat Change - {stat_name_with_emoji}",
                    description=
                    f"**{ctx.author.display_name}**, you've updated your '{matching_stats[0]}' stat.",
                    color=color)
                embed.add_field(name="Previous Value",
                                value=current_value,
                                inline=False)
                embed.add_field(name="Change",
                                value=f"{change_value}",
                                inline=False)
                embed.add_field(name="New Value",
                                value=new_value,
                                inline=False)

                # Odeslání Embedu
                await ctx.send(embed=embed)

                #automatic calculation of HP
                if stat_name == "CON" or stat_name == "SIZ":
                    if player_stats[server_id][user_id][
                            "CON"] != 0 and player_stats[server_id][user_id][
                                "SIZ"] != 0 and player_stats[server_id][
                                    user_id]["HP"] == 0:
                        hp_message = await ctx.send(
                            f"{ctx.author.display_name} filled all stats required to calculate **HP**:heartpulse:. Do you want me to calculate HP:heartpulse:?"
                        )
                        await hp_message.add_reaction("✅")
                        await hp_message.add_reaction("❌")

                        def check(reaction, user):
                            return user == ctx.author and reaction.message.id == hp_message.id and str(
                                reaction.emoji) in ["✅", "❌"]

                        try:
                            reaction, _ = await self.bot.wait_for(
                                "reaction_add", timeout=60, check=check)
                            if str(reaction.emoji) == "✅":
                                HP = math.floor(
                                    (player_stats[server_id][user_id]["CON"] +
                                     player_stats[server_id][user_id]["SIZ"]) /
                                    10)
                                player_stats[server_id][user_id]["HP"] = HP
                                await save_player_stats(
                                    player_stats
                                )  # Save the data to the JSON file
                                await ctx.send(
                                    f"{ctx.author.display_name}'s **HP**:heartpulse: has been calculated as **{HP}** and successfully saved."
                                )
                            elif str(reaction.emoji) == "❌":
                                await ctx.send(
                                    f"The calculation of **HP**:heartpulse: will not proceed."
                                )
                        except asyncio.TimeoutError:
                            await ctx.send(
                                f"{ctx.author.display_name} took too long to react. The calculation of **HP**:heartpulse: will not proceed."
                            )

                #automatic calculation of MP
                if stat_name == "POW":
                    if player_stats[server_id][user_id][
                            "POW"] != 0 and player_stats[server_id][user_id][
                                "MP"] == 0:
                        mp_message = await ctx.send(
                            f"{ctx.author.display_name} filled all stats required to calculate **MP**:sparkles:. Do you want me to calculate MP:sparkles:?"
                        )
                        await mp_message.add_reaction("✅")
                        await mp_message.add_reaction("❌")

                        def check(reaction, user):
                            return user == ctx.author and reaction.message.id == mp_message.id and str(
                                reaction.emoji) in ["✅", "❌"]

                        try:
                            reaction, _ = await self.bot.wait_for(
                                "reaction_add", timeout=60, check=check)
                            if str(reaction.emoji) == "✅":
                                MP = math.floor(
                                    player_stats[server_id][user_id]["POW"] /
                                    5)
                                player_stats[server_id][user_id]["MP"] = MP
                                await save_player_stats(
                                    player_stats
                                )  # Save the data to the JSON file
                                await ctx.send(
                                    f"{ctx.author.display_name}'s **MP**:sparkles: has been calculated as **{MP}** and successfully saved."
                                )
                            elif str(reaction.emoji) == "❌":
                                await ctx.send(
                                    f"The calculation of **MP**:sparkles: will not proceed."
                                )
                        except asyncio.TimeoutError:
                            await ctx.send(
                                f"{ctx.author.display_name} took too long to react. The calculation of **MP**:sparkles: will not proceed."
                            )

                #automatic calculation of SAN
                if stat_name == "POW":
                    if player_stats[server_id][user_id][
                            "POW"] != 0 and player_stats[server_id][user_id][
                                "SAN"] == 0:
                        san_message = await ctx.send(
                            f"{ctx.author.display_name} filled all stats required to calculate **SAN**:scales:. Do you want me to calculate SAN:scales:?"
                        )
                        await san_message.add_reaction("✅")
                        await san_message.add_reaction("❌")

                        def check(reaction, user):
                            return user == ctx.author and reaction.message.id == san_message.id and str(
                                reaction.emoji) in ["✅", "❌"]

                        try:
                            reaction, _ = await self.bot.wait_for(
                                "reaction_add", timeout=60, check=check)
                            if str(reaction.emoji) == "✅":
                                SAN = player_stats[server_id][user_id]["POW"]
                                player_stats[server_id][user_id]["SAN"] = SAN
                                await save_player_stats(
                                    player_stats
                                )  # Save the data to the JSON file
                                await ctx.send(
                                    f"{ctx.author.display_name}'s **SAN**:scales: has been calculated as **{SAN}** and successfully saved."
                                )
                            elif str(reaction.emoji) == "❌":
                                await ctx.send(
                                    f"The calculation of **SAN**:scales: will not proceed."
                                )
                        except asyncio.TimeoutError:
                            await ctx.send(
                                f"{ctx.author.display_name} took too long to react. The calculation of **SAN**:scales: will not proceed."
                            )
                #automatic calculation of Dodge
                if stat_name == "DEX":
                    if player_stats[server_id][user_id][
                            "DEX"] != 0 and player_stats[server_id][user_id][
                                "Dodge"] == 0:
                        dod_message = await ctx.send(
                            f"{ctx.author.display_name} filled all stats required to calculate **Dodge**:warning:. Do you want me to calculate Dodge:warning:?"
                        )
                        await dod_message.add_reaction("✅")
                        await dod_message.add_reaction("❌")

                        def check(reaction, user):
                            return user == ctx.author and reaction.message.id == dod_message.id and str(
                                reaction.emoji) in ["✅", "❌"]

                        try:
                            reaction, _ = await self.bot.wait_for(
                                "reaction_add", timeout=60, check=check)
                            if str(reaction.emoji) == "✅":
                                DODGE = math.floor(
                                    player_stats[server_id][user_id]["DEX"] /
                                    2)
                                player_stats[server_id][user_id][
                                    "Dodge"] = DODGE
                                await save_player_stats(
                                    player_stats
                                )  # Save the data to the JSON file
                                await ctx.send(
                                    f"{ctx.author.display_name}'s **Dodge**:warning: has been calculated as **{DODGE}** and successfully saved."
                                )
                            elif str(reaction.emoji) == "❌":
                                await ctx.send(
                                    f"The calculation of **Dodge**:warning: will not proceed."
                                )
                        except asyncio.TimeoutError:
                            await ctx.send(
                                f"{ctx.author.display_name} took too long to react. The calculation of **Dodge**:warning: will not proceed."
                            )

                #automatic calculation of Language (own)
                if stat_name == "EDU":
                    if player_stats[server_id][user_id][
                            "EDU"] != 0 and player_stats[server_id][user_id][
                                "Language own"] == 0:
                        dod_message = await ctx.send(
                            f"{ctx.author.display_name} filled all stats required to calculate **Language own**:speech_balloon:. Do you want me to calculate Language own:speech_balloon:?"
                        )
                        await dod_message.add_reaction("✅")
                        await dod_message.add_reaction("❌")

                        def check(reaction, user):
                            return user == ctx.author and reaction.message.id == dod_message.id and str(
                                reaction.emoji) in ["✅", "❌"]

                        try:
                            reaction, _ = await self.bot.wait_for(
                                "reaction_add", timeout=60, check=check)
                            if str(reaction.emoji) == "✅":
                                LANGUAGEOWN = player_stats[server_id][user_id][
                                    "EDU"]
                                player_stats[server_id][user_id][
                                    "Language own"] = LANGUAGEOWN
                                await save_player_stats(
                                    player_stats
                                )  # Save the data to the JSON file
                                await ctx.send(
                                    f"{ctx.author.display_name}'s **Language own**:speech_balloon: has been calculated as **{LANGUAGEOWN}** and successfully saved."
                                )
                            elif str(reaction.emoji) == "❌":
                                await ctx.send(
                                    f"The calculation of **Language own**:speech_balloon: will not proceed."
                                )
                        except asyncio.TimeoutError:
                            await ctx.send(
                                f"{ctx.author.display_name} took too long to react. The calculation of **Language own**:speech_balloon: will not proceed."
                            )
                #Prompt about Age
                if stat_name == "STR" or stat_name == "DEX" or stat_name == "CON" or stat_name == "EDU" or stat_name == "APP" or stat_name == "SIZ" or stat_name == "LUCK":
                    if player_stats[server_id][user_id]["STR"] != 0 and player_stats[
                            server_id][user_id]["DEX"] != 0 and player_stats[
                                server_id][user_id]["CON"] != 0 and player_stats[
                                    server_id][user_id][
                                        "EDU"] != 0 and player_stats[server_id][
                                            user_id]["APP"] != 0 and player_stats[
                                                server_id][user_id][
                                                    "SIZ"] != 0 and player_stats[
                                                        server_id][user_id][
                                                            "LUCK"] and player_stats[
                                                                server_id][
                                                                    user_id][
                                                                        "Age"] == 0:
                        await ctx.send(
                            f"{ctx.author.display_name} filled all stats that are affected by Age. Fill your age with `{prefix}cstat Age`"
                        )

                #Age mod help
                if stat_name == "Age":
                    if player_stats[server_id][user_id]["Age"] < 15:
                        await ctx.send(
                            f"Age Modifiers: There are no official rules about investigators under 15 years old. Ignore this if you play Pulp of Cthulhu."
                        )
                    elif player_stats[server_id][user_id]["Age"] < 20:
                        await ctx.send(
                            f"Age Modifiers: Deduct 5 points among STR:muscle: and SIZ:bust_in_silhouette:. Deduct 5 points from EDU:mortar_board:. Roll twice to generate a Luck score and use the higher value. Ignore this if you play Pulp of Cthulhu."
                        )
                    elif player_stats[server_id][user_id]["Age"] < 40:
                        await ctx.send(
                            f"Age Modifiers: Make an improvement check for EDU:mortar_board:. Ignore this if you play Pulp of Cthulhu."
                        )
                        await ctx.send(
                            f"To make improvement check for EDU:mortar_board: run `{prefix}d EDU`. I you FAIL:x: add `{prefix}d 1D10` to your EDU:mortar_board:. "
                        )
                    elif player_stats[server_id][user_id]["Age"] < 50:
                        await ctx.send(
                            f"Age Modifiers: Make 2 improvement checks for EDU:mortar_board: and deduct 5 points among STR:muscle:, CON:heart: or DEX:runner:, and reduce APP:heart_eyes: by 5. Ignore this if you play Pulp of Cthulhu."
                        )
                        await ctx.send(
                            f"To make improvement check for EDU:mortar_board: run `{prefix}d EDU`. I you FAIL:x: add `{prefix}d 1D10` to your EDU:mortar_board:."
                        )
                    elif player_stats[server_id][user_id]["Age"] < 60:
                        await ctx.send(
                            f"Age Modifiers: Make 3 improvement checks for EDU:mortar_board: and deduct 10 points among STR:muscle:, CON:heart: or DEX:runner:, and reduce APP:heart_eyes: by 10. Ignore this if you play Pulp of Cthulhu."
                        )
                        await ctx.send(
                            f"To make improvement check for EDU:mortar_board: run `{prefix}d EDU`. I you FAIL:x: add `{prefix}d 1D10` to your EDU:mortar_board:."
                        )
                    elif player_stats[server_id][user_id]["Age"] < 70:
                        await ctx.send(
                            f"Age Modifiers: Make 4 improvement checks for EDU:mortar_board: and deduct 20 points among STR:muscle:, CON:heart: or DEX:runner:, and reduce APP:heart_eyes: by 15. Ignore this if you play Pulp of Cthulhu."
                        )
                        await ctx.send(
                            f"To make improvement check for EDU:mortar_board: run `{prefix}d EDU`. I you FAIL:x: add `{prefix}d 1D10` to your EDU:mortar_board:."
                        )
                    elif player_stats[server_id][user_id]["Age"] < 80:
                        await ctx.send(
                            f"Age Modifiers:  Make 4 improvement checks for EDU:mortar_board: and deduct 40 points among STR:muscle:, CON:heart: or DEX:runner:, and reduce APP:heart_eyes: by 20. Ignore this if you play Pulp of Cthulhu."
                        )
                        await ctx.send(
                            f"To make improvement check for EDU:mortar_board: run `{prefix}d EDU`. I you FAIL:x: add `{prefix}d 1D10` to your EDU:mortar_board:."
                        )
                    elif player_stats[server_id][user_id]["Age"] < 90:
                        await ctx.send(
                            f"Age Modifiers: Make 4 improvement checks for EDU:mortar_board: and deduct 80 points among STR:muscle:, CON:heart: or DEX:runner:, and reduce APP:heart_eyes: by 25. Ignore this if you play Pulp of Cthulhu."
                        )
                        await ctx.send(
                            f"To make improvement check for EDU:mortar_board: run `{prefix}d EDU`. I you FAIL:x: add `{prefix}d 1D10` to your EDU:mortar_board:."
                        )
                    else:
                        await ctx.send(
                            f"Age Modifiers: There are no official rules about investigators above the age of 90. Ignore this if you play Pulp of Cthulhu."
                        )

            elif len(matching_stats) > 1:
                # Nalezeno více shodujících se statů, vyžaduje přesnější příkaz
                stats_list = ', '.join(matching_stats)
                await ctx.send(
                    f"Zadaný název statu se shoduje s více statistikami: {stats_list}. Zadejte přesnější název."
                )
            else:
                await ctx.send(
                    f"Stat s názvem '{' '.join(stat_name_words)}' nebyl nalezen."
                )
        else:
            # Vstupní výraz neodpovídá očekávanému formátu
            await ctx.send(
                "Nesprávný formát výrazu pro změnu hodnoty. Použijte například `!stat HP +5`, `!stat HP -5` nebo `!stat HP 5`."
            )


async def setup(bot):
    await bot.add_cog(stat(bot))
