import discord
from discord.ext import commands
from discord.ui import View, Select
import asyncio
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

        # Trigger role update
        guild = self.bot.get_guild(int(guild_id))
        if guild:
            member = guild.get_member(int(user_id))
            if member:
                settings = await self.get_guild_settings(guild_id)
                if settings:
                    await self.update_karma_roles(member, stats[guild_id][user_id], settings)

        return stats[guild_id][user_id]

    async def update_karma_roles(self, member, karma, settings):
        """
        Checks and updates roles for a member based on karma thresholds.
        Only applies changes if necessary to avoid API spam.
        """
        if "roles" not in settings:
            return

        # Parse thresholds: { "10": 12345, "50": 67890 }
        # Sort descending by threshold
        try:
            thresholds = []
            for k, r_id in settings["roles"].items():
                thresholds.append((int(k), int(r_id)))
            thresholds.sort(key=lambda x: x[0], reverse=True)
        except ValueError:
            return

        target_role_id = None

        # Find the highest threshold met
        for thresh, r_id in thresholds:
            if karma >= thresh:
                target_role_id = r_id
                break

        # Collect all managed role IDs to know what to remove
        managed_role_ids = {r_id for _, r_id in thresholds}

        roles_to_add = []
        roles_to_remove = []

        # Check current roles
        current_role_ids = {r.id for r in member.roles}

        # 1. If we have a target role, add it if missing
        if target_role_id:
            if target_role_id not in current_role_ids:
                role_obj = member.guild.get_role(target_role_id)
                if role_obj:
                    roles_to_add.append(role_obj)

        # 2. Remove any OTHER managed roles that are not the target role
        # (This implements the "Old role is removed" logic)
        for r_id in managed_role_ids:
            if r_id != target_role_id and r_id in current_role_ids:
                role_obj = member.guild.get_role(r_id)
                if role_obj:
                    roles_to_remove.append(role_obj)

        # Apply changes
        try:
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Karma Threshold Change")
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason="Karma Threshold Reached")
        except discord.Forbidden:
            print(f"Failed to update roles for {member} in {member.guild}: Missing Permissions")
        except Exception as e:
            print(f"Error updating roles for {member}: {e}")

    async def run_guild_karma_update(self, guild_id):
        """
        Iterates over all members in a guild and updates their roles.
        Use this after changing settings.
        """
        stats = await load_karma_stats()
        settings = await self.get_guild_settings(guild_id)

        if not settings or str(guild_id) not in stats:
            return

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return

        guild_stats = stats[str(guild_id)]

        for user_id, karma in guild_stats.items():
            member = guild.get_member(int(user_id))
            if member:
                await self.update_karma_roles(member, karma, settings)
                await asyncio.sleep(0.1) # Be gentle with rate limits

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setupkarma(self, ctx, channel: discord.TextChannel, upvote_emoji: str, downvote_emoji: str):
        """
        ⚙️ Setup the Karma system for this server.
        Usage: !setupkarma #channel <upvote_emoji> <downvote_emoji>
        """
        settings = await load_karma_settings()
        guild_id = str(ctx.guild.id)

        # Preserve existing roles if any
        existing_roles = {}
        if guild_id in settings and "roles" in settings[guild_id]:
            existing_roles = settings[guild_id]["roles"]

        settings[guild_id] = {
            "channel_id": channel.id,
            "upvote_emoji": upvote_emoji,
            "downvote_emoji": downvote_emoji,
            "roles": existing_roles
        }

        await save_karma_settings(settings)
        await ctx.send(f"Karma system setup!\nChannel: {channel.mention}\nUpvote: {upvote_emoji}\nDownvote: {downvote_emoji}")

    @commands.command(aliases=['k'])
    async def karma(self, ctx, user: discord.User = None):
        """
        🌟 Check karma for yourself or another user.
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
        🏆 Show the Karma leaderboard.
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

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setupkarmaroles(self, ctx):
        """
        🧙 Wizard to manage Karma Threshold Roles.
        """
        view = KarmaRoleSetupMainView(self.bot, ctx)
        await ctx.send("Select an option to manage Karma Roles:", view=view)

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
            try:
                user = guild.get_member(payload.user_id)
                if user:
                    await message.remove_reaction(payload.emoji, user)
            except discord.Forbidden:
                pass
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
                pass


# --- UI Classes for setupkarmaroles ---

class KarmaRoleSetupMainView(View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=120)
        self.bot = bot
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

    @discord.ui.button(label="Add/Edit Role", style=discord.ButtonStyle.green, emoji="➕")
    async def add_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        # We need to ask for Role first
        # Since we can't do steps easily in one click, we swap to a Role Select View
        await interaction.response.send_message("Select the role you want to assign:", view=KarmaRoleSelectView(self.bot, self.ctx), ephemeral=True)

    @discord.ui.button(label="Remove Threshold", style=discord.ButtonStyle.red, emoji="➖")
    async def remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await load_karma_settings()
        guild_id = str(self.ctx.guild.id)

        if guild_id not in settings or "roles" not in settings[guild_id] or not settings[guild_id]["roles"]:
            await interaction.response.send_message("No roles configured yet.", ephemeral=True)
            return

        view = KarmaRoleRemoveView(self.bot, self.ctx, settings[guild_id]["roles"])
        await interaction.response.send_message("Select threshold to remove:", view=view, ephemeral=True)

    @discord.ui.button(label="List Config", style=discord.ButtonStyle.blurple, emoji="📜")
    async def list_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await load_karma_settings()
        guild_id = str(self.ctx.guild.id)

        if guild_id not in settings:
            await interaction.response.send_message("Karma not setup.", ephemeral=True)
            return

        embed = discord.Embed(title="Karma Configuration", color=discord.Color.blue())

        # General Settings
        channel_id = settings[guild_id].get("channel_id")
        up = settings[guild_id].get("upvote_emoji")
        down = settings[guild_id].get("downvote_emoji")

        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "None", inline=True)
        embed.add_field(name="Emojis", value=f"{up} / {down}", inline=True)

        # Roles
        roles_text = ""
        if "roles" in settings[guild_id] and settings[guild_id]["roles"]:
            sorted_roles = sorted(settings[guild_id]["roles"].items(), key=lambda x: int(x[0]))
            for thresh, role_id in sorted_roles:
                role = self.ctx.guild.get_role(int(role_id))
                role_name = role.name if role else f"Deleted Role ({role_id})"
                roles_text += f"**{thresh}+**: {role_name}\n"
        else:
            roles_text = "No roles configured."

        embed.add_field(name="Role Thresholds", value=roles_text, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class KarmaRoleSelectView(View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select a role")
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]

        # Ask for Karma amount
        await interaction.response.send_message(f"Selected **{role.name}**. Now, please type the Karma threshold amount in this channel.", ephemeral=True)

        def check(m):
            return m.author == self.ctx.author and m.channel == self.ctx.channel

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30.0)
            try:
                amount = int(msg.content.strip())

                # Save
                settings = await load_karma_settings()
                guild_id = str(self.ctx.guild.id)

                if guild_id not in settings:
                    settings[guild_id] = {}

                if "roles" not in settings[guild_id]:
                    settings[guild_id]["roles"] = {}

                settings[guild_id]["roles"][str(amount)] = role.id
                await save_karma_settings(settings)

                await interaction.followup.send(f"✅ Set **{role.name}** for **{amount}** Karma. Updating users...", ephemeral=True)

                # Trigger retroactive update
                cog = self.bot.get_cog("Karma")
                if cog:
                    self.bot.loop.create_task(cog.run_guild_karma_update(guild_id))

            except ValueError:
                await interaction.followup.send("❌ Invalid number. Setup cancelled.", ephemeral=True)
        except asyncio.TimeoutError:
             await interaction.followup.send("❌ Timed out.", ephemeral=True)


class KarmaRoleRemoveView(View):
    def __init__(self, bot, ctx, current_roles):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx
        self.add_item(KarmaRoleRemoveSelect(current_roles, ctx.guild))

class KarmaRoleRemoveSelect(Select):
    def __init__(self, current_roles, guild):
        options = []
        # Sort by threshold
        sorted_items = sorted(current_roles.items(), key=lambda x: int(x[0]))

        for thresh, role_id in sorted_items:
            role = guild.get_role(int(role_id))
            role_name = role.name if role else f"Unknown ({role_id})"
            options.append(discord.SelectOption(label=f"{thresh} Karma", description=f"Role: {role_name}", value=str(thresh)))

        super().__init__(placeholder="Select threshold to remove...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        threshold = self.values[0]

        settings = await load_karma_settings()
        guild_id = str(interaction.guild_id)

        if guild_id in settings and "roles" in settings[guild_id]:
            if threshold in settings[guild_id]["roles"]:
                del settings[guild_id]["roles"][threshold]
                await save_karma_settings(settings)

                await interaction.response.send_message(f"✅ Removed threshold **{threshold}**. Updating users...", ephemeral=True)

                # Trigger update
                cog = self.view.bot.get_cog("Karma")
                if cog:
                     self.view.bot.loop.create_task(cog.run_guild_karma_update(guild_id))
                return

        await interaction.response.send_message("❌ Error finding threshold.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Karma(bot))
