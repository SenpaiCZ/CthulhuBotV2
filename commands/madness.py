import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from commands._madness_view import MadnessMenuView, MadnessResultView, get_madness_embed, get_menu_embed, MADNESS_COLOR, get_madness_list_embeds


class madness(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="madness", description="Roll for a random madness effect.")
    @app_commands.describe(category="Choose a specific madness category or list options.")
    @app_commands.choices(category=[
        app_commands.Choice(name="Group", value="Group"),
        app_commands.Choice(name="Solo", value="Solo"),
        app_commands.Choice(name="Talent", value="Talent"),
        app_commands.Choice(name="List", value="List")
    ])
    async def madness(self, ctx: commands.Context, category: str = None):
        """
        Roll for a random madness effect or open the menu.
        """
        # If invoked via text command with "list" argument, map it
        if category:
             category = category.lower()
             if category == 'list':
                 category = 'List'
             elif category == 'group':
                 category = 'Group'
             elif category == 'solo':
                 category = 'Solo'
             elif category == 'talent':
                 category = 'Talent'

        if category == 'List':
             ephemeral = ctx.interaction is not None
             embeds = await get_madness_list_embeds()

             if ephemeral:
                 # Sending multiple embeds in one message is limited to 10
                 await ctx.send(embeds=embeds[:10], ephemeral=True)
             else:
                 # For text commands, send up to 10 embeds.
                 # Discord allows 10 embeds per message.
                 await ctx.send(embeds=embeds[:10])
                 if len(embeds) > 10:
                     await ctx.send(f"*(...and {len(embeds)-10} more pages. Use /madness list to see them all)*")
             return

        if category is None:
            # Show Menu
            embed = get_menu_embed()
            view = MadnessMenuView(ctx.author)
            await ctx.send(embed=embed, view=view)
        else:
            # Direct Roll
            # category is 'Group', 'Solo', 'Talent' (normalized above)

            if category in ['Group', 'Solo', 'Talent']:
                embed = await get_madness_embed(category)
                view = MadnessResultView(category, ctx.author)
                await ctx.send(embed=embed, view=view)
            else:
                 await ctx.send("Invalid category. Use Group, Solo, or Talent.", ephemeral=True)

    @commands.hybrid_command(name="madnessalone", description="Roll for a random Solo madness effect.")
    async def madnessalone(self, ctx: commands.Context, option: Optional[str] = None):
        """
        Shortcut for Solo Madness.
        """
        if option and option.lower() == 'list':
            await self.madness(ctx, category='List')
        else:
            await self.madness(ctx, category='Solo')


async def setup(bot):
    await bot.add_cog(madness(bot))
