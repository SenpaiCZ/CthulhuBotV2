import re
import discord
from discord.ext import commands
from loadnsave import load_reaction_roles, save_reaction_roles

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def add_reaction_role(self, guild_id, message_id, emoji_str, role_id, channel_id=None):
        data = await load_reaction_roles()
        guild_id = str(guild_id)
        message_id = str(message_id)
        role_id = str(role_id)

        if guild_id not in data:
            data[guild_id] = {}

        if message_id not in data[guild_id]:
            data[guild_id][message_id] = {}

        # Handle data structure (Old vs New)
        message_data = data[guild_id][message_id]
        if "roles" in message_data:
             # Already new format
             pass
        elif message_data and not any(k in ["roles", "channel_id"] for k in message_data):
             # Old format, migrate
             old_roles = message_data.copy()
             data[guild_id][message_id] = {"roles": old_roles}
             message_data = data[guild_id][message_id]
        elif not message_data:
             # New entry
             data[guild_id][message_id] = {"roles": {}}
             message_data = data[guild_id][message_id]

        # Save channel_id if provided
        if channel_id:
            message_data["channel_id"] = str(channel_id)

        # Save role
        if "roles" in message_data:
             message_data["roles"][emoji_str] = role_id
        else:
             # Should be unreachable if logic above is correct, but fallback to old behavior just in case?
             # If "roles" is not in message_data, then it must be old format that failed migration?
             # But migration logic covers empty and non-empty.
             # Just assume safe.
             pass

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

        resolved_emoji_str = emoji
        emoji_to_react = emoji

        # Check for custom ID format :12345: or just 12345 (if interpreted as string)
        custom_id_match = re.match(r'^:?(\d+):?$', emoji)
        if custom_id_match:
            emoji_id = int(custom_id_match.group(1))
            custom_emoji = self.bot.get_emoji(emoji_id)
            if custom_emoji:
                resolved_emoji_str = str(custom_emoji)
                emoji_to_react = custom_emoji
            else:
                # Can't find it, maybe try to use it as is if it's a valid ID for another server?
                # But we can't react with it if we don't have it.
                await ctx.send(f"I cannot find the emoji with ID {emoji_id}. Make sure I am in the server where this emoji is from.")
                return

        # We need to ensure the bot can use the emoji to react.
        try:
            await message.add_reaction(emoji_to_react)
        except discord.HTTPException:
            await ctx.send(f"I cannot react with {emoji_to_react}. Please make sure I have permission to use external emojis or that the emoji is valid.")
            return

        await self.add_reaction_role(ctx.guild.id, message.id, str(resolved_emoji_str), role.id, message.channel.id)
        await ctx.send(f"Reaction role setup! Reacting with {emoji_to_react} on that message will give the role **{role.name}**.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        data = await load_reaction_roles()
        guild_id = str(payload.guild_id)
        message_id = str(payload.message_id)
        emoji_str = str(payload.emoji)

        if guild_id in data and message_id in data[guild_id]:
            message_data = data[guild_id][message_id]
            roles = {}
            if "roles" in message_data:
                roles = message_data["roles"]
            else:
                roles = message_data

            if emoji_str in roles:
                role_id = int(roles[emoji_str])
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
            message_data = data[guild_id][message_id]
            roles = {}
            if "roles" in message_data:
                roles = message_data["roles"]
            else:
                roles = message_data

            if emoji_str in roles:
                role_id = int(roles[emoji_str])
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
