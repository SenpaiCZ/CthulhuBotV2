import discord
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats

class BackstoryView(discord.ui.View):
    def __init__(self, categories, author):
        super().__init__(timeout=60)
        self.selected_category = None
        self.author = author
        self.message = None

        # Create a button for each category
        for index, category in enumerate(categories):
            self.add_item(discord.ui.Button(label=category, style=discord.ButtonStyle.primary, custom_id=str(index)))

        # Add a cancel button
        self.add_item(discord.ui.Button(label='Cancel', style=discord.ButtonStyle.danger, custom_id='cancel'))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You're not the author of this command!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    async def handle_button_interaction(self, interaction: discord.Interaction, category):
        self.selected_category = category
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content=f"Selected category: {self.selected_category}", view=self)
        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction):
        self.selected_category = None
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="Backstory addition cancelled.", view=self)
        self.stop()

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
        view.message = await ctx.send("Please select a category for your backstory:", view=view)

        # Dynamically create methods for buttons
        for index, category in enumerate(categories):
            async def button_callback(interaction, category=category):
                await view.handle_button_interaction(interaction, category)
            setattr(view, f'button_callback_{index}', button_callback)
            button = view.children[index]
            button.callback = getattr(view, f'button_callback_{index}')

        # Set cancel button callback
        cancel_button = view.children[-1]  # Assuming the last button is 'Cancel'
        cancel_button.callback = view.cancel_callback

        await view.wait()

        if view.selected_category:
            def check(m):
                return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

            await ctx.send(f"Selected category: {view.selected_category}\nPlease type what you want to add:")
            try:
                message = await self.bot.wait_for('message', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond.")
                return

            entry = message.content
            if "Backstory" not in player_stats[server_id][user_id]:
                player_stats[server_id][user_id]["Backstory"] = {}

            if view.selected_category not in player_stats[server_id][user_id]["Backstory"]:
                player_stats[server_id][user_id]["Backstory"][view.selected_category] = []

            player_stats[server_id][user_id]["Backstory"][view.selected_category].append(entry)
            await save_player_stats(player_stats)
            await ctx.send(f"Entry '{entry}' has been added to the '{view.selected_category}' category in your Backstory.")
        elif view.selected_category is None:
            await ctx.send("No category selected or action cancelled.")

async def setup(bot):
    await bot.add_cog(addbackstory(bot))
