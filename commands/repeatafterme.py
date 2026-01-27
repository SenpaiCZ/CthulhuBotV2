import discord
from discord.ext import commands

class repeatafterme(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["ram"], guild_only=True)
    @commands.has_permissions(administrator=True)
    async def repeatafterme(self, ctx, channel: discord.TextChannel, *, text: str):
        """
        `[p]repeatafterme #channel_name "your text here"` - Bot sends command with message that user inputed
        """
        if not channel.permissions_for(ctx.guild.me).send_messages:
            return await ctx.send("I don't have permission to send messages in that channel.")

        await channel.send(text)
        await ctx.send(f"Message sent to {channel.mention}: {text}")

async def setup(bot):
    await bot.add_cog(repeatafterme(bot))