import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select
import asyncio
from loadnsave import load_gamerole_settings, save_gamerole_settings

# Color presets
COLOR_PRESETS = {
    "Red": 0xFF0000, "Orange": 0xFFA500, "Yellow": 0xFFFF00, "Green": 0x008000,
    "Blue": 0x0000FF, "Purple": 0x800080, "Pink": 0xFFC0CB, "White": 0xFFFFFF,
    "Grey": 0x808080, "Cyan": 0x00FFFF, "Teal": 0x008080, "Lime": 0x00FF00,
    "Magenta": 0xFF00FF, "Gold": 0xFFD700, "Brown": 0xA52A2A, "Navy": 0x000080,
    "Maroon": 0x800000, "Olive": 0x808000, "Coral": 0xFF7F50, "Indigo": 0x4B0082,
    "Violet": 0xEE82EE, "Turquoise": 0x40E0D0, "Salmon": 0xFA8072, "Sky Blue": 0x87CEEB
}

class ColorSelect(Select):
    def __init__(self):
        options = [discord.SelectOption(label=name, value=name) for name in COLOR_PRESETS.keys()]
        super().__init__(placeholder="Select a color...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        color_name = self.values[0]
        color_value = COLOR_PRESETS[color_name]

        view: GamerRoleColorView = self.view
        await view.save_color(interaction, color_value, color_name)

class GamerRoleColorView(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.add_item(ColorSelect())

    async def save_color(self, interaction, color_value, color_name):
        hex_color = f"#{color_value:06x}"
        await self.cog.update_settings(self.guild_id, "color", hex_color)
        await interaction.response.send_message(f"Gamer Role color set to **{color_name}**.", ephemeral=False)
        self.stop()

class GamerRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hoist_lock = asyncio.Lock()
        self.settings_cache = {}
        self.cache_lock = asyncio.Lock()

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

    # Define Slash Command Group
    gamerole_group = app_commands.Group(name="gamerole", description="Manages automatic gamer roles")

    @gamerole_group.command(name="enable", description="Enables the gamer role feature.")
    @app_commands.checks.has_permissions(administrator=True)
    async def enable(self, interaction: discord.Interaction):
        await self.update_settings(interaction.guild.id, "enabled", True)
        await interaction.response.send_message("Gamer Roles feature **ENABLED**.")

    @gamerole_group.command(name="disable", description="Disables the gamer role feature.")
    @app_commands.checks.has_permissions(administrator=True)
    async def disable(self, interaction: discord.Interaction):
        await self.update_settings(interaction.guild.id, "enabled", False)
        await interaction.response.send_message("Gamer Roles feature **DISABLED**.")

    @gamerole_group.command(name="status", description="Shows the current status and settings.")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        s = await self.get_settings(interaction.guild.id)
        enabled = s.get("enabled", False)
        color = s.get("color", "#0000FF")
        ignored = s.get("ignored_activities", ["Custom Status"])

        embed = discord.Embed(title="Gamer Roles Settings", color=discord.Color.blue())
        embed.add_field(name="Status", value="Enabled" if enabled else "Disabled", inline=False)
        embed.add_field(name="Role Color", value=color, inline=False)
        embed.add_field(name="Ignored Activities", value=", ".join(ignored) if ignored else "None", inline=False)

        # Add Activity Emojis to Embed
        activity_emojis = s.get("activity_emojis", {})
        if activity_emojis:
            emoji_text = "\n".join([f"{k}: {v}" for k, v in activity_emojis.items()])
            embed.add_field(name="Activity Emojis", value=emoji_text, inline=False)

        await interaction.response.send_message(embed=embed)

    @gamerole_group.command(name="ignore", description="Adds an activity to the ignore list.")
    @app_commands.checks.has_permissions(administrator=True)
    async def ignore(self, interaction: discord.Interaction, activity_name: str):
        async with self.cache_lock:
            await self.ensure_cache()
            guild_id_str = str(interaction.guild.id)
            if guild_id_str not in self.settings_cache:
                self.settings_cache[guild_id_str] = {}

            ignored = self.settings_cache[guild_id_str].get("ignored_activities", ["Custom Status"])
            if activity_name not in ignored:
                ignored.append(activity_name)
                self.settings_cache[guild_id_str]["ignored_activities"] = ignored
                await save_gamerole_settings(self.settings_cache)
                await interaction.response.send_message(f"Added **{activity_name}** to ignore list.")
            else:
                await interaction.response.send_message(f"**{activity_name}** is already in the ignore list.")

    @gamerole_group.command(name="unignore", description="Removes an activity from the ignore list.")
    @app_commands.checks.has_permissions(administrator=True)
    async def unignore(self, interaction: discord.Interaction, activity_name: str):
        async with self.cache_lock:
            await self.ensure_cache()
            guild_id_str = str(interaction.guild.id)
            if guild_id_str not in self.settings_cache:
                 await interaction.response.send_message("Settings not initialized.")
                 return

            ignored = self.settings_cache[guild_id_str].get("ignored_activities", ["Custom Status"])
            if activity_name in ignored:
                ignored.remove(activity_name)
                self.settings_cache[guild_id_str]["ignored_activities"] = ignored
                await save_gamerole_settings(self.settings_cache)
                await interaction.response.send_message(f"Removed **{activity_name}** from ignore list.")
            else:
                await interaction.response.send_message(f"**{activity_name}** is not in the ignore list.")

    @gamerole_group.command(name="color", description="Sets the role color.")
    @app_commands.checks.has_permissions(administrator=True)
    async def color(self, interaction: discord.Interaction, hex_code: str = None):
        if hex_code:
            if not hex_code.startswith("#"):
                hex_code = "#" + hex_code
            try:
                int(hex_code[1:], 16)
                if len(hex_code) != 7: raise ValueError
                await self.update_settings(interaction.guild.id, "color", hex_code)
                await interaction.response.send_message(f"Color set to **{hex_code}**.")
            except ValueError:
                await interaction.response.send_message("Invalid hex code format (e.g. #FF0000).", ephemeral=True)
        else:
            view = GamerRoleColorView(self, interaction.guild.id)
            await interaction.response.send_message("Select a color for Gamer Roles:", view=view)

    @gamerole_group.command(name="setemoji", description="Sets an emoji for a specific game activity.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setemoji(self, interaction: discord.Interaction, activity_name: str, emoji: str):
        await self.update_activity_emoji(interaction.guild, activity_name, emoji)
        await interaction.response.send_message(f"Set emoji for **{activity_name}** to {emoji}.")

    @gamerole_group.command(name="removeemoji", description="Removes the custom emoji for a specific game activity.")
    @app_commands.checks.has_permissions(administrator=True)
    async def removeemoji(self, interaction: discord.Interaction, activity_name: str):
        await self.update_activity_emoji(interaction.guild, activity_name, None)
        await interaction.response.send_message(f"Removed emoji for **{activity_name}**.")

    async def update_activity_emoji(self, guild, activity_name, emoji):
        async with self.cache_lock:
            await self.ensure_cache()
            guild_id_str = str(guild.id)
            if guild_id_str not in self.settings_cache:
                self.settings_cache[guild_id_str] = {}

            activity_emojis = self.settings_cache[guild_id_str].get("activity_emojis", {})
            if emoji:
                activity_emojis[activity_name] = emoji
            else:
                if activity_name in activity_emojis:
                    del activity_emojis[activity_name]

            self.settings_cache[guild_id_str]["activity_emojis"] = activity_emojis
            await save_gamerole_settings(self.settings_cache)

        # Trigger Rename Check
        role = await self.find_role_for_game(guild, activity_name)
        if role:
            # We must fetch new settings to get the correct name logic
            settings = await self.get_settings(guild.id)
            expected_name = self.get_role_name_from_settings(settings, activity_name)

            if role.name != expected_name:
                try:
                    await role.edit(name=expected_name, reason="Gamer Role: Emoji Update")
                except discord.Forbidden:
                    pass

    def get_role_name_from_settings(self, settings, activity_name):
        emojis_map = settings.get("activity_emojis", {})
        emoji = emojis_map.get(activity_name, "🎮") # Default to 🎮
        return f"{emoji} {activity_name}"

    async def find_role_for_game(self, guild, activity_name, settings=None):
        if settings is None:
            settings = await self.get_settings(guild.id)

        # 1. Exact current
        target_name = self.get_role_name_from_settings(settings, activity_name)
        role = discord.utils.get(guild.roles, name=target_name)
        if role: return role

        # 2. Default
        default_name = f"🎮 {activity_name}"
        role = discord.utils.get(guild.roles, name=default_name)
        if role: return role

        # 3. Raw
        role = discord.utils.get(guild.roles, name=activity_name)
        if role: return role

        # 4. Managed Suffix (fallback)
        managed_ids = settings.get("managed_roles", [])
        for r_id in managed_ids:
            r = guild.get_role(int(r_id))
            if r and r.name.endswith(f" {activity_name}"):
                return r

        return None

    async def update_hoisting(self, guild, managed_roles):
        """Updates the hoisting status of managed roles."""
        async with self.hoist_lock:
            if not guild: return
            roles = []
            for r_id in managed_roles:
                role = guild.get_role(int(r_id))
                if role:
                    roles.append(role)
            roles.sort(key=lambda r: len(r.members), reverse=True)
            top_5 = roles[:5]
            others = roles[5:]
            for role in top_5:
                if not role.hoist:
                    try: await role.edit(hoist=True, reason="Gamer Roles: Top 5 Played")
                    except: pass
            for role in others:
                if role.hoist:
                    try: await role.edit(hoist=False, reason="Gamer Roles: Not Top 5")
                    except: pass

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if before.guild is None: return
        guild = before.guild

        settings = await self.get_settings(guild.id)
        if not settings.get("enabled", False):
            return

        ignored = settings.get("ignored_activities", ["Custom Status"])
        color_hex = settings.get("color", "#0000FF")
        color_int = int(color_hex[1:], 16)

        managed_roles = set(settings.get("managed_roles", []))

        def get_game_name(activities):
            for act in activities:
                if act.type == discord.ActivityType.playing or (act.type == discord.ActivityType.listening and act.name == "Spotify"):
                    if act.name not in ignored:
                        return act.name
            return None

        old_game = get_game_name(before.activities)
        new_game = get_game_name(after.activities)

        if old_game == new_game:
            return

        settings_changed = False

        # Handle New Game (Add Role)
        if new_game:
            role = await self.find_role_for_game(guild, new_game, settings)
            target_name = self.get_role_name_from_settings(settings, new_game)

            if not role:
                try:
                    role = await guild.create_role(
                        name=target_name,
                        color=discord.Color(color_int),
                        hoist=False,
                        mentionable=False,
                        reason="Gamer Role: Auto Assignment"
                    )
                except discord.Forbidden:
                    print(f"Missing permissions to create role in {guild.name}")
                    role = None
            else:
                # Rename if needed
                if role.name != target_name:
                    try:
                        await role.edit(name=target_name, reason="Gamer Role: Name Normalization")
                    except discord.Forbidden:
                        pass

            if role:
                if str(role.id) not in managed_roles:
                    managed_roles.add(str(role.id))
                    settings_changed = True

                if role not in after.roles:
                    try:
                        await after.add_roles(role, reason="Gamer Role: Started playing")
                    except discord.Forbidden:
                        pass

        # Handle Old Game (Remove Role)
        if old_game:
            role = await self.find_role_for_game(guild, old_game, settings)
            if role and role in after.roles:
                try:
                    await after.remove_roles(role, reason="Gamer Role: Stopped playing")
                except discord.Forbidden:
                    pass

            # Check cleanup
            if role and str(role.id) in managed_roles:
                if len(role.members) == 0:
                    try:
                        await role.delete(reason="Gamer Role: Unused")
                        managed_roles.remove(str(role.id))
                        settings_changed = True
                    except:
                        pass

        if settings_changed:
            async with self.cache_lock:
                await self.ensure_cache()
                if str(guild.id) not in self.settings_cache:
                    self.settings_cache[str(guild.id)] = {}

                self.settings_cache[str(guild.id)]["managed_roles"] = list(managed_roles)
                await save_gamerole_settings(self.settings_cache)

        asyncio.create_task(self.update_hoisting(guild, list(managed_roles)))

    @gamerole_group.command(name="debug_trigger", description="Debug tool to simulate presence update.")
    @app_commands.checks.has_permissions(administrator=True)
    async def debug_trigger(self, interaction: discord.Interaction, member: discord.Member, activity_name: str, action: str):
        settings = await self.get_settings(interaction.guild.id)
        color_hex = settings.get("color", "#0000FF")
        color_int = int(color_hex[1:], 16)

        async with self.cache_lock:
            await self.ensure_cache()
            if str(interaction.guild.id) not in self.settings_cache: self.settings_cache[str(interaction.guild.id)] = {}
            managed_roles = set(self.settings_cache[str(interaction.guild.id)].get("managed_roles", []))

        if action == "start":
            role = await self.find_role_for_game(interaction.guild, activity_name, settings)
            target_name = self.get_role_name_from_settings(settings, activity_name)

            if not role:
                role = await interaction.guild.create_role(name=target_name, color=discord.Color(color_int))
            else:
                if role.name != target_name:
                    await role.edit(name=target_name)

            managed_roles.add(str(role.id))
            await member.add_roles(role)
            await interaction.response.send_message(f"Simulated START playing {activity_name}")

        elif action == "stop":
            role = await self.find_role_for_game(interaction.guild, activity_name, settings)
            if role:
                await member.remove_roles(role)
                if len(role.members) == 0:
                     await role.delete()
                     if str(role.id) in managed_roles:
                         managed_roles.remove(str(role.id))
                await interaction.response.send_message(f"Simulated STOP playing {activity_name}")
            else:
                await interaction.response.send_message(f"Role for {activity_name} not found.")

        # Save back
        async with self.cache_lock:
            self.settings_cache[str(interaction.guild.id)]["managed_roles"] = list(managed_roles)
            await save_gamerole_settings(self.settings_cache)

        await self.update_hoisting(interaction.guild, list(managed_roles))


async def setup(bot):
    await bot.add_cog(GamerRoles(bot))
