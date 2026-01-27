import discord
from discord.ext import commands, tasks
import asyncio
import json
import pytz
from datetime import datetime, timedelta
from loadnsave import load_deleter_data, save_deleter_data


class deleter(commands.Cog):

  def __init__(self, bot):
      self.bot = bot
      self.autodelete_task.start()  # Start the task

  def cog_unload(self):
      self.autodelete_task.cancel()  # Cancel the task when the cog is unloaded

  @commands.command()
  async def autodeleter(self, ctx, channel: discord.TextChannel, *, time_limit: str):
      """
      `[p]autodeleter channel time_limit` - Automatically delete messages in a channel older than the specified time limit.
      """
      deleter_data = await load_deleter_data()
      try:
          seconds = self.parse_time_limit(time_limit)
          if seconds is None:
              await ctx.send("Invalid time limit format. Please use 'Xd', 'Xh', or 'Xm' (e.g., '1d' for 1 day, '2h' for 2 hours).")
              return
  
          deleter_data[str(channel.id)] = seconds  # Store the deletion time
          await save_deleter_data(deleter_data)
  
          await ctx.send(f"Auto-deleting messages in {channel.mention} older than {time_limit}...")
  
      except discord.Forbidden:
          await ctx.send("I don't have permission to delete messages.")
      except discord.HTTPException as e:
          await ctx.send(f"An error occurred while deleting messages: {e}")
        
  @commands.command()
  async def stopdeleter(self, ctx, channel: discord.TextChannel):
      """
      `[p]stopdeleter channel` - Stop auto-deleting messages in a channel.
      """
      deleter_data = await load_deleter_data()
      if str(channel.id) in deleter_data:
          del deleter_data[str(channel.id)]
          await save_deleter_data(deleter_data)
          await ctx.send(f"Stopped auto-deleting messages in {channel.mention}.")
      else:
          await ctx.send(f"{channel.mention} is not in the auto-deleter list.")
  

  def parse_time_limit(self, time_limit):
      try:
          if time_limit.endswith('d'):
              return int(time_limit[:-1]) * 86400  # 1 day = 86400 seconds
          elif time_limit.endswith('h'):
              return int(time_limit[:-1]) * 3600  # 1 hour = 3600 seconds
          elif time_limit.endswith('m'):
              return int(time_limit[:-1]) * 60  # 1 minute = 60 seconds
          else:
              return None
      except ValueError:
          return None

  @tasks.loop(minutes=1)
  async def autodelete_task(self):
      deleter_data = await load_deleter_data()
      now = datetime.utcnow()
      for channel_id, seconds in deleter_data.items():
          try:
              channel = self.bot.get_channel(int(channel_id))
              if channel:
                  # Calculate the threshold time in the correct time zone (e.g., UTC)
                  desired_timezone = pytz.timezone('UTC')
                  now = datetime.now(desired_timezone)
                  threshold_time = now - timedelta(seconds=seconds)
  
                  def check(message):
                      message_time = message.created_at
                      return message_time < threshold_time
  
                  deleted_messages = await channel.purge(limit=None, check=check)
                  print(f"Auto-deleted {len(deleted_messages)} messages in {channel.mention}.")
  
          except discord.Forbidden:
              print(f"I don't have permission to delete messages in {channel.mention}.")
          except discord.HTTPException as e:
              print(f"An error occurred while deleting messages in {channel.mention}: {e}")



  @autodelete_task.before_loop
  async def before_autodelete_task(self):
      await self.bot.wait_until_ready()  # Wait for the bot to fully connect


  @commands.command()
  async def deleter(self, ctx, messages: int):
    """
    `[p]deleter number` - Delete last X messages in the channel you post this command in.
    """
    if messages < 1:
        await ctx.send("Please provide a valid number greater than 0.")
        return

    try:
        await ctx.message.delete()  # Delete the command message
        deleted = await ctx.channel.purge(limit=messages)  # Delete X messages

        # Send a confirmation message
        await ctx.send(f"Deleted {len(deleted)} messages.")
    except discord.Forbidden:
        await ctx.send("I don't have permission to delete messages.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred while deleting messages: {e}")
    except commands.MissingPermissions:
        await ctx.send("You don't have the necessary permissions to use this command.")




async def setup(bot):
  await bot.add_cog(deleter(bot))
