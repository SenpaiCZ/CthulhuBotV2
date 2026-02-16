import discord
import asyncio
import random
import math
import emojis
import occupation_emoji
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput
from loadnsave import (
    load_player_stats, save_player_stats,
    load_retired_characters_data, save_retired_characters_data,
    load_occupations_data, load_pulp_talents_data,
    load_archetype_data
)

MAX_STARTING_SKILL = 75

BASE_SKILLS = {
    "Accounting": 5, "Anthropology": 1, "Appraise": 5, "Archaeology": 1, "Charm": 15,
    "Art/Craft": 5, "Climb": 20, "Credit Rating": 0, "Cthulhu Mythos": 0, "Disguise": 5,
    "Dodge": 0, "Drive Auto": 20, "Elec. Repair": 10, "Fast Talk": 5, "Fighting Brawl": 25,
    "Firearms Handgun": 20, "Firearms Rifle/Shotgun": 25, "First Aid": 30, "History": 5,
    "Intimidate": 15, "Jump": 10, "Language other": 1, "Language own": 0, "Law": 5,
    "Library Use": 20, "Listen": 20, "Locksmith": 1, "Mech. Repair": 10, "Medicine": 1,
    "Natural World": 10, "Navigate": 10, "Occult": 5, "Persuade": 10, "Pilot": 1,
    "Psychoanalysis": 1, "Psychology": 10, "Ride": 5, "Science specific": 1,
    "Sleight of Hand": 10, "Spot Hidden": 25, "Stealth": 20, "Survival": 10, "Swim": 20,
    "Throw": 20, "Track": 10
}

# ... (Previous imports and classes remain the same) ...
# I will include all previous classes and add the new ones.

# ==============================================================================
# 1. Views & Modals (Initialization & Basic Info)
# ==============================================================================

class BasicInfoModal(Modal, title="Investigator Details"):
    name = TextInput(label="Name", placeholder="Enter character name...", max_length=100)
    residence = TextInput(label="Residence", placeholder="e.g. Arkham", required=False, max_length=100)
    age = TextInput(label="Age", placeholder="15-90", min_length=2, max_length=2)

    def __init__(self, cog, interaction, char_data, player_stats):
        super().__init__()
        self.cog = cog
        self.origin_interaction = interaction
        self.char_data = char_data
        self.player_stats = player_stats

    async def on_submit(self, interaction: discord.Interaction):
        try:
            age_val = int(self.age.value)
            if not (15 <= age_val <= 90): raise ValueError
        except ValueError:
            await interaction.response.send_message("Age must be a number between 15 and 90.", ephemeral=True)
            return
        self.char_data["NAME"] = self.name.value
        self.char_data["Residence"] = self.residence.value if self.residence.value else "Unknown"
        self.char_data["Age"] = age_val
        await self.cog.step_gamemode(interaction, self.char_data, self.player_stats)

