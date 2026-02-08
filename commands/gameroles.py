import discord
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
    def __init__(self, cog, ctx):
        super().__init__(timeout=60)
        self.cog = cog
        self.ctx = ctx
        self.add_item(ColorSelect())

    async def save_color(self, interaction, color_value, color_name):
        # We delegate saving to the cog to ensure cache is updated
        hex_color = f"#{color_value:06x}"
        await self.cog.update_settings(interaction.guild.id, "color", hex_color)

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

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def gamerole(self, ctx):
        """
        Manages automatic gamer roles.
        """
        await ctx.send_help(ctx.command)

    @gamerole.command()
    async def enable(self, ctx):
        """Enables the gamer role feature."""
        await self.update_settings(ctx.guild.id, "enabled", True)
        await ctx.send("Gamer Roles feature **ENABLED**.")

    @gamerole.command()
    async def disable(self, ctx):
        """Disables the gamer role feature."""
        await self.update_settings(ctx.guild.id, "enabled", False)
        await ctx.send("Gamer Roles feature **DISABLED**.")

    @gamerole.command()
    async def status(self, ctx):
        """Shows the current status and settings."""
        s = await self.get_settings(ctx.guild.id)
        enabled = s.get("enabled", False)
        color = s.get("color", "#0000FF")
        ignored = s.get("ignored_activities", ["Custom Status"])

        embed = discord.Embed(title="Gamer Roles Settings", color=discord.Color.blue())
        embed.add_field(name="Status", value="Enabled" if enabled else "Disabled", inline=False)
        embed.add_field(name="Role Color", value=color, inline=False)
        embed.add_field(name="Ignored Activities", value=", ".join(ignored) if ignored else "None", inline=False)

        await ctx.send(embed=embed)

    @gamerole.command()
    async def ignore(self, ctx, *, activity_name: str):
        """Adds an activity to the ignore list."""
        async with self.cache_lock:
            await self.ensure_cache()
            guild_id_str = str(ctx.guild.id)
            if guild_id_str not in self.settings_cache:
                self.settings_cache[guild_id_str] = {}

            ignored = self.settings_cache[guild_id_str].get("ignored_activities", ["Custom Status"])
            if activity_name not in ignored:
                ignored.append(activity_name)
                self.settings_cache[guild_id_str]["ignored_activities"] = ignored
                await save_gamerole_settings(self.settings_cache)
                await ctx.send(f"Added **{activity_name}** to ignore list.")
            else:
                await ctx.send(f"**{activity_name}** is already in the ignore list.")

    @gamerole.command()
    async def unignore(self, ctx, *, activity_name: str):
        """Removes an activity from the ignore list."""
        async with self.cache_lock:
            await self.ensure_cache()
            guild_id_str = str(ctx.guild.id)
            if guild_id_str not in self.settings_cache:
                 await ctx.send("Settings not initialized.")
                 return

            ignored = self.settings_cache[guild_id_str].get("ignored_activities", ["Custom Status"])
            if activity_name in ignored:
                ignored.remove(activity_name)
                self.settings_cache[guild_id_str]["ignored_activities"] = ignored
                await save_gamerole_settings(self.settings_cache)
                await ctx.send(f"Removed **{activity_name}** from ignore list.")
            else:
                await ctx.send(f"**{activity_name}** is not in the ignore list.")

    @gamerole.command()
    async def color(self, ctx, hex_code: str = None):
        """Sets the role color. Use without arguments for a wizard, or provide a hex code."""
        if hex_code:
            if not hex_code.startswith("#"):
                hex_code = "#" + hex_code
            try:
                # Validate hex
                int(hex_code[1:], 16)
                if len(hex_code) != 7: raise ValueError

                await self.update_settings(ctx.guild.id, "color", hex_code)
                await ctx.send(f"Color set to **{hex_code}**.")
            except ValueError:
                await ctx.send("Invalid hex code format (e.g. #FF0000).")
        else:
            view = GamerRoleColorView(self, ctx)
            await ctx.send("Select a color for Gamer Roles:", view=view)

    async def update_hoisting(self, guild, managed_roles):
        """Updates the hoisting status of managed roles."""
        async with self.hoist_lock:
            # Re-fetch guild to ensure cache is fresh-ish
            if not guild: return

            # Get role objects
            roles = []
            for r_id in managed_roles:
                role = guild.get_role(int(r_id))
                if role:
                    roles.append(role)

            # Sort by member count (descending)
            roles.sort(key=lambda r: len(r.members), reverse=True)

            top_5 = roles[:5]
            others = roles[5:]

            # Apply Hoist
            for role in top_5:
                if not role.hoist:
                    try:
                        await role.edit(hoist=True, reason="Gamer Roles: Top 5 Played")
                    except: pass

            for role in others:
                if role.hoist:
                    try:
                        await role.edit(hoist=False, reason="Gamer Roles: Not Top 5")
                    except: pass

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        # Determine if we should process
        if before.guild is None: return # DMs
        guild = before.guild

        # Access cache directly for speed (reading only first)
        # Note: self.get_settings acquires lock, which is safe but might block slightly.
        # Given single-threaded event loop, race conditions are rare unless we await.
        settings = await self.get_settings(guild.id)
        if not settings.get("enabled", False):
            return

        ignored = settings.get("ignored_activities", ["Custom Status"])
        color_hex = settings.get("color", "#0000FF")
        color_int = int(color_hex[1:], 16)

        managed_roles = set(settings.get("managed_roles", []))

        # Get Activities
        def get_game_name(activities):
            for act in activities:
                if act.type == discord.ActivityType.playing or (act.type == discord.ActivityType.listening and act.name == "Spotify"):
                    if act.name not in ignored:
                        return act.name
            return None

        old_game = get_game_name(before.activities)
        new_game = get_game_name(after.activities)

        if old_game == new_game:
            return # No relevant change

        settings_changed = False

        # Handle New Game (Add Role)
        if new_game:
            role = discord.utils.get(guild.roles, name=new_game)
            if not role:
                try:
                    role = await guild.create_role(
                        name=new_game,
                        color=discord.Color(color_int),
                        hoist=False,
                        mentionable=False,
                        reason="Gamer Role: Auto Assignment"
                    )
                except discord.Forbidden:
                    print(f"Missing permissions to create role in {guild.name}")
                    role = None

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
            role = discord.utils.get(guild.roles, name=old_game)
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

        # Trigger Hoisting Update
        asyncio.create_task(self.update_hoisting(guild, list(managed_roles)))

    # Debug command to simulate events (Since we can't play games in sandbox)
    @gamerole.command()
    async def debug_trigger(self, ctx, member: discord.Member, activity_name: str, action: str):
        """Debug tool to simulate presence update. Action: start, stop"""
        # For debug, we update cache/file manually
        async with self.cache_lock:
            await self.ensure_cache()
            if str(ctx.guild.id) not in self.settings_cache: self.settings_cache[str(ctx.guild.id)] = {}
            managed_roles = set(self.settings_cache[str(ctx.guild.id)].get("managed_roles", []))
            color_hex = self.settings_cache[str(ctx.guild.id)].get("color", "#0000FF")

        color_int = int(color_hex[1:], 16)

        if action == "start":
            role = discord.utils.get(ctx.guild.roles, name=activity_name)
            if not role:
                role = await ctx.guild.create_role(name=activity_name, color=discord.Color(color_int))

            managed_roles.add(str(role.id))
            await member.add_roles(role)
            await ctx.send(f"Simulated START playing {activity_name}")

        elif action == "stop":
            role = discord.utils.get(ctx.guild.roles, name=activity_name)
            if role:
                await member.remove_roles(role)
                if len(role.members) == 0:
                     await role.delete()
                     if str(role.id) in managed_roles:
                         managed_roles.remove(str(role.id))
                await ctx.send(f"Simulated STOP playing {activity_name}")

        # Save back
        async with self.cache_lock:
            self.settings_cache[str(ctx.guild.id)]["managed_roles"] = list(managed_roles)
            await save_gamerole_settings(self.settings_cache)

        await self.update_hoisting(ctx.guild, list(managed_roles))


async def setup(bot):
    await bot.add_cog(GamerRoles(bot))
