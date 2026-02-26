import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

class RolePanelModal(Modal, title="Create Role Panel"):
    panel_title = TextInput(label="Title", placeholder="e.g. Server Roles", max_length=100)
    description = TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Click a button to get a role!", max_length=2000)
    color = TextInput(label="Color (Hex)", placeholder="#3498db", max_length=7, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        title = self.panel_title.value
        desc = self.description.value
        color_val = discord.Color.blue() # Default

        if self.color.value:
            try:
                hex_str = self.color.value.strip()
                if not hex_str.startswith("#"):
                    hex_str = "#" + hex_str
                color_val = discord.Color(int(hex_str[1:], 16))
            except ValueError:
                await interaction.response.send_message("Invalid hex color code. Using default.", ephemeral=True)

        embed = discord.Embed(title=title, description=desc, color=color_val)
        embed.set_footer(text="Nexus Role System")

        await interaction.response.send_message(embed=embed)


class RolePanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Admin"

    rolepanel_group = app_commands.Group(name="rolepanel", description="🎭 Manage button-based role panels.")

    @rolepanel_group.command(name="create", description="📝 Create a new role panel message.")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_panel(self, interaction: discord.Interaction):
        """
        📝 Create a new role panel message.
        """
        await interaction.response.send_modal(RolePanelModal())

    @rolepanel_group.command(name="add", description="➕ Add a role button to a panel.")
    @app_commands.describe(message_link="Link to the panel message", role="Role to assign", label="Button label (optional)", emoji="Button emoji (optional)")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_role(self, interaction: discord.Interaction, message_link: str, role: discord.Role, label: str = None, emoji: str = None):
        """
        ➕ Add a role button to a panel.
        """
        await interaction.response.defer(ephemeral=True)

        # Parse Message Link
        try:
            parts = message_link.split('/')
            msg_id = int(parts[-1])
            chan_id = int(parts[-2])
            guild_id = int(parts[-3])

            if guild_id != interaction.guild_id:
                 await interaction.followup.send("Message must be in this server.")
                 return

            channel = interaction.guild.get_channel(chan_id)
            if not channel:
                await interaction.followup.send("Channel not found.")
                return

            message = await channel.fetch_message(msg_id)
        except Exception:
            await interaction.followup.send("Invalid message link or message not found.")
            return

        if message.author.id != self.bot.user.id:
            await interaction.followup.send("I can only edit my own messages.")
            return

        # Check bot permissions regarding the role
        if role >= interaction.guild.me.top_role:
             await interaction.followup.send(f"I cannot assign role **{role.name}** because it is higher than my top role.")
             return

        # Construct/Update View
        view = View.from_message(message)

        # Check existing buttons
        # Max 25 buttons (5 rows of 5)
        if len(view.children) >= 25:
             await interaction.followup.send("This panel is full (max 25 buttons).")
             return

        # Check if role already exists on this panel
        custom_id = f"rolepanel:{role.id}"
        for child in view.children:
            if isinstance(child, Button) and child.custom_id == custom_id:
                await interaction.followup.send(f"Role **{role.name}** is already on this panel.")
                return

        # Defaults
        btn_label = label or role.name
        btn_emoji = emoji

        # Add Button
        # We assume secondary (grey) style for neutral toggle
        button = Button(style=discord.ButtonStyle.secondary, label=btn_label[:80], emoji=btn_emoji, custom_id=custom_id)
        view.add_item(button)

        await message.edit(view=view)
        await interaction.followup.send(f"✅ Added button for **{role.name}**.")

    @rolepanel_group.command(name="remove", description="➖ Remove a role button from a panel.")
    @app_commands.describe(message_link="Link to the panel message", role="Role to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_role(self, interaction: discord.Interaction, message_link: str, role: discord.Role):
        """
        ➖ Remove a role button from a panel.
        """
        await interaction.response.defer(ephemeral=True)

        try:
            parts = message_link.split('/')
            msg_id = int(parts[-1])
            chan_id = int(parts[-2])
            guild_id = int(parts[-3])

            if guild_id != interaction.guild_id:
                 await interaction.followup.send("Message must be in this server.")
                 return

            channel = interaction.guild.get_channel(chan_id)
            if not channel:
                await interaction.followup.send("Channel not found.")
                return

            message = await channel.fetch_message(msg_id)
        except Exception:
            await interaction.followup.send("Invalid message link or message not found.")
            return

        if message.author.id != self.bot.user.id:
            await interaction.followup.send("I can only edit my own messages.")
            return

        view = View.from_message(message)
        custom_id = f"rolepanel:{role.id}"

        found = False
        # Create new view without the target button
        new_view = View()
        for child in view.children:
            if isinstance(child, Button):
                if child.custom_id == custom_id:
                    found = True
                    continue # Skip adding this button
                new_view.add_item(child)

        if found:
            await message.edit(view=new_view)
            await interaction.followup.send(f"✅ Removed button for **{role.name}**.")
        else:
            await interaction.followup.send(f"Button for role **{role.name}** not found on this panel.")


    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """
        Global listener for rolepanel button clicks.
        Stateless: Uses custom_id to determine action.
        """
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("rolepanel:"):
            return

        # It's a RolePanel button
        try:
            role_id_str = custom_id.split(":")[1]
            role_id = int(role_id_str)
        except (IndexError, ValueError):
            return await interaction.response.send_message("❌ Invalid button configuration.", ephemeral=True)

        role = interaction.guild.get_role(role_id)
        if not role:
            # Role might have been deleted
            return await interaction.response.send_message("❌ This role no longer exists.", ephemeral=True)

        member = interaction.user

        # Check Bot Permissions
        if role >= interaction.guild.me.top_role:
             return await interaction.response.send_message(f"❌ I cannot assign/remove role **{role.name}** (it is higher than my top role).", ephemeral=True)

        try:
            if role in member.roles:
                await member.remove_roles(role, reason="RolePanel: User requested removal")
                await interaction.response.send_message(f"➖ Removed **{role.name}**.", ephemeral=True)
            else:
                await member.add_roles(role, reason="RolePanel: User requested add")
                await interaction.response.send_message(f"➕ Added **{role.name}**.", ephemeral=True)
        except discord.Forbidden:
             await interaction.response.send_message("❌ Missing permissions to manage roles.", ephemeral=True)
        except Exception as e:
             await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(RolePanel(bot))
