import discord
from discord import ui
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from commands.reminders import Reminders
    from commands.gameroles import GamerRoles

class ReminderDeleteSelect(ui.Select):
    def __init__(self, reminders):
        options = []
        # Sort by due time
        sorted_reminders = sorted(reminders, key=lambda x: x['due_timestamp'])

        for r in sorted_reminders[:25]: # Limit to 25 options
            dt = datetime.fromtimestamp(r['due_timestamp'], tz=timezone.utc)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
            label = f"{time_str} - {r['message'][:50]}"
            if len(r['message']) > 50:
                label += "..."

            options.append(discord.SelectOption(
                label=label,
                value=r['id'],
                description=f"Due <t:{int(r['due_timestamp'])}:R>"
            ))

        super().__init__(placeholder="Select a reminder to delete...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view: ReminderListView = self.view
        await view.delete_reminder(interaction, self.values[0])

class ReminderListView(ui.View):
    def __init__(self, cog: 'Reminders', guild_id, user_id, reminders):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.reminders = reminders
        self.message = None

        if reminders:
            self.add_item(ReminderDeleteSelect(reminders))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass # Message might be deleted or interaction expired

    async def delete_reminder(self, interaction: discord.Interaction, reminder_id):
        # Proceed to delete
        res, msg = await self.cog.delete_reminder_api(self.guild_id, reminder_id)

        if res:
            await interaction.response.send_message(f"✅ Reminder deleted.", ephemeral=True)
            self.stop()
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message(f"❌ Failed to delete: {msg}", ephemeral=True)

class ReminderContextMenuModal(ui.Modal, title="Set Reminder"):
    def __init__(self, cog: 'Reminders', message: discord.Message):
        super().__init__()
        self.cog = cog

        # Pre-fill note with context
        content_preview = message.content
        if len(content_preview) > 800:
             content_preview = content_preview[:800] + "..."
        default_note = f"Context: {content_preview}\n{message.jump_url}"
        if len(default_note) > 1000:
             default_note = default_note[:1000]

        self.duration = ui.TextInput(
            label="Duration (e.g., 10m, 1h, 1d)",
            placeholder="1h",
            max_length=10,
            required=True
        )
        self.message_note = ui.TextInput(
            label="Reminder Note",
            style=discord.TextStyle.paragraph,
            default=default_note,
            max_length=1000,
            required=True
        )

        self.add_item(self.duration)
        self.add_item(self.message_note)

    async def on_submit(self, interaction: discord.Interaction):
        seconds = self.cog.parse_duration(self.duration.value)
        if seconds <= 0:
            await interaction.response.send_message("❌ Invalid duration. Please use a format like `10m`, `1h`, `1d`, `30s`.", ephemeral=True)
            return

        res, result = await self.cog.create_reminder_api(
            interaction.guild_id,
            interaction.channel_id,
            interaction.user.id,
            self.message_note.value,
            seconds
        )

        if not res:
            await interaction.response.send_message(f"❌ Failed to set reminder: {result}", ephemeral=True)
            return

        reminder = result
        due_time = reminder['due_timestamp']

        human_time = f"<t:{int(due_time)}:R>"
        embed = discord.Embed(
            title="✅ Reminder Set",
            description=f"I'll remind you in {human_time} about:\n**{self.message_note.value}**",
            color=discord.Color.green()
        )
        embed.set_footer(text="I will ping you in this channel when it's time.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

# GamerRole Views

COLOR_PRESETS = {
    "Red": 0xFF0000, "Orange": 0xFFA500, "Yellow": 0xFFFF00, "Green": 0x008000,
    "Blue": 0x0000FF, "Purple": 0x800080, "Pink": 0xFFC0CB, "White": 0xFFFFFF,
    "Grey": 0x808080, "Cyan": 0x00FFFF, "Teal": 0x008080, "Lime": 0x00FF00,
    "Magenta": 0xFF00FF, "Gold": 0xFFD700, "Brown": 0xA52A2A, "Navy": 0x000080,
    "Maroon": 0x800000, "Olive": 0x808000, "Coral": 0xFF7F50, "Indigo": 0x4B0082,
    "Violet": 0xEE82EE, "Turquoise": 0x40E0D0, "Salmon": 0xFA8072, "Sky Blue": 0x87CEEB
}

class ColorSelect(ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=name, value=name) for name in COLOR_PRESETS.keys()]
        super().__init__(placeholder="Select a color...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        color_name = self.values[0]
        color_value = COLOR_PRESETS[color_name]
        view: GamerRoleColorView = self.view
        await view.save_color(interaction, color_value, color_name)

class GamerRoleColorView(ui.View):
    def __init__(self, cog: 'GamerRoles', guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.add_item(ColorSelect())

    async def save_color(self, interaction, color_value, color_name):
        hex_color = f"#{color_value:06x}"
        await self.cog.update_settings(self.guild_id, "color", hex_color)
        await interaction.response.send_message(f"Gamer Role color set to **{color_name}**.", ephemeral=False)
        self.stop()
