import discord

class BackstorySelect(discord.ui.Select):
    def __init__(self, options, placeholder="Select an option..."):
        # Discord select menus can only have 25 options.
        # We store options to map back from index
        self.original_options = options

        truncated_options = options
        if len(options) > 25:
             truncated_options = options[:25] # Truncate for now

        select_options = []
        for i, opt in enumerate(truncated_options):
             label = str(opt)[:100]
             # Use index as value to avoid truncation issues and collisions
             select_options.append(discord.SelectOption(label=label, value=str(i)))

        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=select_options)

    async def callback(self, interaction: discord.Interaction):
        # We need access to the view to verify the author and store the result
        view: BackstoryView = self.view
        if interaction.user != view.author:
            await interaction.response.send_message("You are not the author of this command!", ephemeral=True)
            return

        index = int(self.values[0])
        if 0 <= index < len(self.original_options):
             view.selected_option = self.original_options[index]
        else:
             # Should not happen
             view.selected_option = None

        view.stop()
        await interaction.response.defer()

class BackstoryView(discord.ui.View):
    def __init__(self, options, author, placeholder="Select an option...", timeout=60):
        super().__init__(timeout=timeout)
        self.author = author
        self.selected_option = None

        self.add_item(BackstorySelect(options, placeholder))

        # Add cancel button
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("You are not the author of this command!", ephemeral=True)
            return
        self.selected_option = None
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self):
        self.stop()
