import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from loadnsave import load_gamerole_settings, save_gamerole_settings
from views.utility_views import GamerRoleColorView

class GamerRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hoist_lock = asyncio.Lock()
        self.settings_cache = {}
        self.cache_lock = asyncio.Lock()
        self.help_category = "Admin"

    async def ensure_cache(self):
        if not self.settings_cache:
            self.settings_cache = await load_gamerole_settings()

    async def get_settings(self, guild_id):
        async with self.cache_lock:
            await self.ensure_cache()
            return self.settings_cache.get(str(guild_id), {}).copy()

    async def update_settings(self, guild_id, key, value):
        async with self.cache_lock:
            await self.ensure_cache()
            guild_id_str = str(guild_id)
            if guild_id_str not in self.settings_cache:
                self.settings_cache[guild_id_str] = {}
            self.settings_cache[guild_id_str][key] = value
            await save_gamerole_settings(self.settings_cache)

    @commands.Cog.listener()
    async def on_ready(self):
        async with self.cache_lock:
            self.settings_cache = await load_gamerole_settings()

    gamerole_group = app_commands.Group(name="gamerole", description="🎮 Manages automatic gamer roles")

    @gamerole_group.command(name="enable", description="✅ Enables the gamer role feature.")
    @app_commands.checks.has_permissions(administrator=True)
    async def enable(self, interaction: discord.Interaction):
        await self.update_settings(interaction.guild.id, "enabled", True)
        await interaction.response.send_message("Gamer Roles feature **ENABLED**.")

    @gamerole_group.command(name="disable", description="🛑 Disables the gamer role feature.")
    @app_commands.checks.has_permissions(administrator=True)
    async def disable(self, interaction: discord.Interaction):
        await self.update_settings(interaction.guild.id, "enabled", False)
        await interaction.response.send_message("Gamer Roles feature **DISABLED**.")

    @gamerole_group.command(name="status", description="ℹ️ Shows the current status and settings.")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        s = await self.get_settings(interaction.guild.id)
        embed = discord.Embed(title="Gamer Roles Settings", color=discord.Color.blue())
        embed.add_field(name="Status", value="Enabled" if s.get("enabled") else "Disabled", inline=False)
        embed.add_field(name="Role Color", value=s.get("color", "#0000FF"), inline=False)
        ignored = s.get("ignored_activities", ["Custom Status"])
        embed.add_field(name="Ignored Activities", value=", ".join(ignored) if ignored else "None", inline=False)
        activity_emojis = s.get("activity_emojis", {})
        if activity_emojis:
            embed.add_field(name="Activity Emojis", value="\n".join([f"{k}: {v}" for k, v in activity_emojis.items()]), inline=False)
        await interaction.response.send_message(embed=embed)

    @gamerole_group.command(name="ignore", description="🚫 Adds an activity to the ignore list.")
    @app_commands.checks.has_permissions(administrator=True)
    async def ignore(self, interaction: discord.Interaction, activity_name: str):
        async with self.cache_lock:
            await self.ensure_cache()
            guild_id_str = str(interaction.guild.id)
            ignored = self.settings_cache.setdefault(guild_id_str, {}).get("ignored_activities", ["Custom Status"])
            if activity_name not in ignored:
                ignored.append(activity_name)
                self.settings_cache[guild_id_str]["ignored_activities"] = ignored
                await save_gamerole_settings(self.settings_cache)
                await interaction.response.send_message(f"Added **{activity_name}** to ignore list.")
            else:
                await interaction.response.send_message(f"**{activity_name}** is already in the ignore list.")

    @gamerole_group.command(name="color", description="🎨 Sets the role color.")
    @app_commands.checks.has_permissions(administrator=True)
    async def color(self, interaction: discord.Interaction, hex_code: str = None):
        if hex_code:
            if not hex_code.startswith("#"): hex_code = "#" + hex_code
            try:
                int(hex_code[1:], 16)
                if len(hex_code) != 7: raise ValueError
                await self.update_settings(interaction.guild.id, "color", hex_code)
                await interaction.response.send_message(f"Color set to **{hex_code}**.")
            except ValueError:
                await interaction.response.send_message("Invalid hex code format (e.g. #FF0000).", ephemeral=True)
        else:
            await interaction.response.send_message("Select a color for Gamer Roles:", view=GamerRoleColorView(self, interaction.guild.id))

    async def update_activity_emoji(self, guild, activity_name, emoji):
        async with self.cache_lock:
            await self.ensure_cache()
            emojis = self.settings_cache.setdefault(str(guild.id), {}).get("activity_emojis", {})
            if emoji: emojis[activity_name] = emoji
            elif activity_name in emojis: del emojis[activity_name]
            self.settings_cache[str(guild.id)]["activity_emojis"] = emojis
            await save_gamerole_settings(self.settings_cache)
        role = await self.find_role_for_game(guild, activity_name)
        if role:
            settings = await self.get_settings(guild.id)
            expected_name = self.get_role_name_from_settings(settings, activity_name)
            if role.name != expected_name:
                try: await role.edit(name=expected_name, reason="Gamer Role: Emoji Update")
                except: pass

    def get_role_name_from_settings(self, settings, activity_name):
        return f"{settings.get('activity_emojis', {}).get(activity_name, '🎮')} {activity_name}"

    async def find_role_for_game(self, guild, activity_name, settings=None):
        if settings is None: settings = await self.get_settings(guild.id)
        target_name = self.get_role_name_from_settings(settings, activity_name)
        for name in [target_name, f"🎮 {activity_name}", activity_name]:
            role = discord.utils.get(guild.roles, name=name)
            if role: return role
        for r_id in settings.get("managed_roles", []):
            r = guild.get_role(int(r_id))
            if r and r.name.endswith(f" {activity_name}"): return r
        return None

    async def update_hoisting(self, guild, managed_roles):
        async with self.hoist_lock:
            roles = [r for r in [guild.get_role(int(rid)) for rid in managed_roles] if r]
            roles.sort(key=lambda r: len(r.members), reverse=True)
            for i, role in enumerate(roles):
                target_hoist = i < 5
                if role.hoist != target_hoist:
                    try: await role.edit(hoist=target_hoist)
                    except: pass

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if not before.guild or before.guild.id is None: return
        settings = await self.get_settings(before.guild.id)
        if not settings.get("enabled"): return
        ignored = settings.get("ignored_activities", ["Custom Status"])
        def get_game(activities):
            for a in activities:
                if (a.type == discord.ActivityType.playing or (a.type == discord.ActivityType.listening and a.name == "Spotify")) and a.name not in ignored: return a.name
            return None
        old_g, new_g = get_game(before.activities), get_game(after.activities)
        if old_g == new_g: return
        managed = set(settings.get("managed_roles", []))
        changed = False
        if new_g:
            role = await self.find_role_for_game(before.guild, new_g, settings)
            target = self.get_role_name_from_settings(settings, new_g)
            if not role:
                try: role = await before.guild.create_role(name=target, color=discord.Color(int(settings.get("color", "#0000FF")[1:], 16)))
                except: role = None
            elif role.name != target:
                try: await role.edit(name=target)
                except: pass
            if role:
                if str(role.id) not in managed:
                    managed.add(str(role.id)); changed = True
                if role not in after.roles:
                    try: await after.add_roles(role)
                    except: pass
        if old_g:
            role = await self.find_role_for_game(before.guild, old_g, settings)
            if role and role in after.roles:
                try: await after.remove_roles(role)
                except: pass
            if role and str(role.id) in managed and len(role.members) == 0:
                try: await role.delete(); managed.remove(str(role.id)); changed = True
                except: pass
        if changed:
            async with self.cache_lock:
                await self.ensure_cache()
                self.settings_cache.setdefault(str(before.guild.id), {})["managed_roles"] = list(managed)
                await save_gamerole_settings(self.settings_cache)
        asyncio.create_task(self.update_hoisting(before.guild, list(managed)))

async def setup(bot):
    await bot.add_cog(GamerRoles(bot))
