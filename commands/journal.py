import discord
from discord import app_commands
from discord.ext import commands
from loadnsave import load_journal_data, save_journal_data
from commands._journal_views import JournalView, ClueDestinationView, JournalEntryModal

class Journal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name='Save as Clue',
            callback=self.save_clue_context,
        )
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    journal_group = app_commands.Group(name="journal", description="📔 Manage and view journals")

    async def save_clue_context(self, interaction: discord.Interaction, message: discord.Message):
        """
        Context Menu: Right-click a message -> Apps -> Save as Clue.
        Opens a modal to save the message content as a journal entry.
        """
        # Prepare pre-filled data
        # Truncate content if too long for modal (4000 char limit usually, but field is 2000)
        content = message.content
        if len(content) > 2000:
            content = content[:1997] + "..."

        # Check for image attachments
        image_attachments = []
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    image_attachments.append(attachment)

        # We use a trick here: passing 'original_entry' populates the fields,
        # but since it lacks 'timestamp' and 'author_id', on_submit will treat it as a NEW entry.
        pre_filled_data = {
            "title": f"Clue from {message.author.display_name}",
            "content": content
        }

        # Check for Admin permissions to offer advanced options
        is_admin = interaction.user.guild_permissions.administrator

        if is_admin:
             view = ClueDestinationView(self, pre_filled_data, image_attachments)
             await interaction.response.send_message("Where should this clue be saved?", view=view, ephemeral=True)
        else:
             # Default to Personal
             modal = JournalEntryModal(self, "personal", target_user_id=None, original_entry=pre_filled_data, title="Save Clue", image_attachments=image_attachments)
             await interaction.response.send_modal(modal)

    @journal_group.command(name="open", description="📖 Open your journal (Personal or Master).")
    async def open_journal(self, interaction: discord.Interaction):
        view = JournalView(self, interaction, mode="personal")
        embed = await view.get_embed()

        # Update buttons initial state
        entries = await view.load_entries()
        view._update_buttons(entries)

        files = view.get_files_for_current_page(entries)

        await interaction.response.send_message(embed=embed, view=view, files=files, ephemeral=True)
        view.message = await interaction.original_response()

    @journal_group.command(name="grant", description="🔓 Grant a user access to the Master Journal (Admin only).")
    @app_commands.describe(user="The user to grant access to")
    @app_commands.checks.has_permissions(administrator=True)
    async def grant_access(self, interaction: discord.Interaction, user: discord.Member):
        guild_id = str(interaction.guild_id)
        user_id = str(user.id)

        data = await load_journal_data()
        if guild_id not in data:
            data[guild_id] = {"master": {"access": [], "entries": []}, "personal": {}}

        if "master" not in data[guild_id]:
             data[guild_id]["master"] = {"access": [], "entries": []}

        if user_id not in data[guild_id]["master"]["access"]:
            data[guild_id]["master"]["access"].append(user_id)
            await save_journal_data(data)
            await interaction.response.send_message(f"✅ Granted **{user.display_name}** access to the Master Journal.", ephemeral=True)
        else:
            await interaction.response.send_message(f"ℹ️ **{user.display_name}** already has access.", ephemeral=True)

    @journal_group.command(name="revoke", description="🔒 Revoke a user's access to the Master Journal (Admin only).")
    @app_commands.describe(user="The user to revoke access from")
    @app_commands.checks.has_permissions(administrator=True)
    async def revoke_access(self, interaction: discord.Interaction, user: discord.Member):
        guild_id = str(interaction.guild_id)
        user_id = str(user.id)

        data = await load_journal_data()
        if guild_id in data and "master" in data[guild_id]:
            if user_id in data[guild_id]["master"]["access"]:
                data[guild_id]["master"]["access"].remove(user_id)
                await save_journal_data(data)
                await interaction.response.send_message(f"🚫 Revoked access for **{user.display_name}**.", ephemeral=True)
                return

        await interaction.response.send_message(f"ℹ️ **{user.display_name}** does not have access.", ephemeral=True)

    @journal_group.command(name="inspect", description="🧐 View a player's personal journal (Admin only).")
    @app_commands.describe(user="The player whose journal you want to read")
    @app_commands.checks.has_permissions(administrator=True)
    async def inspect_journal(self, interaction: discord.Interaction, user: discord.Member):
        view = JournalView(self, interaction, mode="inspect", target_user_id=user.id)
        embed = await view.get_embed()

        # Update buttons initial state
        entries = await view.load_entries()
        view._update_buttons(entries)

        files = view.get_files_for_current_page(entries)

        await interaction.response.send_message(embed=embed, view=view, files=files, ephemeral=True)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(Journal(bot))
