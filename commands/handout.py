import discord
from discord import app_commands
from discord.ext import commands
import urllib.parse
import random
import os
from loadnsave import load_fonts_config

def get_available_fonts():
    fonts_dir = os.path.join("data", "fonts")
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

    name = discord.ui.Label(text="Newspaper Name", component=discord.ui.TextInput(placeholder="The Arkham Advertiser", default="The Arkham Advertiser", max_length=50))
    city = discord.ui.Label(text="City", component=discord.ui.TextInput(placeholder="Arkham", default="Arkham", max_length=50))
    date_field = discord.ui.Label(text="Date", component=discord.ui.TextInput(placeholder="October 24, 1929", default="October 24, 1929", max_length=30))
    headline = discord.ui.Label(text="Headline", component=discord.ui.TextInput(placeholder="MYSTERIOUS LIGHTS SEEN...", style=discord.TextStyle.paragraph, max_length=100))
    body = discord.ui.Label(text="Article Body", component=discord.ui.TextInput(placeholder="Residents were awoken...", style=discord.TextStyle.paragraph, max_length=2000))

    async def on_submit(self, interaction: discord.Interaction):
        width = random.randint(450, 650)
        # Generate clip path (random jagged edges)
        points = []
        for i in range(0, 101, 5): points.append(f"{i}% {random.uniform(0, 1.5):.1f}%") # Top
        for i in range(0, 101, 5): points.append(f"{100 - random.uniform(0, 1.5):.1f}% {i}%") # Right (x, y) ? No, Right is x=100.

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
            "name": self.name.component.value,
            "city": self.city.component.value,
            "date": self.date_field.component.value,
            "headline": self.headline.component.value,
            "body": self.body.component.value,
            "width": width,
            "clip_path": clip_path
        }
        query = urllib.parse.urlencode(params)
        await self._render(interaction, f"/render/newspaper?{query}", self.headline.component.value[:50], "newspaper")

class TelegramModal(HandoutBaseModal):
    def __init__(self, bot, ctx):
        super().__init__(bot, ctx, "Telegram Generator")

    origin = discord.ui.Label(text="Origin", component=discord.ui.TextInput(placeholder="ARKHAM", default="ARKHAM", max_length=50))
    date_field = discord.ui.Label(text="Date", component=discord.ui.TextInput(placeholder="OCT 24 1929", default="OCT 24 1929", max_length=30))
    recipient = discord.ui.Label(text="Recipient", component=discord.ui.TextInput(placeholder="INVESTIGATOR", default="INVESTIGATOR", max_length=50))
    sender = discord.ui.Label(text="Sender", component=discord.ui.TextInput(placeholder="UNKNOWN", default="UNKNOWN", max_length=50))
    body = discord.ui.Label(text="Message", component=discord.ui.TextInput(placeholder="STOP", style=discord.TextStyle.paragraph, max_length=500))

    async def on_submit(self, interaction: discord.Interaction):
        params = {
            "origin": self.origin.component.value,
            "date": self.date_field.component.value,
            "recipient": self.recipient.component.value,
            "sender": self.sender.component.value,
            "body": self.body.component.value
        }
        query = urllib.parse.urlencode(params)
        await self._render(interaction, f"/render/telegram?{query}", "Telegram", "telegram")

class LetterModal(HandoutBaseModal):
    def __init__(self, bot, ctx):
        super().__init__(bot, ctx, "Letter Generator")

    date_field = discord.ui.Label(text="Date", component=discord.ui.TextInput(placeholder="October 24, 1929", default="October 24, 1929", max_length=50))
    salutation = discord.ui.Label(text="Salutation", component=discord.ui.TextInput(placeholder="Dear Friend,", default="Dear Friend,", max_length=50))
    body = discord.ui.Label(text="Body", component=discord.ui.TextInput(placeholder="I write to you...", style=discord.TextStyle.paragraph, max_length=2000))
    signature = discord.ui.Label(text="Signature", component=discord.ui.TextInput(placeholder="Sincerely, H.P.L.", default="Sincerely, H.P.L.", max_length=50))

    async def on_submit(self, interaction: discord.Interaction):
        params = {
            "date": self.date_field.component.value,
            "salutation": self.salutation.component.value,
            "body": self.body.component.value,
            "signature": self.signature.component.value
        }
        query = urllib.parse.urlencode(params)
        await self._render(interaction, f"/render/letter?{query}", "Letter", "letter")

