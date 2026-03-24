import discord
import random
import re
import math
import asyncio
import aiohttp
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models.social import Poll, Giveaway, PogoEvent, GamerRole
from models.admin import RSSFeed
from schemas.social import PollCreate, GiveawayCreate, PogoEventCreate, GamerRoleCreate
from schemas.admin import RSSFeedCreate
from typing import List, Optional
from loadnsave import (
    load_giveaway_data, save_giveaway_data, load_karma_stats,
    load_pogo_settings, save_pogo_settings, load_pogo_events, save_pogo_events,
    load_rss_data, save_rss_data
)

KARMA_VERIFICATION_HALF_THRESHOLD = 100
PERCENTAGE_TO_TICKETS_MULTIPLIER = 1000

class EngagementService:
    def __init__(self, bot):
        self.bot = bot

    # --- SQL CRUD (Existing) ---
    @staticmethod
    def create_poll(db: Session, data: PollCreate) -> Poll:
        db_poll = Poll(
            message_id=data.message_id,
            guild_id=data.guild_id,
            question=data.question,
            options=data.options,
            votes=data.votes
        )
        db.add(db_poll)
        db.commit()
        db.refresh(db_poll)
        return db_poll

    @staticmethod
    def get_poll(db: Session, message_id: str) -> Optional[Poll]:
        return db.query(Poll).filter(Poll.message_id == message_id).first()

    # --- Giveaway Logic ---

    def calculate_tickets(self, karma):
        try:
            k_val = int(karma)
        except (ValueError, TypeError):
            k_val = 0
        if k_val <= 0:
            return 0
        verification_percentage = k_val / (KARMA_VERIFICATION_HALF_THRESHOLD + k_val)
        return math.ceil(PERCENTAGE_TO_TICKETS_MULTIPLIER * verification_percentage)

    def parse_duration(self, duration_str):
        if not duration_str or duration_str.lower() in ["forever", "none", "no"]:
            return None
        total_seconds = 0
        matches = re.findall(r'(\d+)\s*([dhms])', duration_str.lower())
        for amount, unit in matches:
            amount = int(amount)
            if unit == 'd': total_seconds += amount * 86400
            elif unit == 'h': total_seconds += amount * 3600
            elif unit == 'm': total_seconds += amount * 60
            elif unit == 's': total_seconds += amount
        return total_seconds if total_seconds > 0 else None

    async def save_new_giveaway(self, guild_id, message_id, creator_id, channel_id, title, description, secret, end_time):
        data = await load_giveaway_data()
        if guild_id not in data:
            data[guild_id] = {}
        data[guild_id][message_id] = {
            "creator_id": creator_id,
            "channel_id": channel_id,
            "title": title,
            "description": description,
            "prize_secret": secret,
            "status": "active",
            "participants": [],
            "end_time": end_time
        }
        await save_giveaway_data(data)

    async def add_participant(self, guild_id, message_id, user_id):
        data = await load_giveaway_data()
        if guild_id not in data or message_id not in data[guild_id]:
            return False, "This giveaway no longer exists."
        giveaway = data[guild_id][message_id]
        if giveaway["status"] != "active":
            return False, "This giveaway has ended."
        if user_id in giveaway["participants"]:
            return False, "You have already joined this giveaway!"
        giveaway["participants"].append(user_id)
        await save_giveaway_data(data)
        karma_stats = await load_karma_stats()
        user_karma = karma_stats.get(guild_id, {}).get(user_id, 0)
        tickets = self.calculate_tickets(user_karma)
        return True, f"You have joined the giveaway! (Tickets: {tickets})"

    async def pick_winner(self, guild_id, participants):
        if not participants: return None
        karma_stats = await load_karma_stats()
        guild_karma = karma_stats.get(str(guild_id), {})
        population, weights = [], []
        for user_id in participants:
            k = guild_karma.get(str(user_id), 0)
            population.append(user_id)
            weights.append(self.calculate_tickets(k))
        if not population or sum(weights) == 0: return None
        return random.choices(population, weights=weights, k=1)[0]

    async def end_giveaway(self, guild_id: str, message_id: str, requester=None):
        data = await load_giveaway_data()
        if guild_id not in data or message_id not in data[guild_id]:
            return False, "Giveaway not found."
        gw = data[guild_id][message_id]
        if requester:
            is_admin = requester.guild_permissions.administrator
            is_creator = str(requester.id) == str(gw["creator_id"])
            if not is_admin and not is_creator:
                return False, "You do not have permission to end this giveaway."
        if gw["status"] != "active":
            return False, "This giveaway is already ended."
        participants = gw["participants"]
        if not participants:
            gw["status"] = "ended"
            await save_giveaway_data(data)
            return True, "Giveaway ended. No participants."
        winner_id = await self.pick_winner(guild_id, participants)
        if not winner_id: return False, "Error picking winner."
        gw["status"] = "ended"
        gw["winner_id"] = winner_id
        await save_giveaway_data(data)
        guild = self.bot.get_guild(int(guild_id))
        if guild:
            winner = guild.get_member(int(winner_id))
            channel = guild.get_channel(int(gw["channel_id"]))
            if channel:
                try:
                    msg = await channel.fetch_message(int(message_id))
                    embed = msg.embeds[0]
                    embed.color = discord.Color.greyple()
                    embed.title = f"🚫 ENDED: {gw['title']}"
                    embed.add_field(name="Winner", value=f"🎉 <@{winner_id}> 🎉", inline=False)
                    await msg.edit(embed=embed, view=None)
                    await channel.send(f"🎉 The winner of **{gw['title']}** is <@{winner_id}>! Check your DMs!")
                except: pass
            if winner:
                try: await winner.send(f"🎉 **Congratulations!** You won the giveaway for **{gw['title']}**!\n\nHere is your prize:\n||{gw['prize_secret']}||")
                except: pass
        return True, f"Giveaway ended. Winner: <@{winner_id}>"

    async def reroll_giveaway(self, guild_id: str, message_id: str, requester=None):
        data = await load_giveaway_data()
        if guild_id not in data or message_id not in data[guild_id]:
            return False, "Giveaway not found."
        gw = data[guild_id][message_id]
        if requester:
            is_admin = requester.guild_permissions.administrator
            is_creator = str(requester.id) == str(gw["creator_id"])
            if not is_admin and not is_creator:
                return False, "You do not have permission to reroll this giveaway."
        participants = gw["participants"]
        if not participants: return False, "No participants."
        winner_id = await self.pick_winner(guild_id, participants)
        if not winner_id: return False, "Error picking winner."
        guild = self.bot.get_guild(int(guild_id))
        if guild:
            channel = guild.get_channel(int(gw["channel_id"]))
            if channel: await channel.send(f"🔄 **Reroll!** The new winner of **{gw['title']}** is <@{winner_id}>!")
            winner = guild.get_member(int(winner_id))
            if winner:
                try: await winner.send(f"🎉 **Reroll!** You won the giveaway for **{gw['title']}**!\n\nHere is your prize:\n||{gw['prize_secret']}||")
                except: pass
        return True, f"Rerolled. New Winner: <@{winner_id}>"

    # --- Pogo Logic ---

    def _parse_leekduck_html(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        events = []
        items = soup.find_all(class_="event-header-item-wrapper")
        now = datetime.now()
        for item in items:
            start_date_str = item.get('data-event-start-date')
            if not start_date_str: continue
            try:
                clean_date_str = start_date_str.replace('Z', '')
                start_date = datetime.fromisoformat(clean_date_str)
                if start_date.tzinfo is not None: start_date = start_date.replace(tzinfo=None)
            except ValueError: continue
            if start_date < now: continue
            link_tag = item.find('a', class_='event-item-link')
            link = "https://leekduck.com" + link_tag['href'] if link_tag else ""
            img_tag = item.find('img')
            image_url = img_tag['src'] if img_tag else ""
            text_div = item.find(class_='event-text')
            title = text_div.find('h2').text.strip() if text_div and text_div.find('h2') else "Unknown Event"
            time_str = text_div.find('p').text.strip() if text_div and text_div.find('p') else ""
            if "Calculating..." in time_str:
                try:
                    ts_dt = datetime.fromisoformat(clean_date_str)
                    if ts_dt.tzinfo is None: ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                    time_str = f"<t:{int(ts_dt.timestamp())}:f>"
                except: pass
            heading_span = text_div.find(class_='event-tag-badge')
            heading = heading_span.text.strip() if heading_span else "Event"
            events.append({
                'title': title, 'link': link, 'image': image_url,
                'start_time': start_date.isoformat(), 'time_text': time_str,
                'type': heading, 'timestamp': int(start_date.timestamp())
            })
        events.sort(key=lambda x: x['start_time'])
        return events

    async def scrape_pogo_events(self):
        url = "https://leekduck.com/events/"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200: return []
                    html = await response.text()
            events = await self.bot.loop.run_in_executor(None, self._parse_leekduck_html, html)
            await save_pogo_events(events)
            return events
        except: return []

    async def get_pogo_events(self):
        events = await load_pogo_events()
        if not events:
            events = await self.scrape_pogo_events()
        return events

    async def send_pogo_summary(self, guild_id, settings, events, summary_type="weekly", ping=True):
        config = settings.get(str(guild_id))
        if not config or not config.get('channel_id'): return False, "Not configured"
        channel = self.bot.get_channel(config['channel_id'])
        if not channel: return False, "Channel not found"

        now = datetime.now()
        target_events = []
        
        if summary_type == "weekly":
            end = (now + timedelta(days=7)).replace(hour=23, minute=59, second=59)
            target_events = [ev for ev in events if now < datetime.fromisoformat(ev['start_time']) <= end]
            title, color = "📅 Events This Week", 0x00FFFF
        elif summary_type == "daily":
            tomorrow = now.date() + timedelta(days=1)
            target_events = [ev for ev in events if datetime.fromisoformat(ev['start_time']).date() == tomorrow]
            title, color = "📅 Events Starting Tomorrow", 0x2E8B57
        elif summary_type == "next":
            for ev in events:
                if datetime.fromisoformat(ev['start_time']) > now:
                    target_events = [ev]
                    break
            title, color = f"Upcoming Event: {target_events[0]['title']}" if target_events else "", 0xFFA500

        if not target_events: return False, "No events found"

        role_id = config.get('role_id')
        ping_str = f"<@&{role_id}>" if role_id and ping else ""
        embed = discord.Embed(title=title, color=color)
        
        if summary_type == "next":
            ev = target_events[0]
            embed.url = ev['link']
            if ev['image']: embed.set_thumbnail(url=ev['image'])
            embed.description = f"**Starts:** <t:{ev['timestamp']}:R>\n**Time:** {ev['time_text']}\n**Type:** {ev['type']}"
        else:
            desc = ""
            for ev in target_events:
                dt = datetime.fromisoformat(ev['start_time'])
                if summary_type == "weekly":
                    desc += f"**{dt.strftime('%A')}**: [{ev['title']}]({ev['link']}) ({ev['time_text']} - <t:{ev['timestamp']}:R>)\n"
                else:
                    embed.add_field(name=ev['title'], value=f"**Type:** {ev['type']}\n**Time:** {ev['time_text']} (<t:{ev['timestamp']}:R>)\n[Link]({ev['link']})", inline=False)
            if desc: embed.description = desc

        try:
            await channel.send(f"{ping_str} {summary_type.capitalize()} POGO update:", embed=embed)
            return True, "Sent"
        except Exception as e: return False, str(e)

    # --- RSS Logic ---

    def get_rss_entry_id(self, entry):
        return getattr(entry, 'id', getattr(entry, 'link', getattr(entry, 'title', None)))

    def _get_rss_image_url(self, entry):
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail: return entry.media_thumbnail[0]['url']
        if hasattr(entry, 'media_content') and entry.media_content:
            for item in entry.media_content:
                if item.get('type', '').startswith('image/') or item.get('url', '').lower().split('?')[0].endswith(('.jpg', '.png')):
                    return item['url']
        if hasattr(entry, 'links'):
            for link in entry.links:
                if link.get('type', '').startswith('image/'): return link['href']
        if hasattr(entry, 'enclosures'):
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/'): return enclosure['href']
        return None

    def create_rss_embed(self, entry, feed_title, color_hex):
        try:
            color_val = int(color_hex[1:], 16) if color_hex.startswith('#') else int(color_hex, 16)
        except: color_val = 0x2E8B57
        embed = discord.Embed(title=entry.title, url=entry.link, color=color_val)
        embed.set_footer(text=feed_title)
        image_url = self._get_rss_image_url(entry)
        if image_url: embed.set_image(url=image_url)
        return embed

    async def finalize_rss_subscription(self, interaction, link, feed, channel_id, color_hex):
        server_id = str(interaction.guild_id)
        rss_data = await load_rss_data()
        if server_id in rss_data:
            for sub in rss_data[server_id]:
                if sub["link"] == link and str(sub["channel_id"]) == str(channel_id):
                    return False, "⚠️ This feed is already subscribed in this channel!"
        latest_entry = feed.entries[0] if feed.entries else None
        new_sub = {
            "link": link, "channel_id": channel_id,
            "last_message": latest_entry.title if latest_entry else "No Title",
            "last_id": self.get_rss_entry_id(latest_entry) if latest_entry else None,
            "color": color_hex
        }
        if server_id not in rss_data: rss_data[server_id] = []
        rss_data[server_id].append(new_sub)
        await save_rss_data(rss_data)
        feed_title = feed.feed.get('title', link)
        if latest_entry:
            target_channel = interaction.guild.get_channel(channel_id)
            if target_channel:
                await target_channel.send("New subscription added!", embed=self.create_rss_embed(latest_entry, feed_title, color_hex))
        return True, f"✅ Successfully subscribed to **{feed_title}** in <#{channel_id}>!"

    async def fetch_rss_feed(self, link):
        try:
            return link, await self.bot.loop.run_in_executor(None, feedparser.parse, link)
        except: return link, None

    async def check_all_rss_feeds(self):
        rss_data = await load_rss_data()
        unique_links = {s["link"] for subs in rss_data.values() for s in subs if s.get("link")}
        if not unique_links: return
        results = await asyncio.gather(*(self.fetch_rss_feed(l) for l in unique_links))
        feed_cache = {l: f for l, f in results if f}
        changed = False
        for s_id, subs in rss_data.items():
            for sub in subs:
                feed = feed_cache.get(sub["link"])
                if not feed or not feed.entries: continue
                new_items = []
                for entry in feed.entries:
                    e_id = self.get_rss_entry_id(entry)
                    if (sub.get("last_id") and e_id == sub["last_id"]) or (not sub.get("last_id") and sub.get("last_message") == entry.title):
                        break
                    new_items.append(entry)
                if new_items:
                    channel = self.bot.get_channel(sub["channel_id"])
                    if channel:
                        ft = feed.feed.get('title', sub["link"])
                        for entry in reversed(new_items):
                            await channel.send(embed=self.create_rss_embed(entry, ft, sub.get("color", "#2E8B57")))
                    latest = feed.entries[0]
                    sub["last_message"], sub["last_id"] = latest.title, self.get_rss_entry_id(latest)
                    changed = True
        if changed: await save_rss_data(rss_data)
