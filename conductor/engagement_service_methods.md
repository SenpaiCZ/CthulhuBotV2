    @staticmethod
    def record_poll_vote(poll_data: dict, user_id: str, option_index: int) -> tuple[str, dict]:
        if 'votes' not in poll_data:
            poll_data['votes'] = {}
        
        previous_vote = poll_data['votes'].get(user_id)
        if previous_vote == option_index:
            del poll_data['votes'][user_id]
            return "Vote removed.", poll_data
        else:
            poll_data['votes'][user_id] = option_index
            return f"Voted for **{poll_data['options'][option_index]}**.", poll_data

    @staticmethod
    def initialize_poll_data(guild_id, channel_id, creator_id, question, options):
        return {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "creator_id": creator_id,
            "question": question,
            "options": options,
            "votes": {}
        }

    @staticmethod
    def create_poll_embed(poll_data: dict):
        import discord
        question = poll_data.get('question', 'Poll')
        options = poll_data.get('options', [])
        votes = poll_data.get('votes', {})

        results = [0] * len(options)
        total_votes = len(votes)
        for v_index in votes.values():
            if 0 <= v_index < len(results):
                results[v_index] += 1

        embed = discord.Embed(title=f"📊 {question}", color=discord.Color.blurple())
        desc = ""
        for i, option in enumerate(options):
            count = results[i]
            percentage = (count / total_votes * 100) if total_votes > 0 else 0
            bar_length = 10
            filled = int(bar_length * percentage / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            desc += f"**{option}**\n{bar} {count} ({percentage:.1f}%)\n\n"

        embed.description = desc
        embed.set_footer(text=f"Total Votes: {total_votes}")
        return embed
