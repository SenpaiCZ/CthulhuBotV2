import discord
from discord import app_commands
from discord.ext import commands
from discord import ui
import datetime
from loadnsave import load_journal_data, save_journal_data

class JournalEntryModal(ui.Modal, title="New Journal Entry"):
    def __init__(self, journal_cog, mode, target_user_id=None):
        super().__init__()
        self.journal_cog = journal_cog
        self.mode = mode # 'personal' or 'master'
        self.target_user_id = target_user_id # Only relevant if mode='personal' (user viewing own)

        label = "Date / Title"
        if mode == "master":
            label = "Date (e.g. October 24, 1925)"

        self.entry_title = ui.TextInput(label=label, style=discord.TextStyle.short, placeholder="Enter date or title...", max_length=100)
        self.entry_content = ui.TextInput(label="Entry Content", style=discord.TextStyle.paragraph, placeholder="Write your notes here...", max_length=2000)

        self.add_item(self.entry_title)
        self.add_item(self.entry_content)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)

        data = await load_journal_data()
        if guild_id not in data:
            data[guild_id] = {"master": {"access": [], "entries": []}, "personal": {}}

        entry = {
            "title": self.entry_title.value,
            "content": self.entry_content.value,
            "author_id": user_id,
            "timestamp": datetime.datetime.now().timestamp()
        }

        if self.mode == "master":
            if not interaction.permissions.administrator:
                return await interaction.followup.send("❌ Only Game Masters (Admins) can write to the Master Journal.", ephemeral=True)

            if "master" not in data[guild_id]:
                 data[guild_id]["master"] = {"access": [], "entries": []}

            data[guild_id]["master"]["entries"].append(entry)
            message = "✅ Added entry to **Master Journal**."

        elif self.mode == "personal":
            target = self.target_user_id or user_id
            # Ensure personal structure exists
            if "personal" not in data[guild_id]:
                data[guild_id]["personal"] = {}
            if target not in data[guild_id]["personal"]:
                data[guild_id]["personal"][target] = {"entries": []}

            data[guild_id]["personal"][target]["entries"].append(entry)
            message = "✅ Added entry to **Personal Journal**."

        await save_journal_data(data)
        await interaction.followup.send(message, ephemeral=True)

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

        if self.mode == "inspect":
            return await interaction.response.send_message("You cannot write to another player's journal.", ephemeral=True)

        modal = JournalEntryModal(self.cog, self.mode, self.target_user_id)
        await interaction.response.send_modal(modal)

        # We need to refresh after modal submit, but modal submit is separate interaction.
        # We can't easily wait for it here. The user will have to click prev/next or we can re-send view?
        # Actually, best UX is user re-opens or we add a "Refresh" button?
        # Or simpler: The modal sends a confirmation. The user can click "Next" or "Refresh" if I add one.
        # I'll add a Refresh button.

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", row=0)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.refresh(interaction)

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

    async def refresh(self, interaction):
        embed = await self.get_embed()
        entries = await self.load_entries()

        has_entries = len(entries) > 0
        total_pages = len(entries)

        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= total_pages - 1) or not has_entries

        # Update Switch Label
        if self.mode == "personal":
            self.switch_button.label = "Switch to Master Journal"
        else:
            self.switch_button.label = "Switch to Personal Journal"

        # Permission check for Add Entry
        can_write = False
        if self.mode == "personal":
            can_write = True
        elif self.mode == "master" and interaction.user.guild_permissions.administrator:
            can_write = True

        self.add_entry_button.disabled = not can_write
        self.add_entry_button.style = discord.ButtonStyle.success if can_write else discord.ButtonStyle.secondary

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

class Journal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    journal_group = app_commands.Group(name="journal", description="Manage and view journals")

    @journal_group.command(name="open", description="Open your journal (Personal or Master).")
    async def open_journal(self, interaction: discord.Interaction):
        view = JournalView(self, interaction, mode="personal")
        embed = await view.get_embed()

        # Update buttons initial state
        entries = await view.load_entries()
        has_entries = len(entries) > 0
        view.prev_button.disabled = True
        view.next_button.disabled = (not has_entries) or (len(entries) <= 1)

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
        has_entries = len(entries) > 0
        view.prev_button.disabled = True
        view.next_button.disabled = (not has_entries) or (len(entries) <= 1)

        # Disable Add Entry/Switch for inspect mode initially
        view.add_entry_button.disabled = True
        view.switch_button.label = "Switch to Personal Journal" # Allow admin to switch back to their own

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(Journal(bot))
