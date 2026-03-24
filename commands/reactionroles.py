import re
import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_reaction_roles
from services.admin_service import AdminService

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reactionrole", description="🎭 [DEPRECATED] Setup a reaction role. Use /rolepanel instead.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reaction_role(self, interaction: discord.Interaction, message_link: str, role: discord.Role, emoji: str):
        await interaction.response.send_message("⚠️ Reaction Roles are deprecated. Use `/rolepanel` instead.", ephemeral=True)
        message = None
        if message_link.isdigit():
            try: message = await interaction.channel.fetch_message(int(message_link))
            except: return await interaction.followup.send("Message not found.")
        else:
            try:
                parts = message_link.split('/')
                chan = interaction.guild.get_channel(int(parts[-2]))
                if chan: message = await chan.fetch_message(int(parts[-1]))
            except: pass
        if not message: return await interaction.followup.send("Could not find message.")
        
        resolved_emoji = emoji
        custom_id_match = re.match(r'^<a?:.+:(\d+)>$', emoji) or re.match(r'^:?(\d+):?$', emoji)
        if custom_id_match:
            custom_emoji = self.bot.get_emoji(int(custom_id_match.group(1)))
            if custom_emoji: resolved_emoji = custom_emoji
            else: return await interaction.followup.send("Custom emoji not found.")
        
        try: await message.add_reaction(resolved_emoji)
        except: return await interaction.followup.send("Cannot react with that emoji.")
        
        await AdminService.add_reaction_role(interaction.guild_id, message.id, str(resolved_emoji), role.id, message.channel.id)
        await interaction.followup.send(f"Reaction role setup for **{role.name}**!", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id: return
        data = await load_reaction_roles()
        sid, mid, estr = str(payload.guild_id), str(payload.message_id), str(payload.emoji)
        if sid in data and mid in data[sid]:
            roles = data[sid][mid].get("roles", data[sid][mid])
            if estr in roles:
                guild = self.bot.get_guild(payload.guild_id)
                role = guild.get_role(int(roles[estr])) if guild else None
                member = guild.get_member(payload.user_id) if guild else None
                if role and member:
                    try: await member.add_roles(role)
                    except: pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.bot.user.id: return
        data = await load_reaction_roles()
        sid, mid, estr = str(payload.guild_id), str(payload.message_id), str(payload.emoji)
        if sid in data and mid in data[sid]:
            roles = data[sid][mid].get("roles", data[sid][mid])
            if estr in roles:
                guild = self.bot.get_guild(payload.guild_id)
                role = guild.get_role(int(roles[estr])) if guild else None
                member = guild.get_member(payload.user_id) if guild else None
                if role and member:
                    try: await member.remove_roles(role)
                    except: pass

async def setup(bot): await bot.add_cog(ReactionRoles(bot))
