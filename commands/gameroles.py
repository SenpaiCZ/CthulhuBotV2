import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from services.engagement_service import EngagementService

class GamerRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hoist_lock = asyncio.Lock()
        self.help_category = "Admin"

    gamerole_group = app_commands.Group(name="gamerole", description="🎮 Manages automatic gamer roles")

    @gamerole_group.command(name="enable")
    @app_commands.checks.has_permissions(administrator=True)
    async def enable(self, interaction: discord.Interaction):
        await EngagementService.update_gamerole_settings(interaction.guild.id, "enabled", True)
        await interaction.response.send_message("Gamer Roles **ENABLED**.")

    @gamerole_group.command(name="disable")
    @app_commands.checks.has_permissions(administrator=True)
    async def disable(self, interaction: discord.Interaction):
        await EngagementService.update_gamerole_settings(interaction.guild.id, "enabled", False)
        await interaction.response.send_message("Gamer Roles **DISABLED**.")

    @gamerole_group.command(name="status")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        s = await EngagementService.get_gamerole_settings(interaction.guild.id)
        embed = discord.Embed(title="Gamer Roles Settings", color=discord.Color.blue())
        embed.add_field(name="Status", value="Enabled" if s.get("enabled") else "Disabled")
        embed.add_field(name="Color", value=s.get("color", "#0000FF"))
        await interaction.response.send_message(embed=embed)

    @gamerole_group.command(name="ignore")
    @app_commands.checks.has_permissions(administrator=True)
    async def ignore(self, interaction: discord.Interaction, activity_name: str):
        s = await EngagementService.get_gamerole_settings(interaction.guild.id)
        ignored = s.get("ignored_activities", ["Custom Status"])
        if activity_name not in ignored:
            ignored.append(activity_name)
            await EngagementService.update_gamerole_settings(interaction.guild.id, "ignored_activities", ignored)
            await interaction.response.send_message(f"Added **{activity_name}**.")
        else: await interaction.response.send_message("Already ignored.", ephemeral=True)

    def get_role_name(self, settings, activity_name):
        return f"{settings.get('activity_emojis', {}).get(activity_name, '🎮')} {activity_name}"

    async def find_role(self, guild, name, settings):
        target = self.get_role_name(settings, name)
        for n in [target, f"🎮 {name}", name]:
            r = discord.utils.get(guild.roles, name=n)
            if r: return r
        return None

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if not before.guild: return
        s = await EngagementService.get_gamerole_settings(before.guild.id)
        if not s.get("enabled"): return
        ignored = s.get("ignored_activities", ["Custom Status"])
        def get_g(act):
            for a in act:
                if (a.type == discord.ActivityType.playing or (a.type == discord.ActivityType.listening and a.name == "Spotify")) and a.name not in ignored: return a.name
            return None
        old, new = get_g(before.activities), get_g(after.activities)
        if old == new: return
        managed = set(s.get("managed_roles", []))
        changed = False
        if new:
            role = await self.find_role(before.guild, new, s)
            target = self.get_role_name(s, new)
            if not role:
                try: role = await before.guild.create_role(name=target, color=discord.Color(int(s.get("color", "#0000FF")[1:], 16)))
                except: role = None
            if role:
                if str(role.id) not in managed: managed.add(str(role.id)); changed = True
                try: await after.add_roles(role)
                except: pass
        if old:
            role = await self.find_role(before.guild, old, s)
            if role:
                try: await after.remove_roles(role)
                except: pass
                if str(role.id) in managed and len(role.members) == 0:
                    try: await role.delete(); managed.remove(str(role.id)); changed = True
                    except: pass
        if changed: await EngagementService.update_gamerole_settings(before.guild.id, "managed_roles", list(managed))

async def setup(bot): await bot.add_cog(GamerRoles(bot))
