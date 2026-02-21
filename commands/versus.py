import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select, Button
from loadnsave import load_player_stats
import random

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

class SkillSelect(Select):
    def __init__(self, stats, placeholder, callback_func, row=0):
        # Filter stats for numeric values (skills)
        valid_stats = []
        ignored_keys = [
            "NAME", "Name", "Residence", "Occupation", "Game Mode",
            "Archetype", "Archetype Info", "Backstory", "Custom Emojis",
            "Age", "Move", "Build", "Damage Bonus", "Bonus Damage",
            "CustomSkill", "CustomSkills", "CustomSkillss", "Occupation Info",
            "HP", "MP", "SAN", "LUCK" # Maybe handle luck separately? For now exclude derived.
            # Actually LUCK is often rolled, so keep it? No, keep it out of main skill list usually, or put it at top.
            # Let's include LUCK if present.
        ]

        # Explicitly include LUCK if present
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

        # Row 0: My Skill
        self.add_item(SkillSelect(self.author_stats, "Select Your Skill...", self.on_my_skill_select, row=0))

        # Row 1: Opponent Skill
        self.add_item(SkillSelect(self.opponent_stats, "Select Opponent's Skill...", self.on_opp_skill_select, row=1))

        # Row 2: Modifiers (My Bonus/Penalty)
        self.add_item(Button(label="My Bonus (+)", style=discord.ButtonStyle.success, custom_id="my_bonus", row=2))
        self.add_item(Button(label="My Penalty (-)", style=discord.ButtonStyle.danger, custom_id="my_penalty", row=2))

        # Row 3: Modifiers (Opp Bonus/Penalty)
        self.add_item(Button(label="Opp Bonus (+)", style=discord.ButtonStyle.success, custom_id="opp_bonus", row=3))
        self.add_item(Button(label="Opp Penalty (-)", style=discord.ButtonStyle.danger, custom_id="opp_penalty", row=3))

        # Row 4: Action
        roll_btn = Button(label="ROLL VERSUS", style=discord.ButtonStyle.primary, custom_id="roll", row=4, emoji="🎲")
        # Disable roll until skills selected
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
            embed.set_footer(text="Select skills to proceed.")
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
            dice_text = f"[{', '.join(map(str, tens))}] + {ones}"
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

    @app_commands.command(name="versus", description="Start an interactive opposed roll against another player.")
    @app_commands.describe(opponent="The player to challenge.")
    async def versus(self, interaction: discord.Interaction, opponent: discord.User):
        """
        Start an interactive opposed roll against another player.
        """
        # 1. Load Data
        server_id = str(interaction.guild_id)
        player_stats = await load_player_stats()

        # 2. Check Author
        if server_id not in player_stats or str(interaction.user.id) not in player_stats[server_id]:
            return await interaction.response.send_message("❌ You don't have an investigator sheet! Use `/newinvestigator`.", ephemeral=True)

        # 3. Check Opponent
        if str(opponent.id) not in player_stats[server_id]:
            return await interaction.response.send_message(f"❌ {opponent.display_name} doesn't have an investigator sheet!", ephemeral=True)

        author_stats = player_stats[server_id][str(interaction.user.id)]
        opponent_stats = player_stats[server_id][str(opponent.id)]

        # 4. Launch View
        view = VersusWizardView(interaction.user, opponent, author_stats, opponent_stats)
        embed = view.get_embed()

        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Versus(bot))
