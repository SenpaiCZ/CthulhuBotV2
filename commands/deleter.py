import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import pytz
from loadnsave import load_deleter_data, save_deleter_data

class Deleter(commands.Cog, name="deleter"):
    def __init__(self, bot):
        self.bot = bot
        self.autodelete_task.start()

    def cog_unload(self):
        self.autodelete_task.cancel()

    autodeleter_group = app_commands.Group(name="autodeleter", description="Manage auto-deletion")

    def parse_time_limit(self, time_limit):
        try:
            time_limit = time_limit.lower().strip()
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

    @autodeleter_group.command(name="set", description="Enable auto-deletion for a channel.")
    @app_commands.describe(time_limit="Time limit (e.g., '1d', '2h', '30m')", channel="Channel to set (defaults to current)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def set_deleter(self, interaction: discord.Interaction, time_limit: str, channel: discord.TextChannel = None):
        """Enable auto-deletion for a channel."""
        target_channel = channel or interaction.channel

        if not isinstance(target_channel, discord.TextChannel):
             await interaction.response.send_message("Auto-deleter only works on Text Channels.", ephemeral=True)
             return

        seconds = self.parse_time_limit(time_limit)
        if seconds is None:
            await interaction.response.send_message("Invalid time format. Use '1d', '2h', '30m', etc.", ephemeral=True)
            return

        if seconds < 60:
             await interaction.response.send_message("Time limit must be at least 1 minute (60s).", ephemeral=True)
             return

        deleter_data = await load_deleter_data()
        deleter_data[str(target_channel.id)] = seconds
        await save_deleter_data(deleter_data)

        time_str = str(timedelta(seconds=seconds))
        await interaction.response.send_message(f"Auto-deleter active for {target_channel.mention}. Messages older than {time_str} will be deleted.")

    @autodeleter_group.command(name="stop", description="Stop auto-deletion for a channel.")
    @app_commands.describe(channel="Channel to stop (defaults to current)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def stop_deleter(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Stop auto-deletion for a channel."""
        target_channel = channel or interaction.channel
        target_id = str(target_channel.id)

        deleter_data = await load_deleter_data()

        if target_id in deleter_data:
            del deleter_data[target_id]
            await save_deleter_data(deleter_data)
            await interaction.response.send_message(f"Stopped auto-deleting messages in {target_channel.mention}.")
        else:
            await interaction.response.send_message(f"Auto-deleter is not active in {target_channel.mention}.", ephemeral=True)

    @app_commands.command(name="purge", description="Delete the last X messages in the channel.")
    @app_commands.describe(amount="Number of messages to delete")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int):
        """Delete the last X messages in the channel."""
        if amount < 1:
            await interaction.response.send_message("Please provide a number greater than 0.", ephemeral=True)
            return

        if not isinstance(interaction.channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
             await interaction.response.send_message("This command cannot be used here.", ephemeral=True)
             return

        await interaction.response.defer(ephemeral=True) # Defer as ephemeral since we are deleting messages

        try:
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to delete messages.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    @tasks.loop(minutes=5)
    async def autodelete_task(self):
        deleter_data = await load_deleter_data()
        now = datetime.now(pytz.utc)

        for channel_id, seconds in deleter_data.items():
            try:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    threshold_time = now - timedelta(seconds=seconds)
                    try:
                        await channel.purge(limit=None, before=threshold_time)
                    except Exception:
                        pass # Ignore errors during purge to keep loop running
            except Exception as e:
                print(f"Error in autodelete task: {e}")

    @autodelete_task.before_loop
    async def before_autodelete_task(self):
        await self.bot.wait_until_ready()

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
    await bot.add_cog(Deleter(bot))
