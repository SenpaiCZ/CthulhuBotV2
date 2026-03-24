import discord
from discord.ext import commands
from discord import app_commands
from services.codex_service import CodexService
from views.mechanics_views import GenderSelectView
from emojis import get_stat_emoji

class RandomNPC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Keeper"

    async def create_npc_embed(self, gender: str, region: str):
        name = await CodexService.generate_npc_name(gender, region)
        stats = CodexService.generate_npc_stats()

        embed = discord.Embed(
            title=f"👤 {name}",
            description=f"**Gender:** {gender.capitalize()}\n**Region:** {region.capitalize()}",
            color=discord.Color.gold()
        )

        phys_text = (
            f"{get_stat_emoji('STR')} **STR:** {stats['STR']}\n"
            f"{get_stat_emoji('CON')} **CON:** {stats['CON']}\n"
            f"{get_stat_emoji('SIZ')} **SIZ:** {stats['SIZ']}\n"
            f"{get_stat_emoji('DEX')} **DEX:** {stats['DEX']}\n"
            f"{get_stat_emoji('HP')} **HP:** {stats['HP']}\n"
            f"{get_stat_emoji('Move')} **Move:** {stats['Move']}\n"
            f"{get_stat_emoji('Build')} **Build:** {stats['Build']}\n"
            f"{get_stat_emoji('DB')} **DB:** {stats['DB']}"
        )
        embed.add_field(name="Physical", value=phys_text, inline=True)

        ment_text = (
            f"{get_stat_emoji('INT')} **INT:** {stats['INT']}\n"
            f"{get_stat_emoji('POW')} **POW:** {stats['POW']}\n"
            f"{get_stat_emoji('EDU')} **EDU:** {stats['EDU']}\n"
            f"{get_stat_emoji('APP')} **APP:** {stats['APP']}\n"
            f"{get_stat_emoji('SAN')} **SAN:** {stats['SAN']}\n"
            f"{get_stat_emoji('MP')} **MP:** {stats['MP']}\n"
            f"{get_stat_emoji('LUCK')} **LUCK:** {stats['LUCK']}"
        )
        embed.add_field(name="Mental", value=ment_text, inline=True)
        embed.set_footer(text="Call of Cthulhu NPC Generator")
        return embed

    async def ask_region(self, interaction: discord.Interaction, gender: str):
        from views.mechanics_views import RegionSelectView
        view = RegionSelectView(self, gender)
        embed = discord.Embed(
            title="NPC Generator - Region",
            description=f"Selected Gender: **{gender.capitalize()}**\nNow select a region for the name.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def generate_and_send(self, interaction: discord.Interaction, gender: str, region: str):
        from views.mechanics_views import NPCActionView
        embed = await self.create_npc_embed(gender, region)
        view = NPCActionView(self, interaction, gender, region, embed)
        await interaction.response.edit_message(embed=embed, view=view)

    @app_commands.command(name="randomnpc", description="👤 Generate an NPC with random name and stats.")
    async def randomnpc(self, interaction: discord.Interaction):
        view = GenderSelectView(self, interaction)
        embed = discord.Embed(
            title="NPC Generator",
            description="Select a gender to generate an NPC.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(RandomNPC(bot))
