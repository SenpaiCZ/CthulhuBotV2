import discord

class PollButton(discord.ui.Button):
    def __init__(self, label, index, poll_id):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=label,
            custom_id=f"poll:{poll_id}:{index}"
        )
        self.index = index
        self.poll_id = str(poll_id)

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Polls")
        if cog:
            await cog.handle_vote(interaction, self.poll_id, self.index)
        else:
            await interaction.response.send_message("Poll system error.", ephemeral=True)

class PollView(discord.ui.View):
    def __init__(self, options, poll_id):
        super().__init__(timeout=None)
        for i, option in enumerate(options):
            label = option[:80]
            self.add_item(PollButton(label=label, index=i, poll_id=poll_id))

class PollModal(discord.ui.Modal, title="Create New Poll"):
    question = discord.ui.TextInput(label="Question", placeholder="What do you want to ask?", max_length=256)
    options = discord.ui.TextInput(label="Options (one per line)", style=discord.TextStyle.paragraph, placeholder="Option 1\nOption 2\nOption 3", max_length=2000, required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        raw_options = self.options.value.split('\n')
        parsed_options = [opt.strip() for opt in raw_options if opt.strip()]

        if len(parsed_options) < 2:
            await interaction.response.send_message("You need at least two options.", ephemeral=True)
            return
        if len(parsed_options) > 25:
            await interaction.response.send_message("Too many options (max 25).", ephemeral=True)
            return

        await self.cog._create_poll_internal(interaction, self.question.value, parsed_options)
