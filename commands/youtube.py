import discord
from discord.ext import commands, tasks
import aiohttp
from bs4 import BeautifulSoup
import json
import os
import aiofiles
import requests
from loadnsave import load_settings
from loadnsave import youtube_save, youtube_load
import asyncio

# Load settings
settings = load_settings()

# Define your YouTube API key
# Try environment variable first, then settings.json
YOUTUBE_API_KEY = os.getenv("YOUTUBETOKEN") or settings.get("youtubetoken")

# Define an async function to get the RSS link from a YouTube channel page
async def get_channel_rss_link(channel_input):
    if not YOUTUBE_API_KEY:
        print("Error: YouTube API Key not found.")
        return None

    try:
        async with aiohttp.ClientSession() as session:
            if channel_input.startswith('UC'):
                # If channel_input starts with 'UC', assume it's a channel ID
                channel_id = channel_input
            else:
                # If channel_input is a channel name, use the search API to get the channel ID
                search_url = f'https://youtube.googleapis.com/youtube/v3/search?part=snippet&q={channel_input}&type=channel&key={YOUTUBE_API_KEY}'
                async with session.get(search_url) as search_response:
                    if search_response.status == 200:
                        search_data = await search_response.json()
                        if 'items' in search_data and len(search_data['items']) > 0:
                            channel_id = search_data['items'][0]['id']['channelId']
                        else:
                            print(f"Channel '{channel_input}' not found.")
                            return None
                    else:
                        print(f"Error fetching channel ID: {search_response.status}")
                        return None

            rss_link = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'
            return rss_link
    except Exception as e:
        print(f"Error fetching RSS link: {str(e)}")
    return None

def get_latest_video_link(rss_url):
    try:
        response = requests.get(rss_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'xml')
            entry = soup.find('entry')
            if entry:
                link_tag = entry.find('link', rel='alternate')
                if link_tag:
                    video_link = link_tag.get('href')
                    return video_link

    except Exception as e:
        print(f"An error occurred: {e}")

    return None
  
def get_channel_name(rss_url):
    try:
        response = requests.get(rss_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'xml')
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text
                return title

    except Exception as e:
        print(f"An error occurred: {e}")

    return None
  
class youtube(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        

    def cog_unload(self):
        self.check_new_videos.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print("Bot is live")
        self.check_new_videos.start()

    @commands.command(aliases=["yt"])
    async def youtube(self, ctx, channel_link_or_id: str, channel_mention: discord.TextChannel):
        """
        Set up a subscription to receive new YouTube video notifications in a text channel.
    
        Parameters:
          • channel_link_or_id (str): YouTube channel link or channel ID.
          • channel_mention (discord.TextChannel): Discord text channel to receive notifications.
    
        Example Usage:
          !youtube <YouTube Channel Link or Name> <#TextChannel>
          !yt UC0aMPje3ZACnQPKM_qzY0vw #videos
        """
        if ctx.author != ctx.guild.owner:
            await ctx.send("This command is limited to the server owner only.")
            return
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command is not allowed in DMs.")
            return

        if not YOUTUBE_API_KEY:
            await ctx.send("YouTube API Key is not configured.")
            return
    
        RSS = await get_channel_rss_link(channel_link_or_id)
        if RSS:
            youtube_data = await youtube_load()
            server_id = str(ctx.guild.id)  # Get the server's ID as a string
            if server_id not in youtube_data:
                youtube_data[server_id] = {}
    
            # Check if this RSS link is already in use for any Discord text channel
            for existing_rss_link, channels in youtube_data[server_id].items():
                if existing_rss_link == RSS:
                    for channel in channels:
                        if str(channel["Channel_id"]) == str(channel_mention.id):
                            await ctx.send(f"You are already getting notifications from this YouTube channel in {channel_mention.mention}.")
                            return
    
            # Add the new subscription entry
            if RSS not in youtube_data[server_id]:
                VIDEO = get_latest_video_link(RSS)
                youtube_data[server_id][RSS] = [{"Channel_id": str(channel_mention.id), "Lastvideo": VIDEO}]
                await youtube_save(youtube_data)
        
                await ctx.send(f"Setup successful! New videos from this channel will be posted to {channel_mention.mention}.")
                if VIDEO:
                    await channel_mention.send(f"Latest video from the channel: {VIDEO}")
            else:
                youtube_data[server_id][RSS].append({"Channel_id": str(channel_mention.id), "Lastvideo": None})
                await youtube_save(youtube_data)
        
                await ctx.send(f"Setup successful! New videos from this channel will be posted to {channel_mention.mention}.")
        else:
            await ctx.send("Invalid YouTube channel link.")
    
    @commands.command()
    async def unsubscribe(self, ctx):
        """
        `[p]unsubscribe` - List subscribed YouTube channels for unsubscribing.
        """
        if ctx.author != ctx.guild.owner:
            await ctx.send("This command is limited to the server owner only.")
            return
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command is not allowed in DMs.")
            return
        # Get the server's ID as a string
        server_id = str(ctx.guild.id)
        # Load the existing YouTube subscription data
        youtube_data = await youtube_load()
        await ctx.send("Subscribed YouTube channels:")
        count = 1
        numbered_channels = {}
        if server_id in youtube_data: 
            if youtube_data[server_id]:
                for rss_link, _ in youtube_data[server_id].items():
                    channel_name = get_channel_name(rss_link)
                    await ctx.send(f"{count}. {channel_name}")
                    numbered_channels[count] = rss_link  # Store the channel number and RSS link
                    count += 1
                await ctx.send("To unsubscribe from a channel, type the number corresponding to the channel.")
                try:
                    message = await self.bot.wait_for("message", timeout=60, check=lambda m: m.author == ctx.author)
                    number = int(message.content)
                    if number in numbered_channels:
                        rss_link = numbered_channels[number]
                        youtube_data[server_id].pop(rss_link, None)
                        await youtube_save(youtube_data)
                        await ctx.send("Successfully unsubscribed from the selected channel.")
                    else:
                        await ctx.send("Invalid channel number. No changes were made.")
                except asyncio.TimeoutError:
                    await ctx.send("You took too long to respond. No changes were made.")
                except ValueError:
                    await ctx.send("Invalid input. Please provide a valid number.")
            else:
                await ctx.send("No YouTube channels subscribed.")
        else:
            await ctx.send("No YouTube channels subscribed in this server.")
    
      
  
    @tasks.loop(minutes=15)
    async def check_new_videos(self):
        # Iterate through saved channel info
        youtube_data = await youtube_load()
        print("Checking for new videos")
        for server_id, channel_data in youtube_data.items():
            for rss_url, channels in channel_data.items():
              for channel in channels:
                channel_id = channel["Channel_id"]
                last_video = channel["Lastvideo"]
                latest_video_link = get_latest_video_link(rss_url)
                if latest_video_link != last_video:
                  print("New video found!")
                  discord_channel = self.bot.get_channel(int(channel_id))
                  if discord_channel:
                      await discord_channel.send(f"New video: {latest_video_link}")
                      channel["Lastvideo"] = latest_video_link
                      await youtube_save(youtube_data)
                  else:
                      print(f"Could not find channel {channel_id}")
                        
async def setup(bot):
  await bot.add_cog(youtube(bot))