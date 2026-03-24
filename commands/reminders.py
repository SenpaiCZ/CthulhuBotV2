import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timezone
from loadnsave import load_reminder_data, save_reminder_data
from services.admin_service import AdminService
from views.utility_views import ReminderListView, ReminderContextMenuModal

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = {} # guild_id -> list of reminders
        self.help_category = "Other"

        # Register Context Menu
        self.ctx_menu = app_commands.ContextMenu(
            name='⏰ Remind Me',
            callback=self.remind_me_context,
        )
        self.ctx_menu.binding = self
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_load(self):
        self.reminders = await load_reminder_data()
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def remind_me_context(self, interaction: discord.Interaction, message: discord.Message):
        modal = ReminderContextMenuModal(self, message)
        await interaction.response.send_modal(modal)

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        now = datetime.now(timezone.utc).timestamp()
        changed = False

        for guild_id in list(self.reminders.keys()):
            items = self.reminders[guild_id]
            to_remove = []

            for reminder in items:
                if reminder['due_timestamp'] <= now:
                    await self.send_reminder(reminder)
                    to_remove.append(reminder)
                    changed = True

            if to_remove:
                self.reminders[guild_id] = [r for r in items if r not in to_remove]
                if not self.reminders[guild_id]:
                    del self.reminders[guild_id]

        if changed:
            await save_reminder_data(self.reminders)

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()

    async def send_reminder(self, reminder):
        try:
            channel_id = reminder.get('channel_id')
            user_id = reminder.get('user_id')
            message_text = reminder.get('message', 'Reminder!')

            channel = self.bot.get_channel(channel_id)
            if channel:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                mention = user.mention if user else f"<@{user_id}>"

                embed = discord.Embed(title="⏰ Reminder!", description=f"**{message_text}**", color=discord.Color.gold())
                created_at = reminder.get('created_at')
                if created_at:
                    embed.add_field(name="Set", value=f"<t:{int(created_at)}:f> (<t:{int(created_at)}:R>)", inline=False)
                embed.set_footer(text="To set a new reminder use /reminder set")
                await channel.send(content=mention, embed=embed)
        except Exception as e:
            print(f"Failed to send reminder: {e}")

    def parse_duration(self, duration_str):
        return AdminService.parse_duration(duration_str)

    reminder_group = app_commands.Group(name="reminder", description="⏰ Manage your reminders")

    @reminder_group.command(name="set", description="➕ Set a new reminder.")
    @app_commands.describe(duration="Time until reminder (e.g. 10m, 1h, 1d)", message="What to remind you about")
    async def set_reminder(self, interaction: discord.Interaction, duration: str, message: str):
        seconds = self.parse_duration(duration)
        if seconds <= 0:
            await interaction.response.send_message("❌ Invalid duration. Please use a format like `10m`, `1h`, `1d`, `30s`.", ephemeral=True)
            return

        res, result = await self.create_reminder_api(interaction.guild_id, interaction.channel_id, interaction.user.id, message, seconds)
        due_time = result['due_timestamp']
        embed = discord.Embed(title="✅ Reminder Set", description=f"I'll remind you in <t:{int(due_time)}:R> about:\n**{message}**", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    @set_reminder.autocomplete('duration')
    async def duration_autocomplete(self, interaction: discord.Interaction, current: str):
        options = ["5m", "10m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d", "2d", "1w"]
        return [app_commands.Choice(name=o, value=o) for o in options if current.lower() in o.lower()][:25]

    @reminder_group.command(name="list", description="📃 List your active reminders.")
    async def list_reminders(self, interaction: discord.Interaction):
        guild_id, user_id = str(interaction.guild_id), interaction.user.id
        user_reminders = [r for r in self.reminders.get(guild_id, []) if r['user_id'] == user_id]

        if not user_reminders:
            await interaction.response.send_message("You have no active reminders in this server.", ephemeral=True)
            return

        user_reminders.sort(key=lambda x: x['due_timestamp'])
        embed = discord.Embed(title=f"📅 Your Reminders ({len(user_reminders)})", color=discord.Color.blurple())
        embed.description = "\n".join([f"• <t:{int(r['due_timestamp'])}:R>: **{r['message']}**" for r in user_reminders[:10]])
        
        view = ReminderListView(self, guild_id, user_id, user_reminders)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @reminder_group.command(name="delete", description="🗑️ Delete a specific reminder.")
    async def delete_reminder_cmd(self, interaction: discord.Interaction, reminder_id: str):
        res, msg = await self.delete_reminder_api(str(interaction.guild_id), reminder_id)
        await interaction.response.send_message("✅ Reminder deleted." if res else f"❌ Error: {msg}", ephemeral=True)

    @delete_reminder_cmd.autocomplete('reminder_id')
    async def delete_autocomplete(self, interaction: discord.Interaction, current: str):
        user_reminders = [r for r in self.reminders.get(str(interaction.guild_id), []) if r['user_id'] == interaction.user.id]
        return [app_commands.Choice(name=f"{r['message'][:30]}...", value=r['id']) for r in user_reminders if current.lower() in r['message'].lower()][:25]

    async def create_reminder_api(self, guild_id, channel_id, user_id, message, seconds):
        due_time = datetime.now(timezone.utc).timestamp() + seconds
        reminder = {"id": str(int(datetime.now(timezone.utc).timestamp() * 1000)), "user_id": int(user_id), "channel_id": int(channel_id), "message": message, "due_timestamp": due_time, "created_at": datetime.now(timezone.utc).timestamp()}
        self.reminders.setdefault(str(guild_id), []).append(reminder)
        await save_reminder_data(self.reminders)
        return True, reminder

    async def delete_reminder_api(self, guild_id, reminder_id):
        if str(guild_id) in self.reminders:
            old_len = len(self.reminders[str(guild_id)])
            self.reminders[str(guild_id)] = [r for r in self.reminders[str(guild_id)] if r.get('id') != reminder_id]
            if len(self.reminders[str(guild_id)]) < old_len:
                await save_reminder_data(self.reminders)
                return True, "Deleted"
        return False, "Not found"

async def setup(bot):
    await bot.add_cog(Reminders(bot))
