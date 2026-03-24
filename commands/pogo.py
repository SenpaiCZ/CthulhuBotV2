import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
import asyncio
from loadnsave import load_pogo_settings, save_pogo_settings, load_pogo_events
from services.engagement_service import EngagementService

class PokemonGo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = EngagementService(bot)
        self.settings = {}

    async def cog_load(self):
        self.settings = await load_pogo_settings()
        self.check_events_task.start()
        self.notify_events_task.start()
        self.weekly_summary_task.start()

    def cog_unload(self):
        self.check_events_task.cancel()
        self.notify_events_task.cancel()
        self.weekly_summary_task.cancel()

    pogo_group = app_commands.Group(name="pogo", description="🥎 Pokemon GO Event Commands", guild_only=True)

    @pogo_group.command(name="setchannel", description="📢 Set the channel for POGO notifications.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target = channel or interaction.channel
        self.settings.setdefault(str(interaction.guild_id), {})['channel_id'] = target.id
        await save_pogo_settings(self.settings)
        await interaction.response.send_message(f"Notifications set to {target.mention}")

    @pogo_group.command(name="setrole", description="👥 Set the role to ping.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_role(self, interaction: discord.Interaction, role: discord.Role):
        self.settings.setdefault(str(interaction.guild_id), {})['role_id'] = role.id
        await save_pogo_settings(self.settings)
        await interaction.response.send_message(f"Role {role.mention} will be pinged.")

    @pogo_group.command(name="forceupdate", description="🔄 Force update events.")
    @app_commands.checks.has_permissions(administrator=True)
    async def force_update(self, interaction: discord.Interaction):
        await interaction.response.defer()
        events = await self.service.scrape_pogo_events()
        await interaction.followup.send(f"Updated! Found {len(events)} events.")

    @tasks.loop(hours=24)
    async def check_events_task(self):
        events = await self.service.scrape_pogo_events()
        for g_id in self.settings:
            await self.service.send_pogo_summary(g_id, self.settings, events, "daily")

    @check_events_task.before_loop
    async def before_check_events(self):
        await self.bot.wait_until_ready()
        now = datetime.datetime.now()
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if target <= now: target += datetime.timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())

    @tasks.loop(minutes=5)
    async def notify_events_task(self):
        events = await load_pogo_events()
        now = datetime.datetime.now()
        for g_id, config in self.settings.items():
            if not config.get('channel_id') or not config.get('event_start_enabled', True): continue
            advance = config.get('advance_minutes', 120)
            for ev in events:
                minutes_until = (datetime.datetime.fromisoformat(ev['start_time']) - now).total_seconds() / 60
                if advance - 5 < minutes_until <= advance:
                    await self.service.send_pogo_summary(g_id, self.settings, events, "next")

    @notify_events_task.before_loop
    async def before_notify_events(self): await self.bot.wait_until_ready()

    @tasks.loop(hours=168)
    async def weekly_summary_task(self):
        events = await load_pogo_events()
        for g_id in self.settings:
            await self.service.send_pogo_summary(g_id, self.settings, events, "weekly")

    @weekly_summary_task.before_loop
    async def before_weekly_summary(self):
        await self.bot.wait_until_ready()
        now = datetime.datetime.now()
        target = now.replace(hour=20, minute=0, second=0, microsecond=0) + datetime.timedelta(days=(6 - now.weekday()))
        if target <= now: target += datetime.timedelta(days=7)
        await asyncio.sleep((target - now).total_seconds())

async def setup(bot): await bot.add_cog(PokemonGo(bot))
