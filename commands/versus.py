import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
from loadnsave import load_player_stats
import random
from rapidfuzz import process, fuzz

# --- Helper Logic ---

def calculate_roll_result(roll, skill_value):
    """
    Calculates the success tier for a CoC 7th Ed roll.
    Returns: (Label, Tier Value)
    Tier Values: 5=Crit, 4=Extreme, 3=Hard, 2=Regular, 1=Fail, 0=Fumble
    """
    is_fumble = False
    if skill_value < 50:
        if roll >= 96: is_fumble = True
    else:
        if roll == 100: is_fumble = True

    if is_fumble: return "Fumble 💀", 0
    if roll == 1: return "Critical Success 🌟", 5
    if roll <= skill_value // 5: return "Extreme Success 💎", 4
    if roll <= skill_value // 2: return "Hard Success ✅", 3
    if roll <= skill_value: return "Regular Success ☑️", 2
    return "Fail ❌", 1

def get_roll_dice(mod):
    """
    Calculates the final roll value based on bonus/penalty dice.
    mod > 0: Bonus Dice
    mod < 0: Penalty Dice
    """
    ones = random.randint(0, 9)
    num_tens = 1 + abs(mod)
    tens_options = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
    tens_rolls = [random.choice(tens_options) for _ in range(num_tens)]

    possible_rolls = []
    for t in tens_rolls:
        val = t + ones
        if val == 0: val = 100
        possible_rolls.append(val)

    final_roll = possible_rolls[0]
    if mod > 0: final_roll = min(possible_rolls)
    elif mod < 0: final_roll = max(possible_rolls)

    return final_roll, tens_rolls, ones

# --- Components ---

class VersusSearchModal(Modal):
    def __init__(self, view, target):
        title = "Search Skill"
        if target == "self": title = "Search Your Skill"
        elif target == "opponent": title = "Search Opponent Skill"

        super().__init__(title=title)
        self.view = view
        self.target = target # 'self' or 'opponent'

        self.query = TextInput(
            label="Skill Name",
            placeholder="e.g. Spot Hidden, Brawl...",
            min_length=2,
            max_length=50
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        query = self.query.value

        # Determine which stats to search
        if self.target == "self":
            stats = self.view.author_stats
        else:
            stats = self.view.opponent_stats

        # Filter valid numeric stats
        valid_keys = []
        ignored_keys = [
            "NAME", "Name", "Residence", "Occupation", "Game Mode",
            "Archetype", "Archetype Info", "Backstory", "Custom Emojis",
            "Age", "Move", "Build", "Damage Bonus", "Bonus Damage",
            "CustomSkill", "CustomSkills", "CustomSkillss", "Occupation Info",
            "HP", "MP", "SAN" # LUCK is handled
        ]

        for k, v in stats.items():
            if k in ignored_keys: continue
            if isinstance(v, (int, float)):
                valid_keys.append(k)

        # Ensure LUCK is explicitly allowed
        if "LUCK" in stats and "LUCK" not in valid_keys:
             valid_keys.append("LUCK")

        choices = valid_keys

        # Fuzzy search
        extract = process.extractOne(query, choices, scorer=fuzz.WRatio)

        if extract:
            match_key, score, _ = extract
            if score > 60:
                # Update View
                if self.target == "self":
                    self.view.my_skill_name = match_key
                    self.view.my_skill_val = stats[match_key]
                else:
                    self.view.opp_skill_name = match_key
                    self.view.opp_skill_val = stats[match_key]

                await self.view.update_view(interaction)
                return

        await interaction.response.send_message(f"❌ No matching skill found for '{query}'.", ephemeral=True)

class SkillSelect(Select):
    def __init__(self, stats, placeholder, callback_func, row=0):
        # Filter stats for numeric values (skills)
        valid_stats = []
        ignored_keys = [
            "NAME", "Name", "Residence", "Occupation", "Game Mode",
            "Archetype", "Archetype Info", "Backstory", "Custom Emojis",
            "Age", "Move", "Build", "Damage Bonus", "Bonus Damage",
            "CustomSkill", "CustomSkills", "CustomSkillss", "Occupation Info",
            "HP", "MP", "SAN", "LUCK"
        ]

        if "LUCK" in stats:
            valid_stats.append(("LUCK", stats["LUCK"]))

        for k, v in stats.items():
            if k in ignored_keys and k != "LUCK": continue
            if isinstance(v, (int, float)):
                valid_stats.append((k, v))

        # Sort by value descending
        valid_stats.sort(key=lambda x: x[1], reverse=True)

        # Top 25
        top_stats = valid_stats[:25]

        options = []
        for k, v in top_stats:
            options.append(discord.SelectOption(label=f"{k} ({v}%)", value=k))

        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, row=row)
        self.callback_func = callback_func

    async def callback(self, interaction: discord.Interaction):
        await self.callback_func(interaction, self.values[0])

