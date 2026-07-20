import discord
import asyncio
import random
import math
import emojis
import emoji
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput, Label
from loadnsave import (
    load_player_stats, save_player_stats,
    load_occupations_data, load_pulp_talents_data,
    load_archetype_data, load_skill_settings
)
from commands._newinvestigator_data import BASE_SKILLS
from commands._newinvestigator_basicinfo import RetireCharacterView, BasicInfoStartView
from commands._newinvestigator_gamemode import GameModeView, EraSelectView, ArchetypeSelectView, CoreStatSelectView
from commands._newinvestigator_stats import StatGenerationView, StatsBulkEntryModal, AssistedRollView, StatsDeductionView
from commands._newinvestigator_talents import CategoryView, TalentOptionView
from commands._newinvestigator_occupation import OccupationSearchStartView

# ==============================================================================
# 6. Views (Skill Assignment)
# ==============================================================================

class SkillPointSetModal(Modal, title="Set Skill Value"):
    value_input = Label(text="New Total Value", component=TextInput(placeholder="e.g. 50", min_length=1, max_length=3))

    def __init__(self, view, skill_name, current_val, base_val):
        super().__init__()
        self.view = view
        self.skill_name = skill_name
        self.current_val = current_val
        self.base_val = base_val
        self.value_input.text = f"Set {skill_name} (Base: {base_val})"
        self.value_input.component.default = str(current_val)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_val = int(self.value_input.component.value)
        except ValueError:
            return await interaction.response.send_message("Please enter a valid number.", ephemeral=True)

        # Bounds check
        # Credit Rating has its own bounds passed in view
        if self.skill_name == "Credit Rating":
            if not (self.view.min_cr <= new_val <= self.view.max_cr):
                return await interaction.response.send_message(f"Credit Rating must be between {self.view.min_cr} and {self.view.max_cr}.", ephemeral=True)
        else:
            if new_val > self.view.max_skill:
                return await interaction.response.send_message(f"Cannot exceed starting limit of {self.view.max_skill}%.", ephemeral=True)
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
    spec_name = Label(text="Specialization Name", component=TextInput(placeholder="e.g. Painting, Geology, German", min_length=2, max_length=30))
    value_input = Label(text="Total Value", component=TextInput(placeholder="e.g. 50", min_length=1, max_length=3))

    def __init__(self, view, parent_skill, base_val):
        super().__init__()
        self.view = view
        self.parent_skill = parent_skill
        self.base_val = base_val

    async def on_submit(self, interaction: discord.Interaction):
        name = self.spec_name.component.value.strip()
        # Format: "Art/Craft (Painting)"
        # parent_skill is e.g. "Art/Craft (Any)" -> remove (Any)
        base_name = self.parent_skill.split("(")[0].strip()
        new_skill_name = f"{base_name} ({name})"

        if new_skill_name in self.view.char_data:
             return await interaction.response.send_message("You already have this specialization.", ephemeral=True)

        try:
            new_val = int(self.value_input.component.value)
        except ValueError:
             return await interaction.response.send_message("Invalid number.", ephemeral=True)

        if new_val > self.view.max_skill:
             return await interaction.response.send_message(f"Cannot exceed starting limit of {self.view.max_skill}%.", ephemeral=True)
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
    skill_name = Label(text="Skill Name", component=TextInput(placeholder="e.g. Lore (Vampires)", min_length=2, max_length=40))
    base_val = Label(text="Base Value (%)", component=TextInput(placeholder="e.g. 05", min_length=1, max_length=2, default="05"))
    value_input = Label(text="Total Value (%)", component=TextInput(placeholder="e.g. 50", min_length=1, max_length=3))
    # Emoji? Discord modals don't support file upload. Just text input for emoji char.
    emoji_input = Label(text="Emoji (Optional)", component=TextInput(placeholder="Paste emoji here", required=False, max_length=5))

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        name = self.skill_name.component.value.strip()
        try:
            base = int(self.base_val.component.value)
            val = int(self.value_input.component.value)
        except ValueError:
            return await interaction.response.send_message("Invalid numbers.", ephemeral=True)

        if name in self.view.char_data:
            return await interaction.response.send_message("Skill already exists.", ephemeral=True)

        if val > self.view.max_skill:
             return await interaction.response.send_message(f"Cannot exceed starting limit of {self.view.max_skill}%.", ephemeral=True)
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

        if self.emoji_input.component.value:
             if "Custom Emojis" not in self.view.char_data:
                 self.view.char_data["Custom Emojis"] = {}
             self.view.char_data["Custom Emojis"][name] = self.emoji_input.component.value.strip()

        await self.view.refresh(interaction)

