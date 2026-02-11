import discord, random
from discord.ext import commands
from loadnsave import load_macguffin_data


class MacGuffinView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.message = None

    @discord.ui.button(label="Random MacGuffin", style=discord.ButtonStyle.success)
    async def random_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return

        macguffin_list = await load_macguffin_data()
        # Ensure list is not empty
        if not macguffin_list:
             await interaction.response.send_message("No MacGuffins found.", ephemeral=True)
             return

        random_macguffin = random.choice(list(macguffin_list.keys()))
        embed = discord.Embed(title="Random MacGuffin", description=f"{random_macguffin}\n\n{macguffin_list[random_macguffin]}", color=0xff0000)

        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="List All", style=discord.ButtonStyle.secondary)
    async def list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return

        macguffin_list = await load_macguffin_data()
        if not macguffin_list:
             await interaction.response.send_message("No MacGuffins found.", ephemeral=True)
             return

        macguffin_data = [f"**{name}**: {description}" for name, description in macguffin_list.items()]
        macguffin_all = '\n\n'.join(macguffin_data)
        embed = discord.Embed(title="MacGuffin Options", description=macguffin_all, color=0x00ff00)

        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(content="Timed out.", view=None)
            except:
                pass
        self.stop()


class macguffin(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.hybrid_command(description="Outputs a random MacGuffin or lists options.")
  async def macguffin(self, ctx):
    """
    `[p]macguffin` - outputs random macguffin.
    """
    view = MacGuffinView(ctx)
    ephemeral = False
    if ctx.interaction:
        ephemeral = True

    msg = await ctx.send("Choose an option:", view=view, ephemeral=ephemeral)
    view.message = msg


async def setup(bot):
  await bot.add_cog(macguffin(bot))
