import discord
from discord.ext import commands
import time

class ping(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.hybrid_command(name="ping", description="Check bot latency and API response time.")
  async def ping(self, ctx):
    """
    `[p]ping` - Check bot latency and API response time.
    """
    start_time = time.perf_counter()

    # Send initial message (ephemeral if slash command)
    if ctx.interaction:
        # For slash commands, we respond ephemerally
        await ctx.interaction.response.send_message("🏓 Pinging...", ephemeral=True)
        # We need to fetch the message object to edit it later
        initial_msg = await ctx.interaction.original_response()
    else:
        # For text commands, we just send a message
        initial_msg = await ctx.send("🏓 Pinging...")

    end_time = time.perf_counter()

    rest_latency = (end_time - start_time) * 1000
    gateway_latency = self.bot.latency * 1000 if self.bot.latency else 0

    # Determine color based on health
    if gateway_latency < 100 and rest_latency < 200:
        color = discord.Color.green()
    elif gateway_latency < 200 and rest_latency < 400:
        color = discord.Color.gold()
    else:
        color = discord.Color.red()

    embed = discord.Embed(title="🏓 Pong!", color=color)
    embed.add_field(name="Gateway Latency", value=f"`{gateway_latency:.2f}ms`", inline=True)
    embed.add_field(name="REST Latency", value=f"`{rest_latency:.2f}ms`", inline=True)

    await initial_msg.edit(content=None, embed=embed)

async def setup(bot):
  await bot.add_cog(ping(bot))
