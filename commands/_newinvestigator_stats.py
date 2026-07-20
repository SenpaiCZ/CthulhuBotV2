import discord
from discord.ui import View, Modal, TextInput, Label

# ==============================================================================
# 3. Views (Stats Generation)
# ==============================================================================

class StatGenerationView(View):
    def __init__(self, cog, char_data, player_stats):
        super().__init__(timeout=300)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
    @discord.ui.button(label="Full Auto", style=discord.ButtonStyle.success)
    async def auto(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.mode_full_auto(interaction, self.char_data, self.player_stats)
    @discord.ui.button(label="Quick Fire", style=discord.ButtonStyle.primary)
    async def quick(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.mode_quick_fire(interaction, self.char_data, self.player_stats)
    @discord.ui.button(label="Assisted", style=discord.ButtonStyle.primary)
    async def assisted(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.mode_assisted(interaction, self.char_data, self.player_stats)
    @discord.ui.button(label="Forced", style=discord.ButtonStyle.secondary)
    async def forced(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.mode_forced(interaction, self.char_data, self.player_stats)

class StatsBulkEntryModal(Modal, title="Enter Stats"):
    stats_input = Label(text="Stats", component=TextInput(style=discord.TextStyle.paragraph, placeholder="STR 60\nCON 70\nSIZ 50\n...", required=True))
    def __init__(self, cog, interaction, char_data, player_stats, mode, expected_values=None):
        super().__init__()
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.mode = mode
        self.expected_values = expected_values
    async def on_submit(self, interaction: discord.Interaction):
        content = self.stats_input.component.value
        lines = content.splitlines()
        parsed = {}
        valid_stats = ["STR", "CON", "SIZ", "DEX", "APP", "INT", "POW", "EDU", "LUCK"]
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 2:
                stat = parts[0].upper()
                val_str = parts[-1]
                if stat in valid_stats and val_str.isdigit(): parsed[stat] = int(val_str)
        for s, v in parsed.items(): self.char_data[s] = v
        await interaction.response.send_message("Stats applied.", ephemeral=True)
        await self.cog.display_stats_and_continue(interaction, self.char_data, self.player_stats)

class AssistedRollView(View):
    def __init__(self, cog, char_data, player_stats, stat_queue, current_stat, current_formula, current_val):
        super().__init__(timeout=300)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.stat_queue = stat_queue
        self.current_stat = current_stat
        self.current_formula = current_formula
        self.current_val = current_val
    @discord.ui.button(label="Keep", style=discord.ButtonStyle.success)
    async def keep(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.char_data[self.current_stat] = self.current_val
        await interaction.response.defer()
        await self.cog.assisted_loop(interaction, self.char_data, self.player_stats, self.stat_queue)
    @discord.ui.button(label="Reroll", style=discord.ButtonStyle.danger)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_val = self.cog.roll_stat_formula(self.current_formula)
        self.char_data[self.current_stat] = new_val
        await interaction.response.edit_message(content=f"Rerolled: **{new_val}** (Previous: {self.current_val}). Keeping new value.", view=None)
        await self.cog.assisted_loop(interaction, self.char_data, self.player_stats, self.stat_queue)

class StatsDeductionView(View):
    def __init__(self, cog, char_data, player_stats, deduction_remaining):
        super().__init__(timeout=300)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.deduction_remaining = deduction_remaining
    @discord.ui.button(label="STR -5", style=discord.ButtonStyle.primary)
    async def str_minus(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.deduct(interaction, "STR", 5)
    @discord.ui.button(label="CON -5", style=discord.ButtonStyle.primary)
    async def con_minus(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.deduct(interaction, "CON", 5)
    @discord.ui.button(label="DEX -5", style=discord.ButtonStyle.primary)
    async def dex_minus(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.deduct(interaction, "DEX", 5)
    async def deduct(self, interaction, stat, amount):
        if self.char_data[stat] - amount < 0: return await interaction.response.send_message(f"Cannot reduce {stat} below 0.", ephemeral=True)
        self.char_data[stat] -= amount
        self.deduction_remaining -= amount
        if self.deduction_remaining <= 0:
            await interaction.response.edit_message(content=f"Deduction complete! {stat} reduced by {amount}.", view=None)
            await self.cog.finalize_age_modifiers(interaction, self.char_data, self.player_stats)
        else:
            await interaction.response.edit_message(content=f"Deducted {amount} from {stat}. Remaining deduction: **{self.deduction_remaining}**.", view=self)
