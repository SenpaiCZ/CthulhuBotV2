import discord, random
from discord import app_commands
from discord.ext import commands
from loadnsave import load_macguffin_data
from rapidfuzz import process, fuzz


class MacGuffinView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user

    @discord.ui.button(label="Random MacGuffin", style=discord.ButtonStyle.success)
    async def random_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
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
        if interaction.user != self.user:
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
        self.stop()


class macguffin(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @app_commands.command(name="macguffin", description="🔮 Outputs a random MacGuffin or lists options.")
  @app_commands.describe(name="The specific MacGuffin to look up (optional)")
  async def macguffin(self, interaction: discord.Interaction, name: str = None):
    """
    Outputs a specific MacGuffin, a random MacGuffin, or lists options.
    """
    if name:
        macguffin_list = await load_macguffin_data()
        if not macguffin_list:
             await interaction.response.send_message("No MacGuffins found.", ephemeral=True)
             return

        choices = list(macguffin_list.keys())

        # Check for exact match
        exact_match = None
        for choice in choices:
            if choice.lower() == name.lower():
                exact_match = choice
                break

        target_name = exact_match
        if not target_name:
            extract = process.extractOne(name, choices, scorer=fuzz.WRatio)
            if extract and extract[1] > 60:
                target_name = extract[0]

        if target_name:
            embed = discord.Embed(title=target_name, description=macguffin_list[target_name], color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(f"No MacGuffin found matching '{name}'.", ephemeral=True)
    else:
        view = MacGuffinView(interaction.user)
        await interaction.response.send_message("Choose an option:", view=view, ephemeral=True)

  @macguffin.autocomplete('name')
  async def macguffin_autocomplete(self, interaction: discord.Interaction, current: str):
      macguffin_list = await load_macguffin_data()
      if not macguffin_list:
          return []

      choices = list(macguffin_list.keys())
      if not current:
          return [app_commands.Choice(name=c[:100], value=c[:100]) for c in sorted(choices)[:25]]

      matches = process.extract(current, choices, scorer=fuzz.WRatio, limit=25)
      return [app_commands.Choice(name=m[0][:100], value=m[0][:100]) for m in matches]


async def setup(bot):
  await bot.add_cog(macguffin(bot))
