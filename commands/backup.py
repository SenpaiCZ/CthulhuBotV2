import discord
from discord.ext import commands, tasks
import asyncio
import aiofiles
import io


class backup(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.backup_task.start()

  @tasks.loop(hours=24)
  async def backup_task(self):
      try:
          # Fetch application info to get the owner
          app_info = await self.bot.application_info()
          owner = app_info.owner

          async with aiofiles.open('data/player_stats.json', 'rb') as file:
              data = await file.read()
              file_obj = io.BytesIO(data)
              await owner.send(file=discord.File(file_obj, 'player_stats.json'))
      except Exception as e:
          print(f"An error occurred while sending the backup file: {e}")

  @backup_task.before_loop
  async def before_backup_task(self):
      await self.bot.wait_until_ready()
  
  @commands.command()
  async def backup(self, ctx):
    """
    `[p]backup` - Sends the file data/player_data.json to the bot owner.
    """
    # Check if the message author is the bot owner
    if await self.bot.is_owner(ctx.author):
        try:
            # Replace 'data/player_data.json' with the actual file path
            async with aiofiles.open('data/player_stats.json', 'rb') as file:
                data = await file.read()
                file_obj = io.BytesIO(data)
                await ctx.author.send(file=discord.File(file_obj, 'player_stats.json'))
            await ctx.send("Backup file sent to the bot owner.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
    else:
        await ctx.send("You do not have permission to use this command.")



async def setup(bot):
  await bot.add_cog(backup(bot))
