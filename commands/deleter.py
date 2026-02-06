import discord
from discord.ext import commands, tasks
from discord.ui import View, Select, Button
import asyncio
import json
import pytz
from datetime import datetime, timedelta
from loadnsave import load_deleter_data, save_deleter_data

TIME_OPTIONS = {
    "10 Minutes": 600,
    "30 Minutes": 1800,
    "1 Hour": 3600,
    "6 Hours": 21600,
    "12 Hours": 43200,
    "1 Day": 86400,
    "3 Days": 259200,
    "1 Week": 604800,
    "2 Weeks": 1209600,
    "1 Month": 2592000
}

class ChannelSelect(Select):
    def __init__(self, channels):
        options = []
        # Discord allows max 25 options
        for channel in channels[:25]:
            options.append(discord.SelectOption(label=channel.name, value=str(channel.id), emoji="#️⃣"))

        super().__init__(placeholder="Select channel", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.selected_channel_id = int(self.values[0])
        self.view.stop()

class TimeSelect(Select):
    def __init__(self):
        options = []
        for label, seconds in TIME_OPTIONS.items():
             options.append(discord.SelectOption(label=label, value=str(seconds)))

        options.append(discord.SelectOption(label="Custom", value="custom", emoji="✍️"))

        super().__init__(placeholder="Select time limit", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.selected_seconds = self.values[0]
        self.view.stop()

class AutoDeleterView(View):
    def __init__(self, channels=None, type="channel"):
        super().__init__(timeout=60.0)
        self.selected_channel_id = None
        self.selected_seconds = None

        if type == "channel" and channels:
            self.add_item(ChannelSelect(channels))
        elif type == "time":
            self.add_item(TimeSelect())

class deleter(commands.Cog):

  def __init__(self, bot):
      self.bot = bot
      self.autodelete_task.start()  # Start the task

  def cog_unload(self):
      self.autodelete_task.cancel()  # Cancel the task when the cog is unloaded

  @commands.command()
  async def autodeleter(self, ctx):
      """
      `[p]autodeleter` - Interactive wizard to setup auto-deletion.
      """
      def check(m):
          return m.author == ctx.author and m.channel == ctx.channel

      # --- Step 1: Channel ---
      text_channels = [c for c in ctx.guild.text_channels]
      text_channels.sort(key=lambda x: x.position)

      target_channel_id = None

      if len(text_channels) <= 25:
          view = AutoDeleterView(channels=text_channels, type="channel")
          prompt_msg = await ctx.send("Select channel to enable auto-deleter on:", view=view)

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
           await ctx.send("Select channel:\n(Too many channels for selector, please enter the **Channel ID** manually)")
           try:
               msg = await self.bot.wait_for('message', check=check, timeout=60.0)
               try:
                   target_channel_id = int(msg.content.strip())
                   channel = ctx.guild.get_channel(target_channel_id)
                   if not channel or not isinstance(channel, discord.TextChannel):
                        await ctx.send("Invalid Channel ID.")
                        return
               except ValueError:
                   await ctx.send("Invalid ID format.")
                   return
           except asyncio.TimeoutError:
               await ctx.send("Timed out.")
               return

      # --- Step 2: Time Limit ---
      view = AutoDeleterView(type="time")
      prompt_msg = await ctx.send("Select how old messages must be to be deleted:", view=view)

      timeout = await view.wait()
      if timeout:
          await ctx.send("Timed out.")
          return

      seconds = None
      if view.selected_seconds:
          await prompt_msg.delete()
          if view.selected_seconds == "custom":
              await ctx.send("Enter time limit (e.g., '1d', '2h', '30m'):")
              try:
                  msg = await self.bot.wait_for('message', check=check, timeout=60.0)
                  seconds = self.parse_time_limit(msg.content.strip())
                  if seconds is None:
                      await ctx.send("Invalid format.")
                      return
              except asyncio.TimeoutError:
                  await ctx.send("Timed out.")
                  return
          else:
              seconds = int(view.selected_seconds)
      else:
          await ctx.send("Selection cancelled.")
          return

      # --- Save ---
      deleter_data = await load_deleter_data()
      deleter_data[str(target_channel_id)] = seconds
      await save_deleter_data(deleter_data)

      channel = ctx.guild.get_channel(target_channel_id)
      mention = channel.mention if channel else target_channel_id
      time_str = str(timedelta(seconds=seconds))

      await ctx.send(f"Auto-deleter active for {mention}. Messages older than {time_str} will be deleted.")


  @commands.command()
  async def stopdeleter(self, ctx, channel: discord.TextChannel = None):
      """
      `[p]stopdeleter [channel]` - Stop auto-deleting messages.
      """
      deleter_data = await load_deleter_data()

      target_id = str(channel.id) if channel else str(ctx.channel.id)

      if target_id in deleter_data:
          del deleter_data[target_id]
          await save_deleter_data(deleter_data)
          await ctx.send(f"Stopped auto-deleting messages in <#{target_id}>.")
      else:
          await ctx.send(f"Auto-deleter is not active in <#{target_id}>.")
  

  def parse_time_limit(self, time_limit):
      try:
          time_limit = time_limit.lower()
          if time_limit.endswith('d'):
              return int(time_limit[:-1]) * 86400
          elif time_limit.endswith('h'):
              return int(time_limit[:-1]) * 3600
          elif time_limit.endswith('m'):
              return int(time_limit[:-1]) * 60
          elif time_limit.endswith('w'):
              return int(time_limit[:-1]) * 604800
          else:
              return int(time_limit) # Try raw seconds
      except ValueError:
          return None

  @tasks.loop(minutes=5)
  async def autodelete_task(self):
      deleter_data = await load_deleter_data()
      # Use UTC for consistency
      now = datetime.now(pytz.utc)

      for channel_id, seconds in deleter_data.items():
          try:
              channel = self.bot.get_channel(int(channel_id))
              if channel:
                  threshold_time = now - timedelta(seconds=seconds)

                  # Use before=threshold_time for efficiency
                  # Check API docs: purge(limit=None, before=date)
                  # It deletes everything before that date.
                  # Limit is None means "delete all that match".

                  deleted = await channel.purge(limit=None, before=threshold_time)
                  if len(deleted) > 0:
                      print(f"Auto-deleted {len(deleted)} messages in {channel.name} ({channel.id}).")
  
          except discord.Forbidden:
              print(f"I don't have permission to delete messages in channel {channel_id}.")
          except discord.HTTPException as e:
              print(f"An error occurred while deleting messages in channel {channel_id}: {e}")
          except Exception as e:
               print(f"Generic error in autodelete task for {channel_id}: {e}")



  @autodelete_task.before_loop
  async def before_autodelete_task(self):
      await self.bot.wait_until_ready()


  @commands.command()
  async def deleter(self, ctx, messages: int):
    """
    `[p]deleter number` - Delete last X messages in the channel you post this command in.
    """
    if messages < 1:
        await ctx.send("Please provide a valid number greater than 0.")
        return

    try:
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=messages)
        await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("I don't have permission to delete messages.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred while deleting messages: {e}")
    except commands.MissingPermissions:
        await ctx.send("You don't have the necessary permissions to use this command.")

  # API Helper methods
  async def api_bulk_delete(self, channel_id, amount):
      try:
          channel = self.bot.get_channel(int(channel_id))
          if not channel:
              return False, "Channel not found"

          deleted = await channel.purge(limit=int(amount))
          return True, len(deleted)
      except Exception as e:
          return False, str(e)


async def setup(bot):
  await bot.add_cog(deleter(bot))
