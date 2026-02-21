import discord
from discord import app_commands
from discord.ext import commands
from discord import ui
import datetime
from loadnsave import load_journal_data, save_journal_data

class JournalEntryModal(ui.Modal, title="New Journal Entry"):
    def __init__(self, journal_cog, mode, target_user_id=None, entry_index=None, original_entry=None, parent_view=None, title=None):
        super().__init__(title=title or "New Journal Entry")
        self.journal_cog = journal_cog
        self.mode = mode # 'personal' or 'master'
        self.target_user_id = target_user_id # Only relevant if mode='personal' (user viewing own)
        self.entry_index = entry_index
        self.original_entry = original_entry
        self.parent_view = parent_view

        if self.entry_index is not None:
            self.title = "Edit Journal Entry"

        label = "Date / Title"
        if mode == "master":
            label = "Date (e.g. October 24, 1925)"

        default_title = original_entry.get("title", "") if original_entry else ""
        default_content = original_entry.get("content", "") if original_entry else ""

        self.entry_title = ui.TextInput(label=label, style=discord.TextStyle.short, placeholder="Enter date or title...", max_length=100, default=default_title)
        self.entry_content = ui.TextInput(label="Entry Content", style=discord.TextStyle.paragraph, placeholder="Write your notes here...", max_length=2000, default=default_content)

        self.add_item(self.entry_title)
        self.add_item(self.entry_content)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)

        data = await load_journal_data()
        if guild_id not in data:
            data[guild_id] = {"master": {"access": [], "entries": []}, "personal": {}}

        # Construct new entry data
        timestamp = datetime.datetime.now().timestamp()
        author = user_id

        if self.original_entry:
            # Preserve original timestamp and author if editing
            timestamp = self.original_entry.get("timestamp", timestamp)
            author = self.original_entry.get("author_id", author)

        entry = {
            "title": self.entry_title.value,
            "content": self.entry_content.value,
            "author_id": author,
            "timestamp": timestamp
        }

        if self.mode == "master":
            if not interaction.permissions.administrator:
                return await interaction.followup.send("❌ Only Game Masters (Admins) can write to the Master Journal.", ephemeral=True)

            if "master" not in data[guild_id]:
                 data[guild_id]["master"] = {"access": [], "entries": []}

            entries_list = data[guild_id]["master"]["entries"]
            if self.entry_index is not None:
                if 0 <= self.entry_index < len(entries_list):
                    entries_list[self.entry_index] = entry
                    message = "✅ Updated entry in **Master Journal**."
                else:
                    return await interaction.followup.send("❌ Error: Entry not found or index out of bounds.", ephemeral=True)
            else:
                entries_list.append(entry)
                message = "✅ Added entry to **Master Journal**."

        elif self.mode in ["personal", "inspect"]:
            # If mode is inspect, target_user_id is the owner. If personal, target_user_id might be None (so use user_id) or set.
            # In inspect, admin is editing. In personal, user is editing.

            target = self.target_user_id or user_id

            # Permission check for Inspect mode (Admin editing other's journal)
            if self.mode == "inspect" and not interaction.permissions.administrator:
                 return await interaction.followup.send("❌ Only Game Masters (Admins) can edit player journals.", ephemeral=True)

            # Ensure personal structure exists
            if "personal" not in data[guild_id]:
                data[guild_id]["personal"] = {}
            if target not in data[guild_id]["personal"]:
                data[guild_id]["personal"][target] = {"entries": []}

            entries_list = data[guild_id]["personal"][target]["entries"]
            if self.entry_index is not None:
                if 0 <= self.entry_index < len(entries_list):
                    entries_list[self.entry_index] = entry
                    message = f"✅ Updated entry in **{target}'s Journal**." if self.mode == "inspect" else "✅ Updated entry in **Personal Journal**."
                else:
                    return await interaction.followup.send("❌ Error: Entry not found or index out of bounds.", ephemeral=True)
            else:
                entries_list.append(entry)
                message = "✅ Added entry to **Personal Journal**."

        await save_journal_data(data)
        await interaction.followup.send(message, ephemeral=True)

        # Refresh parent view if available
        if hasattr(self, 'journal_cog') and hasattr(self, 'parent_view') and self.parent_view:
             await self.parent_view.external_refresh()

