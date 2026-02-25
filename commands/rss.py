import discord
import feedparser
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Select, Modal, TextInput, Button
from loadnsave import load_rss_data, save_rss_data
from rss_utils import get_youtube_rss_url

# Predefined colors for the selector
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

class RSSLinkModal(Modal, title="RSS Setup - Step 1"):
    link_input = TextInput(label="Link", placeholder="RSS Feed or YouTube URL")

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        link = self.link_input.value.strip()

        # Validate Link
        try:
            rss_link = await get_youtube_rss_url(link)
            if rss_link:
                link = rss_link
        except Exception:
            pass

        # Test parse
        feed = await self.cog.bot.loop.run_in_executor(None, feedparser.parse, link)
        if not feed.entries and (not hasattr(feed, 'feed') or not feed.feed.get('title')):
             await interaction.response.send_message("❌ Could not parse RSS feed or feed is invalid/empty. Please check the link.", ephemeral=True)
             return

        # Proceed to Channel Selection
        view = RSSChannelView(self.cog, link, feed, interaction.guild)
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
            new_view = RSSColorView(self.view.cog, self.view.link, self.view.feed, cid)
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
        new_view = RSSColorView(self.view.cog, self.view.link, self.view.feed, channel_id)
        await interaction.response.edit_message(content=f"✅ Channel selected: {channel.mention}\nSelect an accent color:", view=new_view)

class RSSChannelView(View):
    def __init__(self, cog, link, feed, guild):
        super().__init__(timeout=180)
        self.cog = cog
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
             return False # Stop propagation
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
    def __init__(self, cog, link, feed, channel_id):
        super().__init__(timeout=180)
        self.cog = cog
        self.link = link
        self.feed = feed
        self.channel_id = channel_id
        self.add_item(RSSColorSelect())

    async def finalize(self, interaction: discord.Interaction, color_hex):
        try:
             # Save Logic
             server_id = str(interaction.guild_id)
             rss_data = await load_rss_data()

             # Check duplicates
             if server_id in rss_data:
                  for sub in rss_data[server_id]:
                       if sub["link"] == self.link and str(sub["channel_id"]) == str(self.channel_id):
                            await interaction.response.edit_message(content="⚠️ This feed is already subscribed in this channel!", view=None)
                            return

             latest_entry = self.feed.entries[0] if self.feed.entries else None
             latest_id = self.cog.get_entry_id(latest_entry) if latest_entry else None
             latest_title = latest_entry.title if latest_entry else "No Title"

             new_sub = {
                  "link": self.link,
                  "channel_id": self.channel_id,
                  "last_message": latest_title,
                  "last_id": latest_id,
                  "color": color_hex
             }

             if server_id not in rss_data:
                  rss_data[server_id] = []

             rss_data[server_id].append(new_sub)
             await save_rss_data(rss_data)

             feed_title = self.feed.feed.get('title', self.link)

             # Edit the interaction message to confirm
             await interaction.response.edit_message(content=f"✅ Successfully subscribed to **{feed_title}** in <#{self.channel_id}>!", view=None)

             # Send test message to channel
             if latest_entry:
                  target_channel = interaction.guild.get_channel(self.channel_id)
                  if target_channel:
                       embed = self.cog._create_rss_embed(latest_entry, feed_title, color_hex)
                       await target_channel.send(f"New subscription added!", embed=embed)

        except Exception as e:
             await interaction.response.send_message(f"Error saving: {e}", ephemeral=True)


