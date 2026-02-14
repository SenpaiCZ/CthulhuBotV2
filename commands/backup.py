import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import aiofiles
import io
import os
import zipfile
import datetime
from loadnsave import load_settings

class backup(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.last_backup_date = None
    self.backup_task.start()

  async def perform_backup(self, target_user=None):
      try:
          # If no target user is specified, default to the bot owner
          if target_user is None:
              app_info = await self.bot.application_info()
              target_user = app_info.owner

          # Create a zip buffer
          zip_buffer = io.BytesIO()

          # current date/time for filename
          now = datetime.datetime.now()
          filename = f"backup_{now.strftime('%Y-%m-%d_%H-%M')}.zip"

          with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
              # Walk through data directory
              if os.path.exists('data'):
                  for root, dirs, files in os.walk('data'):
                      for file in files:
                          file_path = os.path.join(root, file)
                          # Add file to zip, arcname makes it relative to current directory (so it includes data/)
                          zip_file.write(file_path, os.path.relpath(file_path, '.'))

          zip_buffer.seek(0)

          await target_user.send(file=discord.File(zip_buffer, filename))
          print(f"Backup {filename} sent to {target_user}.")
          return True, filename
      except Exception as e:
          print(f"An error occurred while performing backup: {e}")
          return False, str(e)

  @tasks.loop(minutes=1)
  async def backup_task(self):
      try:
          settings = load_settings()
          backup_time = settings.get("backup_time") # Expecting "HH:MM" 24h format

          if not backup_time:
              return

          now = datetime.datetime.now()
          current_time_str = now.strftime("%H:%M")
          current_date_str = now.strftime("%Y-%m-%d")

          # Check if time matches and we haven't backed up today already
          if current_time_str == backup_time:
              if self.last_backup_date != current_date_str:
                  await self.perform_backup()
                  self.last_backup_date = current_date_str
      except Exception as e:
          print(f"Error in backup task: {e}")

  @backup_task.before_loop
  async def before_backup_task(self):
      await self.bot.wait_until_ready()
  
  @app_commands.command(name="backup", description="Zips the data/ folder and sends it to the bot owner.")
  async def backup(self, interaction: discord.Interaction):
    # Check for ownership manually since app_commands.checks doesn't have is_owner built-in directly
    if not await self.bot.is_owner(interaction.user):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    # We can send to interaction user since we verified they are owner
    success, result = await self.perform_backup(interaction.user)

    if success:
        await interaction.followup.send(f"Backup `{result}` sent successfully to your DM.")
    else:
        await interaction.followup.send(f"Backup failed: {result}")

async def setup(bot):
  await bot.add_cog(backup(bot))