class DeleteConfirmationView(ui.View):
    def __init__(self, mode, target_user_id, entry_index, parent_view):
        super().__init__(timeout=60)
        self.mode = mode
        self.target_user_id = target_user_id
        self.entry_index = entry_index
        self.parent_view = parent_view

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        data = await load_journal_data()

        deleted = False
        if self.mode == "master":
             if guild_id in data and "master" in data[guild_id]:
                  entries = data[guild_id]["master"]["entries"]
                  if 0 <= self.entry_index < len(entries):
                      entries.pop(self.entry_index)
                      deleted = True

        elif self.mode in ["personal", "inspect"]:
             target = self.target_user_id
             if guild_id in data and "personal" in data[guild_id] and target in data[guild_id]["personal"]:
                  entries = data[guild_id]["personal"][target]["entries"]
                  if 0 <= self.entry_index < len(entries):
                      entries.pop(self.entry_index)
                      deleted = True

        if deleted:
            await save_journal_data(data)
            await interaction.followup.send("🗑️ Entry deleted.", ephemeral=True)
            if hasattr(self.parent_view, 'external_refresh'):
                await self.parent_view.external_refresh()
        else:
            await interaction.followup.send("❌ Error: Could not find entry to delete.", ephemeral=True)

        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Deletion cancelled.", ephemeral=True)
        self.stop()

