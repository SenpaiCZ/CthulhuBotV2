import discord
from discord.ext import commands
from loadnsave import load_karma_settings, save_karma_settings, load_karma_stats, save_karma_stats

class Karma(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_guild_settings(self, guild_id):
        settings = await load_karma_settings()
        return settings.get(str(guild_id))

    async def update_karma(self, guild_id, user_id, amount):
        stats = await load_karma_stats()
        guild_id = str(guild_id)
        user_id = str(user_id)

        if guild_id not in stats:
            stats[guild_id] = {}

        current_karma = stats[guild_id].get(user_id, 0)
        stats[guild_id][user_id] = current_karma + amount
        await save_karma_stats(stats)
        return stats[guild_id][user_id]

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setupkarma(self, ctx, channel: discord.TextChannel, upvote_emoji: str, downvote_emoji: str):
        """
        Setup the Karma system for this server.
        Usage: !setupkarma #channel <upvote_emoji> <downvote_emoji>
        """
        settings = await load_karma_settings()
        guild_id = str(ctx.guild.id)

        settings[guild_id] = {
            "channel_id": channel.id,
            "upvote_emoji": upvote_emoji,
            "downvote_emoji": downvote_emoji
        }

        await save_karma_settings(settings)
        await ctx.send(f"Karma system setup!\nChannel: {channel.mention}\nUpvote: {upvote_emoji}\nDownvote: {downvote_emoji}")

    @commands.command(aliases=['k'])
    async def karma(self, ctx, user: discord.User = None):
        """
        Check karma for yourself or another user.
        Usage: !karma [@user]
        """
        if user is None:
            user = ctx.author

        stats = await load_karma_stats()
        guild_id = str(ctx.guild.id)
        user_id = str(user.id)

        karma_score = stats.get(guild_id, {}).get(user_id, 0)

        await ctx.send(f"{user.display_name} has {karma_score} karma.")

    @commands.command(aliases=['karmatop', 'top'])
    async def leaderboard(self, ctx, page: int = 1):
        """
        Show the Karma leaderboard.
        Usage: !leaderboard [page]
        """
        if page < 1:
            page = 1

        stats = await load_karma_stats()
        guild_id = str(ctx.guild.id)

        if guild_id not in stats or not stats[guild_id]:
            await ctx.send("No karma stats found for this server.")
            return

        # Sort users by karma (descending)
        sorted_users = sorted(stats[guild_id].items(), key=lambda item: item[1], reverse=True)

        items_per_page = 10
        total_pages = (len(sorted_users) - 1) // items_per_page + 1

        if page > total_pages:
            await ctx.send(f"Page {page} does not exist. Total pages: {total_pages}")
            return

        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page

        current_page_users = sorted_users[start_index:end_index]

        embed = discord.Embed(title=f"Karma Leaderboard - Page {page}/{total_pages}", color=discord.Color.gold())

        description = ""
        for i, (user_id, score) in enumerate(current_page_users, start=start_index + 1):
            user = ctx.guild.get_member(int(user_id))
            user_name = user.display_name if user else f"Unknown User ({user_id})"
            description += f"**{i}.** {user_name}: **{score}**\n"

        embed.description = description
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        settings = await self.get_guild_settings(payload.guild_id)
        if not settings:
            return

        if payload.channel_id != settings.get("channel_id"):
            return

        # Fetch the message to check the author
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        # Prevent self-voting
        if message.author.id == payload.user_id:
            # We can optionally remove the reaction here to enforce "no self-voting"
            try:
                user = guild.get_member(payload.user_id)
                if user:
                    await message.remove_reaction(payload.emoji, user)
            except discord.Forbidden:
                pass # Can't remove reaction, oh well
            return

        emoji_str = str(payload.emoji)

        change = 0
        if emoji_str == settings.get("upvote_emoji"):
            change = 1
        elif emoji_str == settings.get("downvote_emoji"):
            change = -1

        if change != 0:
            await self.update_karma(payload.guild_id, message.author.id, change)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        settings = await self.get_guild_settings(payload.guild_id)
        if not settings:
            return

        if payload.channel_id != settings.get("channel_id"):
            return

        # Fetch the message to check the author (need to ensure we are not reverting self-votes if they somehow got through)
        # But wait, if self-vote was blocked in on_add, it won't be here.
        # If it wasn't blocked (e.g. bot was down), we might revert a vote that never counted.
        # But assuming the bot removes self-votes instantly, this shouldn't be a huge issue.
        # Ideally we should verify if the user is the author again.

        guild = self.bot.get_guild(payload.guild_id)
        if not guild: return
        channel = guild.get_channel(payload.channel_id)
        if not channel: return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        if message.author.id == payload.user_id:
            return

        emoji_str = str(payload.emoji)

        change = 0
        if emoji_str == settings.get("upvote_emoji"):
            change = -1 # Revert upvote
        elif emoji_str == settings.get("downvote_emoji"):
            change = 1 # Revert downvote

        if change != 0:
            await self.update_karma(payload.guild_id, message.author.id, change)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:
            return

        if not message.guild:
            return

        settings = await self.get_guild_settings(message.guild.id)
        if not settings:
            return

        if message.channel.id == settings.get("channel_id"):
            try:
                await message.add_reaction(settings.get("upvote_emoji"))
                await message.add_reaction(settings.get("downvote_emoji"))
            except discord.HTTPException:
                # Emojis might be invalid or bot lacks permissions
                pass

async def setup(bot):
    await bot.add_cog(Karma(bot))
