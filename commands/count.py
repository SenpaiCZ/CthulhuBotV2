import discord
from discord.ext import commands
import asyncio

class Count(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def count(self, ctx, channel_id: str = None):
        """
        `!count <channel_id>` - Counts all messages in the specified channel.
        """
        if channel_id is None:
             await ctx.send("❌ Please provide a Channel ID. Usage: `!count <channel_id>`")
             return

        # Validate channel ID
        try:
            c_id = int(channel_id)
        except ValueError:
            await ctx.send("❌ Please provide a valid numeric Channel ID.")
            return

        channel = ctx.guild.get_channel(c_id)
        if not channel:
            await ctx.send(f"❌ Channel with ID `{channel_id}` not found in this server.")
            return

        if not isinstance(channel, discord.TextChannel):
            await ctx.send("❌ The specified channel is not a text channel.")
            return

        # Initial status message
        status_msg = await ctx.send(f"🔄 Counting messages in {channel.mention}... This may take a while.")

        count = 0
        try:
            # Iterate through history
            async for _ in channel.history(limit=None):
                count += 1
                # Update progress every 1000 messages
                if count % 1000 == 0:
                    await status_msg.edit(content=f"🔄 Counting messages in {channel.mention}... Found **{count}** so far.")

            # Final count
            await status_msg.edit(content=f"✅ Counting complete for {channel.mention}. Total messages: **{count}**")

        except discord.Forbidden:
            await status_msg.edit(content=f"❌ I do not have permission to read message history in {channel.mention}.")
        except Exception as e:
            await status_msg.edit(content=f"❌ An error occurred while counting: {str(e)}")

async def setup(bot):
    await bot.add_cog(Count(bot))