class ScriptModal(HandoutBaseModal):
    def __init__(self, bot, ctx, font_name):
        super().__init__(bot, ctx, f"Script Generator ({font_name})")
        self.font_name = font_name

    text = discord.ui.Label(text="Text to Transcribe", component=discord.ui.TextInput(style=discord.TextStyle.paragraph, max_length=1000))

    async def on_submit(self, interaction: discord.Interaction):
        params = {
            "text": self.text.component.value,
            "font": self.font_name
        }
        query = urllib.parse.urlencode(params)
        await self._render(interaction, f"/render/script?{query}", "Script", "script")

class MorseModal(HandoutBaseModal):
    def __init__(self, bot, ctx, font_name):
        super().__init__(bot, ctx, f"Morse Code Generator ({font_name})")
        self.font_name = font_name

    text = discord.ui.Label(text="Text to Convert", component=discord.ui.TextInput(style=discord.TextStyle.paragraph, max_length=1000))

    async def on_submit(self, interaction: discord.Interaction):
        params = {
            "text": self.text.component.value,
            "font": self.font_name
        }
        query = urllib.parse.urlencode(params)
        await self._render(interaction, f"/render/morse?{query}", "Morse Code", "morse")

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

        if not options:
             select = discord.ui.Select(placeholder="No fonts available", options=[discord.SelectOption(label="None", value="none")], disabled=True)
        else:
             select = discord.ui.Select(placeholder="Select a Font", options=options)
             select.callback = self.select_callback

        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        selected_font = interaction.data['values'][0]
        modal = ScriptModal(self.bot, self.ctx, selected_font)
        await interaction.response.send_modal(modal)

class MorseFontSelectView(discord.ui.View):
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

        if not options:
             select = discord.ui.Select(placeholder="No decorative fonts available", options=[discord.SelectOption(label="Default", value="default")])
        else:
             select = discord.ui.Select(placeholder="Select a Decorative Font", options=options)

        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        selected_font = interaction.data['values'][0]
        modal = MorseModal(self.bot, self.ctx, selected_font)
        await interaction.response.send_modal(modal)

class ScriptCategorySelectView(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx

    async def _handle_category(self, interaction, category):
        if interaction.user != self.ctx.author:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        # Defer to allow async loading
        await interaction.response.defer(ephemeral=True)

        fonts = get_available_fonts()
        config = await load_fonts_config()

        filtered_fonts = []
        for f in fonts:
            # Default to Decorative
            font_cat = config.get(f, "Decorative")
            if font_cat == category:
                filtered_fonts.append(f)

        if not filtered_fonts:
             await interaction.followup.send(f"No fonts found for category '{category}'.", ephemeral=True)
             return

        view = ScriptFontSelectView(self.bot, self.ctx, filtered_fonts)
        await interaction.followup.send(f"Select a {category} Font:", view=view, ephemeral=True)

    @discord.ui.button(label="Decorative", style=discord.ButtonStyle.primary)
    async def decorative_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_category(interaction, "Decorative")

    @discord.ui.button(label="Cryptic", style=discord.ButtonStyle.secondary)
    async def cryptic_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_category(interaction, "Cryptic")

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

        view = ScriptCategorySelectView(self.bot, self.ctx)
        await interaction.response.send_message("Select a font category:", view=view, ephemeral=True)

    @discord.ui.button(label="Morse Code", style=discord.ButtonStyle.success, emoji="➖")
    async def morse_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        fonts = get_available_fonts()
        config = await load_fonts_config()

        decorative_fonts = []
        for f in fonts:
            if config.get(f, "Decorative") == "Decorative":
                decorative_fonts.append(f)

        view = MorseFontSelectView(self.bot, self.ctx, decorative_fonts)
        await interaction.followup.send("Select a font for Morse Code:", view=view, ephemeral=True)

class Handout(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="Create a prop/handout (Newspaper, Telegram, Letter, Script, Morse).")
    @app_commands.describe(type="The type of handout to create")
    @app_commands.choices(type=[
        app_commands.Choice(name="Newspaper", value="newspaper"),
        app_commands.Choice(name="Telegram", value="telegram"),
        app_commands.Choice(name="Letter", value="letter"),
        app_commands.Choice(name="Occult Script", value="script"),
        app_commands.Choice(name="Morse Code", value="morse")
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
                view = ScriptCategorySelectView(self.bot, ctx)
                await ctx.send("Select a font category:", view=view, ephemeral=True)

        elif selected_value == "morse":
            fonts = get_available_fonts()
            if not fonts:
                if ctx.interaction:
                    await ctx.interaction.response.send_modal(MorseModal(self.bot, ctx, "default"))
                else:
                    await ctx.send("Use slash command.")
            else:
                config = await load_fonts_config()
                decorative_fonts = [f for f in fonts if config.get(f, "Decorative") == "Decorative"]
                view = MorseFontSelectView(self.bot, ctx, decorative_fonts)
                await ctx.send("Select a font for Morse Code:", view=view, ephemeral=True)

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
