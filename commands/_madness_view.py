import discord
import random
from discord.ui import View, Button
from loadnsave import load_madness_group_data, load_madness_solo_data, load_madness_insane_talent_data

# Theme Color
MADNESS_COLOR = 0x8800cc


class MadnessResultView(View):
    def __init__(self, category: str, original_author: discord.User):
        super().__init__(timeout=180)
        self.category = category
        self.original_author = original_author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.original_author:
            await interaction.response.send_message("Only the person who invoked the madness can control it!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🎲 Reroll", style=discord.ButtonStyle.primary)
    async def reroll_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = await get_madness_embed(self.category)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="🔙 Back to Menu", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = get_menu_embed()
        view = MadnessMenuView(self.original_author)
        await interaction.edit_original_response(embed=embed, view=view)


class MadnessMenuView(View):
    def __init__(self, original_author: discord.User):
        super().__init__(timeout=180)
        self.original_author = original_author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.original_author:
            await interaction.response.send_message("Only the person who invoked the madness can control it!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="👥 Group Madness", style=discord.ButtonStyle.primary, row=0)
    async def group_madness(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = await get_madness_embed("Group")
        view = MadnessResultView("Group", self.original_author)
        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="👤 Solo Madness", style=discord.ButtonStyle.primary, row=0)
    async def solo_madness(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = await get_madness_embed("Solo")
        view = MadnessResultView("Solo", self.original_author)
        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="🧠 Insane Talent", style=discord.ButtonStyle.danger, row=1)
    async def insane_talent(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = await get_madness_embed("Talent")
        view = MadnessResultView("Talent", self.original_author)
        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="📜 List All", style=discord.ButtonStyle.secondary, row=1)
    async def list_madness(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        embeds = await get_madness_list_embeds()
        await interaction.followup.send(embeds=embeds[:10], ephemeral=True)


def get_menu_embed():
    embed = discord.Embed(
        title="🌀 Madness Menu",
        description="Select a category of madness to inflict upon the investigators.",
        color=MADNESS_COLOR
    )
    embed.add_field(name="Types", value="• **Group:** Effects that impact the party.\n• **Solo:** Personal descents into madness.\n• **Talent:** Powerful but dangerous pulp abilities.", inline=False)
    return embed


async def get_madness_embed(category: str):
    data = {}
    if category == "Group":
        data = await load_madness_group_data()
        title = "👥 Group Madness"
    elif category == "Solo":
        data = await load_madness_solo_data()
        title = "👤 Solo Madness"
    elif category == "Talent":
        data = await load_madness_insane_talent_data()
        title = "🧠 Insane Talent"

    if not data:
        return discord.Embed(title="Error", description="Could not load madness data.", color=0xFF0000)

    name, description = random.choice(list(data.items()))

    embed = discord.Embed(
        title=f"{title}: {name}",
        description=description,
        color=MADNESS_COLOR
    )
    embed.set_footer(text=f"Category: {category}")
    return embed

async def get_madness_list_embeds():
    embeds = []
    group_data = await load_madness_group_data()
    solo_data = await load_madness_solo_data()
    talent_data = await load_madness_insane_talent_data()

    def create_list_embed(title, data):
        desc = ""
        temp_embeds = []
        for name, description in data.items():
            entry = f"**{name}**: {description}\n\n"
            if len(desc) + len(entry) > 3500:
                temp_embeds.append(discord.Embed(title=title, description=desc, color=MADNESS_COLOR))
                desc = ""
                title = f"{title} (Cont.)"
            desc += entry
        if desc:
            temp_embeds.append(discord.Embed(title=title, description=desc, color=MADNESS_COLOR))
        embeds.extend(temp_embeds)

    create_list_embed("👥 Group Madness Options", group_data)
    create_list_embed("👤 Solo Madness Options", solo_data)
    create_list_embed("🧠 Insane Talents", talent_data)
    return embeds
