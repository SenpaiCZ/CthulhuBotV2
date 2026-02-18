import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select
import asyncio
import io
import urllib.parse
from playwright.async_api import async_playwright
from loadnsave import load_karma_settings, save_karma_settings, load_karma_stats, save_karma_stats, load_settings

class Karma(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu_check = app_commands.ContextMenu(
            name='Check Karma',
            callback=self.karma_context_menu,
        )
        self.ctx_menu_rank = app_commands.ContextMenu(
            name='View Rank Card',
            callback=self.view_rank_card_menu,
        )
        self.bot.tree.add_command(self.ctx_menu_check, override=True)
        self.bot.tree.add_command(self.ctx_menu_rank, override=True)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu_check.name, type=self.ctx_menu_check.type)
        self.bot.tree.remove_command(self.ctx_menu_rank.name, type=self.ctx_menu_rank.type)

    async def get_guild_settings(self, guild_id):
        settings = await load_karma_settings()
        return settings.get(str(guild_id))

    def _get_rank_name(self, karma, settings, guild):
        if "roles" not in settings or not settings["roles"]:
            return "Unranked"

        # Parse thresholds: { "10": 12345, "50": 67890 }
        try:
            thresholds = []
            for k, r_id in settings["roles"].items():
                thresholds.append((int(k), int(r_id)))
            thresholds.sort(key=lambda x: x[0], reverse=True)
        except ValueError:
            return "Error"

        target_role_id = None
        for thresh, r_id in thresholds:
            if karma >= thresh:
                target_role_id = r_id
                break

        if target_role_id:
            role = guild.get_role(target_role_id)
            return role.name if role else "Unknown Rank"

        return "Unranked"

    async def generate_notification_image(self, guild_id, user_id, rank_name, change_type):
        settings = load_settings()
        port = settings.get('dashboard_port', 5000)

        encoded_rank = urllib.parse.quote(rank_name)
        url = f"http://127.0.0.1:{port}/render/karma/{guild_id}/{user_id}?rank={encoded_rank}&type={change_type}"

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                try:
                    page = await browser.new_page(viewport={'width': 800, 'height': 400})
                    await page.goto(url, timeout=10000)

                    try:
                        element = await page.wait_for_selector('.karma-card', timeout=5000)
                    except:
                        element = None

                    if element:
                        return await element.screenshot()
                    else:
                        return await page.screenshot()
                finally:
                    await browser.close()
        except Exception as e:
            print(f"Error generating karma image: {e}")
            return None

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

        # Determine previous managed role
        previous_role_id = None
        for r_id in managed_role_ids:
            if r_id in current_role_ids:
                previous_role_id = r_id
                break

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

            # Check for rank change and notify
            if target_role_id != previous_role_id:
                # Determine type
                change_type = "up"
                new_rank_name = "None"

                # Get threshold values for comparison
                prev_thresh = -1
                curr_thresh = -1

                for t, rid in thresholds:
                    if rid == previous_role_id: prev_thresh = t
                    if rid == target_role_id: curr_thresh = t

                if target_role_id is None:
                    change_type = "down"
                    new_rank_name = "Unranked"
                elif previous_role_id is None:
                    change_type = "up"
                    role_obj = member.guild.get_role(target_role_id)
                    new_rank_name = role_obj.name if role_obj else "Unknown"
                else:
                    if curr_thresh > prev_thresh:
                        change_type = "up"
                    else:
                        change_type = "down"
                    role_obj = member.guild.get_role(target_role_id)
                    new_rank_name = role_obj.name if role_obj else "Unknown"

                # Notification
                notify_channel_id = settings.get("notification_channel_id")
                if notify_channel_id:
                    channel = member.guild.get_channel(int(notify_channel_id))
                    if channel:
                         # Run in background to not block
                         self.bot.loop.create_task(self.send_rank_notification(channel, member, new_rank_name, change_type))

        except discord.Forbidden:
            print(f"Failed to update roles for {member} in {member.guild}: Missing Permissions")
        except Exception as e:
            print(f"Error updating roles for {member}: {e}")

    async def send_rank_notification(self, channel, member, rank_name, change_type):
        try:
            img_bytes = await self.generate_notification_image(member.guild.id, member.id, rank_name, change_type)
            if img_bytes:
                file = discord.File(io.BytesIO(img_bytes), filename="rank_update.png")

                if change_type == "up":
                        msg_content = f"📈 **LEVEL UP!** {member.mention} has reached **{rank_name}**!"
                else:
                        msg_content = f"📉 **DERANKED...** {member.mention} dropped to **{rank_name}**."

                await channel.send(content=msg_content, file=file)
        except Exception as e:
            print(f"Error sending rank notification: {e}")

    async def recalculate_karma(self, guild_id):
        """
        Wipes existing karma stats for the guild and rescans the entire history
        of the configured karma channel to recalculate scores.
        Ignores self-votes.
        """
        guild_id = str(guild_id)
        settings = await self.get_guild_settings(guild_id)
        if not settings or not settings.get("channel_id"):
            print(f"Recalculate failed for {guild_id}: No channel configured.")
            return

        channel_id = int(settings["channel_id"])
        guild = self.bot.get_guild(int(guild_id))
        if not guild: return
        channel = guild.get_channel(channel_id)
        if not channel: return

        up_emoji = settings.get("upvote_emoji")
        down_emoji = settings.get("downvote_emoji")

        print(f"Starting karma recalculation for {guild.name} in #{channel.name}...", flush=True)

        # Temp stats
        new_stats = {}
        message_count = 0

        try:
            print("Scanning channel history...", flush=True)
            # Iterate history (scan all messages)
            try:
                async for message in channel.history(limit=None):
                    message_count += 1

                    if message_count == 1:
                        print("Processing first batch of messages...", flush=True)

                    if message_count % 25 == 0:
                        print(f"Recalculating Karma... Scanned {message_count} messages so far.", flush=True)

                    try:
                        # Check if author exists
                        if not message.author:
                            continue

                        if message.author.bot:
                            continue # Do not count karma FOR bots

                        # We need to iterate over all reactions
                        for reaction in message.reactions:
                            emoji_str = str(reaction.emoji)
                            change = 0
                            if emoji_str == up_emoji:
                                change = 1
                            elif emoji_str == down_emoji:
                                change = -1

                            if change == 0:
                                continue

                            # Fetch users who reacted (required to filter self-votes)
                            async for user in reaction.users():
                                if user.bot:
                                    continue # Ignore votes FROM bots

                                if user.id == message.author.id:
                                    continue # Ignore self-votes

                                author_id = str(message.author.id)
                                new_stats[author_id] = new_stats.get(author_id, 0) + change

                    except Exception as msg_error:
                        # Log error but continue processing other messages
                        # This handles deleted users or malformed data issues gracefully
                        print(f"Error processing message {message.id} during recalculation: {msg_error}", flush=True)
                        continue

            except Exception as history_error:
                print(f"Error iterating channel history: {history_error}", flush=True)

            if message_count == 0:
                print("Warning: No messages found in channel history. Aborting update to prevent data loss.", flush=True)
                return

            print(f"Recalculation finished. Total messages scanned: {message_count}", flush=True)

            # Save new stats
            all_stats = await load_karma_stats()
            all_stats[guild_id] = new_stats
            await save_karma_stats(all_stats)

            print(f"Karma recalculation for {guild.name} complete. Updating roles...")

            # Trigger retroactive role updates
            await self.run_guild_karma_update(guild_id)

        except Exception as e:
            print(f"Error during karma recalculation for {guild.name}: {e}")

    async def get_guild_leaderboard_data(self, guild_id):
        stats = await load_karma_stats()
        guild_id = str(guild_id)

        if guild_id not in stats:
            return []

        # Sort users by karma (descending)
        sorted_users = sorted(stats[guild_id].items(), key=lambda item: item[1], reverse=True)

        results = []
        guild = self.bot.get_guild(int(guild_id))

        for user_id, score in sorted_users:
            user_name = f"Unknown User ({user_id})"
            if guild:
                member = guild.get_member(int(user_id))
                if member:
                    user_name = member.display_name

            results.append({
                "user_id": user_id,
                "name": user_name,
                "score": score
            })

        return results

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

    @app_commands.command(name="setupkarma", description="⚙️ Setup the Karma system for this server (Wizard).")
    @app_commands.checks.has_permissions(administrator=True)
    async def setupkarma(self, interaction: discord.Interaction):
        """
        ⚙️ Setup the Karma system for this server (Wizard).
        """
        await interaction.response.send_message("Let's set up the Karma system! First, select the channel where reactions should count.",
                       view=KarmaSetupChannelView(self.bot, interaction.user), ephemeral=True)

    @app_commands.command(name="karma", description="🌟 Check karma for yourself or another user.")
    @app_commands.describe(user="The user to check karma for (defaults to you)")
    async def karma(self, interaction: discord.Interaction, user: discord.User = None):
        """
        🌟 Check karma for yourself or another user.
        """
        if user is None:
            user = interaction.user

        await self._send_karma_response(interaction, user)

    async def karma_context_menu(self, interaction: discord.Interaction, user: discord.User):
        await self._send_karma_response(interaction, user)

    async def view_rank_card_menu(self, interaction: discord.Interaction, user: discord.Member):
        await self._show_rank_card(interaction, user)

    async def _send_karma_response(self, interaction: discord.Interaction, user: discord.User):
        stats = await load_karma_stats()
        guild_id = str(interaction.guild_id)
        user_id = str(user.id)

        karma_score = stats.get(guild_id, {}).get(user_id, 0)

        await interaction.response.send_message(f"{user.display_name} has {karma_score} karma.", ephemeral=True)

    @app_commands.command(name="memelevel", description="🔮 Show your current rank card.")
    @app_commands.describe(user="The user whose rank card you want to see (defaults to you)")
    async def memelevel(self, interaction: discord.Interaction, user: discord.Member = None):
        """
        🔮 Show your current rank card.
        """
        if user is None:
            user = interaction.user

        await self._show_rank_card(interaction, user)

    async def _show_rank_card(self, interaction: discord.Interaction, user: discord.Member):
        stats = await load_karma_stats()
        guild_id = str(interaction.guild_id)
        user_id = str(user.id)

        karma = stats.get(guild_id, {}).get(user_id, 0)
        settings = await self.get_guild_settings(guild_id)

        if not settings:
             await interaction.response.send_message("Karma system is not set up on this server.", ephemeral=True)
             return

        rank_name = self._get_rank_name(karma, settings, interaction.guild)

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        # Generate image
        img_bytes = await self.generate_notification_image(interaction.guild_id, user.id, rank_name, "status")

        if img_bytes:
            file = discord.File(io.BytesIO(img_bytes), filename="rank_status.png")
            await interaction.followup.send(file=file)
        else:
            await interaction.followup.send("Failed to generate rank card.")

    @app_commands.command(name="leaderboard", description="🏆 Show the Karma leaderboard.")
    async def leaderboard(self, interaction: discord.Interaction):
        """
        🏆 Show the Karma leaderboard.
        """
        stats = await load_karma_stats()
        guild_id = str(interaction.guild_id)

        if guild_id not in stats or not stats[guild_id]:
            await interaction.response.send_message("No karma stats found for this server.", ephemeral=True)
            return

        # Sort users by karma (descending)
        sorted_users = sorted(stats[guild_id].items(), key=lambda item: item[1], reverse=True)

        view = LeaderboardView(interaction, sorted_users)
        embed = view.get_embed()

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="setupkarmaroles", description="🧙 Wizard to manage Karma Threshold Roles.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setupkarmaroles(self, interaction: discord.Interaction):
        """
        🧙 Wizard to manage Karma Threshold Roles.
        """
        view = KarmaRoleSetupMainView(self.bot, interaction.user)
        await interaction.response.send_message("Select an option to manage Karma Roles:", view=view, ephemeral=True)

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
    def __init__(self, bot, user):
        super().__init__(timeout=120)
        self.bot = bot
        self.user = user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    @discord.ui.button(label="Add/Edit Role", style=discord.ButtonStyle.green, emoji="➕")
    async def add_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        # We need to ask for Role first
        # Since we can't do steps easily in one click, we swap to a Role Select View
        await interaction.response.send_message("Select the role you want to assign:", view=KarmaRoleSelectView(self.bot, self.user), ephemeral=True)

    @discord.ui.button(label="Remove Threshold", style=discord.ButtonStyle.red, emoji="➖")
    async def remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await load_karma_settings()
        guild_id = str(interaction.guild_id)

        if guild_id not in settings or "roles" not in settings[guild_id] or not settings[guild_id]["roles"]:
            await interaction.response.send_message("No roles configured yet.", ephemeral=True)
            return

        view = KarmaRoleRemoveView(self.bot, self.user, settings[guild_id]["roles"], interaction.guild)
        await interaction.response.send_message("Select threshold to remove:", view=view, ephemeral=True)

    @discord.ui.button(label="List Config", style=discord.ButtonStyle.blurple, emoji="📜")
    async def list_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await load_karma_settings()
        guild_id = str(interaction.guild_id)

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
                role = interaction.guild.get_role(int(role_id))
                role_name = role.name if role else f"Deleted Role ({role_id})"
                roles_text += f"**{thresh}+**: {role_name}\n"
        else:
            roles_text = "No roles configured."

        embed.add_field(name="Role Thresholds", value=roles_text, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class KarmaRoleSelectView(View):
    def __init__(self, bot, user):
        super().__init__(timeout=60)
        self.bot = bot
        self.user = user

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select a role")
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]

        # Use Modal for amount
        await interaction.response.send_modal(KarmaThresholdModal(role, self.bot))


