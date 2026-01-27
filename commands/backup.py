import discord
from discord.ext import commands, tasks
import asyncio


class backup(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.backup_task.start()

  @tasks.loop(hours=24)
  async def backup_task(self):
      user_id = 214351769243877376  # Replace with your bot owner's user ID
      try:
          with open('data/player_stats.json', 'rb') as file:
              owner = await self.bot.fetch_user(user_id)
              await owner.send(file=discord.File(file, 'player_stats.json'))
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
    if ctx.message.author.id == 214351769243877376:
        try:
            # Replace 'data/player_data.json' with the actual file path
            with open('data/player_stats.json', 'rb') as file:
                await ctx.author.send(file=discord.File(file, 'player_stats.json'))
            await ctx.send("Backup file sent to the bot owner.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
    else:
        await ctx.send("You do not have permission to use this command.")



async def setup(bot):
  await bot.add_cog(backup(bot))