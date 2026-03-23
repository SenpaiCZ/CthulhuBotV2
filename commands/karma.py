import discord
from discord import app_commands
from discord.ext import commands
from models.database import SessionLocal
from services.campaign_service import CampaignService
import io
import urllib.parse
from playwright.async_api import async_playwright

class Karma(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def generate_rank_card(self, guild_id, user_id, karma_score):
        # Simplified rank card generation using the existing dashboard route
        url = f"http://127.0.0.1:5000/render/karma/{guild_id}/{user_id}?score={karma_score}"
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(viewport={'width': 800, 'height': 400})
                await page.goto(url, timeout=10000)
                element = await page.wait_for_selector('.karma-card', timeout=5000)
                screenshot = await element.screenshot() if element else await page.screenshot()
                await browser.close()
                return screenshot
        except Exception as e:
            print(f"Error generating karma image: {e}")
            return None

    @app_commands.command(name="karma", description="🌟 Check karma for yourself or another user.")
    @app_commands.describe(user="The user to check karma for")
    async def karma(self, interaction: discord.Interaction, user: discord.User = None):
        user = user or interaction.user
        db = SessionLocal()
        try:
            stats = CampaignService.get_karma_leaderboard(db, str(interaction.guild_id))
            user_karma = next((s.score for s in stats if s.user_id == str(user.id)), 0)
            await interaction.response.send_message(f"🌟 **{user.display_name}** has **{user_karma}** karma.", ephemeral=True)
        finally: db.close()

    @app_commands.command(name="memelevel", description="🔮 Show your current rank card.")
    async def memelevel(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        await interaction.response.defer(ephemeral=True)
        db = SessionLocal()
        try:
            stats = CampaignService.get_karma_leaderboard(db, str(interaction.guild_id))
            score = next((s.score for s in stats if s.user_id == str(user.id)), 0)
            img_bytes = await self.generate_rank_card(interaction.guild_id, user.id, score)
            if img_bytes:
                file = discord.File(io.BytesIO(img_bytes), filename="rank_status.png")
                await interaction.followup.send(file=file)
            else: await interaction.followup.send("Failed to generate rank card.")
        finally: db.close()

    @app_commands.command(name="leaderboard", description="🏆 Show the Karma leaderboard.")
    async def leaderboard(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            stats = CampaignService.get_karma_leaderboard(db, str(interaction.guild_id))[:10]
            embed = discord.Embed(title="🏆 Karma Leaderboard", color=discord.Color.gold())
            desc = "\n".join([f"**{i+1}.** <@{s.user_id}>: {s.score}" for i, s in enumerate(stats)])
            embed.description = desc or "No karma recorded yet."
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally: db.close()

async def setup(bot):
    await bot.add_cog(Karma(bot))
