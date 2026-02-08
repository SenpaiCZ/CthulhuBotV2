import discord
from discord.ext import commands, tasks
import aiohttp
from bs4 import BeautifulSoup
import datetime
import asyncio
from loadnsave import load_pogo_settings, save_pogo_settings, load_pogo_events, save_pogo_events

class PokemonGo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = [] # List of dicts
        self.settings = {} # guild_id -> {channel_id, role_id, ...}

        # Load data immediately
        self.bot.loop.create_task(self.load_data())

        self.check_events_task.start()
        self.notify_events_task.start()
        self.weekly_summary_task.start()

    async def load_data(self):
        self.settings = await load_pogo_settings()
        cached_events = await load_pogo_events()
        if cached_events:
            self.events = cached_events

        # Initial scrape if empty
        if not self.events:
            await self.scrape_events()

    def cog_unload(self):
        self.check_events_task.cancel()
        self.notify_events_task.cancel()
        self.weekly_summary_task.cancel()

    async def scrape_events(self):
        url = "https://leekduck.com/events/"
        print("Scraping LeekDuck events...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        print(f"Failed to fetch LeekDuck: {response.status}")
                        return []
                    html = await response.text()

            soup = BeautifulSoup(html, 'html.parser')
            events = []

            # LeekDuck uses data attributes for sorting and dates
            # We look for the span wrapper
            items = soup.find_all(class_="event-header-item-wrapper")

            now = datetime.datetime.now()

            for item in items:
                start_date_str = item.get('data-event-start-date') # ISO format: YYYY-MM-DDTHH:MM:SS
                if not start_date_str: continue

                # Parse date (Naive)
                try:
                    clean_date_str = start_date_str.replace('Z', '')
                    start_date = datetime.datetime.fromisoformat(clean_date_str)

                    # Force naive to match system time (requested by user)
                    if start_date.tzinfo is not None:
                         start_date = start_date.replace(tzinfo=None)
                except ValueError:
                    continue

                # Filter out past events
                if start_date < now:
                    continue

                link_tag = item.find('a', class_='event-item-link')
                link = "https://leekduck.com" + link_tag['href'] if link_tag else ""

                img_tag = item.find('img')
                image_url = img_tag['src'] if img_tag else ""

                text_div = item.find(class_='event-text')
                title = text_div.find('h2').text.strip() if text_div and text_div.find('h2') else "Unknown Event"

                time_str = text_div.find('p').text.strip() if text_div and text_div.find('p') else ""

                # Fix "Calculating..." time string by using Discord timestamp
                if "Calculating..." in time_str:
                    try:
                        # Re-parse to get aware datetime for timestamp
                        # If start_date_str had 'Z', clean_date_str is naive (implicit UTC)
                        # If start_date_str had offset, clean_date_str has offset
                        ts_dt = datetime.datetime.fromisoformat(clean_date_str)
                        if ts_dt.tzinfo is None:
                            ts_dt = ts_dt.replace(tzinfo=datetime.timezone.utc)

                        timestamp = int(ts_dt.timestamp())
                        time_str = f"<t:{timestamp}:f>"
                    except Exception as e:
                        print(f"Error calculating timestamp for {title}: {e}")

                heading_span = text_div.find(class_='event-tag-badge')
                heading = heading_span.text.strip() if heading_span else "Event"

                events.append({
                    'title': title,
                    'link': link,
                    'image': image_url,
                    'start_time': start_date.isoformat(), # Store as naive ISO string
                    'time_text': time_str,
                    'type': heading
                })

            # Sort by date
            events.sort(key=lambda x: x['start_time'])

            self.events = events
            await save_pogo_events(events)
            print(f"Scraped {len(events)} upcoming events.")
            return events

        except Exception as e:
            print(f"Error scraping LeekDuck: {e}")
            return []

    # --- Commands ---

    @commands.group(invoke_without_command=True)
    async def pogo(self, ctx):
        """Pokemon GO Event Commands"""
        await ctx.send_help(ctx.command)

    @pogo.command(name="setchannel")
    @commands.has_permissions(administrator=True)
    async def set_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel for POGO notifications."""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.settings:
            self.settings[guild_id] = {}

        self.settings[guild_id]['channel_id'] = channel.id
        await save_pogo_settings(self.settings)
        await ctx.send(f"Pokemon GO notifications will be sent to {channel.mention}")

    @pogo.command(name="setrole")
    @commands.has_permissions(administrator=True)
    async def set_role(self, ctx, role: discord.Role):
        """Set the role to ping for POGO notifications."""
        guild_id = str(ctx.guild.id)
        if guild_id not in self.settings:
            self.settings[guild_id] = {}

        self.settings[guild_id]['role_id'] = role.id
        await save_pogo_settings(self.settings)
        await ctx.send(f"Role {role.mention} will be pinged for notifications.")

    @pogo.command(name="forceupdate")
    @commands.has_permissions(administrator=True)
    async def force_update(self, ctx):
        """Force update events from LeekDuck."""
        msg = await ctx.send("Scraping events...")
        events = await self.scrape_events()
        await msg.edit(content=f"Updated! Found {len(events)} upcoming events.")

    async def send_weekly_summary_to_guild(self, guild_id, ping=True):
        """Sends weekly summary to a specific guild immediately."""
        config = self.settings.get(str(guild_id))
        if not config: return False, "Guild not configured"

        channel_id = config.get('channel_id')
        if not channel_id: return False, "Channel not configured"

        channel = self.bot.get_channel(channel_id)
        if not channel: return False, "Channel not found"

        now = datetime.datetime.now()
        # Extend to the end of the next Sunday to include late evening events
        next_week_end = (now + datetime.timedelta(days=7)).replace(hour=23, minute=59, second=59)

        upcoming_week_events = []
        for ev in self.events:
            start_dt = datetime.datetime.fromisoformat(ev['start_time'])
            if now < start_dt <= next_week_end:
                upcoming_week_events.append(ev)

        if not upcoming_week_events:
            return False, "No upcoming events this week"

        role_id = config.get('role_id')
        ping_str = f"<@&{role_id}>" if role_id and ping else ""

        embed = discord.Embed(title="📅 Events This Week", color=0x00FFFF)

        description = ""
        for ev in upcoming_week_events:
            start_dt = datetime.datetime.fromisoformat(ev['start_time'])
            day_name = start_dt.strftime("%A")
            description += f"**{day_name}**: [{ev['title']}]({ev['link']}) ({ev['time_text']})\n"

        embed.description = description

        try:
            await channel.send(f"{ping_str} Here is the summary for the upcoming week!", embed=embed)
            return True, "Sent"
        except Exception as e:
            return False, f"Failed to send: {e}"

    async def send_next_event_to_guild(self, guild_id, ping=True):
        """Sends the next upcoming event to a specific guild immediately."""
        config = self.settings.get(str(guild_id))
        if not config: return False, "Guild not configured"

        channel_id = config.get('channel_id')
        if not channel_id: return False, "Channel not configured"

        channel = self.bot.get_channel(channel_id)
        if not channel: return False, "Channel not found"

        now = datetime.datetime.now()
        next_event = None
        for ev in self.events:
            start_dt = datetime.datetime.fromisoformat(ev['start_time'])
            if start_dt > now:
                next_event = ev
                break

        if not next_event:
            return False, "No upcoming events found"

        role_id = config.get('role_id')
        ping_str = f"<@&{role_id}>" if role_id and ping else ""

        embed = discord.Embed(title=f"Upcoming Event: {next_event['title']}", url=next_event['link'], color=0xFFA500)
        if next_event['image']:
            embed.set_thumbnail(url=next_event['image'])

        # Calculate time until
        start_dt = datetime.datetime.fromisoformat(next_event['start_time'])
        time_diff = start_dt - now
        minutes_until = int(time_diff.total_seconds() / 60)
        hours_until = minutes_until // 60
        mins_rem = minutes_until % 60

        time_str = ""
        if hours_until > 0:
            time_str += f"{hours_until}h "
        time_str += f"{mins_rem}m"

        description = f"**Starts in:** {time_str}\n**Time:** {next_event['time_text']}\n**Type:** {next_event['type']}"
        embed.description = description

        try:
            await channel.send(f"{ping_str} Next upcoming event:", embed=embed)
            return True, "Sent"
        except Exception as e:
            return False, f"Failed to send: {e}"

    # --- Tasks ---

    @tasks.loop(hours=24)
    async def check_events_task(self):
        """Daily task at 08:00 to scrape and send daily summary."""
        await self.scrape_events()

        # Send Daily Summary (Events starting tomorrow)
        now = datetime.datetime.now()
        tomorrow = now.date() + datetime.timedelta(days=1)

        tomorrow_events = []
        for ev in self.events:
            start_dt = datetime.datetime.fromisoformat(ev['start_time'])
            if start_dt.date() == tomorrow:
                tomorrow_events.append(ev)

        if tomorrow_events:
            await self.send_daily_summary(tomorrow_events)

    @check_events_task.before_loop
    async def before_check_events(self):
        await self.bot.wait_until_ready()
        now = datetime.datetime.now()
        # Calculate next 08:00
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)

        seconds = (target - now).total_seconds()
        print(f"POGO: Sleeping {seconds}s until daily update at 08:00")
        await asyncio.sleep(seconds)

    async def send_daily_summary(self, events):
        """Sends a summary of events starting tomorrow."""
        for guild_id, config in self.settings.items():
            channel_id = config.get('channel_id')
            if not channel_id: continue

            channel = self.bot.get_channel(channel_id)
            if not channel: continue

            # Check if daily summary is enabled (default True)
            if not config.get('daily_summary_enabled', True):
                continue

            role_id = config.get('role_id')
            ping = f"<@&{role_id}>" if role_id else ""

            embed = discord.Embed(title="📅 Events Starting Tomorrow", color=0x2E8B57)

            for ev in events:
                embed.add_field(
                    name=ev['title'],
                    value=f"**Type:** {ev['type']}\n**Time:** {ev['time_text']}\n[Link]({ev['link']})",
                    inline=False
                )

            try:
                await channel.send(f"{ping} Here is the summary for tomorrow's Pokemon GO events!", embed=embed)
            except Exception as e:
                print(f"Failed to send daily summary to guild {guild_id}: {e}")

    @tasks.loop(minutes=5)
    async def notify_events_task(self):
        """Checks for events starting soon (default 2h)."""
        now = datetime.datetime.now()

        if not self.events:
            return

        for guild_id, config in self.settings.items():
            channel_id = config.get('channel_id')
            if not channel_id: continue

            channel = self.bot.get_channel(channel_id)
            if not channel: continue

            # Check if event start notification is enabled (default True)
            if not config.get('event_start_enabled', True):
                continue

            advance_minutes = config.get('advance_minutes', 120)
            role_id = config.get('role_id')
            ping = f"<@&{role_id}>" if role_id else ""

            for ev in self.events:
                start_dt = datetime.datetime.fromisoformat(ev['start_time'])
                time_diff = start_dt - now
                minutes_until = time_diff.total_seconds() / 60

                # Check if we are in the notification window (e.g. 120 min to 115 min)
                if advance_minutes - 5 < minutes_until <= advance_minutes:
                    # Send notification
                    embed = discord.Embed(title=f"⏰ Upcoming Event: {ev['title']}", url=ev['link'], color=0xFFA500)
                    if ev['image']:
                        embed.set_thumbnail(url=ev['image'])

                    description = f"**Starts in:** {int(minutes_until)} minutes\n**Time:** {ev['time_text']}\n**Type:** {ev['type']}"
                    embed.description = description

                    try:
                        await channel.send(f"{ping} Event starting soon!", embed=embed)
                    except Exception as e:
                        print(f"Failed to send event notification to guild {guild_id}: {e}")

    @notify_events_task.before_loop
    async def before_notify_events(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=168) # Weekly
    async def weekly_summary_task(self):
        """Weekly summary on Sunday 20:00."""
        now = datetime.datetime.now()
        # Extend to the end of the next Sunday to include late evening events
        next_week_end = (now + datetime.timedelta(days=7)).replace(hour=23, minute=59, second=59)

        upcoming_week_events = []
        for ev in self.events:
            start_dt = datetime.datetime.fromisoformat(ev['start_time'])
            if now < start_dt <= next_week_end:
                upcoming_week_events.append(ev)

        if not upcoming_week_events:
            return

        for guild_id, config in self.settings.items():
            channel_id = config.get('channel_id')
            if not channel_id: continue

            channel = self.bot.get_channel(channel_id)
            if not channel: continue

            # Check if weekly summary is enabled (default True)
            if not config.get('weekly_summary_enabled', True):
                continue

            role_id = config.get('role_id')
            ping = f"<@&{role_id}>" if role_id else ""

            embed = discord.Embed(title="📅 Events This Week", color=0x00FFFF)

            description = ""
            for ev in upcoming_week_events:
                start_dt = datetime.datetime.fromisoformat(ev['start_time'])
                day_name = start_dt.strftime("%A")
                description += f"**{day_name}**: [{ev['title']}]({ev['link']}) ({ev['time_text']})\n"

            embed.description = description

            try:
                await channel.send(f"{ping} Here is the summary for the upcoming week!", embed=embed)
            except Exception as e:
                print(f"Failed to send weekly summary to guild {guild_id}: {e}")

    @weekly_summary_task.before_loop
    async def before_weekly_summary(self):
        await self.bot.wait_until_ready()
        now = datetime.datetime.now()
        # Find next Sunday
        days_ahead = 6 - now.weekday() # 6 = Sunday. If today is Sunday (6), days_ahead=0.

        target = now.replace(hour=20, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_ahead)

        # If today is Sunday and it's already past 20:00, target is in past. Move to next week.
        if target <= now:
            target += datetime.timedelta(days=7)

        seconds = (target - now).total_seconds()
        print(f"POGO: Sleeping {seconds}s until weekly summary on Sunday 20:00")
        await asyncio.sleep(seconds)

async def setup(bot):
    await bot.add_cog(PokemonGo(bot))
