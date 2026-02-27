import discord
from discord import ui

class RenameRoomModal(ui.Modal, title="Rename Voice Channel"):
    name = ui.TextInput(label="New Channel Name", placeholder="e.g. Secret Lair", max_length=100, style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.name.value
        try:
            await interaction.channel.edit(name=new_name)
            await interaction.response.send_message(f"✅ Renamed channel to **{new_name}**", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to rename this channel.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


class KickUserSelect(ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="🚫 Kick User...", min_values=1, max_values=1, row=2)

    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]
        if member == interaction.user:
            return await interaction.response.send_message("❌ You cannot kick yourself!", ephemeral=True)

        if member.voice and member.voice.channel == interaction.channel:
            try:
                await member.move_to(None)
                await interaction.response.send_message(f"👋 Kicked {member.mention} from the room.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ I don't have permission to kick this user.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        else:
             await interaction.response.send_message(f"❌ {member.display_name} is not in this voice channel.", ephemeral=True)


class RoomControlView(ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=None) # Persistent view
        self.owner_id = int(owner_id)
        self.add_item(KickUserSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("🔒 Only the room owner can use these controls.", ephemeral=True)
            return False
        return True

    @ui.button(label="Lock 🔒", style=discord.ButtonStyle.secondary, row=0)
    async def lock_button(self, interaction: discord.Interaction, button: ui.Button):
        # Toggle connect permission for @everyone
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)

        # Check current state
        is_locked = (overwrite.connect is False)

        # Toggle
        new_state = None if is_locked else False # None allows inherit (usually True if category allows), False explicitly denies
        overwrite.connect = new_state

        try:
            await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

            # Update Button
            if new_state is False:
                button.label = "Unlock 🔓"
                button.style = discord.ButtonStyle.danger
                msg = "🔒 Room **Locked**."
            else:
                button.label = "Lock 🔒"
                button.style = discord.ButtonStyle.secondary
                msg = "🔓 Room **Unlocked**."

            await interaction.response.edit_message(view=self)
            await interaction.followup.send(msg, ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage permissions.", ephemeral=True)

    @ui.button(label="Hide 👻", style=discord.ButtonStyle.secondary, row=0)
    async def hide_button(self, interaction: discord.Interaction, button: ui.Button):
        # Toggle view_channel permission for @everyone
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)

        # Check current state
        is_hidden = (overwrite.view_channel is False)

        # Toggle
        new_state = None if is_hidden else False
        overwrite.view_channel = new_state

        try:
            await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

            # Update Button
            if new_state is False:
                button.label = "Show 👁️"
                button.style = discord.ButtonStyle.primary
                msg = "👻 Room is now **Invisible**."
            else:
                button.label = "Hide 👻"
                button.style = discord.ButtonStyle.secondary
                msg = "👁️ Room is now **Visible**."

            await interaction.response.edit_message(view=self)
            await interaction.followup.send(msg, ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage permissions.", ephemeral=True)

    @ui.button(label="Rename ✏️", style=discord.ButtonStyle.secondary, row=1)
    async def rename_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(RenameRoomModal())

    @ui.button(label="Bitrate 📶", style=discord.ButtonStyle.secondary, row=1)
    async def bitrate_button(self, interaction: discord.Interaction, button: ui.Button):
         # Toggle between 64kbps (low) and Max (high) or simple 64/96/Max
         # Checking current bitrate
         current = interaction.channel.bitrate
         max_bitrate = interaction.guild.bitrate_limit

         new_bitrate = 64000
         msg = "📶 Bitrate set to **64kbps** (Low Latency)"

         if current <= 65000:
             new_bitrate = max_bitrate
             msg = f"📶 Bitrate set to **{int(max_bitrate/1000)}kbps** (Max Quality)"

         try:
             await interaction.channel.edit(bitrate=new_bitrate)
             await interaction.response.send_message(msg, ephemeral=True)
         except Exception as e:
             await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
