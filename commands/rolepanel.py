import discord
from discord.ext import commands
from discord import app_commands
from discord import ui

class RolePanelModal(ui.Modal, title="Create Role Panel"):
    panel_title = ui.TextInput(label="Title", placeholder="Role Selection", max_length=256)
    description = ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Click buttons below to get roles!", max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=self.panel_title.value,
            description=self.description.value,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Role Panel")
        await interaction.response.send_message(embed=embed)

class RolePanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Admin"

    rolepanel_group = app_commands.Group(name="rolepanel", description="🎛️ Manage button-based role panels.")

    @rolepanel_group.command(name="create", description="✨ Create a new role panel embed.")
    @app_commands.checks.has_permissions(administrator=True)
    async def create(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RolePanelModal())

    @rolepanel_group.command(name="add", description="➕ Add a role button to a panel.")
    @app_commands.describe(message_id="The ID of the panel message", role="The role to assign", label="Button label", emoji="Button emoji")
    @app_commands.checks.has_permissions(administrator=True)
    async def add(self, interaction: discord.Interaction, message_id: str, role: discord.Role, label: str = None, emoji: str = None):
        # Validation
        if not label and not emoji:
            return await interaction.response.send_message("❌ You must provide at least a label or an emoji.", ephemeral=True)

        try:
            msg = await interaction.channel.fetch_message(int(message_id))
        except:
            return await interaction.response.send_message("❌ Message not found in this channel.", ephemeral=True)

        if msg.author != self.bot.user:
             return await interaction.response.send_message("❌ I can only edit my own messages.", ephemeral=True)

        # Get existing view or create new
        # We need to reconstruct the view from the message components
        view = discord.ui.View(timeout=None)

        # Add existing buttons
        for child in msg.components:
            for item in child.children:
                if item.type == discord.ComponentType.button:
                    # Recreate button
                    btn = discord.ui.Button(
                        style=item.style,
                        label=item.label,
                        emoji=item.emoji,
                        custom_id=item.custom_id,
                        disabled=item.disabled
                    )
                    view.add_item(btn)

        # Check limit (5 rows * 5 buttons = 25)
        if len(view.children) >= 25:
             return await interaction.response.send_message("❌ This panel is full (25 buttons max).", ephemeral=True)

        # Create new button
        # Custom ID format: rolepanel:role_id
        custom_id = f"rolepanel:{role.id}"

        # Check if button already exists
        for child in view.children:
            if child.custom_id == custom_id:
                 return await interaction.response.send_message("❌ That role is already on this panel.", ephemeral=True)

        new_btn = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label=label or role.name,
            emoji=emoji,
            custom_id=custom_id
        )
        view.add_item(new_btn)

        await msg.edit(view=view)
        await interaction.response.send_message(f"✅ Added button for **{role.name}**.", ephemeral=True)

    @rolepanel_group.command(name="remove", description="➖ Remove a role button from a panel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(self, interaction: discord.Interaction, message_id: str, role: discord.Role):
        try:
            msg = await interaction.channel.fetch_message(int(message_id))
        except:
            return await interaction.response.send_message("❌ Message not found in this channel.", ephemeral=True)

        view = discord.ui.View(timeout=None)
        target_id = f"rolepanel:{role.id}"
        found = False

        for child in msg.components:
            for item in child.children:
                if item.type == discord.ComponentType.button:
                    if item.custom_id == target_id:
                        found = True
                        continue # Skip this one

                    btn = discord.ui.Button(
                        style=item.style,
                        label=item.label,
                        emoji=item.emoji,
                        custom_id=item.custom_id,
                        disabled=item.disabled
                    )
                    view.add_item(btn)

        if not found:
             return await interaction.response.send_message("❌ Role button not found on this panel.", ephemeral=True)

        await msg.edit(view=view)
        await interaction.response.send_message(f"✅ Removed button for **{role.name}**.", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id")
        if not custom_id or not custom_id.startswith("rolepanel:"):
            return

        role_id_str = custom_id.split(":")[1]
        try:
            role_id = int(role_id_str)
        except ValueError:
            return

        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ Role not found (maybe deleted?).", ephemeral=True)
            return

        if role in interaction.user.roles:
            try:
                await interaction.user.remove_roles(role, reason="Role Panel")
                await interaction.response.send_message(f"❌ Removed **{role.name}**.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ Missing permissions to remove role.", ephemeral=True)
        else:
            try:
                await interaction.user.add_roles(role, reason="Role Panel")
                await interaction.response.send_message(f"✅ Added **{role.name}**.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ Missing permissions to add role.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RolePanel(bot))
