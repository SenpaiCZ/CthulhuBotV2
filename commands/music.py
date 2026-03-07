import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
import yt_dlp
import random
from functools import partial
from dashboard.app import guild_mixers, server_volumes
from dashboard.audio_mixer import MixingAudioSource
from loadnsave import load_music_blacklist, save_music_blacklist, load_server_volumes, save_server_volumes
from commands._music_view import MusicView

# YT-DLP options
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',

}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Music"
        # guild_id -> list of dicts {title, url, thumbnail, ...}
        self.queue = {}
        # guild_id -> current Track object
        self.current_track = {}
        # guild_id -> Message object
        self.dashboard_messages = {}
        # List of banned URLs
        self.blacklist = []

        # Expose self to bot for dashboard access
        self.bot.music_cog = self

    async def cog_load(self):
        loaded = await load_music_blacklist()
        if isinstance(loaded, list):
            self.blacklist = loaded
        else:
            self.blacklist = []

        # Load server volumes into shared dict
        volumes = await load_server_volumes()
        server_volumes.update(volumes)

    def cog_unload(self):
        pass

    def _on_track_finish(self, guild_id):
        # Triggered from Mixer Thread
        coro = self._process_queue(guild_id)
        fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

        def check_error(f):
            try:
                f.result()
            except Exception as e:
                print(f"Error processing queue for guild {guild_id}: {e}")

        fut.add_done_callback(check_error)

    async def _process_queue(self, guild_id=None):
        # Iterate over all guilds that have a mixer or a queue
        if guild_id:
            guild_ids = [str(guild_id)]
        else:
            guild_ids = set(list(self.queue.keys()) + list(self.current_track.keys()))

        for guild_id_str in guild_ids:
            # Check if we have a current track
            track = self.current_track.get(guild_id_str)

            # If track exists and is finished, or if no track but queue has items
            if (track and track.finished) or (not track and guild_id_str in self.queue and self.queue[guild_id_str]):
                # If finished, clear it
                if track and track.finished:
                    self.current_track.pop(guild_id_str, None)
                    track = None

                # Play next if available
                if not track and guild_id_str in self.queue and self.queue[guild_id_str]:
                    next_song = self.queue[guild_id_str].pop(0)
                    await self._play_song(guild_id_str, next_song)
                else:
                    # Queue finished, refresh dashboard to show empty state
                    await self.refresh_dashboard(guild_id=guild_id_str)

    async def _play_song(self, guild_id, song_info):
        mixer = guild_mixers.get(str(guild_id))

        # Ensure mixer exists and is playing
        guild = self.bot.get_guild(int(guild_id))
        if not guild: return

        if not mixer:
            mixer = MixingAudioSource()
            guild_mixers[str(guild_id)] = mixer

        if guild.voice_client:
             is_playing_mixer = False
             if guild.voice_client.is_playing() and isinstance(guild.voice_client.source, discord.PCMVolumeTransformer):
                 if guild.voice_client.source.original == mixer:
                     is_playing_mixer = True

             if not is_playing_mixer:
                 if guild.voice_client.is_playing():
                     guild.voice_client.stop()
                 # Mixer handles volume per track now
                 source = discord.PCMVolumeTransformer(mixer, volume=1.0)
                 guild.voice_client.play(source)

        url = song_info['url']
        original_url = song_info.get('original_url', url)
        # Double check blacklist (in case it was added while in queue)
        if original_url in self.blacklist:
            # Could notify, but no context here
            return

        # Retrieve music volume
        vol_data = server_volumes.get(str(guild_id), {'music': 1.0, 'soundboard': 0.5})
        music_vol = vol_data.get('music', 1.0)

        # Add metadata for tracking
        song_info['type'] = 'music'

        track = mixer.add_track(
            file_path=url,
            is_url=True,
            metadata=song_info,
            volume=music_vol,
            before_options=FFMPEG_OPTIONS['before_options'],
            options=FFMPEG_OPTIONS['options'],
            on_finish=partial(self._on_track_finish, str(guild_id))
        )
        self.current_track[str(guild_id)] = track

        # Update Dashboard
        await self.refresh_dashboard(guild_id=str(guild_id))

    # --- Dashboard Helpers ---

    async def refresh_dashboard(self, interaction=None, guild_id=None):
        if interaction:
            guild_id = str(interaction.guild.id)

        if not guild_id: return

        # 1. Update Existing Message
        message = self.dashboard_messages.get(guild_id)
        view = MusicView(self, guild_id)
        embed = view.get_embed()

        if message:
            try:
                await message.edit(embed=embed, view=view)
            except discord.NotFound:
                self.dashboard_messages.pop(guild_id, None)
                message = None
            except Exception as e:
                print(f"Error updating dashboard: {e}")

        # 2. Handle Interaction (Button click)
        if interaction:
            if not interaction.response.is_done():
                if message:
                    await interaction.response.defer() # Just acknowledge
                else:
                    # If message was lost, send new one as response
                    await interaction.response.send_message(embed=embed, view=view)
                    self.dashboard_messages[guild_id] = await interaction.original_response()
            else:
                # Interaction already handled (e.g. by command), but maybe we need to followup?
                # Usually play command handles sending the first message.
                pass

    async def toggle_pause(self, interaction):
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if track:
            track.paused = not track.paused
            state = "Paused" if track.paused else "Resumed"
            # Feedback only if direct command or button needs it (refresh_dashboard handles defer if not done)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"⏯️ {state}.", ephemeral=True)

            await self.refresh_dashboard(interaction)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    async def skip_track(self, interaction):
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if track:
            track.finished = True
            if not interaction.response.is_done():
                await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)
            await self._process_queue(guild_id)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    async def stop_music(self, interaction):
        guild_id = str(interaction.guild.id)

        # Clear queue and track
        if guild_id in self.queue: del self.queue[guild_id]
        if guild_id in self.current_track: del self.current_track[guild_id]

        # Stop Voice
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()

        if guild_id in guild_mixers:
            guild_mixers.pop(guild_id).cleanup()

        if not interaction.response.is_done():
            await interaction.response.send_message("⏹️ Stopped.", ephemeral=True)

        # Update Dashboard to "Empty" state
        await self.refresh_dashboard(interaction)
        # Maybe delete dashboard message?
        # self.dashboard_messages.pop(guild_id, None)

    async def toggle_loop(self, interaction):
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if track:
            track.loop = not track.loop
            state = "ON" if track.loop else "OFF"
            if not interaction.response.is_done():
                await interaction.response.send_message(f"🔁 Loop {state}.", ephemeral=True)
            await self.refresh_dashboard(interaction)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    async def shuffle_queue(self, interaction):
        guild_id = str(interaction.guild.id)
        if guild_id in self.queue and len(self.queue[guild_id]) > 1:
            random.shuffle(self.queue[guild_id])
            if not interaction.response.is_done():
                await interaction.response.send_message("🔀 Queue shuffled.", ephemeral=True)
            await self.refresh_dashboard(interaction)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message("Not enough songs to shuffle.", ephemeral=True)

    # --- Slash Commands ---

    @app_commands.command(name="play", description="▶️ Plays a song from YouTube.")
    @app_commands.describe(query="The song name or URL to play")
    async def play(self, interaction: discord.Interaction, query: str):
        """🎵 Plays a song from YouTube."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.")
            return

        # Defer immediately to prevent timeout if connect takes too long
        await interaction.response.defer()

        if not interaction.guild.voice_client:
            if interaction.user.voice:
                await interaction.user.voice.channel.connect()
            else:
                await interaction.followup.send("You are not connected to a voice channel.")
                return

        # Check for cookies file
        opts = YTDL_OPTIONS.copy()
        if os.path.isfile('cookies/cookies.txt'):
            opts['cookiefile'] = 'cookies/cookies.txt'

        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                # Run blocking call in executor
                info = await self.bot.loop.run_in_executor(
                    None,
                    partial(ydl.extract_info, query, download=False)
                )

                if 'entries' in info:
                    info = info['entries'][0]

                url = info['url']
                title = info['title']
                thumbnail = info.get('thumbnail', '')
                original_url = info.get('webpage_url', url)
                duration = info.get('duration')

                if original_url in self.blacklist:
                    await interaction.followup.send(f"❌ This song is blacklisted: {title}")
                    return

                song_info = {
                    'title': title,
                    'url': url,
                    'original_url': original_url,
                    'thumbnail': thumbnail,
                    'duration': duration,
                    'requested_by': interaction.user.display_name
                }

                guild_id = str(interaction.guild.id)
                if guild_id not in self.queue:
                    self.queue[guild_id] = []

                self.queue[guild_id].append(song_info)

                # Send Dashboard
                view = MusicView(self, guild_id)
                embed = view.get_embed()

                # If we already have a dashboard, delete it to send a fresh one at bottom
                old_msg = self.dashboard_messages.get(guild_id)
                if old_msg:
                    try: await old_msg.delete()
                    except: pass

                msg = await interaction.followup.send(embed=embed, view=view)
                self.dashboard_messages[guild_id] = msg

                if not self.current_track.get(guild_id):
                    await self._process_queue(guild_id) # Trigger immediately

            except Exception as e:
                await interaction.followup.send(f"An error occurred: {e}")

    @app_commands.command(name="skip", description="⏭️ Skips the current song.")
    async def skip(self, interaction: discord.Interaction):
        """⏭️ Skips the current song."""
        await self.skip_track(interaction)

    @app_commands.command(name="stop", description="🛑 Stops music, clears queue, and disconnects.")
    async def stop(self, interaction: discord.Interaction):
        """🛑 Stops music, clears queue, and disconnects."""
        await self.stop_music(interaction)

    @app_commands.command(name="pause", description="⏸️ Pauses the current song.")
    async def pause(self, interaction: discord.Interaction):
        """⏸️ Pauses the current song."""
        await self.toggle_pause(interaction)

    @app_commands.command(name="resume", description="▶️ Resumes the current song.")
    async def resume(self, interaction: discord.Interaction):
        """▶️ Resumes the current song."""
        await self.toggle_pause(interaction)

    @app_commands.command(name="shuffle", description="🔀 Shuffles the queue.")
    async def shuffle(self, interaction: discord.Interaction):
        """🔀 Shuffles the queue."""
        await self.shuffle_queue(interaction)

    @app_commands.command(name="volume", description="🔊 Sets the music volume (0-100). Persists per server.")
    @app_commands.describe(vol="Volume level (0-100)")
    async def volume(self, interaction: discord.Interaction, vol: int):
        """🔊 Sets the music volume (0-100). Persists per server."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        new_vol = max(0, min(100, vol)) / 100

        # Update persistent storage
        if guild_id not in server_volumes:
            server_volumes[guild_id] = {'music': 1.0, 'soundboard': 0.5}

        server_volumes[guild_id]['music'] = new_vol
        await save_server_volumes(server_volumes)

        track = self.current_track.get(guild_id)
        if track:
            track.volume = new_vol
            await self.refresh_dashboard(interaction)
        else:
            await interaction.response.send_message(f"🔊 Music volume set to {vol}% (will apply to next song)", ephemeral=True)

    @app_commands.command(name="loop", description="🔁 Toggles loop for the current song.")
    async def loop(self, interaction: discord.Interaction):
        """🔁 Toggles loop for the current song."""
        await self.toggle_loop(interaction)

    @app_commands.command(name="queue", description="🎼 Shows the current queue.")
    async def queue(self, interaction: discord.Interaction):
        """🎼 Shows the current queue."""
        # We can just send the dashboard embed ephemerally if they ask for queue
        guild_id = str(interaction.guild.id)
        view = MusicView(self, guild_id)
        embed = view.get_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="nowplaying", description="🎵 Shows the currently playing song.")
    async def nowplaying(self, interaction: discord.Interaction):
        """💿 Shows the currently playing song."""
        guild_id = str(interaction.guild.id)
        view = MusicView(self, guild_id)
        embed = view.get_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Music(bot))
