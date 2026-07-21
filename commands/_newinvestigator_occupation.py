import discord
import occupation_emoji
from discord.ui import View, Button, Select, Modal, TextInput, Label

# ==============================================================================
# 5. Views (Occupation)
# ==============================================================================

class OccupationSearchModal(Modal, title="Search Occupation"):
    search_term = Label(text="Search", component=TextInput(placeholder="e.g. Detective, Soldier...", min_length=2))
    def __init__(self, cog, interaction, char_data, player_stats, occupations_data):
        super().__init__()
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.occupations_data = occupations_data
    async def on_submit(self, interaction: discord.Interaction):
        term = self.search_term.component.value.lower()
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
    def __init__(self, cog, char_data, player_stats, occupations_data, sort_mode="points"):
        super().__init__(timeout=600)
        self.cog = cog
        self.char_data = char_data
        self.player_stats = player_stats
        self.occupations_data = occupations_data
        self.sort_mode = sort_mode
        self.page = 0

        # Calculate points and sort
        self.sorted_list = []
        for name, info in occupations_data.items():
            pts = cog.calculate_occupation_points(char_data, info)
            self.sorted_list.append((name, pts))

        if sort_mode == "alpha":
            self.sorted_list.sort(key=lambda x: x[0])
        else:
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

    def get_embed(self):
        per_page = 25
        start = self.page * per_page
        end = start + per_page
        current_items = self.sorted_list[start:end]

        description = ""
        for name, pts in current_items:
            emoji_char = occupation_emoji.get_occupation_emoji(name)
            line = f"**{name}**: {pts} pts"
            if emoji_char:
                 line = f"{emoji_char} {line}"
            description += line + "\n"

        if not description:
            description = "No occupations found."

        max_pages = max(1, (len(self.sorted_list) - 1) // per_page + 1)

        title_suffix = " (A-Z)" if self.sort_mode == "alpha" else " (Sorted by Points)"
        embed = discord.Embed(title=f"Occupations List{title_suffix}", description=description, color=discord.Color.blue())
        embed.set_footer(text=f"Page {self.page + 1} / {max_pages} | Total: {len(self.sorted_list)}")
        return embed

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
        view = PaginatedOccupationListView(self.cog, self.char_data, self.player_stats, self.occupations_data, sort_mode="points")
        embed = view.get_embed()
        await interaction.response.edit_message(content="Browsing Occupations (Sorted by Points):", embed=embed, view=view)

    @discord.ui.button(label="Browse Occupations (A-Z)", style=discord.ButtonStyle.secondary, emoji="🔤")
    async def browse_alpha(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PaginatedOccupationListView(self.cog, self.char_data, self.player_stats, self.occupations_data, sort_mode="alpha")
        embed = view.get_embed()
        await interaction.response.edit_message(content="Browsing Occupations (A-Z):", embed=embed, view=view)
