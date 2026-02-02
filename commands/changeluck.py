import discord, json, aiofiles
from discord.ext import commands
from loadnsave import load_luck_stats, save_luck_stats

class changeluck(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    
  @commands.command()
  async def changeluck(self, ctx, luck=None):
      """
      `[p]changeluck newMaxLuckUsed` - Change how much luck can players spend to make a successful roll.
      If you set value to 0 you will disable spending luck for you players.
      """
      if not isinstance(ctx.channel, discord.TextChannel):
          await ctx.send("This command is not allowed in DMs.")
          return

      if not ctx.author.guild_permissions.administrator:
          await ctx.send("This command is limited to the server administrators only.")
          return
  
      if luck is None:
          await ctx.send("Please add how much luck players can use to make a successful roll on this server.")
          return
  
      if not luck.isdigit():
          await ctx.send("Please enter a valid integer for luck.")
          return
  
      luck = int(luck)  # Convert the input to an integer
  
      server_id = str(ctx.guild.id)  # Get the server's ID as a string
      server_stats = await load_luck_stats()
  
      # Set the custom luck for the server
      server_stats[server_id] = luck
      await save_luck_stats(server_stats)
      await ctx.send(f"The server's luck threshold has been changed to `{luck}`.")
        
  @commands.command()
  async def showluck(self, ctx):
      """
      `[p]showluck` - Show the luck settings for the server.
      """
      server_id = str(ctx.guild.id)  # Get the server's ID as a string
      server_stats = await load_luck_stats()
  
      # Check if the server has a custom luck setting; if not, use a default value of 10
      luck_value = server_stats.get(server_id, 10)
  
      await ctx.send(f"The current luck threshold for this server is `{luck_value}`.")  

async def setup(bot):
  await bot.add_cog(changeluck(bot))
