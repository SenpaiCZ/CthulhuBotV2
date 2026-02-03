import discord
import asyncio
import random
import math
import emojis
import occupation_emoji
from discord.ext import commands
from loadnsave import (
    load_player_stats, save_player_stats,
    load_retired_characters_data, save_retired_characters_data,
    load_occupations_data
)

class newinvestigator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_input(self, ctx, prompt, check=None, timeout=300):
        """Helper to get input from the user."""
        await ctx.send(prompt)

        if check is None:
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=timeout)
            return msg.content
        except asyncio.TimeoutError:
            await ctx.send("Character creation timed out.")
            return None

    @commands.command(aliases=["newInv", "newinv"])
    async def newinvestigator(self, ctx):
        """
        🕵️‍♂️ Starts the character creation wizard.
        """
        user_id = str(ctx.author.id)
        server_id = str(ctx.guild.id)

        # Load stats
        player_stats = await load_player_stats()

        # Check for existing character
        if server_id in player_stats and user_id in player_stats[server_id]:
            existing_char = player_stats[server_id][user_id]
            char_name = existing_char.get("NAME", "Unknown")

            response = await self.get_input(
                ctx,
                f"You already have an investigator named **{char_name}**. \n"
                "Do you want to **retire** this character to create a new one? (yes/no)"
            )

            if response is None: return

            if response.lower() in ["yes", "y"]:
                # Retirement logic
                retired_characters = await load_retired_characters_data()
                if user_id not in retired_characters:
                    retired_characters[user_id] = []

                # Pop the character and save to retired
                character_data = player_stats[server_id].pop(user_id)
                retired_characters[user_id].append(character_data)

                await save_retired_characters_data(retired_characters)
                await save_player_stats(player_stats)
                await ctx.send(f"**{char_name}** has been retired.")
            else:
                await ctx.send("Character creation cancelled. You kept your current investigator.")
                return

        # Ensure server entry exists
        if server_id not in player_stats:
            player_stats[server_id] = {}

        # Step 1: Character Name
        name = await self.get_input(ctx, "Please enter the **Name** of your new investigator:")
        if name is None: return

        # Initialize basic character structure
        new_char = {
            "NAME": name,
            "STR": 0, "DEX": 0, "CON": 0, "INT": 0, "POW": 0, "EDU": 0, "SIZ": 0, "APP": 0,
            "SAN": 0, "HP": 0, "MP": 0, "LUCK": 0,
            "Move": 0, "Build": 0, "Damage Bonus": 0,
            "Age": 0,
            "Occupation": "Unknown",
            "Credit Rating": 0,
        }

        # Populate default skills (Hardcoded to match original behavior)
        default_skills = {
            "Accounting": 5, "Anthropology": 1, "Appraise": 5, "Archaeology": 1, "Charm": 15,
            "Art/Craft": 5, "Climb": 20, "Credit Rating": 0, "Cthulhu Mythos": 0, "Disguise": 5,
            "Dodge": 0, "Drive Auto": 20, "Elec. Repair": 10, "Fast Talk": 5, "Fighting Brawl": 25,
            "Firearms Handgun": 20, "Firearms Rifle/Shotgun": 25, "First Aid": 30, "History": 5,
            "Intimidate": 15, "Jump": 10, "Language other": 1, "Language own": 0, "Law": 5,
            "Library Use": 20, "Listen": 20, "Locksmith": 1, "Mech. Repair": 10, "Medicine": 1,
            "Natural World": 10, "Navigate": 10, "Occult": 5, "Persuade": 10, "Pilot": 1,
            "Psychoanalysis": 1, "Psychology": 10, "Ride": 5, "Science specific": 1,
            "Sleight of Hand": 10, "Spot Hidden": 25, "Stealth": 20, "Survival": 10, "Swim": 20,
            "Throw": 20, "Track": 10, "CustomSkill": 0, "CustomSkills": 0, "CustomSkillss": 0,
            "Backstory": {
                'My Story': [], 'Personal Description': [], 'Ideology and Beliefs': [],
                'Significant People': [], 'Meaningful Locations': [], 'Treasured Possessions': [],
                'Traits': [], 'Injuries and Scars': [], 'Phobias and Manias': [],
                'Arcane Tome and Spells': [], 'Encounters with Strange Entities': [],
                'Fellow Investigators': [], 'Gear and Possessions': [],
                'Spending Level': [], 'Cash': [], 'Assets': [],
            }
        }
        new_char.update(default_skills)

        await ctx.send(f"Welcome, **{name}**. Let's determine your statistics.")

        # Mode Selection
        await self.select_mode(ctx, new_char, player_stats)

    async def select_mode(self, ctx, char_data, player_stats):
        prompt = (
            "Please choose a method for generating statistics:\n"
            "1. **Full Auto**: Completely random rolls.\n"
            "2. **Quick Fire**: Assign standard values (40, 50, 50, 50, 60, 60, 70, 80).\n"
            "3. **Assisted**: Roll each stat one by one with one reroll allowed.\n"
            "4. **Forced**: Manually enter specific values.\n\n"
            "Type the **name** or **number** of the mode."
        )
        mode_input = await self.get_input(ctx, prompt)
        if mode_input is None: return

        mode = mode_input.lower()
        if "1" in mode or "auto" in mode:
            await self.mode_full_auto(ctx, char_data)
        elif "2" in mode or "quick" in mode:
            await self.mode_quick_fire(ctx, char_data)
        elif "3" in mode or "assist" in mode:
            await self.mode_assisted(ctx, char_data)
        elif "4" in mode or "force" in mode:
            await self.mode_forced(ctx, char_data)
        else:
            await ctx.send("Invalid mode selected. Please try `!newinv` again.")
            return

        # Proceed to Age Selection
        await self.select_age(ctx, char_data, player_stats)

    async def mode_full_auto(self, ctx, char_data):
        char_data["STR"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        char_data["CON"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        char_data["SIZ"] = 5 * (sum([random.randint(1, 6) for _ in range(2)]) + 6)
        char_data["DEX"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        char_data["APP"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        char_data["INT"] = 5 * (sum([random.randint(1, 6) for _ in range(2)]) + 6)
        char_data["POW"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        char_data["EDU"] = 5 * (sum([random.randint(1, 6) for _ in range(2)]) + 6)
        char_data["LUCK"] = 5 * sum([random.randint(1, 6) for _ in range(3)])

        await self.display_stats(ctx, char_data)

    async def mode_forced(self, ctx, char_data):
        stats = ["STR", "CON", "SIZ", "DEX", "APP", "INT", "POW", "EDU", "LUCK"]
        await ctx.send("Enter values for stats (range 0-100).")

        for stat in stats:
            while True:
                val = await self.get_input(ctx, f"**{stat}**: ")
                if val is None: return # Timeout
                if val.isdigit() and 0 <= int(val) <= 999: # Allow high values just in case
                    char_data[stat] = int(val)
                    break
                else:
                    await ctx.send("Invalid number. Try again.")

        await self.display_stats(ctx, char_data)

    async def mode_quick_fire(self, ctx, char_data):
        values = [40, 50, 50, 50, 60, 60, 70, 80]
        stats = ["STR", "CON", "SIZ", "DEX", "APP", "INT", "POW", "EDU"]

        # Luck is rolled 3D6 * 5
        char_data["LUCK"] = 5 * sum([random.randint(1, 6) for _ in range(3)])

        await ctx.send(f"**Quick Fire Mode**\nValues to assign: {values}\nLuck has been rolled: {char_data['LUCK']}")

        for stat in stats:
            while True:
                prompt = f"Assign a value to **{stat}**. Available: {values}"
                val_input = await self.get_input(ctx, prompt)
                if val_input is None: return

                if val_input.isdigit() and int(val_input) in values:
                    val = int(val_input)
                    char_data[stat] = val
                    values.remove(val)
                    break
                else:
                    await ctx.send("Invalid value or value already used. Please choose from the list.")

        await self.display_stats(ctx, char_data)

    async def mode_assisted(self, ctx, char_data):
        # Strictly standard formulas
        # STR, DEX, CON, APP, POW: 3D6 * 5
        # SIZ, INT, EDU: (2D6 + 6) * 5

        stat_formulas = {
            "STR": "3D6 * 5", "DEX": "3D6 * 5", "CON": "3D6 * 5", "APP": "3D6 * 5", "POW": "3D6 * 5",
            "SIZ": "(2D6 + 6) * 5", "INT": "(2D6 + 6) * 5", "EDU": "(2D6 + 6) * 5"
        }

        # Luck
        char_data["LUCK"] = random.randint(3, 18) * 5
        await ctx.send(f"**Assisted Mode**\nLuck rolled: {char_data['LUCK']}")

        for stat, formula in stat_formulas.items():
            # Roll function
            def roll_stat(f):
                if f == "3D6 * 5":
                    return sum([random.randint(1, 6) for _ in range(3)]) * 5
                elif f == "(2D6 + 6) * 5":
                    return (sum([random.randint(1, 6) for _ in range(2)]) + 6) * 5
                return 0

            val = roll_stat(formula)
            prompt = f"**{stat}** ({formula}) rolled: **{val}**. Keep or Reroll? (k/r)"
            choice = await self.get_input(ctx, prompt)
            if choice is None: return

            if choice.lower() in ["r", "reroll"]:
                new_val = roll_stat(formula)
                await ctx.send(f"Rerolled: **{new_val}** (Previous: {val}). Keeping new value.")
                char_data[stat] = new_val
            else:
                char_data[stat] = val

        await self.display_stats(ctx, char_data)

    async def display_stats(self, ctx, char_data):
        embed = discord.Embed(title=f"Stats for {char_data['NAME']}", color=discord.Color.green())
        stats_list = ["STR", "DEX", "CON", "APP", "POW", "SIZ", "INT", "EDU", "LUCK"]
        desc = "\n".join([f"{emojis.get_stat_emoji(s)} **{s}**: {char_data.get(s, 0)}" for s in stats_list])
        embed.description = desc
        await ctx.send(embed=embed)

    async def select_age(self, ctx, char_data, player_stats):
        while True:
            age_input = await self.get_input(ctx, "Enter your investigator's **Age** (15-90):")
            if age_input is None: return
            if age_input.isdigit():
                age = int(age_input)
                if 15 <= age <= 90:
                    char_data["Age"] = age
                    break
            await ctx.send("Invalid age. Please enter a number between 15 and 90.")

        await self.apply_age_modifiers(ctx, char_data, age)

        # Proceed to Occupation Selection
        await self.select_occupation(ctx, char_data, player_stats)

    async def apply_age_modifiers(self, ctx, char_data, age):
        # EDU Improvement Checks
        edu_checks = 0
        if 20 <= age <= 39: edu_checks = 1
        elif 40 <= age <= 49: edu_checks = 2
        elif 50 <= age <= 59: edu_checks = 3
        elif age >= 60: edu_checks = 4

        if edu_checks > 0:
            await ctx.send(f"Performing **{edu_checks}** EDU improvement check(s)...")
            for i in range(edu_checks):
                roll = random.randint(1, 100)
                current_edu = char_data["EDU"]
                if roll > current_edu:
                    gain = random.randint(1, 10)
                    char_data["EDU"] = min(99, current_edu + gain)
                    await ctx.send(f"Check {i+1}: Rolled {roll} (> {current_edu}). **Success!** Gained {gain} EDU. New EDU: {char_data['EDU']}")
                else:
                    await ctx.send(f"Check {i+1}: Rolled {roll} (<= {current_edu}). No improvement.")

        # Young Investigator (15-19)
        if 15 <= age <= 19:
            await ctx.send("Young Investigator adjustments: STR -5, SIZ -5, EDU -5. Luck rolled twice (taking best).")
            char_data["STR"] = max(0, char_data["STR"] - 5)
            char_data["SIZ"] = max(0, char_data["SIZ"] - 5)
            char_data["EDU"] = max(0, char_data["EDU"] - 5)

            # Luck Improvement
            new_luck = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])) # 3D6*5
            if new_luck > char_data["LUCK"]:
                await ctx.send(f"Rolled new Luck: {new_luck} (Old: {char_data['LUCK']}). Taking higher value.")
                char_data["LUCK"] = new_luck
            else:
                await ctx.send(f"Rolled new Luck: {new_luck} (Old: {char_data['LUCK']}). Keeping old value.")

        # Aging Effects (40+)
        deduction = 0
        app_penalty = 0
        if 40 <= age <= 49:
            deduction = 5
            app_penalty = 5
        elif 50 <= age <= 59:
            deduction = 10
            app_penalty = 10
        elif 60 <= age <= 69:
            deduction = 20
            app_penalty = 15
        elif 70 <= age <= 79:
            deduction = 40
            app_penalty = 20
        elif age >= 80:
            deduction = 80
            app_penalty = 25

        if app_penalty > 0:
            char_data["APP"] = max(0, char_data["APP"] - app_penalty)
            await ctx.send(f"Due to age, APP reduced by {app_penalty}. New APP: {char_data['APP']}")

        if deduction > 0:
            await ctx.send(f"Due to age, you must deduct a total of **{deduction}** points from **STR**, **CON**, or **DEX**.")
            await self.deduct_stats(ctx, char_data, deduction)

        # Recalculate Base Skills dependent on stats
        # Dodge = DEX / 2
        # Language Own = EDU
        char_data["Dodge"] = char_data["DEX"] // 2
        char_data["Language own"] = char_data["EDU"]

        await self.display_stats(ctx, char_data)

    async def deduct_stats(self, ctx, char_data, total_deduction):
        remaining = total_deduction
        stats_to_reduce = ["STR", "CON", "DEX"]

        while remaining > 0:
            prompt = (
                f"Points remaining to deduct: **{remaining}**\n"
                f"Current Stats: STR: {char_data['STR']}, CON: {char_data['CON']}, DEX: {char_data['DEX']}\n"
                "Type `STR 5` to deduct 5 from STR, etc."
            )
            val_input = await self.get_input(ctx, prompt)
            if val_input is None: return

            parts = val_input.split()
            if len(parts) == 2 and parts[0].upper() in stats_to_reduce and parts[1].isdigit():
                stat = parts[0].upper()
                amount = int(parts[1])

                if amount > remaining:
                    await ctx.send(f"You only need to deduct {remaining}.")
                    continue

                if char_data[stat] - amount < 0:
                    await ctx.send(f"Cannot reduce {stat} below 0.")
                    continue

                char_data[stat] -= amount
                remaining -= amount
                await ctx.send(f"Deducted {amount} from {stat}. {remaining} left.")
            else:
                await ctx.send("Invalid format. Use `STR 5`, `CON 2`, etc.")

    async def select_occupation(self, ctx, char_data, player_stats):
        occupations_data = await load_occupations_data()

        # Calculate points for all occupations to provide suggestions
        scored_occupations = []
        for name, info in occupations_data.items():
            pts = self.calculate_occupation_points(char_data, info)
            if pts > 0:
                scored_occupations.append((name, pts))

        # Shuffle to randomize ties, then sort by points descending
        random.shuffle(scored_occupations)
        scored_occupations.sort(key=lambda x: x[1], reverse=True)

        # Prepare top 5 suggestion string
        top_5 = scored_occupations[:5]
        suggestion_str = ""
        if top_5:
            suggestions = [f"{name} ({pts})" for name, pts in top_5]
            suggestion_str = f"Best option for you is {', '.join(suggestions)}"

            # Check for more with the same score as the 5th one (if 5 exist)
            if len(top_5) == 5:
                last_score = top_5[-1][1]
                # Count remaining with same score
                more_count = sum(1 for _, pts in scored_occupations[5:] if pts == last_score)
                if more_count > 0:
                    suggestion_str += f" and {more_count} more occupation{'s' if more_count > 1 else ''} with {last_score} points."
            suggestion_str += "."

        if suggestion_str:
            await ctx.send(suggestion_str)

        # Send initial prompt
        await ctx.send(
            "Please select an **Occupation**.\n"
            "Type `list` to see all options with points, or type a search term (e.g. `detective`, `soldier`).\n"
            "Type the name to select."
        )

        # Mapping for case-insensitive lookup
        occupation_map = {k.lower(): k for k in occupations_data.keys()}

        # Pagination State
        list_msg = None
        current_page = 1
        valid_occupations = [] # List of (name, pts)
        items_per_page = 15
        page_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

        async def send_page(page_num, total_pages, data):
            start_idx = (page_num - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_items = data[start_idx:end_idx]

            description = ""
            for name, pts in page_items:
                emojis_str = occupation_emoji.get_occupation_emoji(name)
                description += f"{emojis_str} **{name}** ({pts})\n"

            embed = discord.Embed(
                title=f"Available Occupations (Page {page_num}/{total_pages})",
                description=description,
                color=discord.Color.green()
            )
            return embed

        while True:
            # Prepare tasks
            tasks = []

            # 1. Message Listener
            def msg_check(m):
                return m.author == ctx.author and m.channel == ctx.channel
            tasks.append(asyncio.create_task(self.bot.wait_for('message', check=msg_check)))

            # 2. Reaction Listener (only if list is active)
            if list_msg:
                def reaction_check(reaction, user):
                    return user == ctx.author and reaction.message.id == list_msg.id and str(reaction.emoji) in page_emojis
                tasks.append(asyncio.create_task(self.bot.wait_for('reaction_add', check=reaction_check)))

            try:
                # Wait for FIRST interaction (Message OR Reaction)
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED, timeout=300)

                # Cancel pending tasks
                for task in pending:
                    task.cancel()

                if not done:
                    # Timeout
                    await ctx.send("Character creation timed out during occupation selection.")
                    return

                result = done.pop().result()

                # Handle Message Input
                if isinstance(result, discord.Message):
                    val = result.content.strip()
                    lower_val = val.lower()

                    if lower_val == "list":
                        # Generate/Reset List
                        valid_occupations = []
                        for name, info in occupations_data.items():
                            pts = self.calculate_occupation_points(char_data, info)
                            if pts > 0:
                                valid_occupations.append((name, pts))

                        valid_occupations.sort(key=lambda x: x[1], reverse=True)

                        if not valid_occupations:
                            await ctx.send("No occupations available with current stats.")
                            continue

                        current_page = 1
                        total_pages = math.ceil(len(valid_occupations) / items_per_page)

                        embed = await send_page(current_page, total_pages, valid_occupations)

                        if list_msg:
                            try:
                                await list_msg.delete()
                            except: pass

                        list_msg = await ctx.send(embed=embed)

                        if total_pages > 1:
                            for i in range(min(total_pages, len(page_emojis))):
                                await list_msg.add_reaction(page_emojis[i])

                    # Exact Match (Case Insensitive)
                    elif lower_val in occupation_map:
                        occupation_name = occupation_map[lower_val]
                        occupation_info = occupations_data[occupation_name]
                        await ctx.send(f"Selected **{occupation_name}**.")
                        await self.assign_occupation_skills(ctx, char_data, occupation_name, occupation_info)
                        return # Exit Loop

                    # Partial Match
                    else:
                        matches = [k for k in occupations_data.keys() if lower_val in k.lower()]
                        if len(matches) == 1:
                            # Auto-select single match
                            occupation_name = matches[0]
                            occupation_info = occupations_data[occupation_name]
                            await ctx.send(f"Found match: **{occupation_name}**.")
                            await self.assign_occupation_skills(ctx, char_data, occupation_name, occupation_info)
                            return # Exit Loop
                        elif len(matches) > 1:
                            # Show matches
                            await ctx.send(f"Found multiple matches: {', '.join(matches)}. Please be more specific.")
                        else:
                            await ctx.send("No occupation found. Try again.")

                # Handle Reaction Input
                elif isinstance(result, tuple):
                    # (reaction, user)
                    reaction, user = result

                    selected_page_idx = page_emojis.index(str(reaction.emoji))
                    new_page = selected_page_idx + 1
                    total_pages = math.ceil(len(valid_occupations) / items_per_page)

                    if new_page != current_page and new_page <= total_pages:
                        current_page = new_page
                        await list_msg.edit(embed=await send_page(current_page, total_pages, valid_occupations))

                    try:
                        await list_msg.remove_reaction(reaction, user)
                    except:
                        pass

            except asyncio.TimeoutError:
                await ctx.send("Character creation timed out.")
                if list_msg:
                    try: await list_msg.clear_reactions()
                    except: pass
                return
            except Exception as e:
                print(f"Error in select_occupation loop: {e}")
                await ctx.send("An unexpected error occurred. Please try again.")
                return

    def calculate_occupation_points(self, char_data, info):
        """Calculates occupation skill points based on character stats and occupation formula."""
        edu = char_data.get("EDU", 0)
        dex = char_data.get("DEX", 0)
        str_stat = char_data.get("STR", 0)
        app = char_data.get("APP", 0)
        pow_stat = char_data.get("POW", 0)

        formula = info.get("skill_points", "EDU × 4")

        # Normalize formula
        formula = formula.replace("x", "×").replace("X", "×").replace("*", "×").replace("–", "-")

        if "Varies" in formula:
            return 0

        try:
            # Simple Case
            if formula == "EDU × 4":
                return edu * 4

            # Complex parsing
            parts = formula.split("+")
            total = 0

            for part in parts:
                part = part.strip()
                if "or" in part:
                    # (Option A or Option B)
                    clean_part = part.replace("(", "").replace(")", "")
                    options = clean_part.split("or")
                    best_val = 0
                    for opt in options:
                        val = self.evaluate_term(opt.strip(), edu, dex, str_stat, app, pow_stat)
                        if val > best_val:
                            best_val = val
                    total += best_val
                else:
                    total += self.evaluate_term(part, edu, dex, str_stat, app, pow_stat)

            return total
        except Exception as e:
            print(f"Error parsing formula '{formula}': {e}")
            return edu * 4

    def evaluate_term(self, term, edu, dex, str_stat, app, pow_stat):
        """Helper to evaluate a single term like 'EDU × 2'."""
        try:
            if "×" not in term: return 0
            stat_name, mult_str = term.split("×")
            stat_name = stat_name.strip()
            mult = int(mult_str.strip())

            if stat_name == "EDU": return edu * mult
            if stat_name == "DEX": return dex * mult
            if stat_name == "STR": return str_stat * mult
            if stat_name == "APP": return app * mult
            if stat_name == "POW": return pow_stat * mult
        except:
            return 0
        return 0

    async def assign_occupation_skills(self, ctx, char_data, occupation_name, info):
        # Save Occupation Name
        char_data["Occupation"] = occupation_name

        # Calculate Points
        points = self.calculate_occupation_points(char_data, info)

        # Credit Rating
        cr_range = info.get("credit_rating", "0-99")
        min_cr, max_cr = 0, 99
        if "–" in cr_range: cr_range = cr_range.replace("–", "-") # Handle en-dash
        if "-" in cr_range:
            parts = cr_range.split("-")
            try:
                min_cr = int(parts[0].strip())
                max_cr = int(parts[1].strip())
            except: pass

        await ctx.send(
            f"**Occupation**: {occupation_name}\n"
            f"**Skill Points**: {points}\n"
            f"**Credit Rating Range**: {min_cr} - {max_cr}\n"
            f"**Suggested Skills**: {info.get('skills', 'None')}"
        )

        # Force Minimum Credit Rating
        if min_cr > 0:
            char_data["Credit Rating"] = min_cr
            points -= min_cr
            await ctx.send(f"**Minimum Credit Rating** of {min_cr} has been automatically assigned. {min_cr} points deducted.")

        # Show all skills and default values
        excluded_keys = [
            "NAME", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP",
            "SAN", "HP", "MP", "LUCK", "Move", "Build", "Damage Bonus", "Age",
            "Backstory", "CustomSkill", "CustomSkills", "CustomSkillss"
        ]

        skills_output = []
        for k in sorted(char_data.keys()):
            if k not in excluded_keys and isinstance(char_data[k], int):
                skills_output.append(f"{emojis.get_stat_emoji(k)} {k}: {char_data[k]}")

        # Send in chunks to avoid hitting character limits
        chunk_str = ""
        await ctx.send("**Current Skill Values (Defaults):**")
        for s in skills_output:
            line = s + "\n"
            if len(chunk_str) + len(line) > 1800:
                await ctx.send(chunk_str)
                chunk_str = ""
            chunk_str += line
        if chunk_str:
            await ctx.send(chunk_str.strip())

        # Skill Assignment Loop
        await self.skill_assignment_loop(ctx, char_data, points, min_cr, max_cr, is_occupation=True)

        # Personal Interest
        pi_points = char_data["INT"] * 2
        await ctx.send(f"**Personal Interest Points**: {pi_points}. Assign to any skill (except Cthulhu Mythos).")
        await self.skill_assignment_loop(ctx, char_data, pi_points, 0, 99, is_occupation=False)

        # Finalization
        await self.finalize_character(ctx, char_data)

    async def skill_assignment_loop(self, ctx, char_data, total_points, min_cr, max_cr, is_occupation):
        remaining = total_points

        while remaining > 0:
            await ctx.send(f"Points remaining: **{remaining}**.\nType `SkillName Value` to add points (e.g. `Spot Hidden 20`). Type `done` to finish.")

            user_input = await self.get_input(ctx, "Command:")
            if user_input is None: return

            if user_input.lower() == "done":
                # Validation checks
                if is_occupation:
                    current_cr = char_data.get("Credit Rating", 0)
                    if not (min_cr <= current_cr <= max_cr):
                        await ctx.send(f"Credit Rating must be between {min_cr} and {max_cr}. Current: {current_cr}. Please adjust.")
                        continue
                if remaining > 0:
                     confirm = await self.get_input(ctx, f"You have {remaining} points left. Are you sure? (yes/no)")
                     if confirm and confirm.lower() in ["yes", "y"]:
                         break
                     else:
                         continue
                break

            # Parse Input
            parts = user_input.split()
            if len(parts) >= 2 and parts[-1].isdigit():
                val = int(parts[-1])
                skill_name_input = " ".join(parts[:-1])

                # Match skill name
                skill_key = None
                # Check exact match
                for k in char_data.keys():
                    if k.lower() == skill_name_input.lower():
                        skill_key = k
                        break

                # Check partial match if not found
                if not skill_key:
                     matches = [k for k in char_data.keys() if skill_name_input.lower() in k.lower()]
                     if len(matches) == 1:
                         skill_key = matches[0]
                     elif len(matches) > 1:
                         await ctx.send(f"Multiple skills found: {', '.join(matches)}. Be more specific.")
                         continue

                if skill_key:
                    # Logic
                    if skill_key == "Cthulhu Mythos":
                        await ctx.send("Cannot assign points to Cthulhu Mythos.")
                        continue

                    if val > remaining:
                        await ctx.send(f"Not enough points. Remaining: {remaining}")
                        continue

                    current_val = char_data.get(skill_key, 0)
                    new_val = current_val + val

                    if new_val > 90:
                        warn_msg = await ctx.send(f"⚠️ **Warning**: Setting **{skill_key}** to **{new_val}** (over 90). This is rare for starting characters.\nAre you sure? React with ✅ to confirm or ❌ to cancel.")
                        await warn_msg.add_reaction("✅")
                        await warn_msg.add_reaction("❌")

                        def reaction_check(reaction, user):
                            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == warn_msg.id

                        try:
                            reaction, _ = await self.bot.wait_for('reaction_add', timeout=60.0, check=reaction_check)
                            if str(reaction.emoji) == "❌":
                                await ctx.send("Cancelled.")
                                continue
                        except asyncio.TimeoutError:
                            await ctx.send("Timed out. Cancelled.")
                            continue

                    char_data[skill_key] = new_val
                    remaining -= val
                    await ctx.send(f"{emojis.get_stat_emoji(skill_key)} Added {val} to **{skill_key}**. New Value: {char_data[skill_key]}. Remaining: {remaining}")
                else:
                    await ctx.send("Skill not found in character sheet.")
            else:
                await ctx.send("Invalid format. Use `Skill Name Value`.")

    async def finalize_character(self, ctx, char_data):
        # Derived Stats
        str_stat = char_data["STR"]
        con = char_data["CON"]
        siz = char_data["SIZ"]
        dex = char_data["DEX"]
        pow_stat = char_data["POW"]

        char_data["HP"] = (con + siz) // 10
        char_data["MP"] = pow_stat // 5
        char_data["SAN"] = pow_stat

        # Build & Damage Bonus
        str_siz = str_stat + siz
        db = "0"
        build = 0

        if 2 <= str_siz <= 64: db = "-2"; build = -2
        elif 65 <= str_siz <= 84: db = "-1"; build = -1
        elif 85 <= str_siz <= 124: db = "0"; build = 0
        elif 125 <= str_siz <= 164: db = "+1D4"; build = 1
        elif 165 <= str_siz <= 204: db = "+1D6"; build = 2
        elif 205 <= str_siz <= 284: db = "+2D6"; build = 3
        elif 285 <= str_siz <= 364: db = "+3D6"; build = 4
        elif 365 <= str_siz <= 444: db = "+4D6"; build = 5
        elif 445 <= str_siz <= 524: db = "+5D6"; build = 6
        else: db = "+6D6"; build = 7 # Rough extrapolation

        char_data["Damage Bonus"] = db
        char_data["Build"] = build

        # Movement Rate
        mov = 8
        if dex < siz and str_stat < siz: mov = 7
        elif dex > siz and str_stat > siz: mov = 9

        # Age Mod to MOV
        age = char_data.get("Age", 20)
        if 40 <= age <= 49: mov -= 1
        elif 50 <= age <= 59: mov -= 2
        elif 60 <= age <= 69: mov -= 3
        elif 70 <= age <= 79: mov -= 4
        elif age >= 80: mov -= 5

        char_data["Move"] = max(0, mov)

        # Save
        player_stats = await load_player_stats()
        server_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        if server_id not in player_stats: player_stats[server_id] = {}
        player_stats[server_id][user_id] = char_data

        await save_player_stats(player_stats)

        await ctx.send(f"**Character Creation Complete!**\nInvestigator **{char_data['NAME']}** has been saved.")
        await self.display_stats(ctx, char_data)

async def setup(bot):
    await bot.add_cog(newinvestigator(bot))