class VersusWizardView(View):
    def __init__(self, author, opponent, author_stats, opponent_stats):
        super().__init__(timeout=300)
        self.author = author
        self.opponent = opponent
        self.author_stats = author_stats
        self.opponent_stats = opponent_stats

        self.my_skill_name = None
        self.my_skill_val = 0
        self.opp_skill_name = None
        self.opp_skill_val = 0

        self.my_mod = 0 # >0 Bonus, <0 Penalty
        self.opp_mod = 0

        # Setup Components
        self.setup_components()

    def setup_components(self):
        self.clear_items()

        # Row 0: My Skill Select
        self.add_item(SkillSelect(self.author_stats, "Select Your Skill...", self.on_my_skill_select, row=0))

        # Row 1: Opponent Skill Select
        self.add_item(SkillSelect(self.opponent_stats, "Select Opponent's Skill...", self.on_opp_skill_select, row=1))

        # Row 2: Search Buttons
        search_my = Button(label="Search My Skill", style=discord.ButtonStyle.secondary, emoji="🔍", custom_id="search_my", row=2)
        search_opp = Button(label="Search Opponent Skill", style=discord.ButtonStyle.secondary, emoji="🔍", custom_id="search_opp", row=2)
        self.add_item(search_my)
        self.add_item(search_opp)

        # Row 3: Modifiers (Compact)
        self.add_item(Button(label="My Bonus", style=discord.ButtonStyle.success, emoji="➕", custom_id="my_bonus", row=3))
        self.add_item(Button(label="My Penalty", style=discord.ButtonStyle.danger, emoji="➖", custom_id="my_penalty", row=3))
        self.add_item(Button(label="Opp Bonus", style=discord.ButtonStyle.success, emoji="➕", custom_id="opp_bonus", row=3))
        self.add_item(Button(label="Opp Penalty", style=discord.ButtonStyle.danger, emoji="➖", custom_id="opp_penalty", row=3))

        # Row 4: Action
        roll_btn = Button(label="ROLL VERSUS", style=discord.ButtonStyle.primary, custom_id="roll", row=4, emoji="🎲")
        if not self.my_skill_name or not self.opp_skill_name:
            roll_btn.disabled = True
        self.add_item(roll_btn)

        # Hook up button callbacks
        for child in self.children:
            if isinstance(child, Button):
                child.callback = self.button_callback

    async def on_my_skill_select(self, interaction, skill_name):
        self.my_skill_name = skill_name
        self.my_skill_val = self.author_stats.get(skill_name, 0)
        await self.update_view(interaction)

    async def on_opp_skill_select(self, interaction, skill_name):
        self.opp_skill_name = skill_name
        self.opp_skill_val = self.opponent_stats.get(skill_name, 0)
        await self.update_view(interaction)

    async def button_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]

        if custom_id == "roll":
            await self.perform_roll(interaction)
            return

        elif custom_id == "search_my":
            await interaction.response.send_modal(VersusSearchModal(self, "self"))
            return
        elif custom_id == "search_opp":
            await interaction.response.send_modal(VersusSearchModal(self, "opponent"))
            return

        elif custom_id == "my_bonus":
            self.my_mod = min(2, self.my_mod + 1)
        elif custom_id == "my_penalty":
            self.my_mod = max(-2, self.my_mod - 1)
        elif custom_id == "opp_bonus":
            self.opp_mod = min(2, self.opp_mod + 1)
        elif custom_id == "opp_penalty":
            self.opp_mod = max(-2, self.opp_mod - 1)

        await self.update_view(interaction)

    async def update_view(self, interaction):
        self.setup_components()
        embed = self.get_embed()

        # If called from modal, we might need to edit original response differently
        if interaction.response.is_done():
             await interaction.edit_original_response(embed=embed, view=self)
        else:
             await interaction.response.edit_message(embed=embed, view=self)

    def get_embed(self):
        embed = discord.Embed(
            title="⚔️ Versus Roll Setup",
            description=f"**{self.author.display_name}** vs **{self.opponent.display_name}**",
            color=discord.Color.blue()
        )

        # My Field
        my_dice_str = "Normal"
        if self.my_mod > 0: my_dice_str = f"Bonus ({self.my_mod})"
        elif self.my_mod < 0: my_dice_str = f"Penalty ({abs(self.my_mod)})"

        my_val_str = f"{self.my_skill_val}%" if self.my_skill_name else "Select Skill..."
        embed.add_field(
            name=f"👤 {self.author.display_name}",
            value=f"Skill: **{self.my_skill_name or 'None'}** ({my_val_str})\nDice: **{my_dice_str}**",
            inline=True
        )

        embed.add_field(name="VS", value="⚡", inline=True)

        # Opponent Field
        opp_dice_str = "Normal"
        if self.opp_mod > 0: opp_dice_str = f"Bonus ({self.opp_mod})"
        elif self.opp_mod < 0: opp_dice_str = f"Penalty ({abs(self.opp_mod)})"

        opp_val_str = f"{self.opp_skill_val}%" if self.opp_skill_name else "Select Skill..."
        embed.add_field(
            name=f"👤 {self.opponent.display_name}",
            value=f"Skill: **{self.opp_skill_name or 'None'}** ({opp_val_str})\nDice: **{opp_dice_str}**",
            inline=True
        )

        if not self.my_skill_name or not self.opp_skill_name:
            embed.set_footer(text="Select or Search skills to proceed.")
        else:
            embed.set_footer(text="Ready to roll!")

        return embed

    async def perform_roll(self, interaction: discord.Interaction):
        # Calculate rolls
        my_roll, my_tens, my_ones = get_roll_dice(self.my_mod)
        my_label, my_tier = calculate_roll_result(my_roll, self.my_skill_val)

        opp_roll, opp_tens, opp_ones = get_roll_dice(self.opp_mod)
        opp_label, opp_tier = calculate_roll_result(opp_roll, self.opp_skill_val)

        # Determine Winner
        # Logic: Higher Tier wins. If tie, higher skill wins. If tie, draw.
        result_title = "Draw!"
        result_color = discord.Color.gold()

        if my_tier > opp_tier:
            result_title = f"🏆 {self.author.display_name} Wins!"
            result_color = discord.Color.green()
        elif opp_tier > my_tier:
            result_title = f"🏆 {self.opponent.display_name} Wins!"
            result_color = discord.Color.red()
        else:
            # Tier Tie
            if self.my_skill_val > self.opp_skill_val:
                result_title = f"🏆 {self.author.display_name} Wins! (Higher Skill)"
                result_color = discord.Color.green()
            elif self.opp_skill_val > self.my_skill_val:
                result_title = f"🏆 {self.opponent.display_name} Wins! (Higher Skill)"
                result_color = discord.Color.red()
            else:
                result_title = "🤝 Draw! (Equal Skill)"
                result_color = discord.Color.light_grey()

        # Build Result Embed
        embed = discord.Embed(title=f"⚔️ Versus Result", color=result_color)

        def format_roll(user, skill, val, roll, label, tens, ones, mod):
            mod_text = ""
            if mod > 0: mod_text = f"(Bonus {mod})"
            elif mod < 0: mod_text = f"(Penalty {abs(mod)})"

            return (
                f"**{skill}** ({val}%)\n"
                f"🎲 Roll: **{roll}** {mod_text}\n"
                f"🔹 {label}"
            )

        embed.add_field(
            name=f"👤 {self.author.display_name}",
            value=format_roll(self.author, self.my_skill_name, self.my_skill_val, my_roll, my_label, my_tens, my_ones, self.my_mod),
            inline=True
        )

        embed.add_field(name="VS", value="⚡", inline=True)

        embed.add_field(
            name=f"👤 {self.opponent.display_name}",
            value=format_roll(self.opponent, self.opp_skill_name, self.opp_skill_val, opp_roll, opp_label, opp_tens, opp_ones, self.opp_mod),
            inline=True
        )

        embed.add_field(name="Result", value=f"### {result_title}", inline=False)

        # Edit message to show result and remove view (or disable)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


