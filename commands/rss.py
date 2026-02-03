import discord
import feedparser
from discord.ext import commands, tasks
from loadnsave import load_rss_data, save_rss_data
from asyncio import sleep

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
          # Parse the RSS feed
          feed = feedparser.parse(link)
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
                  feed = feedparser.parse(link)
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
