import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord import ui
import asyncio
import re
from datetime import datetime, timedelta, timezone
from loadnsave import load_reminder_data, save_reminder_data

class ReminderDeleteSelect(ui.Select):
    def __init__(self, reminders):
        options = []
        # Sort by due time
        sorted_reminders = sorted(reminders, key=lambda x: x['due_timestamp'])

        for r in sorted_reminders[:25]: # Limit to 25 options
            dt = datetime.fromtimestamp(r['due_timestamp'], tz=timezone.utc)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
            label = f"{time_str} - {r['message'][:50]}"
            if len(r['message']) > 50:
                label += "..."

            options.append(discord.SelectOption(
                label=label,
                value=r['id'],
                description=f"Due <t:{int(r['due_timestamp'])}:R>"
            ))

        super().__init__(placeholder="Select a reminder to delete...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # We need access to the Cog to delete
        # Since we can't easily pass the cog instance without complications,
        # we'll rely on the view having a callback or handling it.
        # But wait, the view can have the callback.

        view: ReminderListView = self.view
        await view.delete_reminder(interaction, self.values[0])

class ReminderListView(ui.View):
    def __init__(self, cog, guild_id, user_id, reminders):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.reminders = reminders
        self.message = None

        if reminders:
            self.add_item(ReminderDeleteSelect(reminders))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass # Message might be deleted or interaction expired

    async def delete_reminder(self, interaction: discord.Interaction, reminder_id):
        # Verify ownership (already filtered by user_id in command, but good to be safe)
        # Actually, list command filters by user_id.

        # Proceed to delete
        res, msg = await self.cog.delete_reminder_api(self.guild_id, reminder_id)

        if res:
            await interaction.response.send_message(f"✅ Reminder deleted.", ephemeral=True)
            # Update the original message?
            # It's ephemeral, so we can't easily update the original list without re-fetching.
            # But we can try to disable the view.
            self.stop()
            # Also disable components immediately to show state
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message(f"❌ Failed to delete: {msg}", ephemeral=True)

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = {} # guild_id -> list of reminders

    async def cog_load(self):
        self.reminders = await load_reminder_data()
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        # Current UTC timestamp
        now = datetime.now(timezone.utc).timestamp()
        changed = False

        # Iterate copy of keys to avoid modification issues
        for guild_id in list(self.reminders.keys()):
            items = self.reminders[guild_id]
            to_remove = []

            for reminder in items:
                if reminder['due_timestamp'] <= now:
                    # Trigger reminder
                    await self.send_reminder(reminder)
                    to_remove.append(reminder)
                    changed = True

            if to_remove:
                # Remove triggered reminders from list
                self.reminders[guild_id] = [r for r in items if r not in to_remove]

                # Cleanup empty guilds
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
                user = self.bot.get_user(user_id)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except:
                        pass

                mention = user.mention if user else f"<@{user_id}>"

                embed = discord.Embed(title="⏰ Reminder!", description=f"**{message_text}**", color=discord.Color.gold())

                # Nexus Polish: Add timestamp of when it was set if available
                created_at = reminder.get('created_at')
                if created_at:
                    embed.add_field(name="Set", value=f"<t:{int(created_at)}:f> (<t:{int(created_at)}:R>)", inline=False)

                embed.set_footer(text="To set a new reminder use /reminder set")

                await channel.send(content=mention, embed=embed)
            else:
                print(f"Could not find channel {channel_id} for reminder.")
        except Exception as e:
            print(f"Failed to send reminder: {e}")

    def parse_duration(self, duration_str):
        total_seconds = 0
        text = duration_str.lower().strip()

        # Keyword support
        if text in ['tomorrow', 'tmrw']:
            return 86400
        if text in ['week', 'next week']:
            return 604800
        if text in ['hour', '1h']:
            return 3600

        # Regex for structured duration
        matches = re.findall(r'(\d+)\s*([dhms])', text)
        for amount, unit in matches:
            amount = int(amount)
            if unit == 'd': total_seconds += amount * 86400
            elif unit == 'h': total_seconds += amount * 3600
            elif unit == 'm': total_seconds += amount * 60
            elif unit == 's': total_seconds += amount

        return total_seconds

    # --- Slash Command Group ---
    reminder_group = app_commands.Group(name="reminder", description="Manage your reminders")

    @reminder_group.command(name="set", description="Set a new reminder.")
    @app_commands.describe(duration="Time until reminder (e.g. 10m, 1h, 1d)", message="What to remind you about")
    async def set_reminder(self, interaction: discord.Interaction, duration: str, message: str):
        """Set a reminder."""
        seconds = self.parse_duration(duration)
        if seconds <= 0:
            await interaction.response.send_message("❌ Invalid duration. Please use a format like `10m`, `1h`, `1d`, `30s`.", ephemeral=True)
            return

        res, result = await self.create_reminder_api(
            interaction.guild_id,
            interaction.channel_id,
            interaction.user.id,
            message,
            seconds
        )

        reminder = result
        due_time = reminder['due_timestamp']

        human_time = f"<t:{int(due_time)}:R>"
        embed = discord.Embed(
            title="✅ Reminder Set",
            description=f"I'll remind you in {human_time} about:\n**{message}**",
            color=discord.Color.green()
        )
        embed.set_footer(text="I will ping you in this channel when it's time.")

        await interaction.response.send_message(embed=embed)

    @set_reminder.autocomplete('duration')
    async def duration_autocomplete(self, interaction: discord.Interaction, current: str):
        options = ["5m", "10m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d", "2d", "1w"]
        return [
            app_commands.Choice(name=option, value=option)
            for option in options if current.lower() in option.lower()
        ][:25]

    @reminder_group.command(name="list", description="List your active reminders.")
    async def list_reminders(self, interaction: discord.Interaction):
        """List active reminders."""
        guild_id = str(interaction.guild_id)
        user_id = interaction.user.id

        user_reminders = []
        if guild_id in self.reminders:
            user_reminders = [r for r in self.reminders[guild_id] if r['user_id'] == user_id]

        if not user_reminders:
            embed = discord.Embed(
                title="📭 No Reminders",
                description="You have no active reminders in this server.\nUse `/reminder set` to create one!",
                color=discord.Color.light_grey()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Sort by due time
        user_reminders.sort(key=lambda x: x['due_timestamp'])

        embed = discord.Embed(title=f"📅 Your Reminders ({len(user_reminders)})", color=discord.Color.blurple())

        description = ""
        for r in user_reminders[:10]: # Show top 10 in description
            dt = int(r['due_timestamp'])
            description += f"• <t:{dt}:R>: **{r['message']}**\n"

        if len(user_reminders) > 10:
            description += f"\n*...and {len(user_reminders)-10} more.*"

        embed.description = description

        view = ReminderListView(self, guild_id, user_id, user_reminders)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @reminder_group.command(name="delete", description="Delete a specific reminder.")
    @app_commands.describe(reminder_id="Search for the reminder to delete")
    async def delete_reminder_cmd(self, interaction: discord.Interaction, reminder_id: str):
        """Delete a reminder."""
        guild_id = str(interaction.guild_id)
        res, msg = await self.delete_reminder_api(guild_id, reminder_id)

        if res:
            await interaction.response.send_message(f"✅ Reminder deleted.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Could not delete reminder: {msg}", ephemeral=True)

    @delete_reminder_cmd.autocomplete('reminder_id')
    async def delete_autocomplete(self, interaction: discord.Interaction, current: str):
        guild_id = str(interaction.guild_id)
        user_id = interaction.user.id

        if guild_id not in self.reminders:
            return []

        user_reminders = [r for r in self.reminders[guild_id] if r['user_id'] == user_id]

        choices = []
        for r in user_reminders:
            # Format: "Message (Time)"
            dt = datetime.fromtimestamp(r['due_timestamp'], tz=timezone.utc)
            time_str = dt.strftime("%H:%M") # Short time
            name = f"{r['message'][:30]}... ({time_str})"
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=r['id']))

        return choices[:25]

    # API Methods
    async def create_reminder_api(self, guild_id, channel_id, user_id, message, seconds):
        due_time = datetime.now(timezone.utc).timestamp() + seconds

        if str(guild_id) not in self.reminders:
            self.reminders[str(guild_id)] = []

        reminder = {
            "id": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
            "user_id": int(user_id),
            "channel_id": int(channel_id),
            "message": message,
            "due_timestamp": due_time,
            "created_at": datetime.now(timezone.utc).timestamp()
        }

        self.reminders[str(guild_id)].append(reminder)
        await save_reminder_data(self.reminders)

        return True, reminder

    async def delete_reminder_api(self, guild_id, reminder_id):
        if str(guild_id) in self.reminders:
            original_len = len(self.reminders[str(guild_id)])
            self.reminders[str(guild_id)] = [r for r in self.reminders[str(guild_id)] if r.get('id') != reminder_id]

            if len(self.reminders[str(guild_id)]) < original_len:
                await save_reminder_data(self.reminders)
                return True, "Deleted"

        return False, "Not found"

async def setup(bot):
    await bot.add_cog(Reminders(bot))
