import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_enroll_settings
from views.utility_views import EnrollView

class Enroll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Admin"

    @app_commands.command(name="enroll", description="📝 Start the new user enrollment process.")
    async def enroll(self, interaction: discord.Interaction):
        settings = await load_enroll_settings()
        guild_id = str(interaction.guild_id)
        guild_config = settings.get(guild_id, {})
        if not guild_config.get('enabled', False):
            msg = "Enrollment is not enabled on this server."
            return await (interaction.followup.send(msg, ephemeral=True) if interaction.response.is_done() else interaction.response.send_message(msg, ephemeral=True))
        pages = guild_config.get('pages', [])
        if not pages:
            msg = "No enrollment pages configured."
            return await (interaction.followup.send(msg, ephemeral=True) if interaction.response.is_done() else interaction.response.send_message(msg, ephemeral=True))
        view = EnrollView(pages, guild_config.get('final_message', "Enrollment complete!"))
        embed = discord.Embed(title=f"Enrollment: {pages[0].get('title', 'Start')}", description=pages[0].get('description', ''), color=discord.Color.blue())
        embed.set_footer(text=f"Page 1/{len(pages)}")
        await (interaction.followup.send(embed=embed, view=view, ephemeral=True) if interaction.response.is_done() else interaction.response.send_message(embed=embed, view=view, ephemeral=True))

async def setup(bot):
    await bot.add_cog(Enroll(bot))
