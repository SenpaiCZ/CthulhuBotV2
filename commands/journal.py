import discord
from discord import app_commands
from discord.ext import commands
from discord import ui
import os
import uuid
from models.database import SessionLocal
from services.campaign_service import CampaignService
from services.character_service import CharacterService
from views.campaign_dashboard import CampaignDashboardView
from schemas.campaign import JournalEntryCreate

class JournalEntryModal(ui.Modal, title="New Journal Entry"):
    def __init__(self, journal_type="Personal", image_attachments=None, target_user_id=None):
        super().__init__()
        self.journal_type = journal_type
        self.image_attachments = image_attachments or []
        self.target_user_id = target_user_id
        
        self.entry_title = ui.TextInput(label="Title", placeholder="Entry title...", max_length=100)
        self.entry_content = ui.TextInput(label="Content", style=discord.TextStyle.paragraph, placeholder="Write your notes here...", max_length=2000)
        self.add_item(self.entry_title)
        self.add_item(self.entry_content)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        db = SessionLocal()
        try:
            saved_images = []
            if self.image_attachments:
                folder_path = os.path.join("data", "journal_images")
                os.makedirs(folder_path, exist_ok=True)
                for attachment in self.image_attachments:
                    filename = f"{uuid.uuid4()}{os.path.splitext(attachment.filename)[1]}"
                    await attachment.save(os.path.join(folder_path, filename))
                    saved_images.append(filename)

            owner_id = self.target_user_id or str(interaction.user.id)
            data = JournalEntryCreate(
                guild_id=str(interaction.guild_id),
                journal_type=self.journal_type,
                author_id=str(interaction.user.id),
                owner_id=owner_id if self.journal_type == "Personal" else None,
                title=self.entry_title.value,
                content=self.entry_content.value,
                images=saved_images
            )
            CampaignService.add_journal_entry(db, data)
            await interaction.followup.send(f"✅ Added entry to {self.journal_type} Journal.", ephemeral=True)
        finally:
            db.close()

class Journal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(name='Save as Clue', callback=self.save_clue_context)
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def save_clue_context(self, interaction: discord.Interaction, message: discord.Message):
        images = [a for a in message.attachments if a.content_type and a.content_type.startswith('image/')]
        modal = JournalEntryModal(journal_type="Personal", image_attachments=images)
        modal.entry_title.default = f"Clue: {message.author.display_name}"
        modal.entry_content.default = message.content[:2000]
        await interaction.response.send_modal(modal)

    journal_group = app_commands.Group(name="journal", description="📔 Manage and view journals")

    @journal_group.command(name="open", description="📖 Open your campaign dashboard on the Journal tab.")
    async def open_journal(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            investigator = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild_id), str(interaction.user.id))
            if not investigator:
                return await interaction.response.send_message("❌ You don't have an active investigator.", ephemeral=True)
            
            view = CampaignDashboardView(str(interaction.guild_id), str(interaction.user.id), investigator.id)
            view.current_tab = "Journal"
            await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)
        finally:
            db.close()

    @journal_group.command(name="add", description="✍️ Add a new entry to your journal.")
    @app_commands.choices(journal_type=[
        app_commands.Choice(name="Personal", value="Personal"),
        app_commands.Choice(name="Master", value="Master")
    ])
    async def add_entry(self, interaction: discord.Interaction, journal_type: str = "Personal"):
        if journal_type == "Master" and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only GMs can write to the Master Journal.", ephemeral=True)
        await interaction.response.send_modal(JournalEntryModal(journal_type=journal_type))

async def setup(bot):
    await bot.add_cog(Journal(bot))