class KarmaThresholdModal(discord.ui.Modal, title="Karma Threshold"):
    amount = discord.ui.Label(text="Karma Amount", component=discord.ui.TextInput(placeholder="e.g. 10", required=True, min_length=1, max_length=5))

    def __init__(self, role, bot):
        super().__init__()
        self.role = role
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount_val = int(self.amount.component.value.strip())

            # Save
            settings = await load_karma_settings()
            guild_id = str(interaction.guild_id)

            if guild_id not in settings:
                settings[guild_id] = {}

            if "roles" not in settings[guild_id]:
                settings[guild_id]["roles"] = {}

            settings[guild_id]["roles"][str(amount_val)] = self.role.id
            await save_karma_settings(settings)

            await interaction.response.send_message(f"✅ Set **{self.role.name}** for **{amount_val}** Karma. Updating users...", ephemeral=True)

            # Trigger retroactive update
            cog = self.bot.get_cog("Karma")
            if cog:
                self.bot.loop.create_task(cog.run_guild_karma_update(guild_id))

        except ValueError:
            await interaction.response.send_message("❌ Invalid number. Please enter a valid integer.", ephemeral=True)


class KarmaRoleRemoveView(View):
    def __init__(self, bot, user, current_roles, guild):
        super().__init__(timeout=60)
        self.bot = bot
        self.user = user
        self.add_item(KarmaRoleRemoveSelect(current_roles, guild))

