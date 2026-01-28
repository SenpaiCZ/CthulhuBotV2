import discord
import asyncio
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats
from commands.backstory_common import BackstoryView

class updatebackstory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["ub", "UB"])
    async def updatebackstory(self, ctx):
        user_id = str(ctx.author.id)
        server_id = str(ctx.guild.id)

        player_stats = await load_player_stats()
        if user_id not in player_stats[server_id]:
            await ctx.send("You don't have an investigator.")
            return

        backstory = player_stats[server_id][user_id].get("Backstory", {})
        if not backstory:
            await ctx.send("Your backstory is empty.")
            return

        categories = list(backstory.keys())
        if not categories:
             await ctx.send("Your backstory is empty.")
             return

        category_view = BackstoryView(categories, ctx.author)
        message = await ctx.send("Select a category from your backstory:", view=category_view)
        await category_view.wait()

        if category_view.selected_option:
            selected_category = category_view.selected_option
            items = backstory[selected_category]

            if not items:
                await ctx.send(f"Category '{selected_category}' is empty.")
                return

            # Update the message for the next step
            await message.edit(content=f"Selected category: **{selected_category}**", view=None)

            item_view = BackstoryView(items, ctx.author)
            item_msg = await ctx.send(f"Select an item from '{selected_category}' to update:", view=item_view)
            await item_view.wait()

            if item_view.selected_option:
                selected_item = item_view.selected_option

                # Cleanup UI
                try:
                    await item_msg.delete()
                    await message.delete()
                except:
                    pass

                def check(m):
                    return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

                await ctx.send(f"Selected item: '{selected_item}'.\nPlease type the new text for this item:")
                try:
                    new_message = await self.bot.wait_for('message', timeout=120.0, check=check)
                except asyncio.TimeoutError:
                    await ctx.send("You took too long to respond.")
                    return

                try:
                    item_index = backstory[selected_category].index(selected_item)
                    backstory[selected_category][item_index] = new_message.content
                    await save_player_stats(player_stats)
                    await ctx.send(f"Item updated in '{selected_category}'.")
                except ValueError:
                    await ctx.send("Error: The item seems to have changed or was removed.")
            else:
                 await item_msg.edit(content="Item selection cancelled.", view=None)
        else:
             await message.edit(content="Category selection cancelled.", view=None)

async def setup(bot):
    await bot.add_cog(updatebackstory(bot))
