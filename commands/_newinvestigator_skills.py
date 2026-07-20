import discord
import emojis
import emoji
from discord.ui import View, Button, Select, Modal, TextInput, Label
from commands._newinvestigator_data import BASE_SKILLS

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