class RetireCharacterView(View):
    def __init__(self, cog, user_id, server_id, player_stats):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.server_id = server_id
        self.player_stats = player_stats
        self.value = None
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("Not your session!", ephemeral=True)
            return False
        return True
    @discord.ui.button(label="Retire Old Character", style=discord.ButtonStyle.danger)
    async def retire(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        retired_characters = await load_retired_characters_data()
        if self.user_id not in retired_characters: retired_characters[self.user_id] = []
        character_data = self.player_stats[self.server_id].pop(self.user_id)
        retired_characters[self.user_id].append(character_data)
        await save_retired_characters_data(retired_characters)
        await save_player_stats(self.player_stats)
        char_name = character_data.get("NAME", "Unknown")
        await interaction.response.send_message(f"**{char_name}** has been retired. Starting new character creation...", ephemeral=True)
        await self.cog.start_wizard(interaction, self.player_stats)
        self.stop()
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.send_message("Character creation cancelled.", ephemeral=True)
        self.stop()


class BasicInfoStartView(View):
    def __init__(self, cog, char_data, player_stats):
        super().__init__(timeout=300)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
    @discord.ui.button(label="Enter Character Details", style=discord.ButtonStyle.primary, emoji="📝")
    async def enter_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BasicInfoModal(self.cog, interaction, self.char_data, self.player_stats)
        await interaction.response.send_modal(modal)

# ==============================================================================
# 2. Views (Game Mode & Pulp)
# ==============================================================================

class GameModeView(View):
    def __init__(self, cog, char_data, player_stats):
        super().__init__(timeout=300)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
    @discord.ui.button(label="Call of Cthulhu", style=discord.ButtonStyle.success)
    async def coc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.char_data["Game Mode"] = "Call of Cthulhu"
        await interaction.response.edit_message(content="Selected: **Call of Cthulhu**", view=None)
        await self.cog.step_stats(interaction, self.char_data, self.player_stats)
    @discord.ui.button(label="Pulp Cthulhu", style=discord.ButtonStyle.danger)
    async def pulp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.char_data["Game Mode"] = "Pulp of Cthulhu"
        await interaction.response.edit_message(content="Selected: **Pulp Cthulhu**", view=None)
        await self.cog.select_pulp_archetype(interaction, self.char_data, self.player_stats)

class ArchetypeSelect(Select):
    def __init__(self, archetypes_data):
        options = [discord.SelectOption(label=name, value=name) for name in sorted(archetypes_data.keys())]
        super().__init__(placeholder="Choose a Pulp Archetype...", min_values=1, max_values=1, options=options)
    async def callback(self, interaction: discord.Interaction):
        self.view.selected_archetype = self.values[0]
        await self.view.update_info(interaction)

class ArchetypeSelectView(View):
    def __init__(self, cog, char_data, player_stats, archetypes_data):
        super().__init__(timeout=300)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.archetypes_data = archetypes_data
        self.selected_archetype = None
        self.add_item(ArchetypeSelect(archetypes_data))
    async def update_info(self, interaction: discord.Interaction):
        if not self.selected_archetype: return
        info = self.archetypes_data[self.selected_archetype]
        embed = discord.Embed(title=f"Archetype: {self.selected_archetype}", description=info.get("description", ""), color=discord.Color.blue())
        if "link" in info and info["link"]: embed.set_thumbnail(url=info["link"])
        adjustments = info.get("adjustments", [])
        if adjustments: embed.add_field(name="Adjustments", value="\n".join(adjustments), inline=False)
        await interaction.response.edit_message(embed=embed, view=self)
    @discord.ui.button(label="Confirm Selection", style=discord.ButtonStyle.success, row=1)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_archetype: return await interaction.response.send_message("Please select an archetype first.", ephemeral=True)
        self.char_data["Archetype"] = self.selected_archetype
        self.char_data["Archetype Info"] = self.archetypes_data[self.selected_archetype]
        await interaction.response.edit_message(content=f"Selected Archetype: **{self.selected_archetype}**", embed=None, view=None)
        await self.cog.step_stats(interaction, self.char_data, self.player_stats)

class CoreStatSelectView(View):
    def __init__(self, options, cog, char_data, player_stats):
        super().__init__(timeout=300)
        for opt in options: self.add_button(opt, cog, char_data, player_stats)
    def add_button(self, opt, cog, char_data, player_stats):
        btn = Button(label=opt, style=discord.ButtonStyle.primary)
        async def callback(interaction: discord.Interaction):
            await cog.apply_core_stat_logic(interaction, char_data, player_stats, opt)
        btn.callback = callback
        self.add_item(btn)

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
    stats_input = TextInput(label="Stats", style=discord.TextStyle.paragraph, placeholder="STR 60\nCON 70\nSIZ 50\n...", required=True)
    def __init__(self, cog, interaction, char_data, player_stats, mode, expected_values=None):
        super().__init__()
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.mode = mode
        self.expected_values = expected_values
    async def on_submit(self, interaction: discord.Interaction):
        content = self.stats_input.value
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

# ==============================================================================
# 4. Views (Pulp Talents)
# ==============================================================================

class TalentCategorySelect(Select):
    def __init__(self, talents_data):
        options = [discord.SelectOption(label=cat.capitalize(), value=cat) for cat in talents_data.keys()]
        super().__init__(placeholder="Choose a Talent Category...", min_values=1, max_values=1, options=options)
    async def callback(self, interaction: discord.Interaction):
        await self.view.cog.pulp_talent_category_selected(interaction, self.values[0], self.view.pulp_data, self.view.current_list, self.view.slots_total, self.view.full_map, self.view.char_data, self.view.player_stats)

class CategoryView(View):
    def __init__(self, cog, pulp_data, current_list, slots_total, full_map, char_data, player_stats):
        super().__init__(timeout=300)
        self.cog = cog
        self.pulp_data = pulp_data
        self.current_list = current_list
        self.slots_total = slots_total
        self.full_map = full_map
        self.char_data = char_data
        self.player_stats = player_stats
        self.add_item(TalentCategorySelect(pulp_data))

class TalentSelect(Select):
    def __init__(self, talents_list, already_selected):
        options = []
        for t in talents_list:
            if "**" in t: name = t.split("**")[1]
            else: name = t[:20]
            if t in already_selected: continue
            desc = t.split(":", 1)[1].strip() if ":" in t else ""
            if len(desc) > 100: desc = desc[:97] + "..."
            options.append(discord.SelectOption(label=name, description=desc, value=name))
        if not options: options.append(discord.SelectOption(label="No talents available", value="none"))
        super().__init__(placeholder="Choose a Talent...", min_values=1, max_values=1, options=options[:25])
    async def callback(self, interaction: discord.Interaction):
        await self.view.cog.pulp_talent_selected(interaction, self.values[0], self.view.pulp_data, self.view.current_list, self.view.slots_total, self.view.full_map, self.view.char_data, self.view.player_stats)

class TalentOptionView(View):
    def __init__(self, cog, talents_list, already_selected, full_map, pulp_data, current_list, slots_total, char_data, player_stats):
        super().__init__(timeout=300)
        self.cog = cog
        self.pulp_data = pulp_data
        self.current_list = current_list
        self.slots_total = slots_total
        self.full_map = full_map
        self.char_data = char_data
        self.player_stats = player_stats
        self.add_item(TalentSelect(talents_list, already_selected))
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.pulp_talent_selection_loop(interaction, self.char_data, self.player_stats, self.pulp_data, self.current_list, self.slots_total, self.full_map)

# ==============================================================================
# 5. Views (Occupation)
# ==============================================================================

class OccupationSearchModal(Modal, title="Search Occupation"):
    search_term = TextInput(label="Search", placeholder="e.g. Detective, Soldier...", min_length=2)
    def __init__(self, cog, interaction, char_data, player_stats, occupations_data):
        super().__init__()
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.occupations_data = occupations_data
    async def on_submit(self, interaction: discord.Interaction):
        term = self.search_term.value.lower()
        matches = []
        for name, info in self.occupations_data.items():
            if term in name.lower(): matches.append(name)
        if not matches: return await interaction.response.send_message("No occupations found matching that term.", ephemeral=True)
        view = OccupationSelectView(self.cog, self.char_data, self.player_stats, self.occupations_data, matches[:25])
        await interaction.response.send_message(f"Found {len(matches)} matches. Please select one:", view=view, ephemeral=True)

class OccupationSelectView(View):
    def __init__(self, cog, char_data, player_stats, occupations_data, matches):
        super().__init__(timeout=300)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.occupations_data = occupations_data
        options = [discord.SelectOption(label=name, value=name) for name in matches]
        self.add_item(OccupationSelect(options))

class OccupationSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="Select an Occupation...", min_values=1, max_values=1, options=options)
    async def callback(self, interaction: discord.Interaction):
        occupation_name = self.values[0]
        await self.view.cog.assign_occupation_skills(interaction, self.view.char_data, self.view.player_stats, occupation_name, self.view.occupations_data[occupation_name])

class PaginatedOccupationListView(View):
    def __init__(self, cog, char_data, player_stats, occupations_data):
        super().__init__(timeout=600)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.occupations_data = occupations_data
        self.page = 0

        # Calculate points and sort
        self.sorted_list = []
        for name, info in occupations_data.items():
            pts = cog.calculate_occupation_points(char_data, info)
            self.sorted_list.append((name, pts))

        # Sort descending by points, then alphabetical
        self.sorted_list.sort(key=lambda x: (-x[1], x[0]))

        self.update_view()

    def update_view(self):
        self.clear_items()

        # Pagination logic
        per_page = 25
        max_pages = max(1, (len(self.sorted_list) - 1) // per_page + 1)
        self.page = max(0, min(self.page, max_pages - 1))

        start = self.page * per_page
        end = start + per_page
        current_items = self.sorted_list[start:end]

        # Select Menu
        options = []
        for name, pts in current_items:
            emoji_char = occupation_emoji.get_occupation_emoji(name)
            label = f"{name} ({pts} pts)"
            # Ensure label is not too long
            if len(label) > 100: label = label[:97] + "..."
            options.append(discord.SelectOption(label=label, value=name, emoji=emoji_char))

        select = OccupationPageSelect(options)
        self.add_item(select)

        # Navigation Buttons
        prev_btn = Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=(self.page == 0), row=1)
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)

        page_btn = Button(label=f"Page {self.page+1}/{max_pages}", style=discord.ButtonStyle.secondary, disabled=True, row=1)
        self.add_item(page_btn)

        next_btn = Button(label="Next", style=discord.ButtonStyle.secondary, disabled=(self.page >= max_pages - 1), row=1)
        next_btn.callback = self.next_page
        self.add_item(next_btn)

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_view()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_view()
        await interaction.response.edit_message(view=self)

class OccupationPageSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="Select an Occupation...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        occupation_name = self.values[0]
        # Access parent view's cog and data
        cog = self.view.cog
        await cog.assign_occupation_skills(interaction, self.view.char_data, self.view.player_stats, occupation_name, self.view.occupations_data[occupation_name])

class OccupationSearchStartView(View):
    def __init__(self, cog, char_data, player_stats, occupations_data):
        super().__init__(timeout=300)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.occupations_data = occupations_data
    @discord.ui.button(label="Search Occupation", style=discord.ButtonStyle.primary, emoji="🔍")
    async def search(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = OccupationSearchModal(self.cog, interaction, self.char_data, self.player_stats, self.occupations_data)
        await interaction.response.send_modal(modal)
    @discord.ui.button(label="Browse Occupations (Sorted)", style=discord.ButtonStyle.success, emoji="📜")
    async def browse(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PaginatedOccupationListView(self.cog, self.char_data, self.player_stats, self.occupations_data)
        await interaction.response.edit_message(content="Browsing Occupations (Sorted by Points):", view=view)

# ==============================================================================
# 6. Views (Skill Assignment)
# ==============================================================================

class SkillPointSetModal(Modal, title="Set Skill Value"):
    value_input = TextInput(label="New Total Value", placeholder="e.g. 50", min_length=1, max_length=3)

    def __init__(self, view, skill_name, current_val, base_val):
        super().__init__()
        self.view = view
        self.skill_name = skill_name
        self.current_val = current_val
        self.base_val = base_val
        self.value_input.label = f"Set {skill_name} (Base: {base_val})"
        self.value_input.default = str(current_val)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_val = int(self.value_input.value)
        except ValueError:
            return await interaction.response.send_message("Please enter a valid number.", ephemeral=True)

        # Bounds check
        # Credit Rating has its own bounds passed in view
        if self.skill_name == "Credit Rating":
            if not (self.view.min_cr <= new_val <= self.view.max_cr):
                return await interaction.response.send_message(f"Credit Rating must be between {self.view.min_cr} and {self.view.max_cr}.", ephemeral=True)
        else:
            if new_val > MAX_STARTING_SKILL:
                return await interaction.response.send_message(f"Cannot exceed starting limit of {MAX_STARTING_SKILL}%.", ephemeral=True)
            if new_val < self.base_val:
                return await interaction.response.send_message(f"Cannot go below base value of {self.base_val}%.", ephemeral=True)

        cost = new_val - self.current_val

        if cost > self.view.remaining_points:
            return await interaction.response.send_message(f"Not enough points. Cost: {cost}, Remaining: {self.view.remaining_points}.", ephemeral=True)

        # Apply
        self.view.char_data[self.skill_name] = new_val
        self.view.remaining_points -= cost

        await self.view.refresh(interaction)

class SkillSpecializationModal(Modal, title="Add Specialization"):
    spec_name = TextInput(label="Specialization Name", placeholder="e.g. Painting, Geology, German", min_length=2, max_length=30)
    value_input = TextInput(label="Total Value", placeholder="e.g. 50", min_length=1, max_length=3)

    def __init__(self, view, parent_skill, base_val):
        super().__init__()
        self.view = view
        self.parent_skill = parent_skill
        self.base_val = base_val

    async def on_submit(self, interaction: discord.Interaction):
        name = self.spec_name.value.strip()
        # Format: "Art/Craft (Painting)"
        # parent_skill is e.g. "Art/Craft (Any)" -> remove (Any)
        base_name = self.parent_skill.split("(")[0].strip()
        new_skill_name = f"{base_name} ({name})"

        if new_skill_name in self.view.char_data:
             return await interaction.response.send_message("You already have this specialization.", ephemeral=True)

        try:
            new_val = int(self.value_input.value)
        except ValueError:
             return await interaction.response.send_message("Invalid number.", ephemeral=True)

        if new_val > MAX_STARTING_SKILL:
             return await interaction.response.send_message(f"Cannot exceed starting limit of {MAX_STARTING_SKILL}%.", ephemeral=True)
        if new_val < self.base_val:
             return await interaction.response.send_message(f"Cannot go below base value of {self.base_val}%.", ephemeral=True)

        cost = new_val - self.base_val # It's a new skill starting from base
        if cost > self.view.remaining_points:
             return await interaction.response.send_message(f"Not enough points. Cost: {cost}, Remaining: {self.view.remaining_points}.", ephemeral=True)

        self.view.char_data[new_skill_name] = new_val
        self.view.remaining_points -= cost
        self.view.all_skills.append(new_skill_name)
        self.view.all_skills.sort()

        await self.view.refresh(interaction)

class CustomSkillModal(Modal, title="Add Custom Skill"):
    skill_name = TextInput(label="Skill Name", placeholder="e.g. Lore (Vampires)", min_length=2, max_length=40)
    base_val = TextInput(label="Base Value (%)", placeholder="e.g. 05", min_length=1, max_length=2, default="05")
    value_input = TextInput(label="Total Value (%)", placeholder="e.g. 50", min_length=1, max_length=3)
    # Emoji? Discord modals don't support file upload. Just text input for emoji char.
    emoji_input = TextInput(label="Emoji (Optional)", placeholder="Paste emoji here", required=False, max_length=5)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        name = self.skill_name.value.strip()
        try:
            base = int(self.base_val.value)
            val = int(self.value_input.value)
        except ValueError:
            return await interaction.response.send_message("Invalid numbers.", ephemeral=True)

        if name in self.view.char_data:
            return await interaction.response.send_message("Skill already exists.", ephemeral=True)

        if val > MAX_STARTING_SKILL:
             return await interaction.response.send_message(f"Cannot exceed starting limit of {MAX_STARTING_SKILL}%.", ephemeral=True)
        if val < base:
             return await interaction.response.send_message(f"Value cannot be lower than Base.", ephemeral=True)

        cost = val - base # We pay for everything above base? Usually yes.
        # But wait, if base is 05, and we set to 50, cost is 45.

        if cost > self.view.remaining_points:
             return await interaction.response.send_message(f"Not enough points. Cost: {cost}, Remaining: {self.view.remaining_points}.", ephemeral=True)

        self.view.char_data[name] = val
        self.view.remaining_points -= cost
        self.view.all_skills.append(name)
        self.view.all_skills.sort()

        if self.emoji_input.value:
             if "Custom Emojis" not in self.view.char_data:
                 self.view.char_data["Custom Emojis"] = {}
             self.view.char_data["Custom Emojis"][name] = self.emoji_input.value.strip()

        await self.view.refresh(interaction)

class SkillPageSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="Select a Skill to modify...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        skill = self.values[0]
        current_val = self.view.char_data.get(skill, 0)
        # Determine Base Value?
        # Standard base values are implicit.
        # For generic skills (Any/Other), base is usually what's there.
        # For normal skills, base is... hard to know without lookup.
        # Ideally we load `skills_data`. But we can assume current value IS base if it hasn't been touched?
        # Or just allow going down to 0? No.
        # If we don't have base value, we can assume it's `current_val` if unedited?
        # But if they edited it up, we need to know original base to go down.
        # Hack: Pass 0 as base for now, or just assume they can't go below what it was originally?
        # Wait, if they spend points, `current_val` increases. If they want to lower it, `base` is needed.
        # Let's try to pass `current_val` as base if it's their first time touching it? No.
        # I'll just default base to 0 or 1 for simplicity if lookup fails, but warn user.
        # Actually, `start_wizard` initialized `char_data` with base values!
        # So `current_val` IS correct value. But if they increased it, `char_data` has new value.
        # We need the ORIGINAL base.
        # `start_wizard` initialized `new_char` with base values.
        # We didn't save a copy of base values.
        # However, we can probably just use a safe lower bound of 0 or 1, and trust the user not to exploit (lowering below base to gain free points).
        # OR: We only allow ADDING points. "By setting you can lower the skill down too but dont let them lower under default value."
        # This implies we need to know the default value.
        # Since `char_data` is modified in place, we lost the default.
        # Solution: Load `skills_data` in `SkillPointAllocationView` (async) or pass it.
        # But `load_skills_data` is async. View init is sync.
        # We can call `await self.load_data()` in `update_view`? No.
        # We can pass `occupations_data`? No, skills info.
        # I will assume base is 0 for custom skills, and for standard skills I will try to use a static map or just `1` to be safe.
        # Or better: `SkillPointSetModal` will take `base_val` as argument.
        # Where do we get it?
        # I'll just set base to 0 for now to unblock, unless I can fetch it.
        # Actually, `commands/newinvestigator.py` has a hardcoded dict in `start_wizard`!
        # I can copy that dict to a constant `BASE_SKILLS` and use it for lookup.

        base = BASE_SKILLS.get(skill, 0)
        if "Any" in skill or "Other" in skill or "specific" in skill or "own" in skill:
             modal = SkillSpecializationModal(self.view, skill, base)
             await interaction.response.send_modal(modal)
        else:
             modal = SkillPointSetModal(self.view, skill, current_val, base)
             await interaction.response.send_modal(modal)

class SkillPointAllocationView(View):
    def __init__(self, cog, char_data, player_stats, remaining_points, min_cr, max_cr, is_occupation, allowed_skills=None, pi_points=0):
        super().__init__(timeout=600)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.remaining_points = remaining_points
        self.min_cr = min_cr
        self.max_cr = max_cr
        self.is_occupation = is_occupation
        self.allowed_skills = allowed_skills
        self.pi_points = pi_points

        self.page = 0
        self.all_skills = self.get_skill_list()
        self.update_view()

    def get_skill_list(self):
        excluded_keys = ["NAME", "Residence", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN", "HP", "MP", "LUCK", "Move", "Build", "Damage Bonus", "Age", "Backstory", "CustomSkill", "CustomSkills", "CustomSkillss", "Game Mode", "Archetype", "Archetype Info", "Occupation", "Occupation Info", "Credit Rating"]
        skills = []
        for k in self.char_data:
            if k not in excluded_keys and isinstance(self.char_data[k], int):
                skills.append(k)
        if "Credit Rating" not in skills: skills.append("Credit Rating")
        skills.sort()
        return skills

    def update_view(self):
        self.clear_items()

        # 0. Custom Skill Button
        custom_btn = Button(label="Add Custom Skill", style=discord.ButtonStyle.success, row=0, emoji="➕")
        custom_btn.callback = self.add_custom_skill
        self.add_item(custom_btn)

        # 1. Finish Button
        finish_btn = Button(label="Finish", style=discord.ButtonStyle.primary, row=0, disabled=(self.remaining_points > 0), emoji="✅")
        finish_btn.callback = self.finish
        self.add_item(finish_btn)

        # Filter Logic
        current_list = self.all_skills
        if self.allowed_skills:
             current_list = [s for s in self.all_skills if self.cog.is_skill_allowed_for_archetype(s, self.allowed_skills)]

        # Pagination
        per_page = 20
        max_pages = max(1, (len(current_list) - 1) // per_page + 1)
        self.page = max(0, min(self.page, max_pages - 1))

        start = self.page * per_page
        end = start + per_page
        page_items = current_list[start:end]

        options = []
        for s in page_items:
            val = self.char_data.get(s, 0)
            emoji_char = self.char_data.get("Custom Emojis", {}).get(s) or emojis.get_stat_emoji(s)
            label = f"{s}: {val}%"
            if len(label) > 100: label = label[:97] + "..."
            options.append(discord.SelectOption(label=label, value=s, emoji=emoji_char))

        if options:
            select = SkillPageSelect(options)
            self.add_item(select)

        # Navigation
        if max_pages > 1:
            prev_btn = Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=(self.page == 0), row=2)
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)

            count_btn = Button(label=f"Page {self.page+1}/{max_pages}", style=discord.ButtonStyle.secondary, disabled=True, row=2)
            self.add_item(count_btn)

            next_btn = Button(label="Next", style=discord.ButtonStyle.secondary, disabled=(self.page >= max_pages - 1), row=2)
            next_btn.callback = self.next_page
            self.add_item(next_btn)

    async def add_custom_skill(self, interaction: discord.Interaction):
        modal = CustomSkillModal(self)
        await interaction.response.send_modal(modal)

    async def finish(self, interaction: discord.Interaction):
        await self.cog.finish_skill_assignment(interaction, self)

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_view()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_view()
        await interaction.response.edit_message(view=self)

    async def refresh(self, interaction: discord.Interaction):
        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def get_embed(self):
        embed = discord.Embed(title="Skill Assignment", color=discord.Color.gold())

        desc = f"Points Remaining: **{self.remaining_points}**\nMax Skill Level: **{MAX_STARTING_SKILL}%**"

        if self.is_occupation:
             info = self.char_data.get("Occupation Info", {})
             if info:
                 sug = info.get('skills', 'None')
                 if len(sug) > 500: sug = sug[:497] + "..."
                 desc += f"\n\n**Suggested Occupation Skills**:\n{sug}"

        embed.description = desc

        # Top Skills Field (Non-default or high value)
        # Using BASE_SKILLS to filter "Improved" skills
        improved_skills = []
        for k, v in self.char_data.items():
            if isinstance(v, int) and k in self.all_skills:
                base = BASE_SKILLS.get(k, 0)
                if v > base:
                    improved_skills.append((k, v, v-base))

        # Sort by points spent (v-base) descending
        improved_skills.sort(key=lambda x: -x[2])

        skill_text = ""
        for k, v, diff in improved_skills[:20]: # Show top 20
            skill_text += f"**{k}**: {v}% (+{diff})\n"

        if not skill_text:
            skill_text = "No points spent yet."

        embed.add_field(name="Improved Skills", value=skill_text, inline=False)
        return embed

class FinishConfirmationView(View):
    def __init__(self, cog, parent_view, message):
        super().__init__(timeout=60)
        self.cog = cog
        self.parent_view = parent_view
        self.message = message

    @discord.ui.button(label="YES (Proceed)", style=discord.ButtonStyle.success)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.proceed_after_skills(interaction, self.parent_view)

    @discord.ui.button(label="NO (Back)", style=discord.ButtonStyle.danger)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cancelled. Continue assigning points.", ephemeral=True)

# ==============================================================================
# 7. Main Cog
# ==============================================================================

class newinvestigator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="newinvestigator", description="Starts the character creation wizard.")
    async def newinvestigator(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        player_stats = await load_player_stats()
        await self.check_existing_and_start(interaction, player_stats)

    async def check_existing_and_start(self, interaction: discord.Interaction, player_stats):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        if server_id not in player_stats: player_stats[server_id] = {}

        if user_id in player_stats[server_id]:
            existing_char = player_stats[server_id][user_id]
            char_name = existing_char.get("NAME", "Unknown")
            view = RetireCharacterView(self, user_id, server_id, player_stats)
            if interaction.response.is_done():
                await interaction.followup.send(f"You already have an investigator named **{char_name}**. Retire?", view=view, ephemeral=True)
            else:
                await interaction.response.send_message(f"You already have an investigator named **{char_name}**. Retire?", view=view, ephemeral=True)
        else:
            await self.start_wizard(interaction, player_stats)

    async def start_wizard(self, interaction: discord.Interaction, player_stats):
        new_char = {
            "NAME": "Unknown", "Residence": "Unknown",
            "STR": 0, "DEX": 0, "CON": 0, "INT": 0, "POW": 0, "EDU": 0, "SIZ": 0, "APP": 0,
            "SAN": 0, "HP": 0, "MP": 0, "LUCK": 0,
            "Move": 0, "Build": 0, "Damage Bonus": 0,
            "Age": 0,
            "Occupation": "Unknown", "Credit Rating": 0, "Game Mode": "Call of Cthulhu",
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
            "Backstory": {'Pulp Talents': []}, "Custom Emojis": {}
        }
        view = BasicInfoStartView(self, new_char, player_stats)
        if interaction.response.is_done():
             await interaction.followup.send("Let's begin! Click below to set your basic details.", view=view, ephemeral=True)
        else:
             await interaction.response.send_message("Let's begin! Click below to set your basic details.", view=view, ephemeral=True)

    # ... (Includes all previous methods: step_gamemode, step_stats, apply_age_modifiers, etc.) ...
    # I will paste them here in the final write_file to save space in thought block.
    # Assuming previous methods are here.
    async def step_gamemode(self, interaction, char_data, player_stats):
        view = GameModeView(self, char_data, player_stats)
        await interaction.response.send_message("Are you playing **Call of Cthulhu** (Normal) or **Pulp Cthulhu**?", view=view, ephemeral=True)

    async def select_pulp_archetype(self, interaction, char_data, player_stats):
        archetypes_data = await load_archetype_data()
        view = ArchetypeSelectView(self, char_data, player_stats, archetypes_data)
        await interaction.followup.send("Please select a **Pulp Archetype**:", view=view, ephemeral=True)

    async def step_stats(self, interaction, char_data, player_stats):
        prompt = "Please choose a method for generating statistics:\n1. Full Auto\n2. Quick Fire\n3. Assisted\n4. Forced"
        view = StatGenerationView(self, char_data, player_stats)
        if interaction.response.is_done(): await interaction.followup.send(prompt, view=view, ephemeral=True)
        else: await interaction.response.send_message(prompt, view=view, ephemeral=True)

    async def apply_archetype_core_stat(self, interaction, char_data, player_stats):
        info = char_data["Archetype Info"]
        adjustments = info.get("adjustments", [])
        options = self.get_archetype_core_options(adjustments)
        if not options: return await self.apply_age_modifiers(interaction, char_data, player_stats)
        if len(options) == 1: await self.apply_core_stat_logic(interaction, char_data, player_stats, options[0])
        else:
            view = CoreStatSelectView(options, self, char_data, player_stats)
            await interaction.followup.send(f"Your Archetype allows you to choose a **Core Characteristic** from: **{', '.join(options)}**.", view=view, ephemeral=True)

    async def apply_core_stat_logic(self, interaction, char_data, player_stats, selected_stat):
        roll = random.randint(1, 6)
        new_val = (roll + 13) * 5
        old_val = char_data.get(selected_stat, 0)
        char_data[selected_stat] = new_val
        await interaction.response.send_message(f"**Core Characteristic Adjustment**: {selected_stat} {old_val} -> {new_val}", ephemeral=True)
        await self.apply_age_modifiers(interaction, char_data, player_stats)

    async def mode_full_auto(self, interaction, char_data, player_stats):
        char_data["STR"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        char_data["CON"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        char_data["SIZ"] = 5 * (sum([random.randint(1, 6) for _ in range(2)]) + 6)
        char_data["DEX"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        char_data["APP"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        char_data["INT"] = 5 * (sum([random.randint(1, 6) for _ in range(2)]) + 6)
        char_data["POW"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        char_data["EDU"] = 5 * (sum([random.randint(1, 6) for _ in range(2)]) + 6)
        char_data["LUCK"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        await interaction.response.send_message("Rolling stats...", ephemeral=True)
        await self.display_stats_and_continue(interaction, char_data, player_stats)

    async def mode_forced(self, interaction, char_data, player_stats):
        modal = StatsBulkEntryModal(self, interaction, char_data, player_stats, mode="forced")
        await interaction.response.send_modal(modal)

    async def mode_quick_fire(self, interaction, char_data, player_stats):
        char_data["LUCK"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        modal = StatsBulkEntryModal(self, interaction, char_data, player_stats, mode="quick", expected_values=[40, 50, 50, 50, 60, 60, 70, 80])
        await interaction.response.send_modal(modal)

    async def mode_assisted(self, interaction, char_data, player_stats):
        stat_formulas = {
            "STR": "3D6 * 5", "DEX": "3D6 * 5", "CON": "3D6 * 5", "APP": "3D6 * 5", "POW": "3D6 * 5",
            "SIZ": "(2D6 + 6) * 5", "INT": "(2D6 + 6) * 5", "EDU": "(2D6 + 6) * 5"
        }
        char_data["LUCK"] = random.randint(3, 18) * 5
        queue = list(stat_formulas.items())
        await self.assisted_loop(interaction, char_data, player_stats, queue)

    async def assisted_loop(self, interaction, char_data, player_stats, queue):
        if not queue:
            await self.display_stats_and_continue(interaction, char_data, player_stats)
            return
        current_stat, formula = queue.pop(0)
        val = self.roll_stat_formula(formula)
        view = AssistedRollView(self, char_data, player_stats, queue, current_stat, formula, val)
        msg = f"**{current_stat}** ({formula}) rolled: **{val}**. Keep or Reroll?"
        if interaction.response.is_done(): await interaction.followup.send(msg, view=view, ephemeral=True)
        else: await interaction.response.send_message(msg, view=view, ephemeral=True)

    def roll_stat_formula(self, f):
        if f == "3D6 * 5": return sum([random.randint(1, 6) for _ in range(3)]) * 5
        elif f == "(2D6 + 6) * 5": return (sum([random.randint(1, 6) for _ in range(2)]) + 6) * 5
        return 0

    async def display_stats_and_continue(self, interaction, char_data, player_stats):
        embed = discord.Embed(title=f"Stats for {char_data['NAME']}", color=discord.Color.green())
        stats_list = ["STR", "DEX", "CON", "APP", "POW", "SIZ", "INT", "EDU", "LUCK"]
        desc = "\n".join([f"{emojis.get_stat_emoji(s)} **{s}**: {char_data.get(s, 0)}" for s in stats_list])
        embed.description = desc
        if interaction.response.is_done(): await interaction.followup.send(embed=embed, ephemeral=True)
        else: await interaction.response.send_message(embed=embed, ephemeral=True)
        if char_data.get("Game Mode") == "Pulp of Cthulhu" and "Archetype Info" in char_data:
             await self.apply_archetype_core_stat(interaction, char_data, player_stats)
        else:
             await self.apply_age_modifiers(interaction, char_data, player_stats)

    async def apply_age_modifiers(self, interaction, char_data, player_stats):
        age = char_data["Age"]
        messages = []
        edu_checks = 0
        if 20 <= age <= 39: edu_checks = 1
        elif 40 <= age <= 49: edu_checks = 2
        elif 50 <= age <= 59: edu_checks = 3
        elif age >= 60: edu_checks = 4

        if edu_checks > 0:
            messages.append(f"Performing **{edu_checks}** EDU improvement check(s)...")
            for i in range(edu_checks):
                roll = random.randint(1, 100)
                current_edu = char_data["EDU"]
                if roll > current_edu:
                    gain = random.randint(1, 10)
                    char_data["EDU"] = min(99, current_edu + gain)
                    messages.append(f"Check {i+1}: Rolled {roll} (> {current_edu}). **Success!** Gained {gain} EDU.")
                else: messages.append(f"Check {i+1}: Rolled {roll} (<= {current_edu}). No improvement.")

        if 15 <= age <= 19:
            messages.append("Young Investigator adjustments applied.")
            char_data["STR"] = max(0, char_data["STR"] - 5)
            char_data["SIZ"] = max(0, char_data["SIZ"] - 5)
            char_data["EDU"] = max(0, char_data["EDU"] - 5)
            new_luck = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)]))
            if new_luck > char_data["LUCK"]: char_data["LUCK"] = new_luck

        deduction = 0
        app_penalty = 0
        if 40 <= age <= 49: deduction = 5; app_penalty = 5
        elif 50 <= age <= 59: deduction = 10; app_penalty = 10
        elif 60 <= age <= 69: deduction = 20; app_penalty = 15
        elif 70 <= age <= 79: deduction = 40; app_penalty = 20
        elif age >= 80: deduction = 80; app_penalty = 25

        if app_penalty > 0:
            char_data["APP"] = max(0, char_data["APP"] - app_penalty)
            messages.append(f"APP reduced by {app_penalty}.")
        char_data["Dodge"] = char_data["DEX"] // 2
        char_data["Language own"] = char_data["EDU"]

        report_embed = discord.Embed(title="Age Modifiers Report", description="\n".join(messages), color=discord.Color.orange())
        await interaction.followup.send(embed=report_embed, ephemeral=True)
        if deduction > 0:
            view = StatsDeductionView(self, char_data, player_stats, deduction)
            await interaction.followup.send(f"Due to age, you must deduct **{deduction}** points from STR, CON, or DEX.", view=view, ephemeral=True)
        else:
            await self.finalize_age_modifiers(interaction, char_data, player_stats)

    async def finalize_age_modifiers(self, interaction, char_data, player_stats):
        if char_data.get("Game Mode") == "Pulp of Cthulhu": await self.select_pulp_talents(interaction, char_data, player_stats)
        else: await self.select_occupation(interaction, char_data, player_stats)

    # --- Pulp & Occupation Selection (Collapsed for brevity, using previous implementation) ---
    async def select_pulp_talents(self, interaction, char_data, player_stats):
        await interaction.followup.send("As a Pulp Hero, you must determine your **Pulp Talents**.", ephemeral=True)
        pulp_data = await load_pulp_talents_data()
        full_map = {}
        for cat, t_list in pulp_data.items():
            for t in t_list:
                if "**" in t: full_map[t.split("**")[1]] = t
        required_talents = []
        if "Archetype Info" in char_data:
            reqs = self.get_archetype_talent_reqs(char_data["Archetype Info"]["adjustments"])
            for r in reqs:
                full = full_map.get(r)
                if full: required_talents.append(full)
                else:
                    for k, v in full_map.items():
                         if r.lower() in k.lower(): required_talents.append(v); break
        pulp_talents_list = list(required_talents)
        if required_talents:
            req_names = [t.split("**")[1] for t in required_talents if "**" in t]
            await interaction.followup.send(f"**Archetype Requirement**: You gain: **{', '.join(req_names)}**.", ephemeral=True)
        slots_total = 2
        await self.pulp_talent_selection_loop(interaction, char_data, player_stats, pulp_data, pulp_talents_list, slots_total, full_map)

    async def pulp_talent_selection_loop(self, interaction, char_data, player_stats, pulp_data, current_list, slots_total, full_map):
        slots_remaining = slots_total - len(current_list)
        if slots_remaining <= 0:
             char_data["Backstory"]["Pulp Talents"] = current_list
             await interaction.followup.send("Pulp Talents assigned.", ephemeral=True)
             await self.select_occupation(interaction, char_data, player_stats)
             return
        view = CategoryView(self, pulp_data, current_list, slots_total, full_map, char_data, player_stats)
        await interaction.followup.send(f"Select category for Talent ({slots_remaining} remaining):", view=view, ephemeral=True)

    async def pulp_talent_category_selected(self, interaction, category, pulp_data, current_list, slots_total, full_map, char_data, player_stats):
        talents_in_cat = pulp_data[category]
        view = TalentOptionView(self, talents_in_cat, current_list, full_map, pulp_data, current_list, slots_total, char_data, player_stats)
        await interaction.response.send_message(f"Select a talent from **{category.capitalize()}**:", view=view, ephemeral=True)

    async def pulp_talent_selected(self, interaction, talent_name, pulp_data, current_list, slots_total, full_map, char_data, player_stats):
        if talent_name == "BACK": return await interaction.response.defer()
        selected_full = full_map.get(talent_name, talent_name)
        new_list = current_list + [selected_full]
        await interaction.response.send_message(f"Selected: **{talent_name}**.", ephemeral=True)
        await self.pulp_talent_selection_loop(interaction, char_data, player_stats, pulp_data, new_list, slots_total, full_map)

    async def select_occupation(self, interaction, char_data, player_stats):
        occupations_data = await load_occupations_data()
        scored_occupations = []
        for name, info in occupations_data.items():
            pts = self.calculate_occupation_points(char_data, info)
            if pts > 0: scored_occupations.append((name, pts))
        random.shuffle(scored_occupations)
        scored_occupations.sort(key=lambda x: x[1], reverse=True)
        top_5 = scored_occupations[:5]
        suggestion_str = ""
        if top_5:
            suggestions = [f"{name} ({pts})" for name, pts in top_5]
            suggestion_str = f"Best option for you is {', '.join(suggestions)}."
        if suggestion_str: await interaction.followup.send(suggestion_str, ephemeral=True)
        view = OccupationSearchStartView(self, char_data, player_stats, occupations_data)
        await interaction.followup.send("Please select an **Occupation**.", view=view, ephemeral=True)

    async def assign_occupation_skills(self, interaction, char_data, player_stats, occupation_name, info):
        char_data["Occupation"] = occupation_name
        char_data["Occupation Info"] = info
        points = self.calculate_occupation_points(char_data, info)
        cr_range = info.get("credit_rating", "0-99")
        min_cr, max_cr = 0, 99
        if "–" in cr_range: cr_range = cr_range.replace("–", "-")
        if "-" in cr_range:
            try:
                parts = cr_range.split("-")
                min_cr = int(parts[0].strip())
                max_cr = int(parts[1].strip())
            except: pass
        if min_cr > 0:
            char_data["Credit Rating"] = min_cr
            points -= min_cr

        msg = (f"**Occupation**: {occupation_name}\n**Skill Points**: {points}\n**Credit Rating Range**: {min_cr} - {max_cr}\n**Suggested Skills**: {info.get('skills', 'None')}")
        await interaction.response.edit_message(content=msg, view=None)

        # Start Skill Assignment
        await self.step_skill_assignment(interaction, char_data, player_stats, points, min_cr, max_cr, is_occupation=True)

    # --- Skill Assignment Logic ---
    async def step_skill_assignment(self, interaction, char_data, player_stats, points, min_cr, max_cr, is_occupation, allowed_skills=None, pi_points=0):
        view = SkillPointAllocationView(self, char_data, player_stats, points, min_cr, max_cr, is_occupation, allowed_skills, pi_points)
        embed = view.get_embed()

        if interaction.response.is_done():
             await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
             await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def finish_skill_assignment(self, interaction, view):
        if view.remaining_points > 0:
            confirm_view = FinishConfirmationView(self, view, "You have points remaining.")
            await interaction.response.send_message(f"You have **{view.remaining_points}** points remaining. Are you sure you want to finish and discard them?", view=confirm_view, ephemeral=True)
        else:
            await self.proceed_after_skills(interaction, view)

    async def proceed_after_skills(self, interaction, view):
        if interaction.response.is_done(): pass # maybe edit?
        else: await interaction.response.defer()

        # Check CR if Occupation
        if view.is_occupation:
            cr = view.char_data.get("Credit Rating", 0)
            if not (view.min_cr <= cr <= view.max_cr):
                await interaction.followup.send(f"⚠️ Credit Rating ({cr}) must be between {view.min_cr} and {view.max_cr}. Please adjust.", ephemeral=True)
                # Reopen skill assignment
                await self.step_skill_assignment(interaction, view.char_data, view.player_stats, view.remaining_points, view.min_cr, view.max_cr, view.is_occupation, view.allowed_skills, view.pi_points)
                return

        # Next Phase Logic
        if view.is_occupation:
            # Check for Pulp Bonus
            if view.char_data.get("Game Mode") == "Pulp of Cthulhu" and "Archetype Info" in view.char_data:
                # Pulp Bonus Phase
                bonus_points = 100
                allowed = self.get_archetype_skills(view.char_data["Archetype Info"]["adjustments"])
                if allowed:
                    await interaction.followup.send("Proceeding to **Archetype Bonus Points**.", ephemeral=True)
                    await self.step_skill_assignment(interaction, view.char_data, view.player_stats, bonus_points, 0, 99, is_occupation=False, allowed_skills=allowed, pi_points=view.char_data["INT"]*2)
                    return

            # Personal Interest
            pi = view.char_data["INT"] * 2
            await interaction.followup.send("Proceeding to **Personal Interest Points**.", ephemeral=True)
            await self.step_skill_assignment(interaction, view.char_data, view.player_stats, pi, 0, 99, is_occupation=False, allowed_skills=None)

        elif view.allowed_skills: # Came from Pulp Bonus
             # Go to PI
            pi = view.pi_points # Passed through
            await interaction.followup.send("Proceeding to **Personal Interest Points**.", ephemeral=True)
            await self.step_skill_assignment(interaction, view.char_data, view.player_stats, pi, 0, 99, is_occupation=False, allowed_skills=None)

        else:
            # Finished PI -> Finalize
            await self.finalize_character(interaction, view.char_data)

    async def finalize_character(self, interaction, char_data):
        # ... (Finalization logic from original) ...
        str_stat = char_data["STR"]; con = char_data["CON"]; siz = char_data["SIZ"]; dex = char_data["DEX"]; pow_stat = char_data["POW"]
        game_mode = char_data.get("Game Mode", "Call of Cthulhu")
        if game_mode == "Pulp of Cthulhu": char_data["HP"] = (con + siz) // 5
        else: char_data["HP"] = (con + siz) // 10
        char_data["MP"] = pow_stat // 5
        char_data["SAN"] = pow_stat
        str_siz = str_stat + siz
        if 2 <= str_siz <= 64: db="-2"; b=-2
        elif 65 <= str_siz <= 84: db="-1"; b=-1
        elif 85 <= str_siz <= 124: db="0"; b=0
        elif 125 <= str_siz <= 164: db="+1D4"; b=1
        elif 165 <= str_siz <= 204: db="+1D6"; b=2
        elif 205 <= str_siz <= 284: db="+2D6"; b=3
        elif 285 <= str_siz <= 364: db="+3D6"; b=4
        elif 365 <= str_siz <= 444: db="+4D6"; b=5
        elif 445 <= str_siz <= 524: db="+5D6"; b=6
        else: db="+6D6"; b=7
        char_data["Damage Bonus"] = db
        char_data["Build"] = b
        mov = 8
        if dex < siz and str_stat < siz: mov = 7
        elif dex > siz and str_stat > siz: mov = 9
        age = char_data.get("Age", 20)
        if 40 <= age <= 49: mov -= 1
        elif 50 <= age <= 59: mov -= 2
        elif 60 <= age <= 69: mov -= 3
        elif 70 <= age <= 79: mov -= 4
        elif age >= 80: mov -= 5
        char_data["Move"] = max(0, mov)

        player_stats = await load_player_stats()
        server_id = str(interaction.guild.id); user_id = str(interaction.user.id)
        if server_id not in player_stats: player_stats[server_id] = {}
        player_stats[server_id][user_id] = char_data
        await save_player_stats(player_stats)

        await interaction.followup.send(f"**Character Creation Complete!**\nInvestigator **{char_data['NAME']}** has been saved.", ephemeral=True)
        # Display Final Stats
        await self.display_stats_and_continue(interaction, char_data, player_stats) # Shows embed

    # Helpers
    def get_archetype_skills(self, adjustments):
        for line in adjustments:
            if "100 bonus points" in line:
                parts = line.split("skills:**")
                if len(parts) > 1: skill_str = parts[1]
                else: parts_col = line.split(":", 2); skill_str = parts_col[2] if len(parts_col) > 2 else line
                skill_str = skill_str.strip().rstrip(".")
                raw_skills = [s.strip() for s in skill_str.split(",")]
                return raw_skills
        return []

    def is_skill_allowed_for_archetype(self, skill_name, allowed_list):
        skill_name_lower = skill_name.lower()

        # Helper to strip parens and extra spaces for normalized matching
        def normalize(s):
             return s.replace("(", "").replace(")", "").strip()

        skill_norm = normalize(skill_name_lower)

        for allowed in allowed_list:
            allowed_lower = allowed.lower()

            # 1. Exact match
            if skill_name_lower == allowed_lower: return True

            # 2. Normalized match (handles Firearms (Handgun) vs Firearms Handgun)
            if skill_norm == normalize(allowed_lower): return True

            # 3. (any) logic
            if "(any)" in allowed_lower:
                prefix = allowed_lower.replace("(any)", "").strip()
                if skill_name_lower.startswith(prefix): return True

            # 4. Special cases (Language, Survival)
            if "language (other)" in allowed_lower:
                if skill_name_lower.startswith("language") and "own" not in skill_name_lower: return True
            if "survival (any)" in allowed_lower:
                 if skill_name_lower.startswith("survival"): return True
        return False

    # (Previous Helpers: get_archetype_core_options, get_archetype_talent_reqs, calculate_occupation_points, evaluate_term)
    # Must be included here.
    def get_archetype_core_options(self, adjustments):
        for line in adjustments:
            if "Core characteristic" in line:
                parts = line.split(":", 2)
                content = parts[2].strip() if len(parts) > 2 else line
                content = content.replace("**", "").replace(".", "")
                stats = ["STR", "DEX", "CON", "APP", "POW", "SIZ", "INT", "EDU"]
                return [s for s in stats if s in content]
        return []

    def get_archetype_talent_reqs(self, adjustments):
        for line in adjustments:
            if "Talents" in line:
                if "must take the Hardened talent" in line: return ["Hardened"]
        return []

    def calculate_occupation_points(self, char_data, info):
        edu = char_data.get("EDU", 0)
        dex = char_data.get("DEX", 0)
        str_stat = char_data.get("STR", 0)
        app = char_data.get("APP", 0)
        pow_stat = char_data.get("POW", 0)
        formula = info.get("skill_points", "EDU × 4")
        formula = formula.replace("x", "×").replace("X", "×").replace("*", "×").replace("–", "-")
        if "Varies" in formula: return 0
        try:
            if formula == "EDU × 4": return edu * 4
            parts = formula.split("+")
            total = 0
            for part in parts:
                part = part.strip()
                if "or" in part:
                    clean_part = part.replace("(", "").replace(")", "")
                    options = clean_part.split("or")
                    best_val = 0
                    for opt in options:
                        val = self.evaluate_term(opt.strip(), edu, dex, str_stat, app, pow_stat)
                        if val > best_val: best_val = val
                    total += best_val
                else:
                    total += self.evaluate_term(part, edu, dex, str_stat, app, pow_stat)
            return total
        except: return edu * 4

    def evaluate_term(self, term, edu, dex, str_stat, app, pow_stat):
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
        except: return 0
        return 0

async def setup(bot):
    await bot.add_cog(newinvestigator(bot))
