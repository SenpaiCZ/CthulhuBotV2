import discord
import feedparser
from discord.ext import commands, tasks
from loadnsave import load_rss_data, save_rss_data
from asyncio import sleep


class rss(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.check_rss_feed.start()

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
                  "last_message": feed.entries[0].title
              })
          else:
              # Create a new RSS data entry for this server with the first subscription
              rss_data[server_id] = [{
                  "link": link,
                  "channel_id": ctx.channel.id,
                  "last_message": feed.entries[0].title
              }]

          # Save the updated RSS data
          await save_rss_data(rss_data)

          # Iterate through the latest items in the feed
          for entry in feed.entries:
              await ctx.send(f"**Title:** {entry.title}\n**Link:** {entry.link}")

      except Exception as e:
          await ctx.send(f"An error occurred: {e}")

  @tasks.loop(minutes=5)  # Adjust the interval as needed
  async def check_rss_feed(self):
      # Load RSS data
      rss_data = await load_rss_data()
      print("Checking for stuff in RSS feeds")
      # Iterate through each server's RSS subscriptions
      for server_id, subscriptions in rss_data.items():
          for subscription in subscriptions:
              link = subscription["link"]
              channel_id = subscription["channel_id"]
              last_message = subscription["last_message"]
  
              try:
                  # Parse the RSS feed
                  feed = feedparser.parse(link)
  
                  # Find new posts and send them to the channel
                  for entry in feed.entries:
                      if entry.title != last_message:
                          channel = self.bot.get_channel(channel_id)
                          if channel:
                              await channel.send(f"**Title:** {entry.title}\n**Link:** {entry.link}")
                          subscription["last_message"] = entry.title  # Update last message
  
              except Exception as e:
                  print(f"An error occurred while checking RSS feed: {e}")
  
      # Save the updated RSS data
      await save_rss_data(rss_data)
  
  @check_rss_feed.before_loop
  async def before_check_rss_feed(self):
      await self.bot.wait_until_ready()  # Wait for the bot to be fully ready

async def setup(bot):
  await bot.add_cog(rss(bot))
