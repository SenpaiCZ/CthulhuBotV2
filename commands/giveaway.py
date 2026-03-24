import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone
from loadnsave import load_giveaway_data
from services.engagement_service import EngagementService
from views.engagement_views import GiveawayView, GiveawayCreationModal

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = EngagementService(bot)

    async def cog_load(self):
        self.bot.add_view(GiveawayView(self.service))
        self.check_giveaways.start()

    async def cog_unload(self):
        self.check_giveaways.cancel()

    @tasks.loop(seconds=60)
    async def check_giveaways(self):
        try:
            data = await load_giveaway_data()
            now = datetime.now(timezone.utc).timestamp()
            for guild_id, giveaways in data.items():
                for msg_id, gw in giveaways.items():
                    if gw["status"] == "active" and isinstance(gw.get("end_time"), (int, float)) and now >= gw["end_time"]:
                        await self.service.end_giveaway(guild_id, msg_id)
        except Exception as e: print(f"Error in giveaway loop: {e}")

    @check_giveaways.before_loop
    async def before_check_giveaways(self): await self.bot.wait_until_ready()

    giveaway_group = app_commands.Group(name="giveaway", description="🎉 Manage Giveaways.")

    @giveaway_group.command(name="create", description="➕ Create a new giveaway.")
    async def create_giveaway(self, interaction: discord.Interaction):
        await interaction.response.send_modal(GiveawayCreationModal(self.service, self))

    @giveaway_group.command(name="end", description="🛑 End a giveaway and pick a winner.")
    @app_commands.describe(message_link_or_id="The message link or ID of the giveaway")
    async def end_giveaway(self, interaction: discord.Interaction, message_link_or_id: str):
        msg_id = message_link_or_id.split("/")[-1] if "discord.com/channels/" in message_link_or_id else message_link_or_id
        success, msg = await self.service.end_giveaway(str(interaction.guild.id), msg_id, requester=interaction.user)
        await interaction.response.send_message(msg, ephemeral=not success)

    @giveaway_group.command(name="reroll", description="🔄 Reroll a winner for an ended giveaway.")
    @app_commands.describe(message_link_or_id="The message link or ID of the giveaway")
    async def reroll_giveaway(self, interaction: discord.Interaction, message_link_or_id: str):
        msg_id = message_link_or_id.split("/")[-1] if "discord.com/channels/" in message_link_or_id else message_link_or_id
        success, msg = await self.service.reroll_giveaway(str(interaction.guild.id), msg_id, requester=interaction.user)
        await interaction.response.send_message(msg, ephemeral=not success)

    @giveaway_group.command(name="list", description="📃 List all active giveaways.")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_giveaways(self, interaction: discord.Interaction):
        data = await load_giveaway_data()
        guild_id = str(interaction.guild.id)
        if guild_id not in data or not any(gw["status"] == "active" for gw in data[guild_id].values()):
            return await interaction.response.send_message("No active giveaways.", ephemeral=True)
        embed = discord.Embed(title="Active Giveaways", color=discord.Color.blue())
        for msg_id, gw in data[guild_id].items():
            if gw["status"] == "active":
                embed.add_field(name=gw["title"], value=f"[Link](https://discord.com/channels/{guild_id}/{gw['channel_id']}/{msg_id}) - {len(gw['participants'])} entries", inline=False)
        await interaction.response.send_message(embed=embed)

    @end_giveaway.autocomplete('message_link_or_id')
    async def end_autocomplete(self, interaction: discord.Interaction, current: str):
        data = await load_giveaway_data()
        g_id = str(interaction.guild_id)
        return [app_commands.Choice(name=f"{gw['title']} ({m_id})", value=m_id) for m_id, gw in data.get(g_id, {}).items() if gw["status"] == "active" and current.lower() in gw['title'].lower()][:25]

    @reroll_giveaway.autocomplete('message_link_or_id')
    async def reroll_autocomplete(self, interaction: discord.Interaction, current: str):
        data = await load_giveaway_data()
        g_id = str(interaction.guild_id)
        return [app_commands.Choice(name=f"{gw['title']} ({m_id})", value=m_id) for m_id, gw in data.get(g_id, {}).items() if gw["status"] == "ended" and current.lower() in gw['title'].lower()][:25]

async def setup(bot): await bot.add_cog(Giveaway(bot))
