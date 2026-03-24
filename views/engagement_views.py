import discord
from discord.ui import View, Button, Modal, TextInput, Select
import datetime
from datetime import datetime, timezone
import feedparser

# RSS Colors
COLORS = {
    "SeaGreen (Default)": "#2E8B57",
    "Red": "#FF0000",
    "Green": "#00FF00",
    "Blue": "#0000FF",
    "Orange": "#FFA500",
    "Purple": "#800080",
    "Gold": "#FFD700",
    "Magenta": "#FF00FF",
    "Teal": "#008080",
    "Dark Red": "#8B0000",
    "Dark Blue": "#00008B",
    "Dark Green": "#006400",
    "Cyan": "#00FFFF",
    "Pink": "#FFC0CB",
    "Yellow": "#FFFF00",
    "Brown": "#A52A2A",
    "Black": "#000000",
    "White": "#FFFFFF",
    "Gray": "#808080",
    "Silver": "#C0C0C0",
    "Maroon": "#800000",
    "Olive": "#808000",
    "Navy": "#000080",
}

# --- Giveaway Views ---

class GiveawayCreationModal(Modal, title="Create Giveaway"):
    giveaway_title = TextInput(label="Title", placeholder="e.g. Monthly Steam Key", max_length=100)
    description = TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Details about the prize...", required=False, max_length=1000)
    duration = TextInput(label="Duration", placeholder="e.g. 10m, 1h, 2d", max_length=20)
    prize_secret = TextInput(label="Prize Secret (Hidden)", style=discord.TextStyle.paragraph, placeholder="The key/code sent to winner...", required=True, max_length=1000)

    def __init__(self, service, cog):
        super().__init__()
        self.service = service
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        # Logic moved to service but called from here or directly in cog
        # For simplicity in this refactor, we can call a service method
        duration_str = self.duration.value
        duration_seconds = self.service.parse_duration(duration_str)

        if not duration_seconds:
            await interaction.response.send_message("❌ Invalid duration format. Use 10m, 1h, 2d etc.", ephemeral=True)
            return

        end_time = datetime.now(timezone.utc).timestamp() + duration_seconds
        title = self.giveaway_title.value
        desc = self.description.value
        secret = self.prize_secret.value

        # Create Embed
        embed = discord.Embed(title=f"🎉 GIVEAWAY: {title}", description=desc, color=discord.Color.gold())
        embed.add_field(name="Ends", value=f"<t:{int(end_time)}:R>", inline=False)
        embed.add_field(name="How to win?", value="React with 🎉 to enter!\nKarma increases your chance to win!", inline=False)
        embed.set_footer(text=f"Hosted by {interaction.user.display_name}")

        try:
            if not interaction.channel:
                 await interaction.response.send_message("❌ Cannot post giveaway in DM.", ephemeral=True)
                 return

            view = GiveawayView(self.service)
            await interaction.response.send_message(f"✅ Giveaway creating...", ephemeral=True)
            message = await interaction.channel.send(embed=embed, view=view)

            # Save Data via Service
            await self.service.save_new_giveaway(
                guild_id=str(interaction.guild_id),
                message_id=str(message.id),
                creator_id=interaction.user.id,
                channel_id=interaction.channel.id,
                title=title,
                description=desc,
                secret=secret,
                end_time=end_time
            )

            await interaction.edit_original_response(content=f"✅ Giveaway created! [Jump to message]({message.jump_url})")

        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"Error creating giveaway: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"Error creating giveaway: {e}", ephemeral=True)

class GiveawayView(View):
    def __init__(self, service):
        super().__init__(timeout=None)
        self.service = service

    @discord.ui.button(label="Join Giveaway", style=discord.ButtonStyle.green, emoji="🎉", custom_id="giveaway:join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        success, msg = await self.service.add_participant(
            str(interaction.guild_id),
            str(interaction.message.id),
            str(interaction.user.id)
        )
        await interaction.response.send_message(msg, ephemeral=True)

# --- RSS Views ---

