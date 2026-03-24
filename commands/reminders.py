import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone
from loadnsave import load_reminder_data, save_reminder_data
from services.admin_service import AdminService
from views.utility_views import ReminderListView, ReminderContextMenuModal

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot, self.reminders = bot, {}
        self.help_category = "Other"
        self.ctx_menu = app_commands.ContextMenu(name='⏰ Remind Me', callback=self.remind_me_context)
        self.ctx_menu.binding = self
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_load(self):
        self.reminders = await load_reminder_data()
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def remind_me_context(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.send_modal(ReminderContextMenuModal(self, message))

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        now, changed = datetime.now(timezone.utc).timestamp(), False
        for gid in list(self.reminders.keys()):
            to_rem = [r for r in self.reminders[gid] if r['due_timestamp'] <= now]
            for r in to_rem:
                await self.send_rem(r)
                self.reminders[gid].remove(r); changed = True
            if not self.reminders[gid]: del self.reminders[gid]
        if changed: await save_reminder_data(self.reminders)

    @check_reminders.before_loop
    async def before_check_reminders(self): await self.bot.wait_until_ready()

    async def send_rem(self, r):
        chan = self.bot.get_channel(r.get('channel_id'))
        if chan:
            emb = discord.Embed(title="⏰ Reminder!", description=f"**{r.get('message', '!')}**", color=discord.Color.gold())
            if r.get('created_at'): emb.add_field(name="Set", value=f"<t:{int(r['created_at'])}:R>")
            await chan.send(content=f"<@{r['user_id']}>", embed=emb)

    reminder_group = app_commands.Group(name="reminder", description="⏰ Manage reminders")

    @reminder_group.command(name="set")
    async def set_rem(self, interaction: discord.Interaction, duration: str, message: str):
        sec = AdminService.parse_duration(duration)
        if sec <= 0: return await interaction.response.send_message("❌ Invalid duration.", ephemeral=True)
        _, res = await AdminService.create_reminder_api(self.reminders, interaction.guild_id, interaction.channel_id, interaction.user.id, message, sec)
        await interaction.response.send_message(embed=discord.Embed(title="✅ Reminder Set", description=f"In <t:{int(res['due_timestamp'])}:R>:\n**{message}**", color=discord.Color.green()))

    @reminder_group.command(name="list")
    async def list_rem(self, interaction: discord.Interaction):
        user_rem = sorted([r for r in self.reminders.get(str(interaction.guild_id), []) if r['user_id'] == interaction.user.id], key=lambda x: x['due_timestamp'])
        if not user_rem: return await interaction.response.send_message("No active reminders.", ephemeral=True)
        view = ReminderListView(self, str(interaction.guild_id), interaction.user.id, user_rem)
        await interaction.response.send_message(embed=discord.Embed(title=f"📅 Reminders ({len(user_rem)})", description="\n".join([f"• <t:{int(r['due_timestamp'])}:R>: {r['message']}" for r in user_rem[:10]]), color=discord.Color.blurple()), view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @reminder_group.command(name="delete")
    async def del_rem(self, interaction: discord.Interaction, reminder_id: str):
        res, _ = await AdminService.delete_reminder_api(self.reminders, interaction.guild_id, reminder_id)
        await interaction.response.send_message("✅ Deleted." if res else "❌ Not found.", ephemeral=True)

    @set_rem.autocomplete('duration')
    async def dur_auto(self, it: discord.Interaction, cur: str):
        return [app_commands.Choice(name=o, value=o) for o in ["5m", "15m", "1h", "4h", "1d", "1w"] if cur.lower() in o.lower()]

    @del_rem.autocomplete('reminder_id')
    async def del_auto(self, it: discord.Interaction, cur: str):
        return [app_commands.Choice(name=f"{r['message'][:30]}", value=r['id']) for r in self.reminders.get(str(it.guild_id), []) if r['user_id'] == it.user.id and cur.lower() in r['message'].lower()][:25]

async def setup(bot): await bot.add_cog(Reminders(bot))
