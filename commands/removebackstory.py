import discord
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats
from commands.backstory_common import BackstoryView

class removebackstory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["rb", "RB"])
    async def removebackstory(self, ctx):
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

            await message.edit(content=f"Selected category: **{selected_category}**", view=None)

            item_view = BackstoryView(items, ctx.author)
            item_msg = await ctx.send(f"Select an item from '{selected_category}' to remove:", view=item_view)
            await item_view.wait()

            if item_view.selected_option:
                selected_item = item_view.selected_option

                try:
                    backstory[selected_category].remove(selected_item)
                    await save_player_stats(player_stats)
                    try:
                        await item_msg.delete()
                        await message.delete()
                    except:
                        pass
                    await ctx.send(f"Item '{selected_item}' removed from '{selected_category}'.")
                except ValueError:
                    await ctx.send("Error: Item could not be found to remove.")
            else:
                await item_msg.edit(content="Item selection cancelled.", view=None)
        else:
            await message.edit(content="Category selection cancelled.", view=None)

async def setup(bot):
    await bot.add_cog(removebackstory(bot))
