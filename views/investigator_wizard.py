import discord
import random
import math
import asyncio
import emoji
import emojis
import occupation_emoji
from discord.ui import View, Button, Select, Modal, TextInput, Label
from typing import Dict, Any, List, Optional
from services.character_service import CharacterService
from loadnsave import (
    load_player_stats, save_player_stats,
    load_retired_characters_data, save_retired_characters_data,
    load_occupations_data, load_pulp_talents_data,
    load_archetype_data, load_skill_settings
)

ERA_SKILLS = {
    "1920s Era": {
        "Accounting": 5, "Anthropology": 1, "Archaeology": 1, "Appraise": 5,
        "Art / Craft (any)": 5, "Charm": 15, "Climb": 20, "Credit Rating": 0,
        "Cthulhu Mythos": 0, "Disguise": 5, "Dodge": 0, "Drive Auto": 20,
        "Elec. Repair": 10, "Fast Talk": 5, "Fighting (Brawl)": 25,
        "Firearms (Handgun)": 20, "Firearms (Rifle/Shotgun)": 25, "First Aid": 30,
        "History": 5, "Intimidate": 15, "Jump": 20, "Language (Other)": 1,
        "Language (Own)": 0, "Law": 5, "Library Use": 20, "Listen": 20,
        "Locksmith": 1, "Mech. Repair": 10, "Medicine": 1, "Natural World": 10,
        "Navigate": 10, "Occult": 5, "Persuade": 10, "Pilot (any)": 1,
        "Psychoanalysis": 1, "Psychology": 10, "Ride": 5, "Science (any)": 1,
        "Sleight of Hand": 10, "Spot Hidden": 25, "Stealth": 20,
        "Survival (any)": 10, "Swim": 20, "Throw": 20, "Track": 10
    },
    "1930s Era": {
        "Accounting": 5, "Archaeology": 1, "Appraise": 5, "Art / Craft (any)": 5,
        "Charm": 15, "Climb": 20, "Computer Use": 0, "Credit Rating": 0,
        "Cthulhu Mythos": 0, "Disguise": 5, "Diving": 1, "Demolitions": 1,
        "Dodge": 0, "Drive Auto": 20, "Elec. Repair": 10, "Fast Talk": 5,
        "Fighting (Brawl)": 25, "Firearms (Handgun)": 20,
        "Firearms (Rifle/Shotgun)": 25, "First Aid": 30, "History": 5,
        "Intimidate": 15, "Jump": 20, "Language (Other)": 1, "Language (Own)": 0,
        "Law": 5, "Library Use": 20, "Listen": 20, "Locksmith": 1,
        "Mech. Repair": 10, "Medicine": 1, "Natural World": 10, "Navigate": 10,
        "Occult": 5, "Persuade": 10, "Pilot (any)": 1, "Psychoanalysis": 1,
        "Psychology": 10, "Ride": 5, "Read Lips": 1, "Science (any)": 1,
        "Sleight of Hand": 10, "Spot Hidden": 25, "Stealth": 20,
        "Survival (any)": 10, "Swim": 20, "Throw": 20, "Track": 10
    },
    "Modern Era": {
        "Accounting": 5, "Anthropology": 1, "Archaeology": 1, "Appraise": 5,
        "Art / Craft (any)": 5, "Charm": 15, "Climb": 20, "Computer Use": 5,
        "Credit Rating": 0, "Cthulhu Mythos": 0, "Disguise": 5, "Dodge": 0,
        "Drive Auto": 20, "Elec. Repair": 10, "Electronics": 1, "Fast Talk": 5,
        "Fighting (Brawl)": 25, "Firearms (Handgun)": 20,
        "Firearms (Rifle/Shotgun)": 25, "First Aid": 30, "History": 5,
        "Intimidate": 15, "Jump": 20, "Language (Other)": 1, "Language (Own)": 0,
        "Law": 5, "Library Use": 20, "Listen": 20, "Locksmith": 1,
        "Mech. Repair": 10, "Medicine": 1, "Natural World": 10, "Navigate": 10,
        "Occult": 5, "Persuade": 10, "Pilot (any)": 1, "Psychoanalysis": 1,
        "Psychology": 10, "Ride": 5, "Science (any)": 1, "Sleight of Hand": 10,
        "Spot Hidden": 25, "Stealth": 20, "Survival (any)": 10, "Swim": 20,
        "Throw": 20, "Track": 10
    },
    "Cthulhu by Gaslight": {
        "Accounting": 10, "Alienism": 1, "Anthropology": 1, "Appraise": 5,
        "Archaeology": 1, "Art / Craft (any)": 5, "Charm": 15, "Climb": 20,
        "Credit Rating": 0, "Cthulhu Mythos": 0, "Disguise": 5, "Dodge": 0,
        "Drive Carriage": 20, "Fast Talk": 5, "Fighting (Brawl)": 25,
        "Firearms (Handgun)": 20, "Firearms (Rifle/Shotgun)": 25, "First Aid": 30,
        "History": 5, "Intimidate": 15, "Jump": 20, "Language (Other)": 1,
        "Language (Own)": 0, "Law": 5, "Library Use": 20, "Listen": 20,
        "Locksmith": 1, "Mech. Repair": 20, "Medicine": 1, "Natural World": 10,
        "Navigate": 10, "Occult": 5, "Operate Heavy Machinery": 1, "Persuade": 10,
        "Pilot (any)": 1, "Psychology": 10, "Reassure": 0,
        "Religion": 10, "Ride": 20, "Science (any)": 1, "Sleight of Hand": 10,
        "Spot Hidden": 25, "Stealth": 20, "Survival (any)": 10, "Swim": 30,
        "Throw": 20, "Track": 10
    },
    "Down Darker Trails": {
        "Accounting": 5, "Animal Handling": 5, "Anthropology": 1, "Appraise": 5,
        "Art / Craft (any)": 5, "Charm": 15, "Climb": 20, "Credit Rating": 0,
        "Cthulhu Mythos": 0, "Disguise": 5, "Dodge": 0, "Drive Wagon/Coach": 20,
        "Elec. Repair": 0, "Fast Talk": 5, "Fighting (Brawl)": 25,
        "Firearms (Handgun)": 20, "Firearms (Rifle/Shotgun)": 25, "First Aid": 30,
        "Gambling": 10, "History": 5, "Intimidate": 15, "Jump": 20,
        "Language (Other)": 1, "Language (Own)": 0, "Law": 5, "Library Use": 20,
        "Listen": 20, "Locksmith": 1, "Mech. Repair": 10, "Medicine": 1,
        "Natural World": 20, "Navigate": 10, "Occult": 5,
        "Operate Heavy Machinery": 1, "Persuade": 10, "Pilot (any)": 1,
        "Psychology": 10, "Ride": 15, "Rope Use": 5, "Science (any)": 1,
        "Sleight of Hand": 10, "Spot Hidden": 25, "Stealth": 20,
        "Survival (any)": 10, "Swim": 20, "Throw": 20, "Track": 10, "Trap": 10
    },
    "Dark Ages": {
        "Accounting": 10, "Animal Handling": 15, "Appraise": 5,
        "Art / Craft (any)": 5, "Charm": 15, "Climb": 20, "Cthulhu Mythos": 0,
        "Disguise": 5, "Dodge": 0, "Drive (Horses/Oxen)": 20, "Fast Talk": 5,
        "Fighting (Brawl)": 25, "First Aid": 30, "Insight": 5, "Intimidate": 15,
        "Jump": 25, "Library Use": 5, "Listen": 25, "Medicine": 1,
        "Natural World (any)": 20, "Navigate": 10, "Occult": 5,
        "Other Kingdoms (any)": 10, "Language (Other)": 1, "Kingdom (Own)": 20,
        "Language (Own)": 0, "Persuade": 15, "Pilot Boat": 1,
        "Read/Write Language (any)": 1, "Repair/Devise": 20, "Religion": 20,
        "Ride Horse": 5, "Science (any)": 1, "Sleight of Hand": 25,
        "Spot Hidden": 25, "Status": 0, "Stealth": 20, "Swim": 25, "Throw": 25,
        "Track": 10
    }
}

