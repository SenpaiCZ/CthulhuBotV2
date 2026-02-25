import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from commands._madness_view import MadnessMenuView, MadnessResultView, get_madness_embed, get_menu_embed, MADNESS_COLOR, get_madness_list_embeds


class madness(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Keeper"

    @app_commands.command(name="madness", description="🤪 Roll for a random madness effect.")
    @app_commands.describe(category="Choose a specific madness category or list options.")
    @app_commands.choices(category=[
        app_commands.Choice(name="Group", value="Group"),
        app_commands.Choice(name="Solo", value="Solo"),
        app_commands.Choice(name="Talent", value="Talent"),
        app_commands.Choice(name="List", value="List")
    ])
    async def madness(self, interaction: discord.Interaction, category: app_commands.Choice[str] = None):
        """
        Roll for a random madness effect or open the menu.
        """
        # If category is Choice object (from app command), get value.
        # But if called directly via callback, we might pass Choice object manually.
        selected_category = category.value if category else None

        if selected_category == 'List':
             embeds = await get_madness_list_embeds()
             # Sending multiple embeds in one message is limited to 10
             await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)
             if len(embeds) > 10:
                 await interaction.followup.send(f"*(...and {len(embeds)-10} more pages)*", ephemeral=True)
             return

        if selected_category is None:
            # Show Menu
            embed = get_menu_embed()
            view = MadnessMenuView(interaction.user)
            await interaction.response.send_message(embed=embed, view=view)
        else:
            # Direct Roll
            if selected_category in ['Group', 'Solo', 'Talent']:
                embed = await get_madness_embed(selected_category)
                view = MadnessResultView(selected_category, interaction.user)
                await interaction.response.send_message(embed=embed, view=view)
            else:
                 await interaction.response.send_message("Invalid category. Use Group, Solo, or Talent.", ephemeral=True)

    @app_commands.command(name="madnessalone", description="😱 Roll for a random Solo madness effect.")
    async def madnessalone(self, interaction: discord.Interaction, option: str = None):
        """
        Shortcut for Solo Madness.
        """
        if option and option.lower() == 'list':
            choice = app_commands.Choice(name="List", value="List")
            await self.madness.callback(self, interaction, category=choice)
        else:
            choice = app_commands.Choice(name="Solo", value="Solo")
            await self.madness.callback(self, interaction, category=choice)


async def setup(bot):
    await bot.add_cog(madness(bot))
