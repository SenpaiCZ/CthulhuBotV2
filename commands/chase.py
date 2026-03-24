import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_chase_data, save_chase_data
from services.chase_service import ChaseService
from views.mechanics_views import ChaseSetupView, ChaseDashboardView

class ChaseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = ChaseService()

    async def cog_load(self):
        data = await load_chase_data()
        if data:
            self.service.load_sessions(data)
            for guild_id, guild_sessions in self.service.sessions.items():
                for session in guild_sessions.values():
                    if session.message_id:
                        self.bot.add_view(ChaseDashboardView(self, session), message_id=session.message_id)

    async def initialize_chase(self, interaction: discord.Interaction, environment: str, mode: str):
        session = self.service.create_session(interaction.guild_id, interaction.channel_id, environment, mode)
        embed = self.service.create_dashboard_embed(session)
        view = ChaseDashboardView(self, session)
        msg = await interaction.channel.send(embed=embed, view=view)
        session.message_id = msg.id
        self.bot.add_view(view, message_id=msg.id)
        await save_chase_data(self.service.get_all_sessions_dict())
        
        if not interaction.response.is_done():
            await interaction.response.edit_message(content="✅ Chase started!", embed=None, view=None)
        else:
            await interaction.followup.send("✅ Chase started!", ephemeral=True)

    async def save_and_update(self, session, interaction, update_only=False):
        await save_chase_data(self.service.get_all_sessions_dict())
        embed = self.service.create_dashboard_embed(session)
        view = ChaseDashboardView(self, session)

        if update_only and session.message_id:
            try:
                channel = self.bot.get_channel(int(session.channel_id))
                msg = await channel.fetch_message(session.message_id)
                await msg.edit(embed=embed, view=view)
            except: pass
        elif not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            # If already responded, we try to edit the original message if possible
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except: pass

    @app_commands.command(name="chase", description="🏃 Manage a Chase scene.")
    async def chase_command(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🏃 Chase Setup Wizard", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, view=ChaseSetupView(self, interaction.user), ephemeral=True)

async def setup(bot):
    await bot.add_cog(ChaseCog(bot))
