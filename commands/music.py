import datetime
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
import time
import yt_dlp
import random
from functools import partial
from dashboard.app import guild_mixers, server_volumes
from dashboard.audio_mixer import MixingAudioSource
from loadnsave import (
    load_music_blacklist, save_music_blacklist,
    load_server_volumes, save_server_volumes,
)
from commands._music_view import MusicView, _fmt_duration

# ── yt-dlp options ────────────────────────────────────────────────────────────

YTDL_BASE = {
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
    'socket_timeout': 30,
    'source_address': '0.0.0.0',
}

YTDL_PLAYLIST = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': 'in_playlist',
    'noplaylist': False,
    'ignoreerrors': True,
    'socket_timeout': 30,
}

FFMPEG_OPTIONS = {
    'before_options': (
        '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 '
        '-reconnect_on_network_error 1 -reconnect_on_http_error 4xx,5xx '
        '-timeout 10000000'
    ),
    'options': '-vn',
}

IDLE_TIMEOUT = 300  # 5 minutes before auto-disconnect
DASHBOARD_REFRESH = 20  # seconds between progress-bar updates


def _is_playlist_url(query: str) -> bool:
    return 'list=' in query or '/playlist' in query


async def _delete_after(message, delay: float):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


def _ytdl_opts_with_cookies(base: dict) -> dict:
    opts = base.copy()
    if os.path.isfile('cookies/cookies.txt'):
        opts['cookiefile'] = 'cookies/cookies.txt'
    return opts


COOKIES_DIR = 'cookies'
COOKIES_FILE = os.path.join(COOKIES_DIR, 'cookies.txt')

COOKIE_INSTRUCTIONS = (
    "**How to get your YouTube cookies:**\n"
    "1. Install the **Get cookies.txt LOCALLY** extension (Chrome/Firefox)\n"
    "2. Go to **youtube.com** while logged in to your Google account\n"
    "3. Click the extension icon → select **youtube.com** → click **Export**\n"
    "4. Open the downloaded `.txt` file, copy **all** contents and paste below\n\n"
    "The file starts with `# Netscape HTTP Cookie File`.\n"
    "Cookies are used only for age-restricted video playback."
)


