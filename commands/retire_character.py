import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button
from models.database import SessionLocal
from services.character_service import CharacterService

class RetireConfirmationView(View):
    def __init__(self, investigator_id, user_id):
        super().__init__(timeout=60)
        self.investigator_id = investigator_id
        self.user_id = user_id
        self.confirmed = False

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return
        
        db = SessionLocal()
        try:
            CharacterService.toggle_retirement(db, self.investigator_id, True)
            self.confirmed = True
            await interaction.response.edit_message(content="Your character has been retired successfully. You can now create a new character.", view=None)
        finally:
            db.close()
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return
        await interaction.response.edit_message(content="Retirement cancelled.", view=None)
        self.stop()

class UnretireSelect(Select):
    def __init__(self, characters):
        options = []
        for char in characters:
            options.append(discord.SelectOption(label=char.name, value=str(char.id)))
        super().__init__(placeholder="Select a character to unretire...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_id = int(self.values[0])
        await interaction.response.defer()
        self.view.stop()

class UnretireView(View):
    def __init__(self, characters, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.selected_id = None
        self.add_item(UnretireSelect(characters))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return False
        return True

class CharacterManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="retire", description="👋 Retire your current character.")
    async def retire(self, interaction: discord.Interaction):
        """Retire your current character."""
        db = SessionLocal()
        try:
            investigator = CharacterService.get_investigator_by_guild_and_user(
                db, str(interaction.guild_id), str(interaction.user.id)
            )

            if not investigator:
                await interaction.response.send_message("You do not have an active character to retire.", ephemeral=True)
                return

            view = RetireConfirmationView(investigator.id, interaction.user.id)
            await interaction.response.send_message("Are you sure you want to retire your character?", view=view, ephemeral=True)
        finally:
            db.close()

    @app_commands.command(name="unretire", description="🔙 Unretire a character.")
    async def unretire(self, interaction: discord.Interaction):
        """Unretire a character."""
        db = SessionLocal()
        try:
            active = CharacterService.get_investigator_by_guild_and_user(
                db, str(interaction.guild_id), str(interaction.user.id)
            )
            if active:
                await interaction.response.send_message("You already have an active character. Please retire your current character first.", ephemeral=True)
                return

            retired = CharacterService.get_retired_investigators_by_guild_and_user(
                db, str(interaction.guild_id), str(interaction.user.id)
            )
            if not retired:
                await interaction.response.send_message("You do not have any retired characters.", ephemeral=True)
                return

            view = UnretireView(retired, interaction.user.id)
            await interaction.response.send_message("Please select a character to unretire:", view=view, ephemeral=True)
            await view.wait()

            if view.selected_id is not None:
                CharacterService.toggle_retirement(db, view.selected_id, False)
                # Get the name for the message
                char = CharacterService.get_investigator(db, view.selected_id)
                await interaction.followup.send(f"Character '**{char.name}**' has been unretired and is now active.", ephemeral=True)
            else:
                 await interaction.followup.send("No selection made or timed out.", ephemeral=True)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(CharacterManagement(bot))
