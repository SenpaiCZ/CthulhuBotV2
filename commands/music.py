import discord
from discord.ext import commands, tasks
import asyncio
import os
import yt_dlp
from functools import partial
from dashboard.app import guild_mixers, guild_volumes
from dashboard.audio_mixer import MixingAudioSource
from loadnsave import load_music_blacklist, save_music_blacklist

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
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # guild_id -> list of dicts {title, url, thumbnail, ...}
        self.queue = {}
        # guild_id -> current Track object
        self.current_track = {}
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
        self.check_queue_task.start()

    def cog_unload(self):
        self.check_queue_task.cancel()

    @tasks.loop(seconds=5)
    async def check_queue_task(self):
        await self._process_queue()

    async def _process_queue(self):
        # Iterate over all guilds that have a mixer or a queue
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

    @check_queue_task.before_loop
    async def before_check_queue(self):
        await self.bot.wait_until_ready()

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
                 master_vol = guild_volumes.get(str(guild_id), 0.5)
                 source = discord.PCMVolumeTransformer(mixer, volume=master_vol)
                 guild.voice_client.play(source)

        url = song_info['url']
        original_url = song_info.get('original_url', url)
        # Double check blacklist (in case it was added while in queue)
        if original_url in self.blacklist:
            # Could notify, but no context here
            return

        track = mixer.add_track(
            file_path=url,
            is_url=True,
            metadata=song_info,
            before_options=FFMPEG_OPTIONS['before_options'],
            options=FFMPEG_OPTIONS['options']
        )
        self.current_track[str(guild_id)] = track

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, query: str):
        """Plays a song from YouTube."""
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                return

        async with ctx.typing():
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

                    if original_url in self.blacklist:
                        await ctx.send(f"❌ This song is blacklisted: {title}")
                        return

                    song_info = {
                        'title': title,
                        'url': url,
                        'original_url': original_url,
                        'thumbnail': thumbnail,
                        'requested_by': ctx.author.display_name
                    }

                    guild_id = str(ctx.guild.id)
                    if guild_id not in self.queue:
                        self.queue[guild_id] = []

                    self.queue[guild_id].append(song_info)

                    if not self.current_track.get(guild_id):
                        await ctx.send(f"🎵 Added to queue and playing: **{title}**")
                        await self._process_queue() # Trigger immediately
                    else:
                        await ctx.send(f"🎵 Added to queue: **{title}**")

                except Exception as e:
                    await ctx.send(f"An error occurred: {e}")

    @commands.command(aliases=['s'])
    async def skip(self, ctx):
        """Skips the current song."""
        guild_id = str(ctx.guild.id)
        track = self.current_track.get(guild_id)
        if track:
            track.finished = True # Mark finished
            await ctx.send("⏭️ Skipped.")
            await self._process_queue() # Trigger immediately
        else:
            await ctx.send("Nothing is playing.")

    @commands.command(aliases=['leave', 'disconnect', 'dc'])
    async def stop(self, ctx):
        """Stops music, clears queue, and disconnects."""
        guild_id = str(ctx.guild.id)

        # Clear queue and current track
        if guild_id in self.queue:
            del self.queue[guild_id]
        if guild_id in self.current_track:
            del self.current_track[guild_id]

        # Disconnect from voice
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

        # Cleanup mixer
        if guild_id in guild_mixers:
            mixer = guild_mixers.pop(guild_id)
            mixer.cleanup()

        await ctx.send("🛑 Stopped playing, cleared queue, and disconnected.")

    @commands.command(aliases=['vol'])
    async def volume(self, ctx, vol: int):
        """Sets the volume of the current song (0-100)."""
        guild_id = str(ctx.guild.id)
        track = self.current_track.get(guild_id)
        if track:
            new_vol = max(0, min(100, vol)) / 100
            track.volume = new_vol
            await ctx.send(f"🔊 Volume set to {vol}%")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command()
    async def loop(self, ctx):
        """Toggles loop for the current song."""
        guild_id = str(ctx.guild.id)
        track = self.current_track.get(guild_id)
        if track:
            track.loop = not track.loop
            state = "enabled" if track.loop else "disabled"
            await ctx.send(f"🔁 Loop {state}.")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        """Shows the current queue."""
        guild_id = str(ctx.guild.id)
        q = self.queue.get(guild_id, [])
        if not q and not self.current_track.get(guild_id):
            await ctx.send("Queue is empty.")
            return

        embed = discord.Embed(title="Music Queue")

        curr = self.current_track.get(guild_id)
        if curr:
            embed.add_field(name="Now Playing", value=f"[{curr.metadata.get('title')}]({curr.metadata.get('original_url')})", inline=False)

        if q:
            desc = ""
            for i, song in enumerate(q[:10], 1):
                desc += f"{i}. [{song['title']}]({song['original_url']})\n"
            if len(q) > 10:
                desc += f"...and {len(q)-10} more."
            embed.description = desc

        await ctx.send(embed=embed)

    @commands.command(aliases=['np'])
    async def nowplaying(self, ctx):
        """Shows the currently playing song."""
        guild_id = str(ctx.guild.id)
        curr = self.current_track.get(guild_id)
        if curr:
            await ctx.send(f"🎶 Now Playing: **{curr.metadata.get('title')}**")
        else:
            await ctx.send("Nothing is playing.")

async def setup(bot):
    await bot.add_cog(Music(bot))
