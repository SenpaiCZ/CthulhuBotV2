import discord

class BackstoryView(discord.ui.View):
    def __init__(self, options, author, timeout=60):
        super().__init__(timeout=timeout)
        self.author = author
        self.selected_option = None

        # Add buttons for each option (limit to 24 to leave room for Cancel)
        # Discord limit is 25 buttons per view (5x5 grid)
        if len(options) > 24:
            options = options[:24]
            # Ideally we would paginate or warn, but for now we truncate to prevent crash

        for option in options:
            button = discord.ui.Button(label=str(option)[:80], style=discord.ButtonStyle.primary) # Label limit 80 chars
            button.callback = self.create_callback(option)
            self.add_item(button)

        # Add cancel button if not already implicitly handled by timeout (but explicit is better)
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    def create_callback(self, option):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.author:
                await interaction.response.send_message("You are not the author of this command!", ephemeral=True)
                return
            self.selected_option = option
            self.stop()
            # We don't edit the message here, we leave it to the caller to decide what to do next
            # But we must acknowledge the interaction to prevent "interaction failed"
            await interaction.response.defer()
        return callback

    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("You are not the author of this command!", ephemeral=True)
            return
        self.selected_option = None
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self):
        self.stop()
