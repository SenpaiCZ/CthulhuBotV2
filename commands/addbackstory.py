import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, save_player_stats

class BackstoryAddModal(discord.ui.Modal):
    def __init__(self, category, server_id, user_id, player_stats_ref):
        # Discord Modal title limit is 45 characters
        title = f"Add to {category}"
        if len(title) > 45:
            title = title[:42] + "..."

        super().__init__(title=title)
        self.category = category
        self.server_id = server_id
        self.user_id = user_id
        self.player_stats = player_stats_ref

        self.entry = discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            placeholder="Type your backstory details here...",
            required=True,
            max_length=4000
        )
        self.add_item(discord.ui.Label(text=f"New entry for {category}"[:45], component=self.entry))

    async def on_submit(self, interaction: discord.Interaction):
        # Ensure data structure exists
        if self.server_id not in self.player_stats:
             self.player_stats[self.server_id] = {}

        if self.user_id not in self.player_stats[self.server_id]:
             # Should not happen given command checks, but safety first
             await interaction.response.send_message("Error: Investigator not found.", ephemeral=True)
             return

        if "Backstory" not in self.player_stats[self.server_id][self.user_id]:
            self.player_stats[self.server_id][self.user_id]["Backstory"] = {}

        if self.category not in self.player_stats[self.server_id][self.user_id]["Backstory"]:
            self.player_stats[self.server_id][self.user_id]["Backstory"][self.category] = []

        entry_text = self.entry.value
        self.player_stats[self.server_id][self.user_id]["Backstory"][self.category].append(entry_text)

        await save_player_stats(self.player_stats)

        await interaction.response.send_message(
            f"✅ Added to **{self.category}**:\n>>> {entry_text}",
            ephemeral=True
        )

class BackstoryCategorySelect(discord.ui.Select):
    def __init__(self, categories, server_id, user_id, player_stats_ref):
        options = [
            discord.SelectOption(label=cat[:100], value=cat)
            for cat in categories
        ]
        super().__init__(
            placeholder="Select a category to add to...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.server_id = server_id
        self.user_id = user_id
        self.player_stats = player_stats_ref

    async def callback(self, interaction: discord.Interaction):
        selected_category = self.values[0]
        modal = BackstoryAddModal(selected_category, self.server_id, self.user_id, self.player_stats)
        await interaction.response.send_modal(modal)

class BackstorySelectView(discord.ui.View):
    def __init__(self, categories, author, server_id, user_id, player_stats_ref):
        super().__init__(timeout=60)
        self.author = author
        self.add_item(BackstoryCategorySelect(categories, server_id, user_id, player_stats_ref))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("This isn't your session!", ephemeral=True)
            return False
        return True

class addbackstory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="addbackstory", description="Add a record to your backstory or inventory interactively.")
    async def addbackstory(self, interaction: discord.Interaction):
        """
        Add a record to your backstory or inventory interactively.
        """
        server_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        # Check for DMs
        if not interaction.guild:
             await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)
             return

        player_stats = await load_player_stats()

        # Ensure server/user stats structure exists
        if server_id not in player_stats or user_id not in player_stats[server_id]:
            msg = f"{interaction.user.display_name} doesn't have an investigator. Use `/newinvestigator` to create a new investigator."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        categories = [
          'My Story', 'Personal Description', 'Ideology and Beliefs', 'Significant People',
          'Meaningful Locations', 'Treasured Possessions', 'Traits', 'Injuries and Scars',
          'Phobias and Manias', 'Arcane Tome and Spells', 'Encounters with Strange Entities',
          'Fellow Investigators', 'Gear and Possessions', 'Spending Level', 'Cash', 'Assets'
        ]

        view = BackstorySelectView(categories, interaction.user, server_id, user_id, player_stats)

        await interaction.response.send_message("Select a category to add an entry:", view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(addbackstory(bot))
