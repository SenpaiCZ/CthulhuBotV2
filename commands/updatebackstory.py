import discord
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats

class BackstoryView(discord.ui.View):
    def __init__(self, options, author):
        super().__init__(timeout=60)
        self.author = author
        self.selected_option = None

        for option in options:
            button = discord.ui.Button(label=option, style=discord.ButtonStyle.primary)
            button.callback = lambda interaction, label=option: self.on_button_click(interaction, label)
            self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author

    async def on_button_click(self, interaction: discord.Interaction, label):
        self.selected_option = label
        self.stop()
        await interaction.response.edit_message(content=f"Selected: {label}", view=None)

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
        category_view = BackstoryView(categories, ctx.author)
        category_view.message = await ctx.send("Select a category from your backstory:", view=category_view)
        await category_view.wait()

        if category_view.selected_option:
            selected_category = category_view.selected_option
            items = backstory[selected_category]
            item_view = BackstoryView(items, ctx.author)
            item_view.message = await ctx.send(f"Select an item from '{selected_category}' to update:", view=item_view)
            await item_view.wait()

            if item_view.selected_option:
                selected_item = item_view.selected_option

                def check(m):
                    return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

                await ctx.send(f"Selected item: '{selected_item}'. Please type the new text for this item:")
                try:
                    new_message = await self.bot.wait_for('message', timeout=120.0, check=check)
                except asyncio.TimeoutError:
                    await ctx.send("You took too long to respond.")
                    return

                item_index = backstory[selected_category].index(selected_item)
                backstory[selected_category][item_index] = new_message.content
                await save_player_stats(player_stats)
                await ctx.send(f"Item '{selected_item}' updated in '{selected_category}'.")

async def setup(bot):
    await bot.add_cog(updatebackstory(bot))
