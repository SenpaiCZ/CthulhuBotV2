import discord, random
from discord.ext import commands
from discord import app_commands
from loadnsave import load_names_data


class RandomNameView(discord.ui.View):
    def __init__(self, ctx, cog, region="english"):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.region = region
        self.message = None

    async def _generate_name(self, interaction, gender):
        # Allow only the author to select
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return

        all_names = await load_names_data()

        # Fallback to english if region not found
        region_data = all_names.get(self.region, all_names.get("english"))

        last_names = region_data.get("last", [])

        if gender == "male":
            first_names = region_data.get("male", [])
        else:
            first_names = region_data.get("female", [])

        if not first_names or not last_names:
             await interaction.response.send_message("Error loading names for this region.", ephemeral=True)
             return

        name = random.choice(first_names)
        # 30% chance for middle name
        if random.random() < 0.3:
            name += " " + random.choice(first_names)

        name += " " + random.choice(last_names)

        # 50% chance for double barrel surname
        if random.random() < 0.5:
            name += "-" + random.choice(last_names)

        region_display = self.region.capitalize()
        if self.region == "english":
             region_display = "English/American"

        embed = discord.Embed(title=f"Random {region_display} name",
                              description=f":game_die: **{name}** :game_die:",
                              color=discord.Color.blue())

        # Edit the original message, removing the view
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Male", style=discord.ButtonStyle.primary)
    async def male_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._generate_name(interaction, "male")

    @discord.ui.button(label="Female", style=discord.ButtonStyle.danger)
    async def female_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._generate_name(interaction, "female")

    async def on_timeout(self):
        if self.message:
            try:
                # If interaction, we can't delete ephemeral messages easily if deferred,
                # but here we edit to remove buttons if timed out.
                # However, usually we just delete the message if it's a normal command,
                # or edit content if ephemeral.
                await self.message.edit(content="Timed out.", view=None)
            except:
                pass
        self.stop()


class randomname(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.hybrid_command(name="randomname", aliases=["rname"], description="Generate a random name from the 1920s era.")
  @app_commands.describe(region="Choose a region for the name origin")
  @app_commands.choices(region=[
      app_commands.Choice(name="English & American", value="english"),
      app_commands.Choice(name="Scandinavian", value="scandinavian"),
      app_commands.Choice(name="German", value="german"),
      app_commands.Choice(name="French", value="french"),
      app_commands.Choice(name="Arabic", value="arabic"),
      app_commands.Choice(name="Spanish", value="spanish"),
      app_commands.Choice(name="Russian", value="russian"),
      app_commands.Choice(name="Chinese", value="chinese"),
      app_commands.Choice(name="Japanese", value="japanese")
  ])
  async def randomname(self, ctx, region: str = "english"):
    """
    Generate a random name from the 1920s era.
    """
    view = RandomNameView(ctx, self, region)
    ephemeral = False
    if ctx.interaction:
        ephemeral = True
    
    region_display = region.capitalize()
    if region == "english":
        region_display = "English & American"

    msg = await ctx.send(f"Select gender for random {region_display} name:", view=view, ephemeral=ephemeral)
    view.message = msg


async def setup(bot):
  await bot.add_cog(randomname(bot))