BASE_SKILLS = ERA_SKILLS["1920s Era"]

class BasicInfoModal(Modal, title="Investigator Details"):
    name_input = TextInput(label="Name", placeholder="Enter character name...", max_length=100)
    residence_input = TextInput(label="Residence", placeholder="e.g. Arkham", required=False, max_length=100)
    age_input = TextInput(label="Age", placeholder="15-90", min_length=2, max_length=2)
    language_input = TextInput(label="First Language", placeholder="e.g. English, French, Chinese...", max_length=50)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            age_val = int(self.age_input.value)
            if not (15 <= age_val <= 90): raise ValueError
        except ValueError:
            await interaction.response.send_message("Age must be a number between 15 and 90.", ephemeral=True)
            return
        
        self.view.char_data["NAME"] = self.name_input.value
        self.view.char_data["Residence"] = self.residence_input.value if self.residence_input.value else "Unknown"
        self.view.char_data["Age"] = age_val
        self.view.char_data["First Language"] = self.language_input.value.strip() if self.language_input.value else "Own"
        
        await self.view.step_gamemode(interaction)

class InvestigatorWizardView(View):
    def __init__(self, user: discord.User, guild: discord.Guild):
        super().__init__(timeout=1200) # Long timeout for character creation
        self.user = user
        self.guild = guild
        self.char_data = {
            "NAME": "Unknown", "Residence": "Unknown",
            "STR": 0, "DEX": 0, "CON": 0, "INT": 0, "POW": 0, "EDU": 0, "SIZ": 0, "APP": 0,
            "SAN": 0, "HP": 0, "MP": 0, "LUCK": 0,
            "Move": 0, "Build": 0, "Damage Bonus": 0,
            "Age": 0,
            "Occupation": "Unknown", "Credit Rating": 0, "Game Mode": "Call of Cthulhu",
            "Backstory": {'Pulp Talents': []}, "Custom Emojis": {},
            **BASE_SKILLS
        }
        self.player_stats = None # To be loaded

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your session.", ephemeral=True)
            return False
        return True

    async def start(self, interaction: discord.Interaction):
        self.player_stats = await load_player_stats()
        user_id = str(self.user.id)
        server_id = str(self.guild.id)
        
        if server_id not in self.player_stats:
            self.player_stats[server_id] = {}

        if user_id in self.player_stats[server_id]:
            existing_char = self.player_stats[server_id][user_id]
            char_name = existing_char.get("NAME", "Unknown")
            view = RetireCharacterView(self)
            await interaction.response.send_message(f"You already have an investigator named **{char_name}**. Retire?", view=view, ephemeral=True)
        else:
            await self.show_initial_prompt(interaction)

    async def show_initial_prompt(self, interaction: discord.Interaction):
        self.clear_items()
        btn = Button(label="Enter Character Details", style=discord.ButtonStyle.primary, emoji="📝")
        async def callback(inter: discord.Interaction):
            await inter.response.send_modal(BasicInfoModal(self))
        btn.callback = callback
        self.add_item(btn)
        
        msg = "Let's begin! Click below to set your basic details."
        if interaction.response.is_done():
            await interaction.followup.send(msg, view=self, ephemeral=True)
        else:
            await interaction.response.send_message(msg, view=self, ephemeral=True)

    async def step_gamemode(self, interaction: discord.Interaction):
        self.clear_items()
        
        coc_btn = Button(label="Call of Cthulhu", style=discord.ButtonStyle.success)
        async def coc_callback(inter: discord.Interaction):
            self.char_data["Game Mode"] = "Call of Cthulhu"
            await inter.response.edit_message(content="Selected: **Call of Cthulhu**", view=None)
            await self.step_era(inter)
        coc_btn.callback = coc_callback
        
        pulp_btn = Button(label="Pulp Cthulhu", style=discord.ButtonStyle.danger)
        async def pulp_callback(inter: discord.Interaction):
            self.char_data["Game Mode"] = "Pulp of Cthulhu"
            await inter.response.edit_message(content="Selected: **Pulp Cthulhu**", view=None)
            await self.step_era(inter)
        pulp_btn.callback = pulp_callback
        
        self.add_item(coc_btn)
        self.add_item(pulp_btn)
        
        await interaction.response.edit_message(content="Are you playing **Call of Cthulhu** (Normal) or **Pulp Cthulhu**?", view=self)

    async def step_era(self, interaction: discord.Interaction):
        view = EraSelectView(self)
        await interaction.followup.send("Please select an **Era**:", view=view, ephemeral=True)

    async def step_stats(self, interaction: discord.Interaction):
        prompt = "Please choose a method for generating statistics:\n1. Full Auto\n2. Quick Fire\n3. Assisted\n4. Forced"
        view = StatGenerationView(self)
        await interaction.followup.send(prompt, view=view, ephemeral=True)

    async def display_stats_only(self, interaction: discord.Interaction):
        embed = discord.Embed(title=f"Stats for {self.char_data['NAME']}", color=discord.Color.green())
        stats_list = ["STR", "DEX", "CON", "APP", "POW", "SIZ", "INT", "EDU", "LUCK"]
        desc = "\n".join([f"{emojis.get_stat_emoji(s)} **{s}**: {self.char_data.get(s, 0)}" for s in stats_list])
        embed.description = desc
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def display_stats_and_continue(self, interaction: discord.Interaction):
        await self.display_stats_only(interaction)
        if self.char_data.get("Game Mode") == "Pulp of Cthulhu" and "Archetype Info" in self.char_data:
             await self.apply_archetype_core_stat(interaction)
        else:
             await self.apply_age_modifiers(interaction)

    async def apply_archetype_core_stat(self, interaction: discord.Interaction):
        info = self.char_data["Archetype Info"]
        adjustments = info.get("adjustments", [])
        options = self.get_archetype_core_options(adjustments)
        if not options: return await self.apply_age_modifiers(interaction)
        if len(options) == 1: await self.apply_core_stat_logic(interaction, options[0])
        else:
            view = CoreStatSelectView(options, self)
            await interaction.followup.send(f"Your Archetype allows you to choose a **Core Characteristic** from: **{', '.join(options)}**.", view=view, ephemeral=True)

    async def apply_core_stat_logic(self, interaction: discord.Interaction, selected_stat: str):
        roll = random.randint(1, 6)
        new_val = (roll + 13) * 5
        old_val = self.char_data.get(selected_stat, 0)
        self.char_data[selected_stat] = new_val
        await interaction.response.send_message(f"**Core Characteristic Adjustment**: {selected_stat} {old_val} -> {new_val}", ephemeral=True)
        await self.apply_age_modifiers(interaction)

    async def apply_age_modifiers(self, interaction: discord.Interaction):
        age = self.char_data["Age"]
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
                current_edu = self.char_data["EDU"]
                if roll > current_edu:
                    gain = random.randint(1, 10)
                    self.char_data["EDU"] = min(99, current_edu + gain)
                    messages.append(f"Check {i+1}: Rolled {roll} (> {current_edu}). **Success!** Gained {gain} EDU.")
                else: messages.append(f"Check {i+1}: Rolled {roll} (<= {current_edu}). No improvement.")

        if 15 <= age <= 19:
            messages.append("Young Investigator adjustments applied.")
            self.char_data["STR"] = max(0, self.char_data["STR"] - 5)
            self.char_data["SIZ"] = max(0, self.char_data["SIZ"] - 5)
            self.char_data["EDU"] = max(0, self.char_data["EDU"] - 5)
            new_luck = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)]))
            if new_luck > self.char_data["LUCK"]: self.char_data["LUCK"] = new_luck

        deduction = 0
        app_penalty = 0
        if 40 <= age <= 49: deduction = 5; app_penalty = 5
        elif 50 <= age <= 59: deduction = 10; app_penalty = 10
        elif 60 <= age <= 69: deduction = 20; app_penalty = 15
        elif 70 <= age <= 79: deduction = 40; app_penalty = 20
        elif age >= 80: deduction = 80; app_penalty = 25

        if app_penalty > 0:
            self.char_data["APP"] = max(0, self.char_data["APP"] - app_penalty)
            messages.append(f"APP reduced by {app_penalty}.")
        self.char_data["Dodge"] = self.char_data["DEX"] // 2

        # Language (Own) Logic
        lang = self.char_data.get("First Language", "Own")
        lang_skill_name = f"Language ({lang})"
        self.char_data[lang_skill_name] = self.char_data["EDU"]

        if lang_skill_name != "Language (Own)" and "Language (Own)" in self.char_data:
             del self.char_data["Language (Own)"]

        if "Reassure" in self.char_data:
            self.char_data["Reassure"] = self.char_data.get("APP", 0) // 5

        report_embed = discord.Embed(title="Age Modifiers Report", description="\n".join(messages), color=discord.Color.orange())
        await interaction.followup.send(embed=report_embed, ephemeral=True)
        
        if deduction > 0:
            view = StatsDeductionView(self, deduction)
            await interaction.followup.send(f"Due to age, you must deduct **{deduction}** points from STR, CON, or DEX.", view=view, ephemeral=True)
        else:
            await self.finalize_age_modifiers(interaction)

    async def finalize_age_modifiers(self, interaction: discord.Interaction):
        if self.char_data.get("Game Mode") == "Pulp of Cthulhu":
            await self.select_pulp_talents(interaction)
        else:
            await self.select_occupation(interaction)

    async def select_pulp_talents(self, interaction: discord.Interaction):
        await interaction.followup.send("As a Pulp Hero, you must determine your **Pulp Talents**.", ephemeral=True)
        pulp_data = await load_pulp_talents_data()
        full_map = {}
        for cat, t_list in pulp_data.items():
            for t in t_list:
                if "**" in t: full_map[t.split("**")[1]] = t
        
        required_talents = []
        if "Archetype Info" in self.char_data:
            reqs = self.get_archetype_talent_reqs(self.char_data["Archetype Info"]["adjustments"])
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
        await self.pulp_talent_selection_loop(interaction, pulp_data, pulp_talents_list, slots_total, full_map)

    async def pulp_talent_selection_loop(self, interaction: discord.Interaction, pulp_data, current_list, slots_total, full_map):
        slots_remaining = slots_total - len(current_list)
        if slots_remaining <= 0:
             self.char_data["Backstory"]["Pulp Talents"] = current_list
             await interaction.followup.send("Pulp Talents assigned.", ephemeral=True)
             await self.select_occupation(interaction)
             return
        view = CategoryView(self, pulp_data, current_list, slots_total, full_map)
        await interaction.followup.send(f"Select category for Talent ({slots_remaining} remaining):", view=view, ephemeral=True)

    async def select_occupation(self, interaction: discord.Interaction):
        occupations_data = await load_occupations_data()
        scored_occupations = []
        for name, info in occupations_data.items():
            pts = CharacterService.calculate_skill_points(self.char_data, name)
            if pts > 0: scored_occupations.append((name, pts))
        
        scored_occupations.sort(key=lambda x: x[1], reverse=True)
        top_5 = scored_occupations[:5]
        if top_5:
            suggestions = [f"{name} ({pts})" for name, pts in top_5]
            await interaction.followup.send(f"Best options for you: {', '.join(suggestions)}.", ephemeral=True)
        
        view = OccupationSearchStartView(self, occupations_data)
        await interaction.followup.send("Please select an **Occupation**.", view=view, ephemeral=True)

    async def assign_occupation_skills(self, interaction: discord.Interaction, occupation_name: str, info: dict):
        self.char_data["Occupation"] = occupation_name
        self.char_data["Occupation Info"] = info
        points = CharacterService.calculate_skill_points(self.char_data, occupation_name)
        
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
            self.char_data["Credit Rating"] = min_cr
            points -= min_cr

        msg = (f"**Occupation**: {occupation_name}\n**Skill Points**: {points}\n**Credit Rating Range**: {min_cr} - {max_cr}")
        await interaction.response.edit_message(content=msg, view=None)
        await self.step_skill_assignment(interaction, points, min_cr, max_cr, is_occupation=True)

    async def step_skill_assignment(self, interaction: discord.Interaction, points, min_cr, max_cr, is_occupation, allowed_skills=None, pi_points=0):
        settings = await load_skill_settings()
        max_skill = settings.get(str(self.guild.id), {}).get("max_starting_skill", 75)
        
        view = SkillPointAllocationView(self, points, min_cr, max_cr, is_occupation, allowed_skills, pi_points, max_skill=max_skill)
        embed = view.get_embed()

        if interaction.response.is_done():
             await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
             await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def proceed_after_skills(self, interaction: discord.Interaction, view: 'SkillPointAllocationView'):
        if not interaction.response.is_done():
            await interaction.response.defer()

        if view.is_occupation:
            cr = self.char_data.get("Credit Rating", 0)
            if not (view.min_cr <= cr <= view.max_cr):
                await interaction.followup.send(f"⚠️ Credit Rating ({cr}) must be between {view.min_cr} and {view.max_cr}. Please adjust.", ephemeral=True)
                await self.step_skill_assignment(interaction, view.remaining_points, view.min_cr, view.max_cr, view.is_occupation, view.allowed_skills, view.pi_points)
                return

        if view.is_occupation:
            if self.char_data.get("Game Mode") == "Pulp of Cthulhu" and "Archetype Info" in self.char_data:
                bonus_points = 100
                allowed = self.get_archetype_skills(self.char_data["Archetype Info"]["adjustments"])
                if allowed:
                    await interaction.followup.send("Proceeding to **Archetype Bonus Points**.", ephemeral=True)
                    await self.step_skill_assignment(interaction, bonus_points, 0, 99, is_occupation=False, allowed_skills=allowed, pi_points=self.char_data["INT"]*2)
                    return

            pi = self.char_data["INT"] * 2
            await interaction.followup.send("Proceeding to **Personal Interest Points**.", ephemeral=True)
            await self.step_skill_assignment(interaction, pi, 0, 99, is_occupation=False, allowed_skills=None)

        elif view.allowed_skills:
            pi = view.pi_points
            await interaction.followup.send("Proceeding to **Personal Interest Points**.", ephemeral=True)
            await self.step_skill_assignment(interaction, pi, 0, 99, is_occupation=False, allowed_skills=None)

        else:
            await self.finalize_character(interaction)

    async def finalize_character(self, interaction: discord.Interaction):
        derived = CharacterService.calculate_derived_stats(self.char_data, self.char_data.get("Game Mode", "Call of Cthulhu"))
        self.char_data.update({
            "HP": derived["hp"],
            "MP": derived["mp"],
            "SAN": derived["san"],
            "Damage Bonus": derived["damage_bonus"],
            "Build": derived["build"],
            "Move": derived["move"]
        })

        server_id = str(self.guild.id)
        user_id = str(self.user.id)
        self.player_stats[server_id][user_id] = self.char_data
        await save_player_stats(self.player_stats)

        await interaction.followup.send(f"**Character Creation Complete!**\nInvestigator **{self.char_data['NAME']}** has been saved.", ephemeral=True)
        await self.display_stats_only(interaction)

    # Helpers moved from Cog
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
        def normalize(s): return s.replace("(", "").replace(")", "").strip()
        skill_norm = normalize(skill_name_lower)
        for allowed in allowed_list:
            allowed_lower = allowed.lower()
            if skill_name_lower == allowed_lower: return True
            if skill_norm == normalize(allowed_lower): return True
            if "(any)" in allowed_lower:
                prefix = allowed_lower.replace("(any)", "").strip()
                if skill_name_lower.startswith(prefix): return True
            if "language (other)" in allowed_lower:
                if skill_name_lower.startswith("language") and "own" not in skill_name_lower: return True
            if "survival (any)" in allowed_lower:
                 if skill_name_lower.startswith("survival"): return True
        return False

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

