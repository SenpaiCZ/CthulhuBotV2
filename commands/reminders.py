import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import re
from datetime import datetime, timedelta, timezone
from loadnsave import load_reminder_data, save_reminder_data

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

                embed = discord.Embed(title="⏰ Reminder!", description=message_text, color=discord.Color.gold())
                embed.set_footer(text=f"This reminder was set for now.")

                await channel.send(content=mention, embed=embed)
            else:
                print(f"Could not find channel {channel_id} for reminder.")
        except Exception as e:
            print(f"Failed to send reminder: {e}")

    def parse_duration(self, duration_str):
        total_seconds = 0
        matches = re.findall(r'(\d+)\s*([dhms])', duration_str.lower())
        for amount, unit in matches:
            amount = int(amount)
            if unit == 'd': total_seconds += amount * 86400
            elif unit == 'h': total_seconds += amount * 3600
            elif unit == 'm': total_seconds += amount * 60
            elif unit == 's': total_seconds += amount
        return total_seconds

    @commands.hybrid_command(description="Set a reminder. Example: !remind 2h30m Buy milk")
    @app_commands.describe(duration="Duration (e.g. 1h, 30m, 1d)", message="What to remind you about")
    async def remind(self, ctx, duration: str, *, message: str):
        """⏰ Set a reminder. Usage: !remind 1h30m Do the thing"""
        seconds = self.parse_duration(duration)
        if seconds <= 0:
            await ctx.send("Invalid duration. Use format like `1h`, `30m`, `1d`.", ephemeral=True)
            return

        due_time = datetime.now(timezone.utc).timestamp() + seconds

        guild_id = str(ctx.guild.id)
        if guild_id not in self.reminders:
            self.reminders[guild_id] = []

        reminder = {
            "id": str(int(datetime.now(timezone.utc).timestamp() * 1000)), # Simple ID
            "user_id": ctx.author.id,
            "channel_id": ctx.channel.id,
            "message": message,
            "due_timestamp": due_time,
            "created_at": datetime.now(timezone.utc).timestamp()
        }

        self.reminders[guild_id].append(reminder)
        await save_reminder_data(self.reminders)

        human_time = f"<t:{int(due_time)}:R>"
        embed = discord.Embed(title="⏰ Reminder Set", description=f"I'll remind you {human_time} about:\n**{message}**", color=discord.Color.green())
        await ctx.send(embed=embed)

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

        return True, "Reminder set"

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