class KarmaRoleRemoveSelect(Select):
    def __init__(self, current_roles, guild):
        options = []
        # Sort by threshold
        sorted_items = sorted(current_roles.items(), key=lambda x: int(x[0]))

        for thresh, role_id in sorted_items:
            role = guild.get_role(int(role_id))
            role_name = role.name if role else f"Unknown ({role_id})"
            options.append(discord.SelectOption(label=f"{thresh} Karma", description=f"Role: {role_name}", value=str(thresh)))

        super().__init__(placeholder="Select threshold to remove...", min_values=1, max_values=1, options=options)

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


class LeaderboardView(View):
    def __init__(self, interaction, sorted_users, items_per_page=10):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.sorted_users = sorted_users
        self.items_per_page = items_per_page
        self.current_page = 1
        self.total_pages = max(1, (len(sorted_users) - 1) // items_per_page + 1)
        self.update_buttons()

    def update_buttons(self):
        self.previous_page.disabled = self.current_page <= 1
        self.next_page.disabled = self.current_page >= self.total_pages

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This isn't your leaderboard!", ephemeral=True)
            return False
        return True

    def get_embed(self):
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        current_page_users = self.sorted_users[start_index:end_index]

        embed = discord.Embed(title=f"Karma Leaderboard - Page {self.current_page}/{self.total_pages}", color=discord.Color.gold())
        description = ""
        for i, (user_id, score) in enumerate(current_page_users, start=start_index + 1):
            user = self.interaction.guild.get_member(int(user_id))
            user_name = user.display_name if user else "Unknown User"
            description += f"**{i}.** {user_name}: **{score}**\n"
        embed.description = description
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

# --- UI Classes for setupkarma (Main Setup) ---

class KarmaSetupChannelView(View):
    def __init__(self, bot, user):
        super().__init__(timeout=120)
        self.bot = bot
        self.user = user
        self.channel_id = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select Reaction Channel")
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.channel_id = select.values[0].id
        await interaction.response.send_modal(KarmaSetupEmojiModal(self.bot, self.user, self.channel_id))

class KarmaSetupEmojiModal(discord.ui.Modal, title="Karma Emojis"):
    upvote = discord.ui.Label(text="Upvote Emoji", component=discord.ui.TextInput(placeholder="e.g. 👌 or :custom:", required=True, max_length=50))
    downvote = discord.ui.Label(text="Downvote Emoji", component=discord.ui.TextInput(placeholder="e.g. 🤏 or :custom:", required=True, max_length=50))

    def __init__(self, bot, user, channel_id):
        super().__init__()
        self.bot = bot
        self.user = user
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction):
        # Move to next step: Notification Channel
        await interaction.response.send_message(
            f"Emojis set: {self.upvote.component.value} / {self.downvote.component.value}.\n"
            "Now, select a **Notification Channel** for rank updates (or skip to disable).",
            view=KarmaSetupNotifyView(self.bot, self.user, self.channel_id, self.upvote.component.value, self.downvote.component.value),
            ephemeral=True
        )

