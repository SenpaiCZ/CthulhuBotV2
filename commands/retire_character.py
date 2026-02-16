import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button
from loadnsave import load_player_stats, save_player_stats, load_retired_characters_data, save_retired_characters_data
import asyncio

class RetireConfirmationView(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed = False

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        await interaction.response.defer()
        self.stop()

class UnretireSelect(Select):
    def __init__(self, characters):
        options = []
        for i, char in enumerate(characters):
            # Ensure unique value for each option
            options.append(discord.SelectOption(label=char.get('NAME', 'Unknown'), value=str(i)))
        super().__init__(placeholder="Select a character to unretire...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_index = int(self.values[0])
        await interaction.response.defer()
        self.view.stop()

class UnretireView(View):
    def __init__(self, characters):
        super().__init__(timeout=60)
        self.selected_index = None
        self.add_item(UnretireSelect(characters))

class CharacterManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="retire", description="Retire your current character.")
    async def retire(self, interaction: discord.Interaction):
        """Retire your current character."""
        server_id = str(interaction.guild_id)
        player_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        if server_id not in player_stats or player_id not in player_stats[server_id]:
            await interaction.response.send_message("You do not have an active character to retire.", ephemeral=True)
            return

        view = RetireConfirmationView()
        await interaction.response.send_message("Are you sure you want to retire your character?", view=view, ephemeral=True)
        await view.wait()

        if view.confirmed:
            character_data = player_stats[server_id].pop(player_id)
            retired_characters = await load_retired_characters_data()

            if player_id not in retired_characters:
                retired_characters[player_id] = []

            retired_characters[player_id].append(character_data)
            await save_retired_characters_data(retired_characters)
            await save_player_stats(player_stats)

            await interaction.followup.send("Your character has been retired successfully. You can now create a new character.", ephemeral=True)
        else:
            await interaction.followup.send("Retirement cancelled.", ephemeral=True)

    @app_commands.command(name="unretire", description="Unretire a character.")
    async def unretire(self, interaction: discord.Interaction):
        """Unretire a character."""
        server_id = str(interaction.guild_id)
        player_id = str(interaction.user.id)
        player_stats = await load_player_stats()

        if server_id in player_stats and player_id in player_stats[server_id]:
            await interaction.response.send_message("You already have an active character. Please retire your current character first.", ephemeral=True)
            return

        retired_characters = await load_retired_characters_data()
        if player_id not in retired_characters or not retired_characters[player_id]:
            await interaction.response.send_message("You do not have any retired characters.", ephemeral=True)
            return

        characters = retired_characters[player_id]
        view = UnretireView(characters)
        await interaction.response.send_message("Please select a character to unretire:", view=view, ephemeral=True)
        await view.wait()

        if view.selected_index is not None:
            if 0 <= view.selected_index < len(characters):
                selected_character = retired_characters[player_id].pop(view.selected_index)

                if server_id not in player_stats:
                    player_stats[server_id] = {}

                player_stats[server_id][player_id] = selected_character

                # If list is empty for user, remove key? optional but cleaner
                if not retired_characters[player_id]:
                    del retired_characters[player_id]

                await save_retired_characters_data(retired_characters)
                await save_player_stats(player_stats)
                await interaction.followup.send(f"Character '**{selected_character.get('NAME', 'Unknown')}**' has been unretired and is now active.", ephemeral=True)
            else:
                 await interaction.followup.send("Invalid selection.", ephemeral=True)
        else:
             await interaction.followup.send("No selection made or timed out.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(CharacterManagement(bot))
