import discord
import asyncio
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats
from commands._backstory_common import BackstoryView

class addbackstory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["cb", "CB", "ab"])
    async def addbackstory(self, ctx):
        """
        `[p]cb` - Add a record to your backstory or inventory interactively.
        """
        server_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command is not allowed in DMs.")
            return

        player_stats = await load_player_stats()
        if user_id not in player_stats[server_id]:
            await ctx.send(f"{ctx.author.display_name} doesn't have an investigator. Use `!newInv` to create a new investigator.")
            return

        categories = [
          'My Story', 'Personal Description', 'Ideology and Beliefs', 'Significant People',
          'Meaningful Locations', 'Treasured Possessions', 'Traits', 'Injuries and Scars',
          'Phobias and Manias', 'Arcane Tome and Spells', 'Encounters with Strange Entities',
          'Fellow Investigators', 'Gear and Possessions', 'Spending Level', 'Cash', 'Assets'
        ]

        view = BackstoryView(categories, ctx.author)
        message = await ctx.send("Please select a category for your backstory:", view=view)

        await view.wait()

        if view.selected_option:
            # Clean up the previous message/view
            try:
                await message.delete()
            except:
                pass

            def check(m):
                return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

            await ctx.send(f"Selected category: **{view.selected_option}**\nPlease type what you want to add:")
            try:
                msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond.")
                return

            entry = msg.content
            if "Backstory" not in player_stats[server_id][user_id]:
                player_stats[server_id][user_id]["Backstory"] = {}

            if view.selected_option not in player_stats[server_id][user_id]["Backstory"]:
                player_stats[server_id][user_id]["Backstory"][view.selected_option] = []

            player_stats[server_id][user_id]["Backstory"][view.selected_option].append(entry)
            await save_player_stats(player_stats)
            await ctx.send(f"Entry '{entry}' has been added to the '{view.selected_option}' category in your Backstory.")
        else:
            try:
                await message.edit(content="Action cancelled or timed out.", view=None)
            except:
                pass

async def setup(bot):
    await bot.add_cog(addbackstory(bot))
