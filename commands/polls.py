import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_polls_data, save_polls_data
from views.poll_view import PollView, PollModal
from services.engagement_service import EngagementService

class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_polls = {}

    async def cog_load(self):
        self.active_polls = await load_polls_data()
        for message_id, data in self.active_polls.items():
            try:
                view = PollView(data['options'], message_id)
                self.bot.add_view(view)
            except Exception as e:
                print(f"Failed to restore poll view {message_id}: {e}")

    async def handle_vote(self, interaction: discord.Interaction, poll_id: str, option_index: int):
        if poll_id not in self.active_polls:
            await interaction.response.send_message("This poll has ended.", ephemeral=True)
            return

        poll = self.active_polls[poll_id]
        user_id = str(interaction.user.id)
        
        # Delegate vote logic to EngagementService
        message, updated_poll = EngagementService.record_poll_vote(poll, user_id, option_index)
        self.active_polls[poll_id] = updated_poll
        await save_polls_data(self.active_polls)

        # Update Embed
        try:
            channel = self.bot.get_channel(int(poll['channel_id']))
            if channel:
                msg = await channel.fetch_message(int(poll_id))
                embed = EngagementService.create_poll_embed(updated_poll)
                await msg.edit(embed=embed)
        except Exception as e:
            print(f"Error updating poll message: {e}")

        await interaction.response.send_message(message, ephemeral=True)

    async def _create_poll_internal(self, interaction: discord.Interaction, question: str, option_list: list):
        embed = discord.Embed(title=f"📊 {question}", description="Setting up poll...", color=discord.Color.blurple())

        if not interaction.response.is_done():
             await interaction.response.send_message(embed=embed)
             msg = await interaction.original_response()
        else:
             msg = await interaction.followup.send(embed=embed, wait=True)

        poll_id = str(msg.id)
        poll_data = EngagementService.initialize_poll_data(interaction.guild.id, interaction.channel.id, interaction.user.id, question, option_list)

        self.active_polls[poll_id] = poll_data
        await save_polls_data(self.active_polls)

        view = PollView(option_list, poll_id)
        final_embed = EngagementService.create_poll_embed(poll_data)
        await msg.edit(embed=final_embed, view=view)

    @app_commands.command(description="📊 Create a poll with multiple options.")
    @app_commands.describe(question="The question to ask (leave blank for Modal)", options="Comma-separated options (leave blank for Modal)")
    async def poll(self, interaction: discord.Interaction, question: str = None, options: str = None):
        if question is None:
             await interaction.response.send_modal(PollModal(self))
             return

        opt_str = options if options else "Yes, No"
        parsed_options = [opt.strip() for opt in opt_str.split(',') if opt.strip()]

        if len(parsed_options) < 2 or len(parsed_options) > 25:
            await interaction.response.send_message("Poll requires 2-25 options.", ephemeral=True)
            return

        await self._create_poll_internal(interaction, question, parsed_options)

async def setup(bot):
    await bot.add_cog(Polls(bot))
