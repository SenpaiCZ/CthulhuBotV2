import discord
from discord.ext import commands
import urllib.parse
import random

class NewspaperModal(discord.ui.Modal, title="Newspaper Generator"):
    name = discord.ui.TextInput(
        label="Newspaper Name",
        placeholder="The Arkham Advertiser",
        default="The Arkham Advertiser",
        max_length=50
    )
    city = discord.ui.TextInput(
        label="City",
        placeholder="Arkham",
        default="Arkham",
        max_length=50
    )
    date_field = discord.ui.TextInput(
        label="Date",
        placeholder="October 24, 1929",
        default="October 24, 1929",
        max_length=30
    )
    headline = discord.ui.TextInput(
        label="Headline",
        placeholder="MYSTERIOUS LIGHTS SEEN...",
        style=discord.TextStyle.paragraph,
        max_length=100
    )
    body = discord.ui.TextInput(
        label="Article Body",
        placeholder="Residents were awoken...",
        style=discord.TextStyle.paragraph,
        max_length=2000
    )

    def __init__(self, bot, ctx):
        super().__init__()
        self.bot = bot
        self.ctx = ctx

    async def on_submit(self, interaction: discord.Interaction):
        # Defer immediately as rendering takes time.
        # Using think=True implies we are processing.
        # We want the result to be public (not ephemeral) so everyone sees the newspaper.
        await interaction.response.defer(ephemeral=False, thinking=True)

        # Generate random parameters
        width = random.randint(450, 650)

        # Generate clip path (random jagged edges)
        points = []
        # Top
        for i in range(0, 101, 5):
            y = random.uniform(0, 1.5)
            points.append(f"{i}% {y:.1f}%")
        # Right
        for i in range(0, 101, 5):
            x = 100 - random.uniform(0, 1.5)
            points.append(f"{x:.1f}% {i}%")
        # Bottom
        for i in range(100, -1, -5):
            y = 100 - random.uniform(0, 1.5)
            points.append(f"{i}% {y:.1f}%")
        # Left
        for i in range(100, -1, -5):
            x = random.uniform(0, 1.5)
            points.append(f"{x:.1f}% {i}%")

        clip_path = ", ".join(points)

        # Encode params
        params = {
            "name": self.name.value,
            "city": self.city.value,
            "date": self.date_field.value,
            "headline": self.headline.value,
            "body": self.body.value,
            "width": width,
            "clip_path": clip_path
        }

        query_string = urllib.parse.urlencode(params)
        url = f"/render/newspaper?{query_string}"

        # Call Codex render
        codex_cog = self.bot.get_cog("Codex")
        if codex_cog:
            # We use _render_poster.
            await codex_cog._render_poster(
                self.ctx,
                url,
                self.headline.value[:50], # Short name for file
                "newspaper",
                interaction=interaction,
                ephemeral=False
            )
        else:
            await interaction.followup.send("Error: Codex system not available.", ephemeral=True)

class NewspaperStartView(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx

    @discord.ui.button(label="Create Newspaper", style=discord.ButtonStyle.primary, emoji="📰")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        modal = NewspaperModal(self.bot, self.ctx)
        await interaction.response.send_modal(modal)

    async def on_timeout(self):
        self.disable_all_items()

class Newspaper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="Create a 1920s newspaper clipping.")
    async def newspaper(self, ctx):
        """Starts the Newspaper Wizard."""
        if ctx.interaction:
            modal = NewspaperModal(self.bot, ctx)
            await ctx.interaction.response.send_modal(modal)
        else:
            view = NewspaperStartView(self.bot, ctx)
            msg = await ctx.send("Click below to start the Newspaper Wizard:", view=view)
            # Delete user command message for cleanliness
            try:
                await ctx.message.delete()
            except:
                pass

async def setup(bot):
    await bot.add_cog(Newspaper(bot))