# --- Sub-Views ---

class RetireCharacterView(View):
    def __init__(self, wizard: InvestigatorWizardView):
        super().__init__(timeout=60)
        self.wizard = wizard

    @discord.ui.button(label="Retire Old Character", style=discord.ButtonStyle.danger)
    async def retire(self, interaction: discord.Interaction, button: Button):
        retired_characters = await load_retired_characters_data()
        user_id = str(self.wizard.user.id)
        server_id = str(self.wizard.guild.id)
        if user_id not in retired_characters: retired_characters[user_id] = []
        character_data = self.wizard.player_stats[server_id].pop(user_id)
        retired_characters[user_id].append(character_data)
        await save_retired_characters_data(retired_characters)
        await save_player_stats(self.wizard.player_stats)
        char_name = character_data.get("NAME", "Unknown")
        await interaction.response.send_message(f"**{char_name}** has been retired.", ephemeral=True)
        await self.wizard.show_initial_prompt(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Character creation cancelled.", ephemeral=True)
        self.stop()

class EraSelectView(View):
    def __init__(self, wizard: InvestigatorWizardView):
        super().__init__(timeout=300)
        self.wizard = wizard

    async def select_era(self, interaction: discord.Interaction, era_name):
        self.wizard.char_data["Era"] = era_name
        all_possible_skills = set()
        for s_map in ERA_SKILLS.values(): all_possible_skills.update(s_map.keys())
        for k in all_possible_skills:
            if k in self.wizard.char_data: del self.wizard.char_data[k]
        
        skills = ERA_SKILLS.get(era_name, ERA_SKILLS["1920s Era"])
        self.wizard.char_data.update(skills)
        await interaction.response.edit_message(content=f"Selected Era: **{era_name}**", view=None)

        if self.wizard.char_data.get("Game Mode") == "Pulp of Cthulhu":
             archetypes_data = await load_archetype_data()
             view = ArchetypeSelectView(self.wizard, archetypes_data)
             await interaction.followup.send("Please select a **Pulp Archetype**:", view=view, ephemeral=True)
        else:
             await self.wizard.step_stats(interaction)

    @discord.ui.button(label="1920s", style=discord.ButtonStyle.primary)
    async def era_1920s(self, interaction, button): await self.select_era(interaction, "1920s Era")
    @discord.ui.button(label="1930s", style=discord.ButtonStyle.primary)
    async def era_1930s(self, interaction, button): await self.select_era(interaction, "1930s Era")
    @discord.ui.button(label="Modern", style=discord.ButtonStyle.primary)
    async def era_modern(self, interaction, button): await self.select_era(interaction, "Modern Era")
    @discord.ui.button(label="Gaslight", style=discord.ButtonStyle.secondary)
    async def era_gaslight(self, interaction, button): await self.select_era(interaction, "Cthulhu by Gaslight")
    @discord.ui.button(label="Down Darker Trails", style=discord.ButtonStyle.secondary)
    async def era_ddt(self, interaction, button): await self.select_era(interaction, "Down Darker Trails")
    @discord.ui.button(label="Dark Ages", style=discord.ButtonStyle.secondary)
    async def era_dark_ages(self, interaction, button): await self.select_era(interaction, "Dark Ages")

class ArchetypeSelectView(View):
    def __init__(self, wizard: InvestigatorWizardView, archetypes_data):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.archetypes_data = archetypes_data
        self.selected_archetype = None
        options = [discord.SelectOption(label=name, value=name) for name in sorted(archetypes_data.keys())]
        self.select = Select(placeholder="Choose a Pulp Archetype...", options=options)
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        self.selected_archetype = self.select.values[0]
        info = self.archetypes_data[self.selected_archetype]
        embed = discord.Embed(title=f"Archetype: {self.selected_archetype}", description=info.get("description", ""), color=discord.Color.blue())
        if "link" in info and info["link"]: embed.set_thumbnail(url=info["link"])
        adjustments = info.get("adjustments", [])
        if adjustments: embed.add_field(name="Adjustments", value="\n".join(adjustments), inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Confirm Selection", style=discord.ButtonStyle.success, row=1)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if not self.selected_archetype: return await interaction.response.send_message("Please select an archetype first.", ephemeral=True)
        self.wizard.char_data["Archetype"] = self.selected_archetype
        self.wizard.char_data["Archetype Info"] = self.archetypes_data[self.selected_archetype]
        await interaction.response.edit_message(content=f"Selected Archetype: **{self.selected_archetype}**", embed=None, view=None)
        await self.wizard.step_stats(interaction)

class StatGenerationView(View):
    def __init__(self, wizard: InvestigatorWizardView):
        super().__init__(timeout=300)
        self.wizard = wizard

    @discord.ui.button(label="Full Auto", style=discord.ButtonStyle.success)
    async def auto(self, interaction, button):
        d = self.wizard.char_data
        d["STR"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        d["CON"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        d["SIZ"] = 5 * (sum([random.randint(1, 6) for _ in range(2)]) + 6)
        d["DEX"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        d["APP"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        d["INT"] = 5 * (sum([random.randint(1, 6) for _ in range(2)]) + 6)
        d["POW"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        d["EDU"] = 5 * (sum([random.randint(1, 6) for _ in range(2)]) + 6)
        d["LUCK"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        await interaction.response.send_message("Rolling stats...", ephemeral=True)
        await self.wizard.display_stats_and_continue(interaction)

    @discord.ui.button(label="Quick Fire", style=discord.ButtonStyle.primary)
    async def quick(self, interaction, button):
        self.wizard.char_data["LUCK"] = 5 * sum([random.randint(1, 6) for _ in range(3)])
        await interaction.response.send_modal(StatsBulkEntryModal(self.wizard, mode="quick"))

    @discord.ui.button(label="Assisted", style=discord.ButtonStyle.primary)
    async def assisted(self, interaction, button):
        stat_formulas = {
            "STR": "3D6 * 5", "DEX": "3D6 * 5", "CON": "3D6 * 5", "APP": "3D6 * 5", "POW": "3D6 * 5",
            "SIZ": "(2D6 + 6) * 5", "INT": "(2D6 + 6) * 5", "EDU": "(2D6 + 6) * 5"
        }
        self.wizard.char_data["LUCK"] = random.randint(3, 18) * 5
        queue = list(stat_formulas.items())
        await self.assisted_loop(interaction, queue)

    async def assisted_loop(self, interaction, queue):
        if not queue:
            await self.wizard.display_stats_and_continue(interaction)
            return
        stat, formula = queue.pop(0)
        val = sum([random.randint(1, 6) for _ in range(3)]) * 5 if "3D6" in formula else (sum([random.randint(1, 6) for _ in range(2)]) + 6) * 5
        view = AssistedRollView(self.wizard, queue, stat, formula, val)
        msg = f"**{stat}** ({formula}) rolled: **{val}**. Keep or Reroll?"
        if interaction.response.is_done(): await interaction.followup.send(msg, view=view, ephemeral=True)
        else: await interaction.response.send_message(msg, view=view, ephemeral=True)

    @discord.ui.button(label="Forced", style=discord.ButtonStyle.secondary)
    async def forced(self, interaction, button):
        await interaction.response.send_modal(StatsBulkEntryModal(self.wizard, mode="forced"))

class StatsBulkEntryModal(Modal, title="Enter Stats"):
    stats_input = TextInput(label="Stats", style=discord.TextStyle.paragraph, placeholder="STR 60\nCON 70\nSIZ 50\n...", required=True)
    def __init__(self, wizard, mode):
        super().__init__()
        self.wizard = wizard
        self.mode = mode
    async def on_submit(self, interaction: discord.Interaction):
        lines = self.stats_input.value.splitlines()
        valid_stats = ["STR", "CON", "SIZ", "DEX", "APP", "INT", "POW", "EDU", "LUCK"]
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 2:
                stat = parts[0].upper()
                if stat in valid_stats and parts[-1].isdigit(): self.wizard.char_data[stat] = int(parts[-1])
        await interaction.response.send_message("Stats applied.", ephemeral=True)
        await self.wizard.display_stats_and_continue(interaction)

class AssistedRollView(View):
    def __init__(self, wizard, queue, stat, formula, val):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.queue = queue
        self.stat = stat
        self.formula = formula
        self.val = val
    @discord.ui.button(label="Keep", style=discord.ButtonStyle.success)
    async def keep(self, interaction, button):
        self.wizard.char_data[self.stat] = self.val
        await interaction.response.defer()
        await StatGenerationView(self.wizard).assisted_loop(interaction, self.queue)
    @discord.ui.button(label="Reroll", style=discord.ButtonStyle.danger)
    async def reroll(self, interaction, button):
        new_val = sum([random.randint(1, 6) for _ in range(3)]) * 5 if "3D6" in self.formula else (sum([random.randint(1, 6) for _ in range(2)]) + 6) * 5
        self.wizard.char_data[self.stat] = new_val
        await interaction.response.edit_message(content=f"Rerolled: **{new_val}** (Previous: {self.val}). Keeping new value.", view=None)
        await StatGenerationView(self.wizard).assisted_loop(interaction, self.queue)

class StatsDeductionView(View):
    def __init__(self, wizard, deduction):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.deduction = deduction
    async def deduct(self, interaction, stat, amount):
        if self.wizard.char_data[stat] - amount < 0: return await interaction.response.send_message(f"Cannot reduce {stat} below 0.", ephemeral=True)
        self.wizard.char_data[stat] -= amount
        self.deduction -= amount
        if self.deduction <= 0:
            await interaction.response.edit_message(content=f"Deduction complete! {stat} reduced by {amount}.", view=None)
            await self.wizard.finalize_age_modifiers(interaction)
        else:
            await interaction.response.edit_message(content=f"Deducted {amount} from {stat}. Remaining deduction: **{self.deduction}**.", view=self)
    @discord.ui.button(label="STR -5", style=discord.ButtonStyle.primary)
    async def str_minus(self, interaction, button): await self.deduct(interaction, "STR", 5)
    @discord.ui.button(label="CON -5", style=discord.ButtonStyle.primary)
    async def con_minus(self, interaction, button): await self.deduct(interaction, "CON", 5)
    @discord.ui.button(label="DEX -5", style=discord.ButtonStyle.primary)
    async def dex_minus(self, interaction, button): await self.deduct(interaction, "DEX", 5)

class CategoryView(View):
    def __init__(self, wizard, pulp_data, current_list, slots_total, full_map):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.pulp_data = pulp_data
        self.current_list = current_list
        self.slots_total = slots_total
        self.full_map = full_map
        options = [discord.SelectOption(label=cat.capitalize(), value=cat) for cat in pulp_data.keys()]
        self.select = Select(placeholder="Choose a Talent Category...", options=options)
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        cat = self.select.values[0]
        talents = self.pulp_data[cat]
        view = TalentOptionView(self.wizard, talents, self.current_list, self.full_map, self.pulp_data, self.slots_total)
        await interaction.response.send_message(f"Select a talent from **{cat.capitalize()}**:", view=view, ephemeral=True)

class TalentOptionView(View):
    def __init__(self, wizard, talents_list, already_selected, full_map, pulp_data, slots_total):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.pulp_data = pulp_data
        self.already_selected = already_selected
        self.full_map = full_map
        self.slots_total = slots_total
        
        options = []
        for t in talents_list:
            name = t.split("**")[1] if "**" in t else t[:20]
            if t in already_selected: continue
            desc = t.split(":", 1)[1].strip() if ":" in t else ""
            options.append(discord.SelectOption(label=name, description=desc[:100], value=name))
        
        self.select = Select(placeholder="Choose a Talent...", options=options[:25])
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        name = self.select.values[0]
        selected_full = self.full_map.get(name, name)
        new_list = self.already_selected + [selected_full]
        await interaction.response.send_message(f"Selected: **{name}**.", ephemeral=True)
        await self.wizard.pulp_talent_selection_loop(interaction, self.pulp_data, new_list, self.slots_total, self.full_map)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction, button):
        await self.wizard.pulp_talent_selection_loop(interaction, self.pulp_data, self.already_selected, self.slots_total, self.full_map)

class OccupationSearchStartView(View):
    def __init__(self, wizard, occupations_data):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.occupations_data = occupations_data

    @discord.ui.button(label="Search Occupation", style=discord.ButtonStyle.primary, emoji="🔍")
    async def search(self, interaction, button):
        await interaction.response.send_modal(OccupationSearchModal(self.wizard, self.occupations_data))

    @discord.ui.button(label="Browse (Sorted)", style=discord.ButtonStyle.success, emoji="📜")
    async def browse(self, interaction, button):
        view = PaginatedOccupationListView(self.wizard, self.occupations_data, sort_mode="points")
        await interaction.response.edit_message(content="Browsing Occupations (Sorted by Points):", embed=view.get_embed(), view=view)

    @discord.ui.button(label="Browse (A-Z)", style=discord.ButtonStyle.secondary, emoji="🔤")
    async def browse_alpha(self, interaction, button):
        view = PaginatedOccupationListView(self.wizard, self.occupations_data, sort_mode="alpha")
        await interaction.response.edit_message(content="Browsing Occupations (A-Z):", embed=view.get_embed(), view=view)

class OccupationSearchModal(Modal, title="Search Occupation"):
    search_term = TextInput(label="Search", placeholder="e.g. Detective, Soldier...", min_length=2)
    def __init__(self, wizard, occupations_data):
        super().__init__()
        self.wizard = wizard
        self.occupations_data = occupations_data
    async def on_submit(self, interaction: discord.Interaction):
        term = self.search_term.value.lower()
        matches = [name for name in self.occupations_data if term in name.lower()]
        if not matches: return await interaction.response.send_message("No matches found.", ephemeral=True)
        view = OccupationSelectView(self.wizard, self.occupations_data, matches[:25])
        await interaction.response.send_message(f"Found {len(matches)} matches:", view=view, ephemeral=True)

class OccupationSelectView(View):
    def __init__(self, wizard, occupations_data, matches):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.occupations_data = occupations_data
        options = [discord.SelectOption(label=name, value=name) for name in matches]
        self.select = Select(placeholder="Select an Occupation...", options=options)
        self.select.callback = self.on_select
        self.add_item(self.select)
    async def on_select(self, interaction: discord.Interaction):
        name = self.select.values[0]
        await self.wizard.assign_occupation_skills(interaction, name, self.occupations_data[name])

class PaginatedOccupationListView(View):
    def __init__(self, wizard, occupations_data, sort_mode="points"):
        super().__init__(timeout=600)
        self.wizard = wizard
        self.occupations_data = occupations_data
        self.sort_mode = sort_mode
        self.page = 0
        self.sorted_list = []
        for name, info in occupations_data.items():
            pts = CharacterService.calculate_skill_points(wizard.char_data, name)
            self.sorted_list.append((name, pts))
        if sort_mode == "alpha": self.sorted_list.sort(key=lambda x: x[0])
        else: self.sorted_list.sort(key=lambda x: (-x[1], x[0]))
        self.update_view()

    def update_view(self):
        self.clear_items()
        per_page = 25
        max_pages = max(1, (len(self.sorted_list) - 1) // per_page + 1)
        self.page = max(0, min(self.page, max_pages - 1))
        start = self.page * per_page
        current_items = self.sorted_list[start:start+per_page]
        
        options = []
        for name, pts in current_items:
            options.append(discord.SelectOption(label=f"{name} ({pts} pts)", value=name, emoji=occupation_emoji.get_occupation_emoji(name)))
        
        self.select = Select(placeholder="Select an Occupation...", options=options)
        self.select.callback = self.on_select
        self.add_item(self.select)
        
        self.add_item(Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=(self.page == 0), custom_id="prev", row=1))
        self.add_item(Button(label=f"Page {self.page+1}/{max_pages}", style=discord.ButtonStyle.secondary, disabled=True, row=1))
        self.add_item(Button(label="Next", style=discord.ButtonStyle.secondary, disabled=(self.page >= max_pages - 1), custom_id="next", row=1))

    async def on_select(self, interaction: discord.Interaction):
        await self.wizard.assign_occupation_skills(interaction, self.select.values[0], self.occupations_data[self.select.values[0]])

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="prev_btn", row=1)
    async def prev(self, interaction, button):
        self.page -= 1
        self.update_view()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="next_btn", row=1)
    async def next(self, interaction, button):
        self.page += 1
        self.update_view()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    def get_embed(self):
        per_page = 25
        start = self.page * per_page
        current_items = self.sorted_list[start:start+per_page]
        desc = "\n".join([f"{occupation_emoji.get_occupation_emoji(n)} **{n}**: {p} pts" for n, p in current_items])
        embed = discord.Embed(title="Occupations List", description=desc or "None", color=discord.Color.blue())
        embed.set_footer(text=f"Page {self.page+1} / {max(1, (len(self.sorted_list)-1)//25+1)}")
        return embed

class SkillPointAllocationView(View):
    def __init__(self, wizard, remaining_points, min_cr, max_cr, is_occupation, allowed_skills=None, pi_points=0, max_skill=75):
        super().__init__(timeout=600)
        self.wizard = wizard
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
        excluded = ["NAME", "Residence", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN", "HP", "MP", "LUCK", "Move", "Build", "Damage Bonus", "Age", "Backstory", "Game Mode", "Era", "Archetype", "Archetype Info", "Occupation", "Occupation Info", "Credit Rating", "Custom Emojis"]
        skills = [k for k in self.wizard.char_data if k not in excluded and isinstance(self.wizard.char_data[k], int)]
        if "Credit Rating" not in skills: skills.append("Credit Rating")
        skills.sort()
        return skills

    def update_view(self):
        self.clear_items()
        self.add_item(Button(label="Add Custom Skill", style=discord.ButtonStyle.success, custom_id="custom", row=0, emoji="➕"))
        self.add_item(Button(label="Finish", style=discord.ButtonStyle.primary, custom_id="finish", row=0, disabled=(self.remaining_points > 0), emoji="✅"))
        
        current_list = self.all_skills
        if self.allowed_skills:
            current_list = [s for s in self.all_skills if self.wizard.is_skill_allowed_for_archetype(s, self.allowed_skills)]
            
        per_page = 20
        max_pages = max(1, (len(current_list) - 1) // per_page + 1)
        self.page = max(0, min(self.page, max_pages - 1))
        page_items = current_list[self.page*per_page : (self.page+1)*per_page]
        
        options = []
        for s in page_items:
            val = self.wizard.char_data.get(s, 0)
            e = emoji.emojize(":lips:", language='alias') if s.startswith("Language") else (self.wizard.char_data.get("Custom Emojis", {}).get(s) or emojis.get_stat_emoji(s))
            if e and ":" in e and not e.startswith("<"): e = emoji.emojize(e, language='alias')
            options.append(discord.SelectOption(label=f"{s}: {val}%", value=s, emoji=e))
        
        if options:
            self.select = Select(placeholder="Select a Skill to modify...", options=options)
            self.select.callback = self.on_skill_select
            self.add_item(self.select)
            
        if max_pages > 1:
            self.add_item(Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=(self.page == 0), custom_id="prev_skill", row=2))
            self.add_item(Button(label=f"Page {self.page+1}/{max_pages}", style=discord.ButtonStyle.secondary, disabled=True, row=2))
            self.add_item(Button(label="Next", style=discord.ButtonStyle.secondary, disabled=(self.page >= max_pages - 1), custom_id="next_skill", row=2))

    async def on_skill_select(self, interaction: discord.Interaction):
        skill = self.select.values[0]
        val = self.wizard.char_data.get(skill, 0)
        base = ERA_SKILLS.get(self.wizard.char_data.get("Era"), BASE_SKILLS).get(skill, 0)
        if skill == "Cthulhu Mythos":
            await interaction.response.send_message("Normally you are not allowed to put points into Cthulhu Mythos. Talk to your Keeper.", ephemeral=True)
        elif any(x in skill for x in ["Any", "any", "Other", "specific", "Own", "own"]):
            await interaction.response.send_modal(SkillSpecializationModal(self, skill, base))
        else:
            await interaction.response.send_modal(SkillPointSetModal(self, skill, val, base))

    @discord.ui.button(label="Add Custom Skill", style=discord.ButtonStyle.success, custom_id="custom_btn", row=0, emoji="➕")
    async def add_custom(self, interaction, button):
        await interaction.response.send_modal(CustomSkillModal(self))

    @discord.ui.button(label="Finish", style=discord.ButtonStyle.primary, custom_id="finish_btn", row=0, emoji="✅")
    async def finish(self, interaction, button):
        if self.remaining_points > 0:
            await interaction.response.send_message(f"You have {self.remaining_points} points remaining. Finish anyway?", ephemeral=True)
        await self.wizard.proceed_after_skills(interaction, self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="prev_skill_btn", row=2)
    async def prev(self, interaction, button):
        self.page -= 1; self.update_view(); await interaction.response.edit_message(embed=self.get_embed(), view=self)
    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="next_skill_btn", row=2)
    async def next(self, interaction, button):
        self.page += 1; self.update_view(); await interaction.response.edit_message(embed=self.get_embed(), view=self)

    def get_embed(self):
        desc = f"Points Remaining: **{self.remaining_points}**\nMax Skill Level: **{self.max_skill}%**"
        if self.is_occupation:
             info = self.wizard.char_data.get("Occupation Info", {})
             if info: desc += f"\n\n**Suggested**: {info.get('skills', 'None')}"[:500]
        embed = discord.Embed(title="Skill Assignment", description=desc, color=discord.Color.gold())
        improved = []
        for k, v in self.wizard.char_data.items():
            if isinstance(v, int) and k in self.all_skills:
                base = ERA_SKILLS.get(self.wizard.char_data.get("Era"), BASE_SKILLS).get(k, 0)
                if v > base: improved.append(f"**{k}**: {v}% (+{v-base})")
        embed.add_field(name="Improved Skills", value="\n".join(improved[:20]) or "None", inline=False)
        return embed

class SkillPointSetModal(Modal, title="Set Skill Value"):
    val_input = TextInput(label="New Total Value", min_length=1, max_length=3)
    def __init__(self, view, skill, current, base):
        super().__init__()
        self.view = view; self.skill = skill; self.current = current; self.base = base
        self.val_input.label = f"Set {skill} (Base: {base})"
        self.val_input.default = str(current)
    async def on_submit(self, interaction: discord.Interaction):
        try: v = int(self.val_input.value)
        except: return await interaction.response.send_message("Invalid number.", ephemeral=True)
        if self.skill == "Credit Rating":
            if not (self.view.min_cr <= v <= self.view.max_cr): return await interaction.response.send_message(f"CR must be {self.view.min_cr}-{self.view.max_cr}", ephemeral=True)
        else:
            if v > self.view.max_skill or v < self.base: return await interaction.response.send_message(f"Must be {self.base}-{self.view.max_skill}%", ephemeral=True)
        cost = v - self.current
        if cost > self.view.remaining_points: return await interaction.response.send_message("Not enough points.", ephemeral=True)
        self.view.wizard.char_data[self.skill] = v
        self.view.remaining_points -= cost
        self.view.update_view()
        await interaction.response.edit_message(embed=self.view.get_embed(), view=self.view)

class SkillSpecializationModal(Modal, title="Add Specialization"):
    name_input = TextInput(label="Specialization Name", placeholder="e.g. Painting, Geology")
    val_input = TextInput(label="Total Value", placeholder="e.g. 50")
    def __init__(self, view, parent, base):
        super().__init__()
        self.view = view; self.parent = parent; self.base = base
    async def on_submit(self, interaction: discord.Interaction):
        name = f"{self.parent.split('(')[0].strip()} ({self.name_input.value.strip()})"
        try: v = int(self.val_input.value)
        except: return await interaction.response.send_message("Invalid number.", ephemeral=True)
        cost = v - self.base
        if cost > self.view.remaining_points: return await interaction.response.send_message("Not enough points.", ephemeral=True)
        self.view.wizard.char_data[name] = v
        self.view.remaining_points -= cost
        self.view.all_skills.append(name); self.view.all_skills.sort()
        self.view.update_view()
        await interaction.response.edit_message(embed=self.view.get_embed(), view=self.view)

class CustomSkillModal(Modal, title="Add Custom Skill"):
    name_input = TextInput(label="Skill Name")
    base_input = TextInput(label="Base Value (%)", default="05")
    val_input = TextInput(label="Total Value (%)")
    emoji_input = TextInput(label="Emoji (Optional)", required=False)
    def __init__(self, view):
        super().__init__()
        self.view = view
    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value.strip()
        try: b, v = int(self.base_input.value), int(self.val_input.value)
        except: return await interaction.response.send_message("Invalid numbers.", ephemeral=True)
        cost = v - b
        if cost > self.view.remaining_points: return await interaction.response.send_message("Not enough points.", ephemeral=True)
        self.view.wizard.char_data[name] = v
        self.view.remaining_points -= cost
        self.view.all_skills.append(name); self.view.all_skills.sort()
        if self.emoji_input.value:
            if "Custom Emojis" not in self.view.wizard.char_data: self.view.wizard.char_data["Custom Emojis"] = {}
            self.view.wizard.char_data["Custom Emojis"][name] = self.emoji_input.value.strip()
        self.view.update_view()
        await interaction.response.edit_message(embed=self.view.get_embed(), view=self.view)

class CoreStatSelectView(View):
    def __init__(self, options, wizard):
        super().__init__(timeout=300)
        for opt in options:
            btn = Button(label=opt, style=discord.ButtonStyle.primary)
            btn.callback = self.make_callback(opt, wizard)
            self.add_item(btn)
    def make_callback(self, opt, wizard):
        async def callback(inter): await wizard.apply_core_stat_logic(inter, opt)
        return callback
