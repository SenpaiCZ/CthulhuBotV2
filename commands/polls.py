import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from loadnsave import load_polls_data, save_polls_data

class PollButton(discord.ui.Button):
    def __init__(self, label, index, poll_id):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=label,
            custom_id=f"poll:{poll_id}:{index}"
        )
        self.index = index
        self.poll_id = str(poll_id)

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Polls")
        if cog:
            await cog.handle_vote(interaction, self.poll_id, self.index)
        else:
            await interaction.response.send_message("Poll system error.", ephemeral=True)

class PollView(discord.ui.View):
    def __init__(self, options, poll_id):
        super().__init__(timeout=None)
        for i, option in enumerate(options):
            # Truncate label if too long (max 80 chars per button)
            label = option[:80]
            self.add_item(PollButton(label=label, index=i, poll_id=poll_id))

class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_polls = {} # message_id -> poll_data

    async def cog_load(self):
        self.active_polls = await load_polls_data()
        # Re-register views
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

        # Update vote
        # Structure: poll['votes'] = {user_id: option_index}
        if 'votes' not in poll:
            poll['votes'] = {}

        previous_vote = poll['votes'].get(user_id)

        if previous_vote == option_index:
            # Toggle off if clicking same option? Or just allow changing?
            # Let's say clicking same option removes vote
            del poll['votes'][user_id]
            message = "Vote removed."
        else:
            poll['votes'][user_id] = option_index
            message = f"Voted for **{poll['options'][option_index]}**."

        await save_polls_data(self.active_polls)

        # Update Embed
        try:
            channel = self.bot.get_channel(int(poll['channel_id']))
            if channel:
                msg = await channel.fetch_message(int(poll_id))
                embed = self.create_poll_embed(poll)
                await msg.edit(embed=embed)
        except Exception as e:
            print(f"Error updating poll message: {e}")

        await interaction.response.send_message(message, ephemeral=True)

    def create_poll_embed(self, poll_data):
        question = poll_data.get('question', 'Poll')
        options = poll_data.get('options', [])
        votes = poll_data.get('votes', {})
        creator_id = poll_data.get('creator_id')

        # Calculate results
        results = [0] * len(options)
        total_votes = len(votes)

        for v_index in votes.values():
            if 0 <= v_index < len(results):
                results[v_index] += 1

        embed = discord.Embed(title=f"📊 {question}", color=discord.Color.blurple())

        desc = ""
        for i, option in enumerate(options):
            count = results[i]
            percentage = 0
            if total_votes > 0:
                percentage = (count / total_votes) * 100

            bar_length = 10
            filled_length = int(bar_length * percentage / 100)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)

            desc += f"**{option}**\n{bar} {count} ({percentage:.1f}%)\n\n"

        embed.description = desc
        embed.set_footer(text=f"Total Votes: {total_votes}")
        return embed

    @commands.hybrid_command(description="Create a poll with multiple options.")
    @app_commands.describe(question="The question to ask", options="Comma-separated options (e.g. Yes, No, Maybe)")
    async def poll(self, ctx, question: str, *, options: str = "Yes, No"):
        """📊 Create a poll. Usage: !poll "Question" Option1, Option2..."""
        option_list = [opt.strip() for opt in options.split(',') if opt.strip()]

        if len(option_list) < 2:
            await ctx.send("You need at least two options for a poll.", ephemeral=True)
            return
        if len(option_list) > 25: # Discord limit for buttons/selects is 25 per message (5x5 grid technically 25 components max)
            await ctx.send("Too many options (max 25).", ephemeral=True)
            return

        # Create initial embed
        embed = discord.Embed(title=f"📊 {question}", description="Setting up poll...", color=discord.Color.blurple())

        msg = await ctx.send(embed=embed)
        poll_id = str(msg.id)

        # Initialize data
        poll_data = {
            "channel_id": ctx.channel.id,
            "guild_id": ctx.guild.id,
            "creator_id": ctx.author.id,
            "question": question,
            "options": option_list,
            "votes": {}
        }

        self.active_polls[poll_id] = poll_data
        await save_polls_data(self.active_polls)

        # Create view and update message
        view = PollView(option_list, poll_id)
        final_embed = self.create_poll_embed(poll_data)
        await msg.edit(embed=final_embed, view=view)

    # API Method for Dashboard
    async def create_poll_api(self, guild_id, channel_id, question, options):
        guild = self.bot.get_guild(int(guild_id))
        if not guild: return False, "Guild not found"

        channel = guild.get_channel(int(channel_id))
        if not channel: return False, "Channel not found"

        option_list = [opt.strip() for opt in options if opt.strip()]
        if len(option_list) < 2: return False, "Need at least 2 options"

        # Create initial embed
        embed = discord.Embed(title=f"📊 {question}", description="Setting up poll...", color=discord.Color.blurple())

        try:
            msg = await channel.send(embed=embed)
            poll_id = str(msg.id)

            # Initialize data
            poll_data = {
                "channel_id": channel_id,
                "guild_id": guild_id,
                "creator_id": self.bot.user.id, # Bot created
                "question": question,
                "options": option_list,
                "votes": {}
            }

            self.active_polls[poll_id] = poll_data
            await save_polls_data(self.active_polls)

            view = PollView(option_list, poll_id)
            final_embed = self.create_poll_embed(poll_data)
            await msg.edit(embed=final_embed, view=view)

            return True, poll_id
        except Exception as e:
            return False, str(e)

    async def end_poll_api(self, poll_id):
        if str(poll_id) in self.active_polls:
            data = self.active_polls[poll_id]
            del self.active_polls[str(poll_id)]
            await save_polls_data(self.active_polls)

            # Update message to show closed
            try:
                channel = self.bot.get_channel(int(data['channel_id']))
                if channel:
                    msg = await channel.fetch_message(int(poll_id))
                    embed = msg.embeds[0]
                    embed.title = f"🔴 [CLOSED] {embed.title.replace('📊 ', '')}"
                    embed.color = discord.Color.red()
                    await msg.edit(embed=embed, view=None)
            except:
                pass # Message might be deleted

            return True, "Poll ended"
        return False, "Poll not found"

async def setup(bot):
    await bot.add_cog(Polls(bot))
