import discord
from discord.ext import commands

class AdminSlash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("AdminSlash cog loaded. Use !sync to sync application commands.")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def sync(self, ctx, spec: str = None):
        """
        Syncs slash commands to Discord.
        Usage:
        !sync -> Sync globally (takes up to 1 hour to propagate)
        !sync guild -> Sync to current guild (instant)
        !sync clear -> Clear global commands
        """
        msg = await ctx.send("Syncing...")
        try:
            if spec == "guild":
                if ctx.guild:
                    self.bot.tree.copy_global_to(guild=ctx.guild)
                    synced = await self.bot.tree.sync(guild=ctx.guild)
                    await msg.edit(content=f"✅ Synced {len(synced)} commands to this guild.")
                else:
                    await msg.edit(content="❌ This command must be run in a guild.")
            elif spec == "clear":
                self.bot.tree.clear_commands(guild=None)
                await self.bot.tree.sync()
                await msg.edit(content="✅ Global commands cleared.")
            else:
                synced = await self.bot.tree.sync()
                await msg.edit(content=f"✅ Synced {len(synced)} global commands. Updates may take up to an hour.")
        except Exception as e:
            await msg.edit(content=f"❌ Sync failed: {e}")

async def setup(bot):
    await bot.add_cog(AdminSlash(bot))