class CookieModal(discord.ui.Modal, title="Set YouTube Cookies"):
    cookie_data = discord.ui.TextInput(
        label="Paste cookies.txt content here",
        style=discord.TextStyle.paragraph,
        placeholder="# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\t...",
        max_length=4000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        content = self.cookie_data.value.strip()
        if not content.startswith('# Netscape HTTP Cookie File') and '.youtube.com' not in content:
            return await interaction.response.send_message(
                "❌ Doesn't look like a valid Netscape cookie file. "
                "Make sure you copied the full contents of the exported `.txt` file.",
                ephemeral=True
            )
        os.makedirs(COOKIES_DIR, exist_ok=True)
        with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        await interaction.response.send_message(
            "✅ YouTube cookies saved! Try `/play` again — age-restricted videos should now work.",
            ephemeral=True
        )


class CookieView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Set YouTube Cookie", emoji="🍪", style=discord.ButtonStyle.primary)
    async def set_cookie_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Admins only.", ephemeral=True)
        await interaction.response.send_modal(CookieModal())


# ── Cog ──────────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Music"

        # guild_id (str) → list of song_info dicts
        self.queue: dict[str, list] = {}
        # guild_id (str) → Track object
        self.current_track: dict[str, object] = {}
        # guild_id (str) → dashboard Message object
        self.dashboard_messages: dict[str, discord.Message] = {}
        # guild_id (str) → blacklisted original_url list (loaded lazily)
        self.blacklist: list[str] = []
        # guild_id (str) → monotonic time when queue went empty
        self.idle_since: dict[str, float] = {}

        self.bot.music_cog = self

        self._idle_disconnect.start()
        self._refresh_dashboards.start()

    def cog_unload(self):
        self._idle_disconnect.cancel()
        self._refresh_dashboards.cancel()

    # ── Background tasks ──────────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _idle_disconnect(self):
        now = time.monotonic()
        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                self.idle_since.pop(guild_id, None)
                continue

            track = self.current_track.get(guild_id)
            has_queue = bool(self.queue.get(guild_id))

            if (not track or track.finished) and not has_queue:
                if guild_id not in self.idle_since:
                    self.idle_since[guild_id] = now
                elif now - self.idle_since[guild_id] >= IDLE_TIMEOUT:
                    self.idle_since.pop(guild_id, None)
                    await self._cleanup_guild(guild_id, disconnect=True)
                    try:
                        await vc.disconnect(force=False)
                    except Exception:
                        pass
                    await self._update_dashboard_for_guild(guild_id)
            else:
                self.idle_since.pop(guild_id, None)

    @_idle_disconnect.before_loop
    async def _before_idle(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=DASHBOARD_REFRESH)
    async def _refresh_dashboards(self):
        """Periodically refresh dashboard embeds so the progress bar updates."""
        for guild_id, msg in list(self.dashboard_messages.items()):
            track = self.current_track.get(guild_id)
            # Only refresh if a track is actively playing with a known duration
            if not track or track.finished or track.paused:
                continue
            if not track.metadata.get('duration'):
                continue
            try:
                view = MusicView(self, guild_id)
                embed = view.get_embed()
                await msg.edit(embed=embed, view=view)
            except discord.NotFound:
                self.dashboard_messages.pop(guild_id, None)
            except discord.HTTPException:
                pass
            except Exception:
                pass
            # Small delay between guilds to stay under rate limits
            await asyncio.sleep(0.5)

    @_refresh_dashboards.before_loop
    async def _before_refresh(self):
        await self.bot.wait_until_ready()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _cleanup_guild(self, guild_id: str, disconnect: bool = False):
        """Remove mixer/track/queue state for a guild."""
        self.current_track.pop(guild_id, None)
        self.queue.pop(guild_id, None)
        mixer = guild_mixers.pop(guild_id, None)
        if mixer:
            mixer.cleanup()

    async def _ensure_voice(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
        """Join/return voice client, or send an error and return None."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You need to be in a voice channel first.", ephemeral=True
            )
            return None

        channel = interaction.user.voice.channel
        vc = interaction.guild.voice_client

        if vc:
            if vc.channel != channel:
                await vc.move_to(channel)
            return vc

        try:
            return await channel.connect(timeout=15, reconnect=True)
        except asyncio.TimeoutError:
            await interaction.response.send_message(
                "❌ Timed out connecting to voice. Try again.", ephemeral=True
            )
            return None
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Could not connect to voice: {e}", ephemeral=True
            )
            return None

    def _get_volume(self, guild_id: str) -> float:
        return server_volumes.get(guild_id, {}).get('music', 0.5)

    async def _resolve_stream_url(self, webpage_url: str) -> dict | None:
        """Resolve a YouTube page URL to a direct stream URL via yt-dlp."""
        opts = _ytdl_opts_with_cookies(YTDL_BASE)
        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(webpage_url, download=False)
        try:
            info = await self.bot.loop.run_in_executor(None, _extract)
            if not info:
                return None
            if 'entries' in info:
                info = info['entries'][0]
            return info
        except Exception as e:
            print(f"[Music] resolve_stream_url error: {e}")
            return None

    def _on_track_finish(self, guild_id: str):
        """Called from audio thread when a track naturally ends."""
        coro = self._process_queue(guild_id)
        asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

    async def _process_queue(self, guild_id: str):
        """Advance to next song or update dashboard when queue is empty."""
        track = self.current_track.get(guild_id)
        if track and track.finished:
            self.current_track.pop(guild_id, None)

        if self.queue.get(guild_id):
            next_song = self.queue[guild_id].pop(0)
            await self._play_song(guild_id, next_song)
        else:
            # Queue exhausted — update dashboard to "idle" state
            await self._update_dashboard_for_guild(guild_id)

    async def _play_song(self, guild_id: str, song_info: dict):
        """Resolve (if needed) and play a song in the guild's voice channel."""
        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return

        # Lazy resolution for playlist tracks that only have webpage_url
        if song_info.get('needs_resolve'):
            info = await self._resolve_stream_url(song_info['webpage_url'])
            if not info:
                print(f"[Music] Could not resolve track: {song_info.get('title')}, skipping.")
                await self._process_queue(guild_id)
                return
            song_info['url'] = info['url']
            song_info['thumbnail'] = info.get('thumbnail', song_info.get('thumbnail', ''))
            song_info['duration'] = info.get('duration', song_info.get('duration'))
            song_info['needs_resolve'] = False

        # Set up mixer
        mixer = guild_mixers.get(guild_id)
        if not mixer:
            mixer = MixingAudioSource()
            guild_mixers[guild_id] = mixer

        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return

        # Ensure the mixer is what's playing on the voice client
        if not vc.is_playing() or not (
            isinstance(vc.source, discord.PCMVolumeTransformer)
            and vc.source.original is mixer
        ):
            vc.stop()
            source = discord.PCMVolumeTransformer(mixer, volume=1.0)
            vc.play(source, after=lambda e: print(f"[Music] Voice error: {e}") if e else None)

        music_vol = self._get_volume(guild_id)
        track = mixer.add_track(
            file_path=song_info['url'],
            is_url=True,
            metadata=song_info,
            volume=music_vol,
            before_options=FFMPEG_OPTIONS['before_options'],
            options=FFMPEG_OPTIONS['options'],
            on_finish=partial(self._on_track_finish, guild_id),
        )
        self.current_track[guild_id] = track
        await self._update_dashboard_for_guild(guild_id)

    async def _update_dashboard_for_guild(self, guild_id: str):
        """Edit the existing dashboard message if one exists."""
        msg = self.dashboard_messages.get(guild_id)
        if not msg:
            return
        try:
            view = MusicView(self, guild_id)
            embed = view.get_embed()
            await msg.edit(embed=embed, view=view)
        except discord.NotFound:
            self.dashboard_messages.pop(guild_id, None)
        except Exception:
            pass

    async def refresh_dashboard(self, interaction: discord.Interaction | None = None,
                                guild_id: str | None = None):
        """Send or update the dashboard. Called by button handlers."""
        if interaction:
            guild_id = str(interaction.guild.id)
        if not guild_id:
            return

        msg = self.dashboard_messages.get(guild_id)
        view = MusicView(self, guild_id)
        embed = view.get_embed()

        if msg:
            try:
                await msg.edit(embed=embed, view=view)
                if interaction and not interaction.response.is_done():
                    await interaction.response.defer()
                return
            except discord.NotFound:
                self.dashboard_messages.pop(guild_id, None)
                msg = None

        if interaction and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=view)
            self.dashboard_messages[guild_id] = await interaction.original_response()

    # ── Button-handler methods (called by MusicView) ──────────────────────────

    async def toggle_pause(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            if not interaction.response.is_done():
                await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        track.paused = not track.paused
        await self.refresh_dashboard(interaction)

    async def skip_track(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            if not interaction.response.is_done():
                await interaction.response.send_message("Nothing to skip.", ephemeral=True)
            return
        if not interaction.response.is_done():
            await interaction.response.defer()
        track.finished = True
        await self._process_queue(guild_id)

    async def stop_music(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        vc = interaction.guild.voice_client
        if vc and vc.is_connected():
            vc.stop()
            await vc.disconnect(force=False)
        await self._cleanup_guild(guild_id)
        if not interaction.response.is_done():
            await interaction.response.send_message("⏹️ Stopped and disconnected.", ephemeral=True)
        await self._update_dashboard_for_guild(guild_id)

    async def toggle_loop(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            if not interaction.response.is_done():
                await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        track.loop = not track.loop
        state = "ON" if track.loop else "OFF"
        if not interaction.response.is_done():
            await interaction.response.send_message(f"🔁 Loop {state}.", ephemeral=True)
        await self._update_dashboard_for_guild(guild_id)

    async def shuffle_queue(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        if guild_id in self.queue and len(self.queue[guild_id]) > 1:
            random.shuffle(self.queue[guild_id])
            if not interaction.response.is_done():
                await interaction.response.send_message("🔀 Queue shuffled.", ephemeral=True)
            await self._update_dashboard_for_guild(guild_id)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message("Not enough songs to shuffle.", ephemeral=True)

    # ── Slash commands ────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="▶️ Play a song or playlist by URL or search query.")
    @app_commands.describe(query="YouTube URL, playlist URL, or search terms")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.guild:
            return await interaction.response.send_message("Servers only.", ephemeral=True)

        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        await interaction.response.defer()

        guild_id = str(interaction.guild.id)
        if guild_id not in self.queue:
            self.queue[guild_id] = []

        # Load blacklist once
        if not self.blacklist:
            self.blacklist = await load_music_blacklist() or []

        is_playlist = _is_playlist_url(query)

        try:
            if is_playlist:
                # Fast flat extraction for playlists
                opts = _ytdl_opts_with_cookies(YTDL_PLAYLIST)
                def _extract_playlist():
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(query, download=False)

                info = await self.bot.loop.run_in_executor(None, _extract_playlist)

                if not info:
                    return await interaction.followup.send("❌ Could not load that playlist.")

                entries = info.get('entries') or []
                entries = [e for e in entries if e and e.get('url')]

                if not entries:
                    return await interaction.followup.send("❌ No playable tracks found in that playlist.")

                added = 0
                for entry in entries:
                    orig = entry.get('url', '')
                    if orig in self.blacklist:
                        continue
                    self.queue[guild_id].append({
                        'title': entry.get('title', 'Unknown'),
                        'url': None,
                        'webpage_url': orig,
                        'original_url': orig,
                        'thumbnail': entry.get('thumbnail', ''),
                        'duration': entry.get('duration'),
                        'requested_by': interaction.user.display_name,
                        'needs_resolve': True,
                    })
                    added += 1

                playlist_title = info.get('title', 'Playlist')
                embed = discord.Embed(
                    title="📥 Playlist Added",
                    description=f"**{playlist_title}**\n{added} tracks queued",
                    color=discord.Color.blurple(),
                )
                msg = await interaction.followup.send(embed=embed)
                asyncio.create_task(_delete_after(msg, 10))

            else:
                # Single track — full extraction
                opts = _ytdl_opts_with_cookies(YTDL_BASE)
                def _extract_single():
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(query, download=False)

                info = await self.bot.loop.run_in_executor(None, _extract_single)

                if not info:
                    return await interaction.followup.send("❌ No results found.")

                if 'entries' in info:
                    entry = next((e for e in info['entries'] if e), None)
                    if not entry:
                        return await interaction.followup.send("❌ No playable result found.")
                    info = entry

                original_url = info.get('webpage_url', info.get('url', ''))
                if original_url in self.blacklist:
                    return await interaction.followup.send(
                        f"❌ **{info.get('title', 'That track')}** is blacklisted."
                    )

                song_info = {
                    'title': info.get('title', 'Unknown'),
                    'url': info.get('url', ''),
                    'original_url': original_url,
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration'),
                    'requested_by': interaction.user.display_name,
                    'needs_resolve': False,
                }
                self.queue[guild_id].append(song_info)

                # If something is playing, send "added to queue" notification
                current = self.current_track.get(guild_id)
                if current and not current.finished:
                    pos = len(self.queue[guild_id])
                    dur = song_info['duration']
                    embed = discord.Embed(
                        title="📥 Added to Queue",
                        description=f"[{song_info['title']}]({original_url})",
                        color=discord.Color.blurple(),
                    )
                    if dur:
                        embed.add_field(name="Duration", value=_fmt_duration(dur), inline=True)
                    embed.add_field(name="Position", value=f"#{pos}", inline=True)
                    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
                    if song_info['thumbnail']:
                        embed.set_thumbnail(url=song_info['thumbnail'])
                    msg = await interaction.followup.send(embed=embed)
                    asyncio.create_task(_delete_after(msg, 15))
                    await self._update_dashboard_for_guild(guild_id)
                    return  # Don't replace dashboard; just update queue section

        except yt_dlp.utils.DownloadError as e:
            err = str(e)
            if 'Sign in' in err or 'age' in err.lower() or 'login' in err.lower():
                cookie_exists = os.path.exists(COOKIES_FILE)
                embed = discord.Embed(
                    title="🔞 Age-Restricted Content",
                    description=(
                        "This video requires a YouTube login to play.\n\n"
                        + ("⚠️ Cookies are set but may be expired — try refreshing them.\n\n" if cookie_exists else "")
                        + COOKIE_INSTRUCTIONS
                    ),
                    color=discord.Color.orange()
                )
                return await interaction.followup.send(embed=embed, view=CookieView(), ephemeral=True)
            elif 'Private' in err or 'private' in err:
                msg = "❌ That video is private."
            elif 'unavailable' in err.lower():
                msg = "❌ Video is unavailable."
            else:
                msg = f"❌ Download error: {err[:200]}"
            return await interaction.followup.send(msg)
        except Exception as e:
            return await interaction.followup.send(f"❌ Unexpected error: {type(e).__name__}: {str(e)[:200]}")

        # Delete old dashboard and send fresh one
        old_msg = self.dashboard_messages.get(guild_id)
        if old_msg:
            try:
                await old_msg.delete()
            except Exception:
                pass
            self.dashboard_messages.pop(guild_id, None)

        view = MusicView(self, guild_id)
        embed = view.get_embed()
        msg = await interaction.followup.send(embed=embed, view=view)
        self.dashboard_messages[guild_id] = msg

        # Start playback if nothing is playing
        if not self.current_track.get(guild_id):
            next_song = self.queue[guild_id].pop(0)
            await self._play_song(guild_id, next_song)

    @app_commands.command(name="setytcookie", description="🍪 Set YouTube cookies for age-restricted playback. (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setytcookie(self, interaction: discord.Interaction):
        cookie_status = ""
        if os.path.exists(COOKIES_FILE):
            mtime = os.path.getmtime(COOKIES_FILE)
            age_days = (datetime.datetime.now() - datetime.datetime.fromtimestamp(mtime)).days
            cookie_status = f"✅ Cookies already set (last updated {age_days}d ago). Submit new ones to replace.\n\n"
        embed = discord.Embed(
            title="🍪 YouTube Cookie Setup",
            description=cookie_status + COOKIE_INSTRUCTIONS,
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, view=CookieView(), ephemeral=True)

    @app_commands.command(name="playnext", description="⏩ Insert a song to play next in the queue.")
    @app_commands.describe(query="YouTube URL or search terms")
    async def playnext(self, interaction: discord.Interaction, query: str):
        if not interaction.guild:
            return await interaction.response.send_message("Servers only.", ephemeral=True)

        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        await interaction.response.defer()

        guild_id = str(interaction.guild.id)
        if guild_id not in self.queue:
            self.queue[guild_id] = []

        opts = _ytdl_opts_with_cookies(YTDL_BASE)
        try:
            def _extract():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(query, download=False)

            info = await self.bot.loop.run_in_executor(None, _extract)
            if not info:
                return await interaction.followup.send("❌ No results found.")
            if 'entries' in info:
                info = next((e for e in info['entries'] if e), None)
            if not info:
                return await interaction.followup.send("❌ No results found.")

            original_url = info.get('webpage_url', info.get('url', ''))
            song_info = {
                'title': info.get('title', 'Unknown'),
                'url': info.get('url', ''),
                'original_url': original_url,
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration'),
                'requested_by': interaction.user.display_name,
                'needs_resolve': False,
            }
            self.queue[guild_id].insert(0, song_info)

            embed = discord.Embed(
                title="⏩ Playing Next",
                description=f"[{song_info['title']}]({original_url})",
                color=discord.Color.green(),
            )
            if song_info['duration']:
                embed.add_field(name="Duration", value=_fmt_duration(song_info['duration']))
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            if song_info['thumbnail']:
                embed.set_thumbnail(url=song_info['thumbnail'])
            msg = await interaction.followup.send(embed=embed)
            asyncio.create_task(_delete_after(msg, 10))
            await self._update_dashboard_for_guild(guild_id)

            if not self.current_track.get(guild_id):
                next_song = self.queue[guild_id].pop(0)
                await self._play_song(guild_id, next_song)

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {type(e).__name__}: {str(e)[:200]}")

    @app_commands.command(name="pause", description="⏸️ Pause the current song.")
    async def pause(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            return await interaction.response.send_message("Nothing is playing.", ephemeral=True)
        if track.paused:
            return await interaction.response.send_message("Already paused.", ephemeral=True)
        track.paused = True
        await self.refresh_dashboard(interaction)

    @app_commands.command(name="resume", description="▶️ Resume the paused song.")
    async def resume(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            return await interaction.response.send_message("Nothing to resume.", ephemeral=True)
        if not track.paused:
            return await interaction.response.send_message("Not paused.", ephemeral=True)
        track.paused = False
        await self.refresh_dashboard(interaction)

    @app_commands.command(name="skip", description="⏭️ Skip the current song.")
    async def skip(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            return await interaction.response.send_message("Nothing to skip.", ephemeral=True)
        await interaction.response.defer()
        track.finished = True
        await self._process_queue(guild_id)

    @app_commands.command(name="stop", description="⏹️ Stop music and disconnect from voice.")
    async def stop(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        vc = interaction.guild.voice_client
        if vc and vc.is_connected():
            vc.stop()
            await vc.disconnect(force=False)
        await self._cleanup_guild(guild_id)
        await interaction.response.send_message("⏹️ Stopped and disconnected.", ephemeral=True)
        await self._update_dashboard_for_guild(guild_id)

    @app_commands.command(name="volume", description="🔊 Set music volume (0–100).")
    @app_commands.describe(vol="Volume level 0–100")
    async def volume(self, interaction: discord.Interaction, vol: int):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        clamped = max(0, min(100, vol))
        new_vol = clamped / 100.0

        if guild_id not in server_volumes:
            server_volumes[guild_id] = {'music': 1.0, 'soundboard': 0.5}
        server_volumes[guild_id]['music'] = new_vol
        await save_server_volumes(server_volumes)

        track = self.current_track.get(guild_id)
        if track and not track.finished:
            track.volume = new_vol

        await interaction.response.send_message(
            f"🔊 Volume set to **{clamped}%**", ephemeral=True
        )
        await self._update_dashboard_for_guild(guild_id)

    @app_commands.command(name="loop", description="🔁 Toggle looping the current song.")
    async def loop(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        await self.toggle_loop(interaction)

    @app_commands.command(name="queue", description="📚 Show the current queue.")
    async def queue_cmd(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        view = MusicView(self, guild_id)
        embed = view.get_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="nowplaying", description="🎵 Show what's currently playing.")
    async def nowplaying(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        view = MusicView(self, guild_id)
        embed = view.get_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="remove", description="🗑️ Remove a song from the queue by position.")
    @app_commands.describe(position="Queue position to remove (1 = next up)")
    async def remove(self, interaction: discord.Interaction, position: int):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        q = self.queue.get(guild_id, [])
        if not q:
            return await interaction.response.send_message("Queue is empty.", ephemeral=True)
        if position < 1 or position > len(q):
            return await interaction.response.send_message(
                f"Position must be 1–{len(q)}.", ephemeral=True
            )
        removed = q.pop(position - 1)
        await interaction.response.send_message(
            f"🗑️ Removed **{removed.get('title', 'Unknown')}** from queue.", ephemeral=True
        )
        await self._update_dashboard_for_guild(guild_id)

    @app_commands.command(name="clear", description="🧹 Clear the queue without stopping current song.")
    async def clear(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        self.queue[guild_id] = []
        await interaction.response.send_message("🧹 Queue cleared.", ephemeral=True)
        await self._update_dashboard_for_guild(guild_id)

    @app_commands.command(name="blacklist", description="🚫 Blacklist the currently playing song.")
    async def blacklist_cmd(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            return await interaction.response.send_message("Nothing is playing.", ephemeral=True)

        url = track.metadata.get('original_url', '')
        title = track.metadata.get('title', 'Unknown')
        if url and url not in self.blacklist:
            self.blacklist.append(url)
            await save_music_blacklist(self.blacklist)

        track.finished = True
        await interaction.response.send_message(
            f"🚫 **{title}** blacklisted and skipped.", ephemeral=True
        )
        await self._process_queue(guild_id)

    @app_commands.command(name="unblacklist", description="✅ Remove a URL from the music blacklist.")
    @app_commands.describe(url="The YouTube URL to remove from the blacklist")
    async def unblacklist(self, interaction: discord.Interaction, url: str):
        if url in self.blacklist:
            self.blacklist.remove(url)
            await save_music_blacklist(self.blacklist)
            await interaction.response.send_message(f"✅ Removed from blacklist.", ephemeral=True)
        else:
            await interaction.response.send_message("That URL is not blacklisted.", ephemeral=True)

    # ── Voice state tracking ──────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                    before: discord.VoiceState, after: discord.VoiceState):
        if member == self.bot.user:
            if before.channel and not after.channel:
                guild_id = str(before.channel.guild.id)
                print(f"[Music] Disconnected from {before.channel.name} in {before.channel.guild.name}")
                await self._cleanup_guild(guild_id)
                await self._update_dashboard_for_guild(guild_id)
            return

        # Auto-pause when everyone leaves the voice channel
        if not before.channel:
            return
        guild_id = str(before.channel.guild.id)
        vc = before.channel.guild.voice_client
        if not vc or vc.channel != before.channel:
            return
        # Count non-bot members remaining in channel
        human_members = [m for m in before.channel.members if not m.bot]
        track = self.current_track.get(guild_id)
        if not human_members and track and not track.paused and not track.finished:
            track.paused = True
            await self._update_dashboard_for_guild(guild_id)
            print(f"[Music] Auto-paused in {before.channel.guild.name} — channel empty")
        elif human_members and track and track.paused:
            # Someone rejoined — auto-resume
            track.paused = False
            await self._update_dashboard_for_guild(guild_id)
            print(f"[Music] Auto-resumed in {before.channel.guild.name} — member rejoined")


async def setup(bot):
    await bot.add_cog(Music(bot))
