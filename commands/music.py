import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_music_blacklist, load_server_volumes
from views.music_player import MusicPlayerView
from services.music_service import MusicService
from services.audio_service import AudioService

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Music"
        self.dashboard_messages = {}
        self.blacklist = []
        AudioService(bot)
        self.bot.music_cog = self

    async def cog_load(self):
        loaded = await load_music_blacklist()
        self.blacklist = loaded if isinstance(loaded, list) else []
        volumes = await load_server_volumes()
        for gid, vols in volumes.items():
            try: AudioService._server_volumes[int(gid)] = vols
            except: pass

    async def refresh_dashboard(self, interaction=None, guild_id=None):
        gid = guild_id or (interaction.guild.id if interaction else None)
        if not gid: return
        msg = self.dashboard_messages.get(str(gid))
        view = MusicPlayerView(gid)
        embed = view.get_embed()
        if msg:
            try: await msg.edit(embed=embed, view=view)
            except discord.NotFound: self.dashboard_messages.pop(str(gid), None)
        if interaction and not interaction.response.is_done():
            if msg: await interaction.response.defer()
            else:
                await interaction.response.send_message(embed=embed, view=view)
                self.dashboard_messages[str(gid)] = await interaction.original_response()

    @app_commands.command(name="play", description="▶️ Plays a song from YouTube.")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.guild: return await interaction.response.send_message("Servers only.")
        await interaction.response.defer()
        if not interaction.guild.voice_client or not interaction.guild.voice_client.is_connected():
            if interaction.user.voice:
                vc, error = await AudioService.connect_to_voice(interaction.guild, interaction.user.voice.channel.id)
                if error: return await interaction.followup.send(f"❌ {error}")
            else: return await interaction.followup.send("Connect to voice first.")
        try:
            song_info = await MusicService.add_to_queue(interaction.guild.id, query)
            if song_info.get('original_url') in self.blacklist:
                q = MusicService.get_queue(interaction.guild.id)
                if q: q.pop()
                return await interaction.followup.send(f"❌ Blacklisted: {song_info['title']}")
            song_info['requested_by'] = interaction.user.display_name
            old_msg = self.dashboard_messages.get(str(interaction.guild.id))
            if old_msg:
                try: await old_msg.delete()
                except: pass
            view = MusicPlayerView(interaction.guild.id)
            self.dashboard_messages[str(interaction.guild.id)] = await interaction.followup.send(embed=view.get_embed(), view=view)
            if not MusicService.get_current_track(interaction.guild.id): await MusicService.process_queue(interaction.guild.id)
        except Exception as e: await interaction.followup.send(f"Error: {e}")

    @app_commands.command(name="skip")
    async def skip(self, interaction: discord.Interaction):
        MusicService.skip_track(interaction.guild.id)
        await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)
        await self.refresh_dashboard(guild_id=interaction.guild.id)

    @app_commands.command(name="stop")
    async def stop(self, interaction: discord.Interaction):
        MusicService.stop_music(interaction.guild.id)
        await AudioService.disconnect_from_voice(interaction.guild)
        await interaction.response.send_message("🛑 Stopped.", ephemeral=True)
        await self.refresh_dashboard(guild_id=interaction.guild.id)

    @app_commands.command(name="volume")
    async def volume(self, interaction: discord.Interaction, vol: int):
        guild_id = interaction.guild.id
        new_vol = max(0, min(100, vol)) / 100
        AudioService._server_volumes.setdefault(guild_id, {'music': 1.0, 'soundboard': 0.5})['music'] = new_vol
        from models.database import SessionLocal
        from services.settings_service import SettingsService
        db = SessionLocal()
        try: SettingsService.set_setting(db, str(guild_id), "server_volumes", AudioService._server_volumes[guild_id])
        finally: db.close()
        track = MusicService.get_current_track(guild_id)
        if track: track.volume = new_vol
        await interaction.response.send_message(f"🔊 Volume: {vol}%", ephemeral=True)
        await self.refresh_dashboard(guild_id=guild_id)

    @app_commands.command(name="nowplaying")
    async def nowplaying(self, interaction: discord.Interaction):
        view = MusicPlayerView(interaction.guild.id)
        await interaction.response.send_message(embed=view.get_embed(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Music(bot))
