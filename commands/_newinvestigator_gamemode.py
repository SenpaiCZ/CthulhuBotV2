import discord
from discord.ui import View, Button, Select
from commands._newinvestigator_data import ERA_SKILLS

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
        await self.cog.step_era(interaction, self.char_data, self.player_stats)
    @discord.ui.button(label="Pulp Cthulhu", style=discord.ButtonStyle.danger)
    async def pulp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.char_data["Game Mode"] = "Pulp of Cthulhu"
        await interaction.response.edit_message(content="Selected: **Pulp Cthulhu**", view=None)
        await self.cog.step_era(interaction, self.char_data, self.player_stats)

class EraSelectView(View):
    def __init__(self, cog, char_data, player_stats):
        super().__init__(timeout=300)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats

    async def select_era(self, interaction: discord.Interaction, era_name):
        self.char_data["Era"] = era_name

        # Cleanup old skills
        all_possible_skills = set()
        for s_map in ERA_SKILLS.values():
            all_possible_skills.update(s_map.keys())

        for k in all_possible_skills:
            if k in self.char_data:
                del self.char_data[k]

        # Apply new era skills
        skills = ERA_SKILLS.get(era_name, ERA_SKILLS["1920s Era"])
        self.char_data.update(skills)

        await interaction.response.edit_message(content=f"Selected Era: **{era_name}**", view=None)

        if self.char_data.get("Game Mode") == "Pulp of Cthulhu":
             await self.cog.select_pulp_archetype(interaction, self.char_data, self.player_stats)
        else:
             await self.cog.step_stats(interaction, self.char_data, self.player_stats)

    @discord.ui.button(label="1920s", style=discord.ButtonStyle.primary)
    async def era_1920s(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.select_era(interaction, "1920s Era")

    @discord.ui.button(label="1930s", style=discord.ButtonStyle.primary)
    async def era_1930s(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.select_era(interaction, "1930s Era")

    @discord.ui.button(label="Modern", style=discord.ButtonStyle.primary)
    async def era_modern(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.select_era(interaction, "Modern Era")

    @discord.ui.button(label="Gaslight", style=discord.ButtonStyle.secondary)
    async def era_gaslight(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.select_era(interaction, "Cthulhu by Gaslight")

    @discord.ui.button(label="Down Darker Trails", style=discord.ButtonStyle.secondary)
    async def era_ddt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.select_era(interaction, "Down Darker Trails")

    @discord.ui.button(label="Dark Ages", style=discord.ButtonStyle.secondary)
    async def era_dark_ages(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.select_era(interaction, "Dark Ages")

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