class KarmaSetupNotifyView(View):
    def __init__(self, bot, user, channel_id, up, down):
        super().__init__(timeout=120)
        self.bot = bot
        self.user = user
        self.data = {
            "channel_id": channel_id,
            "upvote_emoji": up,
            "downvote_emoji": down
        }

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select Notification Channel")
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        notify_id = select.values[0].id
        await self.finish_setup(interaction, notify_id)

    @discord.ui.button(label="Skip (No Notifications)", style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish_setup(interaction, None)

    async def finish_setup(self, interaction: discord.Interaction, notify_id):
        settings = await load_karma_settings()
        guild_id = str(interaction.guild_id)

        existing_roles = {}
        if guild_id in settings and "roles" in settings[guild_id]:
            existing_roles = settings[guild_id]["roles"]

        settings[guild_id] = {
            "channel_id": self.data["channel_id"],
            "notification_channel_id": notify_id,
            "upvote_emoji": self.data["upvote_emoji"],
            "downvote_emoji": self.data["downvote_emoji"],
            "roles": existing_roles
        }

        await save_karma_settings(settings)

        notify_text = f"<#{notify_id}>" if notify_id else "Disabled"
        await interaction.response.edit_message(content=f"✅ **Karma Setup Complete!**\n"
                                             f"Reaction Channel: <#{self.data['channel_id']}>\n"
                                             f"Notification Channel: {notify_text}\n"
                                             f"Emojis: {self.data['upvote_emoji']} / {self.data['downvote_emoji']}", view=None)

async def setup(bot):
    await bot.add_cog(Karma(bot))