class Versus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"

        # Context Menu
        self.ctx_menu = app_commands.ContextMenu(
            name='Challenge to Versus',
            callback=self.challenge_context_menu,
        )
        self.ctx_menu.binding = self
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def challenge_context_menu(self, interaction: discord.Interaction, member: discord.Member):
        await self._start_versus(interaction, member)

    @app_commands.command(name="versus", description="⚔️ Start an interactive opposed roll against another player.")
    @app_commands.describe(opponent="The player to challenge.")
    async def versus(self, interaction: discord.Interaction, opponent: discord.User):
        """
        Start an interactive opposed roll against another player.
        """
        await self._start_versus(interaction, opponent)

    async def _start_versus(self, interaction: discord.Interaction, opponent):
        # 1. Load Data
        server_id = str(interaction.guild_id)
        player_stats = await load_player_stats()

        # 2. Check Author
        if server_id not in player_stats or str(interaction.user.id) not in player_stats[server_id]:
            msg = "❌ You don't have an investigator sheet! Use `/newinvestigator`."
            if interaction.response.is_done():
                 await interaction.followup.send(msg, ephemeral=True)
            else:
                 await interaction.response.send_message(msg, ephemeral=True)
            return

        # 3. Check Opponent
        if str(opponent.id) not in player_stats[server_id]:
            msg = f"❌ {opponent.display_name} doesn't have an investigator sheet!"
            if interaction.response.is_done():
                 await interaction.followup.send(msg, ephemeral=True)
            else:
                 await interaction.response.send_message(msg, ephemeral=True)
            return

        author_stats = player_stats[server_id][str(interaction.user.id)]
        opponent_stats = player_stats[server_id][str(opponent.id)]

        # 4. Launch View
        view = VersusWizardView(interaction.user, opponent, author_stats, opponent_stats)
        embed = view.get_embed()

        if interaction.response.is_done():
             await interaction.followup.send(embed=embed, view=view)
        else:
             await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Versus(bot))
