import discord
from discord.ext import commands
from discord import app_commands
from services.admin_service import AdminService
from views.autoroom_view import RoomControlView

class Autoroom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    autoroom_group = app_commands.Group(name="autoroom", description="🔊 Manage auto-rooms")

    @autoroom_group.command(name="setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, channel: discord.VoiceChannel, category: discord.CategoryChannel):
        await AdminService.setup_autoroom(None, str(interaction.guild.id), channel.id, category.id)
        await interaction.response.send_message(f"**Auto Room Setup Complete!**\nSource: {channel.mention}\nTarget: {category.mention}")

    @autoroom_group.command(name="kick")
    async def kick(self, interaction: discord.Interaction, member: discord.Member):
        conf = await AdminService.get_autoroom_config(str(interaction.guild.id))
        user_chan_id = conf.get(str(interaction.user.id))
        if not user_chan_id or (interaction.user.voice and interaction.user.voice.channel.id != user_chan_id):
            return await interaction.response.send_message("You must be in your own autoroom.", ephemeral=True)
        if member.voice and member.voice.channel and member.voice.channel.id == user_chan_id:
            try:
                await member.move_to(None)
                await interaction.response.send_message(f"👢 {member.display_name} kicked.", ephemeral=True)
            except: await interaction.response.send_message("❌ No permission.", ephemeral=True)
        else: await interaction.response.send_message("Member not in your room.", ephemeral=True)

    @autoroom_group.command(name="lock")
    async def lock(self, interaction: discord.Interaction):
        conf = await AdminService.get_autoroom_config(str(interaction.guild.id))
        user_chan_id = conf.get(str(interaction.user.id))
        if interaction.user.voice and interaction.user.voice.channel.id == user_chan_id:
            await interaction.user.voice.channel.set_permissions(interaction.guild.default_role, connect=False)
            await interaction.response.send_message("🔒 Room locked.")
        else: await interaction.response.send_message("You must be in your room.", ephemeral=True)

    @autoroom_group.command(name="unlock")
    async def unlock(self, interaction: discord.Interaction):
        conf = await AdminService.get_autoroom_config(str(interaction.guild.id))
        user_chan_id = conf.get(str(interaction.user.id))
        if interaction.user.voice and interaction.user.voice.channel.id == user_chan_id:
            await interaction.user.voice.channel.set_permissions(interaction.guild.default_role, connect=True)
            await interaction.response.send_message("🔓 Room unlocked.")
        else: await interaction.response.send_message("You must be in your room.", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        sid = str(member.guild.id)
        conf = await AdminService.get_autoroom_config(sid)
        if not conf: return
        if after.channel and after.channel.id == conf.get("channel_id"):
            if before.channel and before.channel.id == conf.get("channel_id"): return
            cat = member.guild.get_channel(conf.get("category_id"))
            if cat and isinstance(cat, discord.CategoryChannel):
                try:
                    new_chan = await member.guild.create_voice_channel(f"{member.display_name}'s Room", category=cat, overwrites=cat.overwrites)
                    await AdminService.save_autoroom_user_channel(sid, str(member.id), new_chan.id)
                    await member.move_to(new_chan)
                    view = RoomControlView(member.id)
                    await new_chan.send(embed=discord.Embed(title="🎛️ Room Controls", description=f"Welcome, {member.mention}!", color=discord.Color.blue()), view=view)
                except: pass
        if str(member.id) in conf and before.channel and before.channel.id == conf[str(member.id)] and (not after.channel or after.channel.id != before.channel.id):
            chan = member.guild.get_channel(conf[str(member.id)])
            if chan:
                try: await chan.delete()
                except: pass
                await AdminService.remove_autoroom_user_channel(sid, str(member.id))

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            conf = await AdminService.get_autoroom_config(str(guild.id))
            if not conf: continue
            for uid, cid in list(conf.items()):
                if uid in ["channel_id", "category_id"]: continue
                chan = guild.get_channel(cid)
                if chan and len(chan.members) == 0:
                    try: await chan.delete()
                    except: pass
                    await AdminService.remove_autoroom_user_channel(str(guild.id), uid)
                elif not chan: await AdminService.remove_autoroom_user_channel(str(guild.id), uid)

async def setup(bot): await bot.add_cog(Autoroom(bot))
