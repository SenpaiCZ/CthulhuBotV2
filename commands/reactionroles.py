import discord
from discord.ext import commands
from loadnsave import load_reaction_roles, save_reaction_roles

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def add_reaction_role(self, guild_id, message_id, emoji_str, role_id):
        data = await load_reaction_roles()
        guild_id = str(guild_id)
        message_id = str(message_id)
        role_id = str(role_id)

        if guild_id not in data:
            data[guild_id] = {}

        if message_id not in data[guild_id]:
            data[guild_id][message_id] = {}

        data[guild_id][message_id][emoji_str] = role_id
        await save_reaction_roles(data)

    @commands.command(aliases=['rr', 'reactionrole'])
    @commands.has_permissions(administrator=True)
    async def reaction_role(self, ctx, message_id_or_link: str, role: discord.Role, emoji: str):
        """
        🎭 Setup a reaction role.
        Usage: !reactionrole <message_id|link> <@role|role_id> <emoji>
        """
        # Determine Message
        message = None
        if message_id_or_link.isdigit():
            try:
                message = await ctx.channel.fetch_message(int(message_id_or_link))
            except discord.NotFound:
                await ctx.send("Message not found in this channel.")
                return
        else:
            try:
                # Try to convert message link
                parts = message_id_or_link.split('/')
                msg_id = int(parts[-1])
                chan_id = int(parts[-2])
                channel = ctx.guild.get_channel(chan_id)
                if channel:
                    message = await channel.fetch_message(msg_id)
            except Exception:
                pass

        if not message:
            await ctx.send("Could not find the message. Please provide a valid Message ID (in this channel) or a Message Link.")
            return

        # Normalize emoji
        # If the user passed a custom emoji string like <:name:id>, discord.py might have already parsed it?
        # No, emoji is str here.

        # If the user reacts to the bot message with the emoji, we can capture it?
        # But here we are passing it as an argument.

        # We need to ensure the bot can use the emoji to react.
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await ctx.send(f"I cannot react with {emoji}. Please make sure I have permission to use external emojis or that the emoji is valid.")
            return

        await self.add_reaction_role(ctx.guild.id, message.id, str(emoji), role.id)
        await ctx.send(f"Reaction role setup! Reacting with {emoji} on that message will give the role **{role.name}**.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        data = await load_reaction_roles()
        guild_id = str(payload.guild_id)
        message_id = str(payload.message_id)
        emoji_str = str(payload.emoji)

        if guild_id in data and message_id in data[guild_id]:
            if emoji_str in data[guild_id][message_id]:
                role_id = int(data[guild_id][message_id][emoji_str])
                guild = self.bot.get_guild(payload.guild_id)
                if guild:
                    role = guild.get_role(role_id)
                    member = guild.get_member(payload.user_id)
                    if role and member:
                        try:
                            await member.add_roles(role)
                        except discord.Forbidden:
                            # Bot doesn't have permission to add role
                            pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        data = await load_reaction_roles()
        guild_id = str(payload.guild_id)
        message_id = str(payload.message_id)
        emoji_str = str(payload.emoji)

        if guild_id in data and message_id in data[guild_id]:
            if emoji_str in data[guild_id][message_id]:
                role_id = int(data[guild_id][message_id][emoji_str])
                guild = self.bot.get_guild(payload.guild_id)
                if guild:
                    role = guild.get_role(role_id)
                    member = guild.get_member(payload.user_id)
                    if role and member:
                        try:
                            await member.remove_roles(role)
                        except discord.Forbidden:
                            pass

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
