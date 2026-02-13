import discord
from discord import app_commands
from discord.ext import commands
import urllib.parse
import random
import os

def get_available_fonts():
    fonts_dir = os.path.join("dashboard", "static", "fonts")
    if not os.path.exists(fonts_dir):
        return []
    fonts = [f for f in os.listdir(fonts_dir) if f.lower().endswith(('.ttf', '.otf', '.woff', '.woff2'))]
    fonts.sort()
    return fonts

class HandoutBaseModal(discord.ui.Modal):
    def __init__(self, bot, ctx, title):
        super().__init__(title=title)
        self.bot = bot
        self.ctx = ctx

    async def _render(self, interaction, url, name, type_slug):
        # Defer immediately as rendering takes time.
        await interaction.response.defer(ephemeral=False, thinking=True)

        codex_cog = self.bot.get_cog("Codex")
        if codex_cog:
            await codex_cog._render_poster(
                self.ctx,
                url,
                name,
                type_slug,
                interaction=interaction,
                ephemeral=False
            )
        else:
            await interaction.followup.send("Error: Codex system not available.", ephemeral=True)

class NewspaperModal(HandoutBaseModal):
    def __init__(self, bot, ctx):
        super().__init__(bot, ctx, "Newspaper Generator")

    name = discord.ui.TextInput(label="Newspaper Name", placeholder="The Arkham Advertiser", default="The Arkham Advertiser", max_length=50)
    city = discord.ui.TextInput(label="City", placeholder="Arkham", default="Arkham", max_length=50)
    date_field = discord.ui.TextInput(label="Date", placeholder="October 24, 1929", default="October 24, 1929", max_length=30)
    headline = discord.ui.TextInput(label="Headline", placeholder="MYSTERIOUS LIGHTS SEEN...", style=discord.TextStyle.paragraph, max_length=100)
    body = discord.ui.TextInput(label="Article Body", placeholder="Residents were awoken...", style=discord.TextStyle.paragraph, max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        width = random.randint(450, 650)
        # Generate clip path (random jagged edges)
        points = []
        for i in range(0, 101, 5): points.append(f"{i}% {random.uniform(0, 1.5):.1f}%") # Top
        for i in range(0, 101, 5): points.append(f"{100 - random.uniform(0, 1.5):.1f}% {i}%") # Right (x, y) ? No, Right is x=100.
        # Wait, polygon points are x y.
        # Top: x varies 0->100, y ~0
        # Right: x ~100, y varies 0->100
        # Bottom: x varies 100->0, y ~100
        # Left: x ~0, y varies 100->0

        # My previous logic in newspaper.py:
        # Top
        top = [f"{i}% {random.uniform(0, 1.5):.1f}%" for i in range(0, 101, 5)]
        # Right
        right = [f"{100 - random.uniform(0, 1.5):.1f}% {i}%" for i in range(0, 101, 5)]
        # Bottom
        bottom = [f"{i}% {100 - random.uniform(0, 1.5):.1f}%" for i in range(100, -1, -5)]
        # Left
        left = [f"{random.uniform(0, 1.5):.1f}% {i}%" for i in range(100, -1, -5)]

        clip_path = ", ".join(top + right + bottom + left)

        params = {
            "name": self.name.value,
            "city": self.city.value,
            "date": self.date_field.value,
            "headline": self.headline.value,
            "body": self.body.value,
            "width": width,
            "clip_path": clip_path
        }
        query = urllib.parse.urlencode(params)
        await self._render(interaction, f"/render/newspaper?{query}", self.headline.value[:50], "newspaper")

class TelegramModal(HandoutBaseModal):
    def __init__(self, bot, ctx):
        super().__init__(bot, ctx, "Telegram Generator")

    origin = discord.ui.TextInput(label="Origin", placeholder="ARKHAM", default="ARKHAM", max_length=50)
    date_field = discord.ui.TextInput(label="Date", placeholder="OCT 24 1929", default="OCT 24 1929", max_length=30)
    recipient = discord.ui.TextInput(label="Recipient", placeholder="INVESTIGATOR", default="INVESTIGATOR", max_length=50)
    sender = discord.ui.TextInput(label="Sender", placeholder="UNKNOWN", default="UNKNOWN", max_length=50)
    body = discord.ui.TextInput(label="Message", placeholder="STOP", style=discord.TextStyle.paragraph, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        params = {
            "origin": self.origin.value,
            "date": self.date_field.value,
            "recipient": self.recipient.value,
            "sender": self.sender.value,
            "body": self.body.value
        }
        query = urllib.parse.urlencode(params)
        await self._render(interaction, f"/render/telegram?{query}", "Telegram", "telegram")

class LetterModal(HandoutBaseModal):
    def __init__(self, bot, ctx):
        super().__init__(bot, ctx, "Letter Generator")

    date_field = discord.ui.TextInput(label="Date", placeholder="October 24, 1929", default="October 24, 1929", max_length=50)
    salutation = discord.ui.TextInput(label="Salutation", placeholder="Dear Friend,", default="Dear Friend,", max_length=50)
    body = discord.ui.TextInput(label="Body", placeholder="I write to you...", style=discord.TextStyle.paragraph, max_length=2000)
    signature = discord.ui.TextInput(label="Signature", placeholder="Sincerely, H.P.L.", default="Sincerely, H.P.L.", max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        params = {
            "date": self.date_field.value,
            "salutation": self.salutation.value,
            "body": self.body.value,
            "signature": self.signature.value
        }
        query = urllib.parse.urlencode(params)
        await self._render(interaction, f"/render/letter?{query}", "Letter", "letter")

class ScriptModal(HandoutBaseModal):
    def __init__(self, bot, ctx, font_name):
        super().__init__(bot, ctx, f"Script Generator ({font_name})")
        self.font_name = font_name

    text = discord.ui.TextInput(label="Text to Transcribe", style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        params = {
            "text": self.text.value,
            "font": self.font_name
        }
        query = urllib.parse.urlencode(params)
        await self._render(interaction, f"/render/script?{query}", "Script", "script")

class ScriptFontSelectView(discord.ui.View):
    def __init__(self, bot, ctx, fonts):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx

        # Paginate or limit to 25
        options = []
        for f in fonts[:25]:
            # Use filename as value, label without extension
            label = os.path.splitext(f)[0]
            options.append(discord.SelectOption(label=label, value=f))

        select = discord.ui.Select(placeholder="Select a Font", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        selected_font = interaction.data['values'][0]
        modal = ScriptModal(self.bot, self.ctx, selected_font)
        await interaction.response.send_modal(modal)

class HandoutTypeSelectView(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx

    async def _launch_modal(self, interaction, modal_cls):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)
        modal = modal_cls(self.bot, self.ctx)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Newspaper", style=discord.ButtonStyle.primary, emoji="📰")
    async def newspaper_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._launch_modal(interaction, NewspaperModal)

    @discord.ui.button(label="Telegram", style=discord.ButtonStyle.secondary, emoji="📨")
    async def telegram_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._launch_modal(interaction, TelegramModal)

    @discord.ui.button(label="Letter", style=discord.ButtonStyle.secondary, emoji="✉️")
    async def letter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._launch_modal(interaction, LetterModal)

    @discord.ui.button(label="Occult Script", style=discord.ButtonStyle.danger, emoji="📜")
    async def script_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        fonts = get_available_fonts()
        if not fonts:
             modal = ScriptModal(self.bot, self.ctx, "default")
             await interaction.response.send_modal(modal)
             return

        view = ScriptFontSelectView(self.bot, self.ctx, fonts)
        await interaction.response.send_message("Select a font for your script:", view=view, ephemeral=True)

class Handout(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="Create a prop/handout (Newspaper, Telegram, Letter, Script).")
    @app_commands.describe(type="The type of handout to create")
    @app_commands.choices(type=[
        app_commands.Choice(name="Newspaper", value="newspaper"),
        app_commands.Choice(name="Telegram", value="telegram"),
        app_commands.Choice(name="Letter", value="letter"),
        app_commands.Choice(name="Occult Script", value="script")
    ])
    async def handout(self, ctx, type: app_commands.Choice[str] = None):
        """Starts the Handout Wizard."""

        selected_value = type.value if type else None

        if selected_value == "newspaper":
            if ctx.interaction:
                await ctx.interaction.response.send_modal(NewspaperModal(self.bot, ctx))
            else:
                await ctx.send("Use slash command for this, or just run /handout without arguments.")

        elif selected_value == "telegram":
            if ctx.interaction:
                await ctx.interaction.response.send_modal(TelegramModal(self.bot, ctx))
            else:
                await ctx.send("Use slash command.")

        elif selected_value == "letter":
            if ctx.interaction:
                await ctx.interaction.response.send_modal(LetterModal(self.bot, ctx))
            else:
                await ctx.send("Use slash command.")

        elif selected_value == "script":
            fonts = get_available_fonts()
            if not fonts:
                if ctx.interaction:
                    await ctx.interaction.response.send_modal(ScriptModal(self.bot, ctx, "default"))
                else:
                    await ctx.send("Use slash command.")
            else:
                view = ScriptFontSelectView(self.bot, ctx, fonts)
                await ctx.send("Select a font:", view=view, ephemeral=True)

        else:
            # No argument provided, show selection view
            view = HandoutTypeSelectView(self.bot, ctx)
            msg = await ctx.send("Select a handout type:", view=view)
            # Delete user command message if possible
            try:
                await ctx.message.delete()
            except:
                pass

async def setup(bot):
    await bot.add_cog(Handout(bot))
