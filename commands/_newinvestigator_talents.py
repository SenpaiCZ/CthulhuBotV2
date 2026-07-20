import discord
from discord.ui import View, Select

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