class rss(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.check_rss_feed.start()

  async def fetch_feed(self, link):
      """Helper to fetch a single feed safely."""
      try:
          feed = await self.bot.loop.run_in_executor(None, feedparser.parse, link)
          return link, feed
      except Exception as e:
          print(f"Error fetching feed {link}: {e}")
          return link, None

  def get_entry_id(self, entry):
      # Try id (guid), then link, then title
      return getattr(entry, 'id', getattr(entry, 'link', getattr(entry, 'title', None)))

  def _get_image_url(self, entry):
      # 1. YouTube: media_thumbnail
      if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
          return entry.media_thumbnail[0]['url']

      # 2. Media Content (e.g. iDNES)
      if hasattr(entry, 'media_content') and entry.media_content:
          for item in entry.media_content:
              if item.get('type', '').startswith('image/'):
                  return item['url']
              # Some feeds might not specify type but have url in media_content
              if 'url' in item and (item['url'].endswith('.jpg') or item['url'].endswith('.png')):
                   return item['url']

      # 3. Links
      if hasattr(entry, 'links'):
          for link in entry.links:
              if link.get('type', '').startswith('image/'):
                  return link['href']

      # 4. Enclosures
      if hasattr(entry, 'enclosures'):
            for enclosure in entry.enclosures:
              if enclosure.get('type', '').startswith('image/'):
                  return enclosure['href']
      return None

  def _create_rss_embed(self, entry, feed_title, color_hex):
      # Parse color
      try:
          if color_hex.startswith('#'):
              color_val = int(color_hex[1:], 16)
          else:
              color_val = int(color_hex, 16)
      except:
          color_val = 0x2E8B57 # Default SeaGreen

      embed = discord.Embed(
          title=entry.title,
          url=entry.link,
          color=color_val
      )

      embed.set_footer(text=feed_title)

      image_url = self._get_image_url(entry)
      if image_url:
          embed.set_image(url=image_url)

      return embed

  @app_commands.command(description="📰 Add an RSS subscription or YouTube channel to the current channel.")
  @app_commands.describe(link="The URL of the RSS feed or YouTube channel/video")
  @app_commands.checks.has_permissions(administrator=True)
  async def rss(self, interaction: discord.Interaction, link: str):
      """
      Add an RSS subscription to the current channel.
      """
      await interaction.response.defer()
      try:
          # Check for YouTube RSS
          rss_link = await get_youtube_rss_url(link)
          if rss_link:
              link = rss_link

          # Parse the RSS feed
          feed = await self.bot.loop.run_in_executor(None, feedparser.parse, link)
          if not feed.entries and (not hasattr(feed, 'feed') or not feed.feed.get('title')):
              await interaction.followup.send("❌ No items found in the RSS feed or invalid link.", ephemeral=True)
              return

          # Get the server ID
          server_id = str(interaction.guild.id)

          # Get latest entry info
          latest_entry = feed.entries[0] if feed.entries else None
          latest_id = self.get_entry_id(latest_entry) if latest_entry else None
          latest_title = latest_entry.title if latest_entry else "No Title"

          # Create an empty RSS data dictionary for this server
          rss_data = await load_rss_data()

          # Check if RSS data already exists for this server
          if server_id in rss_data:
              # Check if the link already exists for this server
              existing_subscriptions = rss_data[server_id]
              for subscription in existing_subscriptions:
                  if subscription["link"] == link and str(subscription["channel_id"]) == str(interaction.channel.id):
                      await interaction.followup.send("RSS feed is already subscribed to this channel.", ephemeral=True)
                      return

              # Add a new RSS subscription for this server
              rss_data[server_id].append({
                  "link": link,
                  "channel_id": interaction.channel.id,
                  "last_message": latest_title,
                  "last_id": latest_id,
                  "color": "#2E8B57"
              })
          else:
              # Create a new RSS data entry for this server with the first subscription
              rss_data[server_id] = [{
                  "link": link,
                  "channel_id": interaction.channel.id,
                  "last_message": latest_title,
                  "last_id": latest_id,
                  "color": "#2E8B57"
              }]

          # Save the updated RSS data
          await save_rss_data(rss_data)

          feed_title = feed.feed.get('title', link)
          await interaction.followup.send(f"✅ Subscribed to **{feed_title}**. Here are the latest entries:")

          if latest_entry:
              # Send up to 3 latest entries to avoid spam
              for entry in feed.entries[:3]:
                  embed = self._create_rss_embed(entry, feed_title, "#2E8B57")
                  await interaction.channel.send(embed=embed)

      except Exception as e:
          await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

  @app_commands.command(description="🧙‍♂️ Wizard to setup a new RSS feed or YouTube subscription.")
  @app_commands.checks.has_permissions(administrator=True)
  async def rsssetup(self, interaction: discord.Interaction):
      """
      Wizard to setup a new RSS feed or YouTube subscription.
      """
      modal = RSSLinkModal(self)
      await interaction.response.send_modal(modal)

  @tasks.loop(minutes=5)
  async def check_rss_feed(self):
      # Load RSS data
      try:
          rss_data = await load_rss_data()
      except Exception as e:
          print(f"Error loading RSS data: {e}")
          return

      data_changed = False

      # 1. Collect all unique links
      unique_links = set()
      for subs in rss_data.values():
          for sub in subs:
              if sub.get("link"):
                  unique_links.add(sub["link"])

      if not unique_links:
          return

      # 2. Fetch all feeds concurrently
      # We use return_exceptions=True implicitly via our wrapper which handles errors
      tasks = [self.fetch_feed(link) for link in unique_links]
      results = await asyncio.gather(*tasks)

      # Create a cache: link -> feed object
      feed_cache = {link: feed for link, feed in results if feed}

      # 3. Iterate through subscriptions and apply updates using cache
      for server_id, subscriptions in rss_data.items():
          for subscription in subscriptions:
              link = subscription["link"]
              feed = feed_cache.get(link)

              # If feed failed to fetch, skip
              if not feed or not feed.entries:
                  continue

              channel_id = subscription["channel_id"]
              last_message = subscription.get("last_message")
              last_id = subscription.get("last_id")
              color = subscription.get("color", "#2E8B57")

              try:
                  new_items = []
                  found_last = False

                  for entry in feed.entries:
                      entry_id = self.get_entry_id(entry)

                      # Check against last_id
                      if last_id is not None and entry_id == last_id:
                          found_last = True
                          break

                      # Fallback to title check if last_id is missing (legacy data)
                      if last_id is None and last_message and entry.title == last_message:
                          found_last = True
                          break

                      new_items.append(entry)

                  # If we found new items
                  if new_items:
                      channel = self.bot.get_channel(channel_id)
                      if channel:
                          feed_title = feed.feed.get('title', link)
                          # Send oldest new item first
                          for entry in reversed(new_items):
                              embed = self._create_rss_embed(entry, feed_title, color)
                              await channel.send(embed=embed)

                      # Update markers
                      latest = feed.entries[0]
                      subscription["last_message"] = latest.title
                      subscription["last_id"] = self.get_entry_id(latest)
                      data_changed = True

              except Exception as e:
                  print(f"An error occurred while processing RSS feed {link} for channel {channel_id}: {e}")
  
      if data_changed:
          await save_rss_data(rss_data)
  
  @check_rss_feed.before_loop
  async def before_check_rss_feed(self):
      await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(rss(bot))