class RSSLinkModal(Modal, title="RSS Setup - Step 1"):
    link_input = TextInput(label="Link", placeholder="RSS Feed or YouTube URL")

    def __init__(self, service, bot):
        super().__init__()
        self.service = service
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        link = self.link_input.value.strip()
        
        from rss_utils import get_youtube_rss_url
        # Validate Link
        try:
            rss_link = await get_youtube_rss_url(link)
            if rss_link:
                link = rss_link
        except Exception:
            pass

        # Test parse
        feed = await self.bot.loop.run_in_executor(None, feedparser.parse, link)
        if not feed.entries and (not hasattr(feed, 'feed') or not feed.feed.get('title')):
             await interaction.response.send_message("❌ Could not parse RSS feed or feed is invalid/empty. Please check the link.", ephemeral=True)
             return

        # Proceed to Channel Selection
        view = RSSChannelView(self.service, self.bot, link, feed, interaction.guild)
        await interaction.response.send_message("✅ Link valid! Select a channel to send updates to:", view=view, ephemeral=True)


class RSSChannelIDModal(Modal, title="Enter Channel ID"):
    channel_id_input = TextInput(label="Channel ID", placeholder="123456789012345678")

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cid = int(self.channel_id_input.value.strip())
            channel = interaction.guild.get_channel(cid)
            if not channel or not isinstance(channel, discord.TextChannel):
                 await interaction.response.send_message("❌ Invalid Channel ID or not a text channel.", ephemeral=True)
                 return

            # Proceed to Color Selection
            new_view = RSSColorView(self.view.service, self.view.bot, self.view.link, self.view.feed, cid)
            await interaction.response.edit_message(content=f"✅ Channel selected: {channel.mention}\nSelect an accent color:", view=new_view)
        except ValueError:
            await interaction.response.send_message("❌ Invalid ID format.", ephemeral=True)

class RSSChannelSelect(Select):
    def __init__(self, channels):
        options = []
        for channel in channels[:25]:
            options.append(discord.SelectOption(label=channel.name, value=str(channel.id), emoji="#️⃣"))
        super().__init__(placeholder="Select channel...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        channel = interaction.guild.get_channel(channel_id)

        # Proceed to Color Selection
        new_view = RSSColorView(self.view.service, self.view.bot, self.view.link, self.view.feed, channel_id)
        await interaction.response.edit_message(content=f"✅ Channel selected: {channel.mention}\nSelect an accent color:", view=new_view)

class RSSChannelView(View):
    def __init__(self, service, bot, link, feed, guild):
        super().__init__(timeout=180)
        self.service = service
        self.bot = bot
        self.link = link
        self.feed = feed

        text_channels = [c for c in guild.text_channels]
        text_channels.sort(key=lambda x: x.position)

        if len(text_channels) <= 25:
             self.add_item(RSSChannelSelect(text_channels))
        else:
             self.add_item(Button(label="Enter Channel ID Manually", style=discord.ButtonStyle.primary, custom_id="manual_channel_id"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data.get('custom_id') == "manual_channel_id":
             await interaction.response.send_modal(RSSChannelIDModal(self))
             return False 
        return True

class RSSColorHexModal(Modal, title="Custom Hex Color"):
    hex_input = TextInput(label="Hex Color", placeholder="#FF0000")

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        color = self.hex_input.value.strip()
        if not color.startswith('#'): color = '#' + color

        try:
            int(color[1:], 16)
            await self.view.finalize(interaction, color)
        except ValueError:
            await interaction.response.send_message("❌ Invalid Hex Code.", ephemeral=True)

class RSSColorSelect(Select):
    def __init__(self):
        options = []
        for name, hex_val in list(COLORS.items())[:24]:
             options.append(discord.SelectOption(label=name, description=hex_val, value=hex_val))
        options.append(discord.SelectOption(label="Custom Hex", description="Type your own hex code", value="custom", emoji="🎨"))
        super().__init__(placeholder="Select accent color", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "custom":
             await interaction.response.send_modal(RSSColorHexModal(self.view))
        else:
             await self.view.finalize(interaction, self.values[0])

class RSSColorView(View):
    def __init__(self, service, bot, link, feed, channel_id):
        super().__init__(timeout=180)
        self.service = service
        self.bot = bot
        self.link = link
        self.feed = feed
        self.channel_id = channel_id
        self.add_item(RSSColorSelect())

    async def finalize(self, interaction: discord.Interaction, color_hex):
        success, msg = await self.service.finalize_rss_subscription(
            interaction, self.link, self.feed, self.channel_id, color_hex
        )
        await interaction.response.edit_message(content=msg, view=None)
