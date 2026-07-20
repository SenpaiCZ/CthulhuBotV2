import discord
from discord.ui import View, Select
from loadnsave import load_karma_settings, save_karma_settings

class KarmaActionsView(discord.ui.View):
    def __init__(self, cog, target_user):
        super().__init__(timeout=60)
        self.cog = cog
        self.target_user = target_user

    @discord.ui.button(label="Check Karma", style=discord.ButtonStyle.primary, emoji="🌟")
    async def check_karma(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._send_karma_response(interaction, self.target_user)

    @discord.ui.button(label="View Rank Card", style=discord.ButtonStyle.secondary, emoji="🔮")
    async def view_rank_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._show_rank_card(interaction, self.target_user)

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
