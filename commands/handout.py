import discord
from discord import app_commands
from discord.ext import commands
import urllib.parse
from models.database import SessionLocal
from services.campaign_service import CampaignService
from schemas.campaign import HandoutCreate

class HandoutModal(discord.ui.Modal):
    def __init__(self, bot, handout_type, fields):
        super().__init__(title=f"{handout_type.capitalize()} Handout")
        self.bot = bot
        self.handout_type = handout_type
        self.inputs = {}
        for label, default in fields.items():
            self.inputs[label] = discord.ui.TextInput(label=label, default=default, style=discord.TextStyle.paragraph if len(default) > 50 else discord.ui.TextStyle.short)
            self.add_item(self.inputs[label])

    async def on_submit(self, interaction: discord.Interaction):
        params = {k: v.value for k, v in self.inputs.items()}
        query = urllib.parse.urlencode(params)
        url = f"/render/{self.handout_type}?{query}"
        
        db = SessionLocal()
        try:
            title = self.inputs.get("Headline", self.inputs.get("Title", f"{self.handout_type.capitalize()} Handout")).value[:100]
            content = "\n".join([f"{k}: {v.value}" for k, v in self.inputs.items()])
            CampaignService.create_handout(db, HandoutCreate(guild_id=str(interaction.guild_id), title=title, content=content, image_url=url))
        finally: db.close()

        codex = self.bot.get_cog("Codex")
        if codex: await codex._render_poster(interaction, url, title, self.handout_type)
        else: await interaction.response.send_message("Error: Codex system not found.", ephemeral=True)

class Handout(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="handout", description="📄 Create a prop/handout.")
    @app_commands.choices(handout_type=[
        app_commands.Choice(name="Newspaper", value="newspaper"),
        app_commands.Choice(name="Telegram", value="telegram"),
        app_commands.Choice(name="Letter", value="letter")
    ])
    async def handout(self, interaction: discord.Interaction, handout_type: app_commands.Choice[str]):
        fields = {
            "newspaper": {"Name": "The Arkham Advertiser", "City": "Arkham", "Date": "Oct 24, 1929", "Headline": "Strange Lights", "Body": "..."},
            "telegram": {"Origin": "Arkham", "Date": "Oct 24, 1929", "Recipient": "Investigator", "Sender": "Unknown", "Body": "STOP"},
            "letter": {"Date": "Oct 24, 1929", "Salutation": "Dear Friend,", "Body": "...", "Signature": "Sincerely,"}
        }[handout_type.value]
        await interaction.response.send_modal(HandoutModal(self.bot, handout_type.value, fields))

async def setup(bot):
    await bot.add_cog(Handout(bot))
