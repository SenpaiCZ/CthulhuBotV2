import discord
import feedparser
import asyncio
from discord.ext import commands, tasks
from discord.ui import View, Select
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

class ChannelSelect(Select):
    def __init__(self, channels):
        options = []
        # Discord allows max 25 options
        for channel in channels[:25]:
            options.append(discord.SelectOption(label=channel.name, value=str(channel.id), emoji="#️⃣"))

        super().__init__(placeholder="Select channel to send feed to", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.selected_channel_id = int(self.values[0])
        self.view.stop()

class ColorSelect(Select):
    def __init__(self):
        options = []
        for name, hex_val in list(COLORS.items())[:24]: # Leave room for custom
             options.append(discord.SelectOption(label=name, description=hex_val, value=hex_val))

        options.append(discord.SelectOption(label="Custom Hex", description="Type your own hex code", value="custom", emoji="🎨"))

        super().__init__(placeholder="Select accent color", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.selected_color = self.values[0]
        self.view.stop()

class RSSSetupView(View):
    def __init__(self, channels=None, type="channel"):
        super().__init__(timeout=60.0)
        self.selected_channel_id = None
        self.selected_color = None

        if type == "channel" and channels:
            self.add_item(ChannelSelect(channels))
        elif type == "color":
            self.add_item(ColorSelect())

class rss(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.check_rss_feed.start()

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

  @commands.command()
  async def rss(self, ctx, link: str):
      """
      `[p]rss link` - Add an RSS subscription to the channel where the command was sent from.
      """
      try:
          # Check for YouTube RSS
          rss_link = await get_youtube_rss_url(link)
          if rss_link:
              link = rss_link

          # Parse the RSS feed
          feed = await self.bot.loop.run_in_executor(None, feedparser.parse, link)
          if not feed.entries:
              await ctx.send("No items found in the RSS feed.")
              return

          # Get the server ID
          server_id = str(ctx.guild.id)

          # Get latest entry info
          latest_entry = feed.entries[0]
          latest_id = self.get_entry_id(latest_entry)
          latest_title = latest_entry.title

          # Create an empty RSS data dictionary for this server
          rss_data = await load_rss_data()

          # Check if RSS data already exists for this server
          if server_id in rss_data:
              # Check if the link already exists for this server
              existing_subscriptions = rss_data[server_id]
              for subscription in existing_subscriptions:
                  if subscription["link"] == link:
                      await ctx.send("RSS feed is already subscribed to this channel.")
                      return

              # Add a new RSS subscription for this server
              rss_data[server_id].append({
                  "link": link,
                  "channel_id": ctx.channel.id,
                  "last_message": latest_title,
                  "last_id": latest_id,
                  "color": "#2E8B57"
              })
          else:
              # Create a new RSS data entry for this server with the first subscription
              rss_data[server_id] = [{
                  "link": link,
                  "channel_id": ctx.channel.id,
                  "last_message": latest_title,
                  "last_id": latest_id,
                  "color": "#2E8B57"
              }]

          # Save the updated RSS data
          await save_rss_data(rss_data)

          feed_title = feed.feed.get('title', link)
          await ctx.send(f"Subscribed to {feed_title}. Here are the latest entries:")
          for entry in feed.entries[:5]:
              embed = self._create_rss_embed(entry, feed_title, "#2E8B57")
              await ctx.send(embed=embed)

      except Exception as e:
          await ctx.send(f"An error occurred: {e}")

  @commands.command()
  async def rsssetup(self, ctx):
      """
      Wizard to setup a new RSS feed subscription.
      """

      def check(m):
          return m.author == ctx.author and m.channel == ctx.channel

      # --- Step 1: Link ---
      await ctx.send("Send link to RSS, YT channel or YT video")

      try:
          msg = await self.bot.wait_for('message', check=check, timeout=60.0)
          link = msg.content.strip()
      except asyncio.TimeoutError:
          await ctx.send("Timed out. Please start over.")
          return

      # Validate Link
      try:
          rss_link = await get_youtube_rss_url(link)
          if rss_link:
              link = rss_link
      except Exception as e:
          pass # Fallback to raw link if error

      # Test parse
      try:
          feed = await self.bot.loop.run_in_executor(None, feedparser.parse, link)
          if not feed.entries:
               # If no entries, it might be invalid or just empty.
               # We'll allow empty if feed.feed has data (title), otherwise error.
               if not hasattr(feed, 'feed') or not feed.feed.get('title'):
                   await ctx.send("Could not parse RSS feed or feed is invalid/empty. Please check the link.")
                   return
      except Exception as e:
          await ctx.send(f"Error parsing feed: {e}")
          return

      # --- Step 2: Channel Selector ---
      # Filter for text channels only
      text_channels = [c for c in ctx.guild.text_channels]
      text_channels.sort(key=lambda x: x.position) # Sort by position

      target_channel_id = None

      if len(text_channels) <= 25:
          view = RSSSetupView(channels=text_channels, type="channel")
          prompt_msg = await ctx.send("Select channel to send feed to:", view=view)

          timeout = await view.wait()
          if timeout:
              await ctx.send("Timed out.")
              return

          if view.selected_channel_id:
              target_channel_id = view.selected_channel_id
              await prompt_msg.delete()
          else:
              await ctx.send("Selection cancelled.")
              return
      else:
          await ctx.send("Select channel to send feed to:\n(Too many channels for selector, please enter the **Channel ID** manually)")
          try:
              msg = await self.bot.wait_for('message', check=check, timeout=60.0)
              try:
                  target_channel_id = int(msg.content.strip())
                  # Validate channel exists and is text channel
                  channel = ctx.guild.get_channel(target_channel_id)
                  if not channel or not isinstance(channel, discord.TextChannel):
                      await ctx.send("Invalid Channel ID or not a text channel.")
                      return
              except ValueError:
                  await ctx.send("Invalid ID format.")
                  return
          except asyncio.TimeoutError:
              await ctx.send("Timed out.")
              return

      # --- Step 3: Color Selector ---
      view = RSSSetupView(type="color")
      prompt_msg = await ctx.send("What accent color you want for embed?", view=view)

      timeout = await view.wait()
      if timeout:
           await ctx.send("Timed out.")
           return

      final_color = "#2E8B57" # Default

      if view.selected_color:
          await prompt_msg.delete()
          if view.selected_color == "custom":
              await ctx.send("Please enter the Hex Color Code (e.g. #FF0000):")
              try:
                  msg = await self.bot.wait_for('message', check=check, timeout=60.0)
                  input_color = msg.content.strip()
                  # Basic validation
                  if not input_color.startswith('#'):
                      input_color = '#' + input_color

                  # Verify it is hex
                  try:
                      int(input_color[1:], 16)
                      final_color = input_color
                  except ValueError:
                      await ctx.send("Invalid Hex Code. Using default.")

              except asyncio.TimeoutError:
                  await ctx.send("Timed out. Using default color.")
          else:
              final_color = view.selected_color
      else:
           await ctx.send("No selection made. Using default color.")
           await prompt_msg.delete()

      # --- Step 4: Save & Confirm ---
      try:
          # Get the server ID
          server_id = str(ctx.guild.id)

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
                  if subscription["link"] == link:
                      await ctx.send(f"RSS feed is already subscribed! (Channel: <#{subscription['channel_id']}>)")
                      return

              # Add a new RSS subscription for this server
              rss_data[server_id].append({
                  "link": link,
                  "channel_id": target_channel_id,
                  "last_message": latest_title,
                  "last_id": latest_id,
                  "color": final_color
              })
          else:
              # Create a new RSS data entry for this server with the first subscription
              rss_data[server_id] = [{
                  "link": link,
                  "channel_id": target_channel_id,
                  "last_message": latest_title,
                  "last_id": latest_id,
                  "color": final_color
              }]

          # Save the updated RSS data
          await save_rss_data(rss_data)

          feed_title = feed.feed.get('title', link)
          await ctx.send(f"Successfully subscribed to **{feed_title}** in <#{target_channel_id}>!")

          if latest_entry:
              target_channel = ctx.guild.get_channel(target_channel_id)
              if target_channel:
                  embed = self._create_rss_embed(latest_entry, feed_title, final_color)
                  await target_channel.send(f"New subscription added!", embed=embed)

      except Exception as e:
          await ctx.send(f"An error occurred while saving: {e}")

  @tasks.loop(minutes=5)
  async def check_rss_feed(self):
      # Load RSS data
      try:
          rss_data = await load_rss_data()
      except Exception as e:
          print(f"Error loading RSS data: {e}")
          return

      data_changed = False

      # Iterate through each server's RSS subscriptions
      # Copy items to avoid modification issues if we were to modify the dict structure (though we just modify values)
      for server_id, subscriptions in rss_data.items():
          for subscription in subscriptions:
              link = subscription["link"]
              channel_id = subscription["channel_id"]
              last_message = subscription.get("last_message")
              last_id = subscription.get("last_id")
              color = subscription.get("color", "#2E8B57")

              try:
                  # Parse the RSS feed
                  feed = await self.bot.loop.run_in_executor(None, feedparser.parse, link)
                  if not feed.entries:
                      continue

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
                  print(f"An error occurred while checking RSS feed {link}: {e}")
  
      if data_changed:
          await save_rss_data(rss_data)
  
  @check_rss_feed.before_loop
  async def before_check_rss_feed(self):
      await self.bot.wait_until_ready()

async def setup(bot):
  await bot.add_cog(rss(bot))