class JournalView(ui.View):
    def __init__(self, cog, interaction, mode="personal", target_user_id=None):
        super().__init__(timeout=300)
        self.cog = cog
        self.interaction = interaction
        self.mode = mode # 'personal', 'master', 'inspect'
        self.target_user_id = str(target_user_id) if target_user_id else str(interaction.user.id)
        self.current_page = 0
        self.data = None
        self.message = None

    async def load_entries(self):
        guild_id = str(self.interaction.guild_id)
        raw_data = await load_journal_data()

        if guild_id not in raw_data:
             return []

        if self.mode == "master":
            return raw_data[guild_id].get("master", {}).get("entries", [])
        elif self.mode in ["personal", "inspect"]:
            personal_data = raw_data[guild_id].get("personal", {})
            user_data = personal_data.get(self.target_user_id, {})
            return user_data.get("entries", [])
        return []

    async def get_embed(self):
        entries = await self.load_entries()
        total_pages = len(entries)

        if self.mode == "master":
            title = "📜 Master Journal"
            color = discord.Color.gold()
        elif self.mode == "inspect":
            member = self.interaction.guild.get_member(int(self.target_user_id))
            name = member.display_name if member else "Unknown"
            title = f"📓 Player Journal: {name}"
            color = discord.Color.blue()
        else:
            title = "📓 Personal Journal"
            color = discord.Color.blue()

        embed = discord.Embed(title=title, color=color)

        if not entries:
            embed.description = "*This journal is empty.*"
            if self.mode == "personal" or (self.mode == "master" and self.interaction.user.guild_permissions.administrator):
                embed.set_footer(text="Use the 'Add Entry' button to start writing.")
            return embed

        # Sort entries? Usually chronological is best for journals.
        # Assuming appended in order, so index 0 is oldest.
        # Maybe show newest first?
        # Let's show newest first by reversing index access logic or reversing list.
        # Reversing list is easier.
        reversed_entries = list(reversed(entries))

        # Pagination
        self.current_page = max(0, min(self.current_page, total_pages - 1))
        entry = reversed_entries[self.current_page]

        embed.title = f"{title} - {entry['title']}"
        embed.description = entry['content']

        timestamp = entry.get('timestamp')
        date_str = ""
        if timestamp:
            date_str = f"<t:{int(timestamp)}:D>"

        footer_text = f"Entry {self.current_page + 1}/{total_pages}"
        if timestamp:
            footer_text += f" • Written: {datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')}"

        embed.set_footer(text=footer_text)

        # Add author info for Master Journal if relevant (though usually GM is author)
        if self.mode == "master":
            author_id = entry.get('author_id')
            if author_id:
                embed.set_footer(text=f"{footer_text} • Author ID: {author_id}")

        return embed


    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.interaction.user.id: return
        entries = await self.load_entries()
        if not entries: return

        self.current_page = max(0, self.current_page - 1)
        await self.refresh(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.interaction.user.id: return
        entries = await self.load_entries()
        if not entries: return

        # Total pages based on reversed list
        total_pages = len(entries)
        self.current_page = min(total_pages - 1, self.current_page + 1)
        await self.refresh(interaction)

    @discord.ui.button(label="Add Entry", style=discord.ButtonStyle.success, row=0)
    async def add_entry_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.interaction.user.id: return

        # Permission check again, just in case
        if self.mode == "inspect" and not interaction.user.guild_permissions.administrator:
             return await interaction.response.send_message("You cannot write to another player's journal.", ephemeral=True)

        modal = JournalEntryModal(self.cog, self.mode, self.target_user_id, parent_view=self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", row=0)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.refresh(interaction)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, row=1)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.interaction.user.id: return

        entries = await self.load_entries()
        if not entries: return

        reversed_entries = list(reversed(entries))
        if not (0 <= self.current_page < len(reversed_entries)):
            return

        entry = reversed_entries[self.current_page]
        real_index = len(entries) - 1 - self.current_page

        modal = JournalEntryModal(self.cog, self.mode, self.target_user_id, entry_index=real_index, original_entry=entry, parent_view=self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, row=1)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.interaction.user.id: return

        entries = await self.load_entries()
        if not entries: return

        real_index = len(entries) - 1 - self.current_page

        view = DeleteConfirmationView(self.mode, self.target_user_id, real_index, self)
        await interaction.response.send_message("⚠️ Are you sure you want to delete this entry?", view=view, ephemeral=True)

    @discord.ui.button(label="Switch Journal", style=discord.ButtonStyle.secondary, row=1)
    async def switch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.interaction.user.id: return

        # Toggle logic
        new_mode = "personal"
        if self.mode == "personal":
            # Check if can access master
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            data = await load_journal_data()
            master_data = data.get(guild_id, {}).get("master", {})
            access_list = master_data.get("access", [])

            is_admin = interaction.user.guild_permissions.administrator
            if is_admin or str(user_id) in access_list:
                new_mode = "master"
            else:
                return await interaction.response.send_message("⛔ You do not have access to the Master Journal.", ephemeral=True)
        elif self.mode == "master":
            new_mode = "personal"
        elif self.mode == "inspect":
            new_mode = "personal" # Back to own

        if new_mode == "personal":
            self.target_user_id = str(interaction.user.id)

        self.mode = new_mode
        self.current_page = 0
        await self.refresh(interaction)

    async def external_refresh(self):
        """Refreshes the view from an external event (e.g. Modal submit or Delete)."""
        if not self.message:
            return

        embed = await self.get_embed()
        entries = await self.load_entries()
        self._update_buttons(entries)

        try:
            await self.message.edit(embed=embed, view=self)
        except discord.NotFound:
            pass # Message deleted
        except Exception as e:
            print(f"Error refreshing journal view: {e}")

    async def refresh(self, interaction):
        embed = await self.get_embed()
        entries = await self.load_entries()

        self._update_buttons(entries)

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    def _update_buttons(self, entries):
        has_entries = len(entries) > 0
        total_pages = len(entries)

        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= total_pages - 1) or not has_entries

        # Update Switch Label
        if self.mode == "personal":
            self.switch_button.label = "Switch to Master Journal"
        else:
            self.switch_button.label = "Switch to Personal Journal"

        # Permission check for Write Access
        can_write = False
        is_admin = self.interaction.user.guild_permissions.administrator

        if self.mode == "personal":
            can_write = True # User owns their personal journal
        elif self.mode == "master" and is_admin:
            can_write = True
        elif self.mode == "inspect" and is_admin:
            can_write = True

        self.add_entry_button.disabled = not can_write
        self.add_entry_button.style = discord.ButtonStyle.success if can_write else discord.ButtonStyle.secondary

        # Edit/Delete Buttons
        # Only show/enable if there are entries and user has write access
        self.edit_button.disabled = not (can_write and has_entries)
        self.delete_button.disabled = not (can_write and has_entries)

class Journal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    journal_group = app_commands.Group(name="journal", description="Manage and view journals")

    @app_commands.context_menu(name="Save as Clue")
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

        # We use a trick here: passing 'original_entry' populates the fields,
        # but since it lacks 'timestamp' and 'author_id', on_submit will treat it as a NEW entry.
        pre_filled_data = {
            "title": f"Clue from {message.author.display_name}",
            "content": content
        }

        # Determine mode - default to Personal for clues
        mode = "personal"

        # Launch Modal
        modal = JournalEntryModal(self, mode, target_user_id=None, original_entry=pre_filled_data, title="Save Clue")
        await interaction.response.send_modal(modal)

    @journal_group.command(name="open", description="Open your journal (Personal or Master).")
    async def open_journal(self, interaction: discord.Interaction):
        view = JournalView(self, interaction, mode="personal")
        embed = await view.get_embed()

        # Update buttons initial state
        entries = await view.load_entries()
        view._update_buttons(entries)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @journal_group.command(name="grant", description="Grant a user access to the Master Journal (Admin only).")
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

    @journal_group.command(name="revoke", description="Revoke a user's access to the Master Journal (Admin only).")
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

    @journal_group.command(name="inspect", description="View a player's personal journal (Admin only).")
    @app_commands.describe(user="The player whose journal you want to read")
    @app_commands.checks.has_permissions(administrator=True)
    async def inspect_journal(self, interaction: discord.Interaction, user: discord.Member):
        view = JournalView(self, interaction, mode="inspect", target_user_id=user.id)
        embed = await view.get_embed()

        # Update buttons initial state
        entries = await view.load_entries()
        view._update_buttons(entries)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(Journal(bot))
