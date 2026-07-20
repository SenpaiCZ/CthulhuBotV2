import discord
from discord.ui import View, Modal, TextInput, Label
from loadnsave import (
    save_player_stats,
    load_retired_characters_data, save_retired_characters_data,
)

class BasicInfoModal(Modal, title="Investigator Details"):
    name = Label(text="Name", component=TextInput(placeholder="Enter character name...", max_length=100))
    residence = Label(text="Residence", component=TextInput(placeholder="e.g. Arkham", required=False, max_length=100))
    age = Label(text="Age", component=TextInput(placeholder="15-90", min_length=2, max_length=2))
    language = Label(text="First Language", component=TextInput(placeholder="e.g. English, French, Chinese...", max_length=50))

    def __init__(self, cog, interaction, char_data, player_stats):
        super().__init__()
        self.cog = cog
        self.origin_interaction = interaction
        self.char_data = char_data
        self.player_stats = player_stats

    async def on_submit(self, interaction: discord.Interaction):
        try:
            age_val = int(self.age.component.value)
            if not (15 <= age_val <= 90): raise ValueError
        except ValueError:
            await interaction.response.send_message("Age must be a number between 15 and 90.", ephemeral=True)
            return
        self.char_data["NAME"] = self.name.component.value
        self.char_data["Residence"] = self.residence.component.value if self.residence.component.value else "Unknown"
        self.char_data["Age"] = age_val
        self.char_data["First Language"] = self.language.component.value.strip() if self.language.component.value else "Own"
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
