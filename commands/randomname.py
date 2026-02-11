import discord, random
from discord.ext import commands
from loadnsave import load_names_male_data, load_names_female_data, load_names_last_data


class RandomNameView(discord.ui.View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.message = None

    async def _generate_name(self, interaction, gender):
        # Allow only the author to select
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return

        last_names = await load_names_last_data()

        if gender == "male":
            male_names = await load_names_male_data()
            name = random.choice(male_names)
            if random.random() < 0.3:
                name += " " + random.choice(male_names)
            name += " " + random.choice(last_names)
            if random.random() < 0.5:
                name += "-" + random.choice(last_names)
        else:
            female_names = await load_names_female_data()
            name = random.choice(female_names)
            if random.random() < 0.3:
                name += " " + random.choice(female_names)
            name += " " + random.choice(last_names)
            if random.random() < 0.5:
                name += "-" + random.choice(last_names)

        embed = discord.Embed(title="Random name for Call of Cthulhu",
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

  @commands.hybrid_command(name="randomname", aliases=["rname"])
  async def randomname(self, ctx):
    """
    `[p]randomname` - Generate random name form 1920s era.
    """
    view = RandomNameView(ctx, self)
    ephemeral = False
    if ctx.interaction:
        ephemeral = True
    
    msg = await ctx.send("Select gender for random name:", view=view, ephemeral=ephemeral)
    view.message = msg


async def setup(bot):
  await bot.add_cog(randomname(bot))
