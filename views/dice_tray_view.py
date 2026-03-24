import discord
from discord.ui import View

class DiceTrayView(View):
    def __init__(self, cog, user):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.expression = ""
        self.update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("This dice tray is not for you!", ephemeral=True)
            return False
        return True

    def update_buttons(self):
        # We don't need to rebuild buttons every time, just update embed via callback
        pass

    def get_embed(self):
        desc = "Click buttons to build your dice pool."
        if self.expression:
            desc = f"```\n{self.expression}\n```"

        embed = discord.Embed(title="🎲 Dice Tray", description=desc, color=discord.Color.gold())
        return embed

    async def update_display(self, interaction):
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def add_term(self, interaction, term):
        if self.expression:
            self.expression += f" + {term}"
        else:
            self.expression = term
        await self.update_display(interaction)

    @discord.ui.button(label="D4", style=discord.ButtonStyle.secondary, row=0)
    async def d4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d4")

    @discord.ui.button(label="D6", style=discord.ButtonStyle.secondary, row=0)
    async def d6(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d6")

    @discord.ui.button(label="D8", style=discord.ButtonStyle.secondary, row=0)
    async def d8(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d8")

    @discord.ui.button(label="D10", style=discord.ButtonStyle.secondary, row=0)
    async def d10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d10")

    @discord.ui.button(label="D12", style=discord.ButtonStyle.secondary, row=0)
    async def d12(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d12")

    @discord.ui.button(label="D20", style=discord.ButtonStyle.secondary, row=1)
    async def d20(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d20")

    @discord.ui.button(label="D100", style=discord.ButtonStyle.secondary, row=1)
    async def d100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d100")

    @discord.ui.button(label="+1", style=discord.ButtonStyle.secondary, row=1)
    async def plus1(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += " + 1"
        await self.update_display(interaction)

    @discord.ui.button(label="+5", style=discord.ButtonStyle.secondary, row=1)
    async def plus5(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += " + 5"
        await self.update_display(interaction)

    @discord.ui.button(label="Clear", style=discord.ButtonStyle.danger, row=1)
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression = ""
        await self.update_display(interaction)

    @discord.ui.button(label="ROLL!", style=discord.ButtonStyle.success, row=2, emoji="🎲")
    async def roll_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.expression:
            return await interaction.response.send_message("Add dice first!", ephemeral=True)

        await interaction.response.defer()
        await interaction.delete_original_response()

        # Tray rolls are always private
        await self.cog._perform_roll(interaction, self.expression, 0, 0, True, "Regular")
