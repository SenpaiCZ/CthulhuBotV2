import discord
from discord.ext import commands
from loadnsave import load_gamemode_stats, save_gamemode_stats

class changemode(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def pulp(self, ctx):
        """
        `[p]pulp` - Toggle between Call of Cthulhu and Pulp Cthulhu mode for this server.
        """
        if ctx.author != ctx.guild.owner:
            await ctx.send("This command is limited to the server owner only.")
            return
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command is not allowed in DMs.")
            return

        server_id = str(ctx.guild.id)  # Get the server's ID as a string
        server_stats = await load_gamemode_stats()


        if server_id not in server_stats:
            server_stats[server_id] = {}

        if 'game_mode' not in server_stats[server_id]:
            server_stats[server_id]['game_mode'] = 'Call of Cthulhu'  # Default to Call of Cthulhu

        current_mode = server_stats[server_id]['game_mode']

        if current_mode == 'Call of Cthulhu':
            server_stats[server_id]['game_mode'] = 'Pulp of Cthulhu'
            await ctx.send("The game mode has been switched to **Pulp of Cthulhu**.")
        else:
            server_stats[server_id]['game_mode'] = 'Call of Cthulhu'
            await ctx.send("The game mode has been switched to **Call of Cthulhu**.")

        await save_gamemode_stats(server_stats)

async def setup(bot):
    await bot.add_cog(changemode(bot))
