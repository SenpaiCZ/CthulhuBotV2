import discord
import feedparser
from discord.ext import commands, tasks
from discord import app_commands
from loadnsave import load_rss_data, save_rss_data
from rss_utils import get_youtube_rss_url
from services.engagement_service import EngagementService
from views.engagement_views import RSSLinkModal

class rss(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = EngagementService(bot)
        self.check_rss_feed.start()

    def cog_unload(self): self.check_rss_feed.cancel()

    @app_commands.command(description="📰 Add an RSS subscription or YouTube channel.")
    @app_commands.describe(link="The URL of the RSS feed or YouTube channel/video")
    @app_commands.checks.has_permissions(administrator=True)
    async def rss(self, interaction: discord.Interaction, link: str):
        await interaction.response.defer()
        try:
            link = await get_youtube_rss_url(link) or link
            _, feed = await self.service.fetch_rss_feed(link)
            if not feed or (not feed.entries and not feed.feed.get('title')):
                return await interaction.followup.send("❌ Invalid RSS feed.", ephemeral=True)
            
            rss_data = await load_rss_data()
            server_id = str(interaction.guild.id)
            if any(sub["link"] == link and str(sub["channel_id"]) == str(interaction.channel.id) for sub in rss_data.get(server_id, [])):
                return await interaction.followup.send("Already subscribed here.", ephemeral=True)

            latest = feed.entries[0] if feed.entries else None
            new_sub = {
                "link": link, "channel_id": interaction.channel.id,
                "last_message": latest.title if latest else "No Title",
                "last_id": self.service.get_rss_entry_id(latest) if latest else None,
                "color": "#2E8B57"
            }
            rss_data.setdefault(server_id, []).append(new_sub)
            await save_rss_data(rss_data)
            
            title = feed.feed.get('title', link)
            await interaction.followup.send(f"✅ Subscribed to **{title}**.")
            if feed.entries:
                for entry in feed.entries[:3]:
                    await interaction.channel.send(embed=self.service.create_rss_embed(entry, title, "#2E8B57"))
        except Exception as e: await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @app_commands.command(description="🧙‍♂️ Wizard to setup a new RSS feed.")
    @app_commands.checks.has_permissions(administrator=True)
    async def rsssetup(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RSSLinkModal(self.service, self.bot))

    @tasks.loop(minutes=5)
    async def check_rss_feed(self): await self.service.check_all_rss_feeds()

    @check_rss_feed.before_loop
    async def before_check_rss_feed(self): await self.bot.wait_until_ready()

async def setup(bot): await bot.add_cog(rss(bot))