class CthulhuMythosWarningView(View):
    def __init__(self, parent_view, skill_name, current_val, base_val):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.skill_name = skill_name
        self.current_val = current_val
        self.base_val = base_val

    @discord.ui.button(label="Assign Points", style=discord.ButtonStyle.danger, emoji="🐙")
    async def assign(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Proceed to modal
        modal = SkillPointSetModal(self.parent_view, self.skill_name, self.current_val, self.base_val)
        await interaction.response.send_modal(modal)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Action cancelled.", view=None)
        self.stop()

class SkillPageSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="Select a Skill to modify...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        skill = self.values[0]
        current_val = self.view.char_data.get(skill, 0)
        base = BASE_SKILLS.get(skill, 0)

        # Cthulhu Mythos Warning Logic
        if skill == "Cthulhu Mythos":
            embed = discord.Embed(
                title="Forbidden Knowledge: Keeper Approval Required",
                description="Normally you are not allowed to put any points into Cthulhu Mythos.\nTalk to your keeper before you assign points to Cthulhu Mythos.",
                color=discord.Color.red()
            )
            view = CthulhuMythosWarningView(self.view, skill, current_val, base)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

        if "Any" in skill or "any" in skill or "Other" in skill or "specific" in skill or "Own" in skill or "own" in skill:
             modal = SkillSpecializationModal(self.view, skill, base)
             await interaction.response.send_modal(modal)
        else:
             modal = SkillPointSetModal(self.view, skill, current_val, base)
             await interaction.response.send_modal(modal)

class SkillPointAllocationView(View):
    def __init__(self, cog, char_data, player_stats, remaining_points, min_cr, max_cr, is_occupation, allowed_skills=None, pi_points=0, max_skill=75):
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
        self.max_skill = max_skill

        self.page = 0
        self.all_skills = self.get_skill_list()
        self.update_view()

    def get_skill_list(self):
        excluded_keys = ["NAME", "Residence", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN", "HP", "MP", "LUCK", "Move", "Build", "Damage Bonus", "Age", "Backstory", "CustomSkill", "CustomSkills", "CustomSkillss", "Game Mode", "Era", "Archetype", "Archetype Info", "Occupation", "Occupation Info", "Credit Rating"]
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

            # Special handling for Language skills to avoid flag issues
            if s.startswith("Language"):
                emoji_char = emoji.emojize(":lips:", language='alias')
            else:
                emoji_char = self.char_data.get("Custom Emojis", {}).get(s) or emojis.get_stat_emoji(s)
                # Convert shortcodes to unicode for SelectOption
                if emoji_char:
                    emoji_char = emoji.emojize(emoji_char, language='alias')

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
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def refresh(self, interaction: discord.Interaction):
        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def get_embed(self):
        embed = discord.Embed(title="Skill Assignment", color=discord.Color.gold())

        desc = f"Points Remaining: **{self.remaining_points}**\nMax Skill Level: **{self.max_skill}%**"

        if self.is_occupation:
             info = self.char_data.get("Occupation Info", {})
             if info:
                 sug = info.get('skills', 'None')
                 if len(sug) > 500: sug = sug[:497] + "..."
                 desc += f"\n\n**Suggested Occupation Skills**:\n{sug}"

        embed.description = desc

        # Current Page Skills Table
        current_list = self.all_skills
        if self.allowed_skills:
             current_list = [s for s in self.all_skills if self.cog.is_skill_allowed_for_archetype(s, self.allowed_skills)]

        per_page = 20
        max_pages = max(1, (len(current_list) - 1) // per_page + 1)
        self.page = max(0, min(self.page, max_pages - 1))

        start = self.page * per_page
        end = start + per_page
        page_items = current_list[start:end]

        page_text = ""
        for s in page_items:
            val = self.char_data.get(s, 0)

            if s.startswith("Language"):
                emoji_char = ":lips:"
            else:
                emoji_char = self.char_data.get("Custom Emojis", {}).get(s) or emojis.get_stat_emoji(s)

            line = f"**{s}**: {val}%"
            if emoji_char:
                 line = f"{emoji_char} {line}"
            page_text += line + "\n"

        if not page_text:
            page_text = "No skills found."

        embed.add_field(name=f"Skills (Page {self.page+1}/{max_pages})", value=page_text, inline=False)

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
        self.help_category = "Player"

    @app_commands.command(name="newinvestigator", description="🆕 Starts the character creation wizard.")
    async def newinvestigator(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        player_stats = await load_player_stats()
        await self.check_existing_and_start(interaction, player_stats)

    async def get_max_skill(self, guild_id):
        settings = await load_skill_settings()
        if str(guild_id) in settings:
            return settings[str(guild_id)].get("max_starting_skill", 75)
        return 75

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
            "Backstory": {
                "Pulp Talents": [],
                "Personal Description": [],
                "Ideology/Beliefs": [],
                "Significant People": [],
                "Meaningful Locations": [],
                "Treasured Possessions": [],
                "Traits": []
            },
            "Connections": [],
            "Custom Emojis": {},
            **BASE_SKILLS
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

    async def step_era(self, interaction, char_data, player_stats):
        view = EraSelectView(self, char_data, player_stats)
        await interaction.followup.send("Please select an **Era**:", view=view, ephemeral=True)

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

    async def display_stats_only(self, interaction, char_data):
        embed = discord.Embed(title=f"Stats for {char_data['NAME']}", color=discord.Color.green())
        stats_list = ["STR", "DEX", "CON", "APP", "POW", "SIZ", "INT", "EDU", "LUCK"]
        desc = "\n".join([f"{emojis.get_stat_emoji(s)} **{s}**: {char_data.get(s, 0)}" for s in stats_list])
        embed.description = desc
        if interaction.response.is_done(): await interaction.followup.send(embed=embed, ephemeral=True)
        else: await interaction.response.send_message(embed=embed, ephemeral=True)

    async def display_stats_and_continue(self, interaction, char_data, player_stats):
        await self.display_stats_only(interaction, char_data)
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

        # Language (Own) Logic
        lang = char_data.get("First Language", "Own")
        if not lang: lang = "Own"
        lang_skill_name = f"Language ({lang})"
        char_data[lang_skill_name] = char_data["EDU"]

        # Remove generic 'Language (Own)' if it exists and we have a specific one
        if lang_skill_name != "Language (Own)" and "Language (Own)" in char_data:
             del char_data["Language (Own)"]

        if "Reassure" in char_data:
            char_data["Reassure"] = char_data.get("APP", 0) // 5

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
        max_skill = await self.get_max_skill(interaction.guild.id)
        view = SkillPointAllocationView(self, char_data, player_stats, points, min_cr, max_cr, is_occupation, allowed_skills, pi_points, max_skill=max_skill)
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
        await self.display_stats_only(interaction, char_data) # Shows embed

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
        # Note: don't blindly replace "X" here — "DEX" contains an uppercase X,
        # and a blanket replace corrupts it into "DE×" before parsing.
        formula = formula.replace("x", "×").replace("*", "×").replace("–", "-")
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
