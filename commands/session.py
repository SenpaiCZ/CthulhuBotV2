import discord
from discord.ext import commands
from discord import app_commands
from models.database import SessionLocal
from services.session_service import SessionService

class Session(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="session", description="📅 Manage your gaming session.")
    @app_commands.describe(action="The session action to perform")
    @app_commands.choices(action=[
        app_commands.Choice(name="Start Session", value="start"),
        app_commands.Choice(name="View Recent Logs", value="logs")
    ])
    async def session(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
        """Delegates session tracking and logging to SessionService."""
        db = SessionLocal()
        try:
            guild_id = str(interaction.guild_id)
            
            if action.value == "start":
                SessionService.start_session(db, guild_id)
                embed = discord.Embed(
                    title="🎬 Session Started",
                    description="A new gaming session has been logged and is now active.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
                
            elif action.value == "logs":
                logs = SessionService.get_recent_logs(db, guild_id)
                if not logs:
                    await interaction.response.send_message("No session logs found for this server.", ephemeral=True)
                    return
                
                log_text = "\n".join([f"[{log.timestamp.strftime('%Y-%m-%d %H:%M')}] **{log.event_type}**: {log.description}" for log in logs])
                embed = discord.Embed(
                    title="📜 Recent Session Logs",
                    description=log_text[:4000],
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            db.close()

async def setup(bot):
    await bot.add_cog(Session(bot))
