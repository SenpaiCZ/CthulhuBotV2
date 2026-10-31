import collections
import datetime
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import hashlib
import logging
import os
import re
import shutil
import sys
import time
import yt_dlp
import importlib
import random
from functools import partial
from rapidfuzz import fuzz, process
from dashboard.state import guild_mixers, server_volumes, MUSIC_CACHE_FOLDER, SOUNDBOARD_FOLDER
from dashboard.audio_mixer import MixingAudioSource, Track


class _VoiceLogBuffer(logging.Handler):
    """Ring-buffer logging handler capturing recent discord.voice_state / voice_client / player logs."""

    def __init__(self, maxlen: int = 30):
        super().__init__(level=logging.INFO)
        self.records: collections.deque[str] = collections.deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord):
        try:
            ts = time.strftime("%H:%M:%S", time.localtime(record.created))
            short_name = record.name.replace("discord.", "")
            msg = record.getMessage()
            line = f"{ts} [{short_name}] {record.levelname}: {msg}"
            if record.exc_info:
                exc_type, exc_val, _ = record.exc_info
                if exc_type is not None:
                    line += f" ({exc_type.__name__}: {exc_val})"
            self.records.append(line)
        except Exception:
            pass

    def get_recent(self, max_chars: int = 900) -> str:
        if not self.records:
            return ""
        text = "\n".join(self.records)
        if len(text) > max_chars:
            text = "..." + text[-max_chars:]
        return text


_voice_log_buffer = _VoiceLogBuffer()
for _logger_name in ("discord.voice_state", "discord.voice_client", "discord.player"):
    _lg = logging.getLogger(_logger_name)
    if _voice_log_buffer not in _lg.handlers:
        _lg.addHandler(_voice_log_buffer)
    if _lg.level == logging.NOTSET or _lg.level > logging.INFO:
        _lg.setLevel(logging.INFO)


def _get_bot_pids() -> list[int]:
    """Return all running bot.py PIDs on the host."""
    pids = []
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "cmdline", "status"]):
            try:
                if proc.info.get("status") == psutil.STATUS_ZOMBIE:
                    continue
                cmdline = proc.info.get("cmdline") or []
                if any(os.path.basename(arg) == "bot.py" for arg in cmdline):
                    pids.append(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return pids or [os.getpid()]


def _get_process_table_diagnostics() -> str:
    """Return detailed list of running python/bot processes for duplicate-instance debugging."""
    lines = []
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "ppid", "cmdline", "cwd", "create_time", "status"]):
            try:
                if proc.info.get("status") == psutil.STATUS_ZOMBIE:
                    continue
                cmdline = proc.info.get("cmdline") or []
                cmd_str = " ".join(cmdline)
                if "bot.py" in cmd_str or "updater.py" in cmd_str or "restarter.py" in cmd_str:
                    age_s = int(time.time() - (proc.info.get("create_time") or time.time()))
                    cwd = proc.info.get("cwd") or "?"
                    marker = " (THIS)" if proc.pid == os.getpid() else ""
                    lines.append(f"PID {proc.pid}{marker} (PPID {proc.info.get('ppid')}, up {age_s}s, cwd={cwd}): {cmd_str}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        lines.append(f"psutil error: {e}")
    return "\n".join(lines) if lines else f"PID {os.getpid()} (only)"


def _get_voice_env_diagnostics() -> str:
    """Return a compact one-line summary of voice-critical library versions and bot PIDs."""
    try:
        import davey
        dave_str = f"davey {getattr(davey, '__version__', 'installed')}"
    except ImportError:
        dave_str = "❌ davey MISSING"

    try:
        import nacl
        nacl_str = f"PyNaCl {getattr(nacl, '__version__', 'installed')}"
    except ImportError:
        nacl_str = "❌ PyNaCl MISSING"

    ytdl_ver = getattr(getattr(yt_dlp, "version", None), "__version__", "unknown")
    ffmpeg_ok = "✅" if shutil.which("ffmpeg") else "❌ MISSING"
    opus_ok = "✅" if discord.opus.is_loaded() else "auto"
    pids = _get_bot_pids()
    pid_warn = f"⚠️ DUPLICATE BOT PIDs `{pids}`" if len(pids) > 1 else f"PID `{os.getpid()}`"
    return (
        f"discord.py `{discord.__version__}` | `{dave_str}` | `{nacl_str}` | "
        f"yt-dlp `{ytdl_ver}` | ffmpeg {ffmpeg_ok} | opus {opus_ok} | {pid_warn}"
    )
from loadnsave import (
    load_music_blacklist, save_music_blacklist,
    load_server_volumes, save_server_volumes,
    load_music_favorites, save_music_favorites,
    load_music_cache_settings, save_music_cache_settings,
    load_music_cache_index, save_music_cache_index,
    load_ambience_scenes, save_ambience_scenes,
    load_soundboard_settings,
)
from commands._music_view import MusicView, SceneControllerView, _fmt_duration, _pct_to_vol, _vol_to_pct

_YT_ID_RE = re.compile(r"(?:[?&]v=|youtu\.be/|/(?:shorts|embed|live)/)([A-Za-z0-9_-]{6,})")


def _extract_video_key(url: str) -> str:
    """Return a deterministic, filesystem-safe key for a YouTube/audio URL."""
    url = (url or "").strip()
    m = _YT_ID_RE.search(url)
    if m:
        return f"yt_{m.group(1)}"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"url_{digest}"

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
    'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
}

YTDL_PLAYLIST = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': 'in_playlist',
    'noplaylist': False,
    'playlistend': 100,
    'lazy_playlist': True,
    'ignoreerrors': True,
    'socket_timeout': 15,
    'source_address': '0.0.0.0',
}

_LIST_ID_RE = re.compile(r"[?&]list=([A-Za-z0-9_-]+)")


def _prepare_playlist_extraction(query: str) -> tuple[dict, str]:
    """Return optimized (ytdl_opts, extract_url) for fast playlist extraction on RPi5.
    - For standard playlists (e.g. PL..., OLAK..., UU..., FL...) embedded in a `watch?v=...&list=...`
      URL, rewrite to `https://www.youtube.com/playlist?list=...` so yt-dlp fetches the playlist tab
      directly instead of first downloading and parsing the single-video watch page.
    - For YouTube Radio/Mixes (`list=RD...`), cap `playlistend` at 25 so yt-dlp doesn't paginate
      infinite auto-generated mixes."""
    opts = _ytdl_opts_with_cookies(YTDL_PLAYLIST)
    m = _LIST_ID_RE.search(query or "")
    if not m:
        return opts, query
    list_id = m.group(1)
    if list_id.startswith("RD"):
        opts["playlistend"] = 25
        return opts, query
    return opts, f"https://www.youtube.com/playlist?list={list_id}"

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


def _query_has_explicit_video(query: str) -> bool:
    """True if the query references a specific video (watch?v=... or youtu.be/...), as
    opposed to a bare playlist link with no video reference."""
    return '?v=' in query or '&v=' in query or 'youtu.be/' in query


def _parse_seek_position(position: str) -> tuple[float, bool]:
    """Parse a /seek argument. Returns (seconds, is_relative).
    '+30' / '-15' / '+1:30' -> relative, signed seconds.
    '90' / '1:30' / '1:02:03' -> absolute, unsigned.
    Raises ValueError with a user-facing message on unparseable input."""
    position = position.strip()
    error = ValueError(
        f"❌ Couldn't parse a time from '{position}' — try a number of seconds, MM:SS, or +/-30."
    )
    if not position:
        raise error

    is_relative = position[0] in ('+', '-')
    sign = -1.0 if position[0] == '-' else 1.0
    body = position[1:] if is_relative else position

    parts = body.split(':')
    if not (1 <= len(parts) <= 3):
        raise error

    try:
        nums = [float(p) for p in parts]
    except ValueError:
        raise error

    seconds = 0.0
    for n in nums:
        seconds = seconds * 60 + n

    if is_relative:
        seconds *= sign

    return seconds, is_relative


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


class MusicLookupError(Exception):
    """Raised by queue helpers for an expected 'no results / blacklisted' condition — the
    caller sends str(exc) to the user unmodified, with no '❌ Unexpected error' prefix."""


def _format_download_error(e: yt_dlp.utils.DownloadError) -> tuple[str | None, discord.Embed | None, discord.ui.View | None, bool]:
    """Map a yt-dlp DownloadError to (content, embed, view, ephemeral) for an interaction
    response/followup/message-edit — matches /play's DownloadError branches exactly."""
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
        return None, embed, CookieView(), True
    elif 'Private' in err or 'private' in err:
        return "❌ That video is private.", None, None, False
    elif 'unavailable' in err.lower():
        return "❌ Video is unavailable.", None, None, False
    else:
        return f"❌ Download error: {err[:200]}", None, None, False


class PlaylistChoiceView(discord.ui.View):
    def __init__(self, cog, guild_id: str, requester_id: int, single_query: str,
                 has_explicit_video: bool, entries: list, playlist_title: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.requester_id = requester_id
        self.single_query = single_query
        self.entries = entries
        self.playlist_title = playlist_title
        self.message: discord.Message | None = None

        self.just_one.label = "🎵 Just this song" if has_explicit_video else "🎵 Just the first song"
        self.whole_playlist.label = f"📥 Whole playlist ({len(entries)})"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("This choice isn't for you.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="⌛ Choice timed out — run `/play` again.", embed=None, view=self)
            except discord.NotFound:
                pass
            except Exception:
                pass

    @discord.ui.button(label="Just one song", style=discord.ButtonStyle.primary)
    async def just_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            embed, already_playing = await self.cog._queue_single_track(
                self.guild_id, self.single_query, interaction.user
            )
        except MusicLookupError as e:
            await interaction.message.edit(content=str(e), embed=None, view=None)
            self.stop()
            return
        except yt_dlp.utils.DownloadError as e:
            content, err_embed, err_view, _ephemeral = _format_download_error(e)
            await interaction.message.edit(content=content, embed=err_embed, view=err_view)
            self.stop()
            return
        except Exception as e:
            await interaction.message.edit(
                content=f"❌ Unexpected error: {type(e).__name__}: {str(e)[:200]}", embed=None, view=None
            )
            self.stop()
            return

        if already_playing:
            await interaction.message.edit(embed=embed, view=None)
            await self.cog._update_dashboard_for_guild(self.guild_id)
        else:
            queued_embed = discord.Embed(
                description="▶️ Queued — starting playback.", color=discord.Color.blurple()
            )
            await interaction.message.edit(embed=queued_embed, view=None)
            await self.cog._finalize_play(interaction, self.guild_id)
        self.stop()

    @discord.ui.button(label="Whole playlist", style=discord.ButtonStyle.secondary)
    async def whole_playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed, _already_playing = await self.cog._queue_playlist_entries(
            self.guild_id, self.entries, self.playlist_title, interaction.user
        )
        await interaction.message.edit(embed=embed, view=None)
        await self.cog._finalize_play(interaction, self.guild_id)
        self.stop()


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
        # guild_id (str) → "off" | "track" | "queue"
        self.loop_mode: dict[str, str] = {}
        # Cache keys currently being downloaded in the background
        self._caching_in_progress: set[str] = set()
        self._cache_tasks: set[asyncio.Task] = set()
        self._cache_lock = asyncio.Lock()
        self._bg_ytdl_semaphore = asyncio.Semaphore(1)
        # Diagnostics & error reporting state
        self._intentional_disconnects: set[str] = set()
        self.last_text_channel: dict[str, discord.abc.Messageable] = {}
        self.last_requester: dict[str, discord.abc.User] = {}
        self.last_track: dict[str, object] = {}
        self._last_bg_error: dict[str, str] = {}
        self.last_ytdlp_check: str | None = None
        self.last_ytdlp_status: str = "pending"

        self.bot.music_cog = self

        self._idle_disconnect.start()
        self._refresh_dashboards.start()
        self._auto_update_ytdlp.start()

    def cog_unload(self):
        self._idle_disconnect.cancel()
        self._refresh_dashboards.cancel()
        self._auto_update_ytdlp.cancel()
        for t in list(self._cache_tasks):
            t.cancel()

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
            channel_empty = vc.channel is not None and not any(not m.bot for m in vc.channel.members)

            if ((not track or track.finished) and not has_queue) or channel_empty:
                if guild_id not in self.idle_since:
                    self.idle_since[guild_id] = now
                elif now - self.idle_since[guild_id] >= IDLE_TIMEOUT:
                    self.idle_since.pop(guild_id, None)
                    self._intentional_disconnects.add(guild_id)
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

    @tasks.loop(hours=24)
    async def _auto_update_ytdlp(self):
        """Periodically check and upgrade yt-dlp in the background so YouTube extractor changes
        never break playback."""
        await self.upgrade_ytdlp_now()

    @_auto_update_ytdlp.before_loop
    async def _before_auto_update_ytdlp(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(30)

    async def upgrade_ytdlp_now(self) -> dict:
        """Run `pip install --upgrade yt-dlp` asynchronously and reload yt_dlp.version."""
        old_ver = getattr(getattr(yt_dlp, "version", None), "__version__", "unknown")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "yt-dlp",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode == 0:
                try:
                    importlib.reload(yt_dlp.version)
                except Exception:
                    pass
                new_ver = getattr(getattr(yt_dlp, "version", None), "__version__", old_ver)
                self.last_ytdlp_check = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if new_ver != old_ver:
                    self.last_ytdlp_status = f"updated ({old_ver} -> {new_ver})"
                    print(f"[Music] Auto-updated yt-dlp: {old_ver} -> {new_ver}")
                else:
                    self.last_ytdlp_status = f"up-to-date ({new_ver})"
                return {"status": "success", "old_version": old_ver, "new_version": new_ver, "checked_at": self.last_ytdlp_check}
            else:
                err_msg = (stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")).strip()[:200]
                self.last_ytdlp_check = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.last_ytdlp_status = f"error: {err_msg}"
                return {"status": "error", "message": err_msg, "version": old_ver}
        except Exception as e:
            self.last_ytdlp_check = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.last_ytdlp_status = f"error: {e}"
            return {"status": "error", "message": str(e), "version": old_ver}

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _cleanup_guild(self, guild_id: str, disconnect: bool = False):
        """Remove mixer/track/queue state for a guild."""
        self.current_track.pop(guild_id, None)
        self.queue.pop(guild_id, None)
        self.loop_mode.pop(guild_id, None)
        mixer = guild_mixers.pop(guild_id, None)
        if mixer:
            mixer.cleanup()

    async def _send_error_log(
        self,
        guild_id: str,
        reason: str,
        track=None,
        extra: str | None = None,
    ):
        """Send a diagnostic error log embed via DM (PM) to the requester (or bot owner),
        falling back to the guild text channel only if DM delivery is blocked."""
        recipient = self.last_requester.get(guild_id)
        channel = self.last_text_channel.get(guild_id)
        if not channel:
            dash_msg = self.dashboard_messages.get(guild_id)
            if dash_msg and getattr(dash_msg, "channel", None):
                channel = dash_msg.channel
        if not recipient and not channel:
            return

        guild = self.bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        guild_label = f" (`{guild.name}`)" if guild and getattr(guild, "name", None) else ""

        embed = discord.Embed(
            title=f"⚠️ Music Diagnostic / Error Log{guild_label}",
            description=f"**Reason:** {reason}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        embed.add_field(
            name="Environment",
            value=_get_voice_env_diagnostics()[:1024],
            inline=False,
        )

        proc_diag = _get_process_table_diagnostics()
        if proc_diag:
            embed.add_field(
                name="Running Bot Processes",
                value=f"```\n{proc_diag[:900]}\n```",
                inline=False,
            )

        if track is not None:
            meta = getattr(track, "metadata", None) or {}
            title = meta.get("title", "Unknown")
            mode = "💾 Local Cache" if meta.get("is_cached") else "🌐 YouTube Stream"
            chunks = getattr(track, "chunks_read", None)
            elapsed = getattr(track, "elapsed", 0.0)
            read_err = getattr(track, "read_error", None)
            track_lines = [
                f"**Title:** {title}",
                f"**Source:** {mode}",
                f"**Elapsed Timer:** `{elapsed:.2f}s`",
            ]
            if chunks is not None:
                track_lines.append(f"**PCM Chunks Read:** `{chunks}` (`{chunks * 0.02:.2f}s` of audio)")
            if read_err:
                track_lines.append(f"**Read Error:** `{read_err}`")
            embed.add_field(
                name="Track State",
                value="\n".join(track_lines)[:1024],
                inline=False,
            )

            stderr_tail = ""
            if hasattr(track, "get_stderr_tail"):
                try:
                    stderr_tail = track.get_stderr_tail(max_chars=800)
                except Exception:
                    stderr_tail = ""
            if stderr_tail:
                embed.add_field(
                    name="FFmpeg stderr",
                    value=f"```\n{stderr_tail}\n```"[:1024],
                    inline=False,
                )

        voice_logs = _voice_log_buffer.get_recent(max_chars=800)
        if voice_logs:
            embed.add_field(
                name="Discord Voice / Player Logs",
                value=f"```\n{voice_logs}\n```"[:1024],
                inline=False,
            )

        bg_err = extra or self._last_bg_error.get(guild_id)
        if bg_err:
            embed.add_field(
                name="Additional Error Details",
                value=f"```\n{str(bg_err)[:900]}\n```",
                inline=False,
            )

        # 1. Primary delivery: Direct Message (PM) to the user who invoked playback
        if recipient and hasattr(recipient, "send"):
            try:
                await recipient.send(embed=embed)
                return
            except Exception as e:
                print(f"[Music] Could not DM error log to {recipient}: {e}")

        # 2. Fallback: Guild text channel if DM could not be delivered
        if channel and hasattr(channel, "send"):
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"[Music] Failed to send error log embed: {e}")

    async def _ensure_voice(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
        """Join/return voice client, or send an error and return None."""
        if interaction.guild:
            guild_id = str(interaction.guild.id)
            self._intentional_disconnects.discard(guild_id)
            if getattr(interaction, "user", None):
                self.last_requester[guild_id] = interaction.user
            if getattr(interaction, "channel", None):
                self.last_text_channel[guild_id] = interaction.channel

        if not interaction.user.voice or not interaction.user.voice.channel:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ You need to be in a voice channel first.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ You need to be in a voice channel first.", ephemeral=True
                )
            return None

        channel = interaction.user.voice.channel
        vc = interaction.guild.voice_client

        if vc and vc.is_connected():
            if vc.channel != channel:
                if not interaction.response.is_done():
                    await interaction.response.defer()
                await vc.move_to(channel)
            return vc

        # Acknowledge the interaction before the voice handshake (which can exceed 3s on RPi5)
        if not interaction.response.is_done():
            await interaction.response.defer()

        if vc and not vc.is_connected():
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass

        try:
            return await asyncio.wait_for(
                channel.connect(timeout=12, reconnect=True),
                timeout=14,
            )
        except asyncio.TimeoutError:
            msg = "❌ Timed out connecting to voice. Try again."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            if interaction.guild:
                await self._send_error_log(
                    str(interaction.guild.id),
                    f"Timed out during voice handshake connecting to **#{channel.name}**.",
                )
            return None
        except Exception as e:
            msg = f"❌ Could not connect to voice: {e}"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            if interaction.guild:
                await self._send_error_log(
                    str(interaction.guild.id),
                    f"Exception connecting to voice channel **#{channel.name}**: `{type(e).__name__}: {e}`",
                )
            return None

    async def _finalize_play(self, interaction: discord.Interaction, guild_id: str):
        """Update the existing dashboard message or send a new one (avoid delete+send to
        keep the panel stable); start playback if nothing is currently playing."""
        old_msg = self.dashboard_messages.get(guild_id)
        view = MusicView(self, guild_id)
        embed = view.get_embed()

        if old_msg:
            try:
                await old_msg.edit(embed=embed, view=view)
            except discord.NotFound:
                self.dashboard_messages.pop(guild_id, None)
                old_msg = None
            except Exception:
                old_msg = None

        if not old_msg:
            new_msg = await interaction.followup.send(embed=embed, view=view)
            self.dashboard_messages[guild_id] = new_msg
        elif getattr(interaction, "message", None) is None and getattr(interaction, "_followup_sent", False) is not True:
            try:
                await interaction.delete_original_response()
            except Exception:
                pass

        current = self.current_track.get(guild_id)
        if (not current or current.finished) and self.queue.get(guild_id):
            next_song = self.queue[guild_id].pop(0)
            await self._play_song(guild_id, next_song)

    async def _queue_playlist_entries(self, guild_id: str, entries: list[dict], playlist_title: str,
                                       requester) -> tuple[discord.Embed, bool]:
        """Append flat playlist entries to the guild queue, skipping blacklisted URLs.
        Marks any tracks already present in the local audio cache so they play immediately
        with 0ms latency.
        Returns (embed, already_playing) — already_playing is always False; queueing a
        playlist never short-circuits the dashboard/playback-start step the way a
        single-track 'something's already playing' add does."""
        self.queue.setdefault(guild_id, [])
        added = 0
        for entry in entries:
            orig = entry.get('url', '')
            if orig in self.blacklist:
                continue
            cached = await self._get_cached_entry(orig) if orig else None
            if cached:
                self.queue[guild_id].append({
                    'title': cached.get('title') or entry.get('title', 'Unknown'),
                    'url': cached['file_path'],
                    'cached_path': cached['file_path'],
                    'is_cached': True,
                    'webpage_url': orig,
                    'original_url': cached.get('original_url', orig),
                    'thumbnail': cached.get('thumbnail') or entry.get('thumbnail', ''),
                    'duration': cached.get('duration') or entry.get('duration'),
                    'requested_by': requester.display_name,
                    'needs_resolve': False,
                })
            else:
                self.queue[guild_id].append({
                    'title': entry.get('title', 'Unknown'),
                    'url': None,
                    'webpage_url': orig,
                    'original_url': orig,
                    'thumbnail': entry.get('thumbnail', ''),
                    'duration': entry.get('duration'),
                    'requested_by': requester.display_name,
                    'needs_resolve': True,
                })
            added += 1

        embed = discord.Embed(
            title="📥 Playlist Added",
            description=f"**{playlist_title}**\n{added} tracks queued",
            color=discord.Color.blurple(),
        )
        return embed, False

    # ── Audio Cache Helpers ───────────────────────────────────────────────────

    async def _get_cached_entry(self, query_or_url: str) -> dict | None:
        """Return a valid cache index entry for `query_or_url` if caching is enabled
        and the file exists on disk; otherwise return None (cleaning up stale index entries)."""
        if not query_or_url:
            return None
        settings = await load_music_cache_settings()
        if not settings.get("enabled", True):
            return None

        index = await load_music_cache_index()
        entries = index.get("entries", {})
        queries = index.get("queries", {})

        key = _extract_video_key(query_or_url)
        entry = entries.get(key)
        if not entry:
            norm_q = query_or_url.strip().lower()
            mapped_key = queries.get(norm_q)
            if mapped_key:
                entry = entries.get(mapped_key)
                key = mapped_key

        if not entry:
            return None

        file_path = entry.get("file_path", "")
        if file_path and os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
            return entry

        # Stale entry — file was deleted externally
        entries.pop(key, None)
        for q_k, q_v in list(queries.items()):
            if q_v == key:
                queries.pop(q_k, None)
        await save_music_cache_index(index)
        return None

    def _schedule_background_cache(self, song_info: dict, query: str | None = None):
        """Schedule a background task to download `song_info` into the local audio cache
        if it has a valid URL and known duration."""
        url = song_info.get("original_url") or song_info.get("webpage_url")
        duration = song_info.get("duration")
        if not url or not isinstance(duration, (int, float)) or duration <= 0:
            return
        if song_info.get("is_cached"):
            return
        key = _extract_video_key(url)
        if key in self._caching_in_progress:
            return
        snapshot = dict(song_info)

        async def _delayed_cache():
            await asyncio.sleep(2.0)
            async with self._bg_ytdl_semaphore:
                await self._cache_track_in_background(snapshot, query=query)

        task = asyncio.create_task(_delayed_cache())
        self._cache_tasks.add(task)
        task.add_done_callback(self._cache_tasks.discard)

    async def _cache_track_in_background(self, song_info: dict, query: str | None = None):
        """Download a track to `MUSIC_CACHE_FOLDER` in the background if it meets the
        configured duration and size limits, then run LRU eviction."""
        url = song_info.get("original_url") or song_info.get("webpage_url")
        duration = song_info.get("duration")
        if not url or not isinstance(duration, (int, float)) or duration <= 0:
            return

        settings = await load_music_cache_settings()
        if not settings.get("enabled", True):
            return

        max_dur_sec = float(settings.get("max_duration_minutes", 30)) * 60
        if duration > max_dur_sec:
            return

        max_size_bytes = int(float(settings.get("max_size_gb", 10.0)) * (1024 ** 3))
        if max_size_bytes <= 0:
            return

        existing = await self._get_cached_entry(url)
        if existing:
            return

        key = _extract_video_key(url)
        if key in self._caching_in_progress:
            return

        self._caching_in_progress.add(key)
        try:
            os.makedirs(MUSIC_CACHE_FOLDER, exist_ok=True)
            base_dl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(MUSIC_CACHE_FOLDER, f"{key}.%(ext)s"),
                "noplaylist": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 30,
                "source_address": "0.0.0.0",
                "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            }
            if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK):
                base_dl_opts["paths"] = {
                    "home": MUSIC_CACHE_FOLDER,
                    "temp": "/dev/shm",
                }
                base_dl_opts["outtmpl"] = f"{key}.%(ext)s"
            dl_opts = _ytdl_opts_with_cookies(base_dl_opts)

            def _download():
                with yt_dlp.YoutubeDL(dl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        return None, None
                    if "entries" in info:
                        info = next((e for e in info["entries"] if e), None)
                    if not info:
                        return None, None
                    return info, ydl.prepare_filename(info)

            res = await self.bot.loop.run_in_executor(None, _download)
            if not res or not isinstance(res, tuple):
                return
            info, file_path = res
            if not file_path or not os.path.isfile(file_path):
                # Fallback scan for any file matching `<key>.*` in MUSIC_CACHE_FOLDER
                file_path = None
                if os.path.isdir(MUSIC_CACHE_FOLDER):
                    for fname in os.listdir(MUSIC_CACHE_FOLDER):
                        if fname.startswith(f"{key}.") and not fname.endswith((".part", ".ytdl")):
                            candidate = os.path.join(MUSIC_CACHE_FOLDER, fname)
                            if os.path.isfile(candidate):
                                file_path = candidate
                                break
            if not file_path or not os.path.isfile(file_path):
                return

            size_bytes = os.path.getsize(file_path)
            if size_bytes <= 0 or size_bytes > max_size_bytes:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                return

            now = time.time()
            async with self._cache_lock:
                index = await load_music_cache_index()
                index.setdefault("entries", {})[key] = {
                    "key": key,
                    "title": song_info.get("title") or (info.get("title", "Unknown") if info else "Unknown"),
                    "original_url": url,
                    "thumbnail": song_info.get("thumbnail") or (info.get("thumbnail", "") if info else ""),
                    "duration": duration,
                    "file_path": file_path,
                    "size_bytes": size_bytes,
                    "last_played": now,
                    "cached_at": now,
                }
                if query:
                    norm_q = query.strip().lower()
                    if norm_q:
                        index.setdefault("queries", {})[norm_q] = key
                await save_music_cache_index(index)

            # Mark any matching active track or queued items as cached
            for track in self.current_track.values():
                if track and getattr(track, "metadata", None):
                    if track.metadata.get("original_url") == url:
                        track.metadata["is_cached"] = True
                        track.metadata["cached_path"] = file_path
            for q in self.queue.values():
                for item in q:
                    if item.get("original_url") == url or item.get("webpage_url") == url:
                        item["is_cached"] = True
                        item["cached_path"] = file_path

            await self._enforce_cache_limits()
        except Exception as e:
            print(f"[MusicCache] Background download failed for {url}: {e}")
        finally:
            self._caching_in_progress.discard(key)

    async def _get_favorite_keys_and_urls(self) -> tuple[set[str], set[str]]:
        favorites = await load_music_favorites()
        fav_keys: set[str] = set()
        fav_urls: set[str] = set()
        if isinstance(favorites, dict):
            for guild_favs in favorites.values():
                if isinstance(guild_favs, dict):
                    for user_favs in guild_favs.values():
                        if isinstance(user_favs, list):
                            for f in user_favs:
                                u = f.get("url", "")
                                if u:
                                    fav_urls.add(u)
                                    fav_keys.add(_extract_video_key(u))
        return fav_keys, fav_urls

    async def _enforce_cache_limits(self):
        """Evict least-recently-played cached files until total size is within max_size_gb.
        Favorited (❤️) songs are given priority protection and only evicted as a last resort."""
        settings = await load_music_cache_settings()
        max_size_bytes = int(float(settings.get("max_size_gb", 10.0)) * (1024 ** 3))
        index = await load_music_cache_index()
        entries = index.get("entries", {})
        queries = index.get("queries", {})

        # 1. Prune missing files and refresh file sizes
        changed = False
        for k, entry in list(entries.items()):
            fp = entry.get("file_path", "")
            if not fp or not os.path.isfile(fp):
                entries.pop(k, None)
                changed = True
            else:
                try:
                    entry["size_bytes"] = os.path.getsize(fp)
                except OSError:
                    entries.pop(k, None)
                    changed = True

        total_bytes = sum(e.get("size_bytes", 0) for e in entries.values())
        if total_bytes <= max_size_bytes:
            if changed:
                await save_music_cache_index(index)
            return

        fav_keys, fav_urls = await self._get_favorite_keys_and_urls()
        active_paths = {
            getattr(t, "file_path", None)
            for t in self.current_track.values()
            if t and not getattr(t, "finished", True)
        }

        def _is_fav(e: dict) -> bool:
            return e.get("key") in fav_keys or e.get("original_url") in fav_urls

        # Non-favorites (0) before favorites (1), oldest last_played first
        candidates = [
            e for e in entries.values()
            if e.get("file_path") not in active_paths
        ]
        candidates.sort(key=lambda e: (1 if _is_fav(e) else 0, e.get("last_played", 0.0)))

        for entry in candidates:
            if total_bytes <= max_size_bytes:
                break
            k = entry.get("key")
            fp = entry.get("file_path", "")
            sz = entry.get("size_bytes", 0)
            try:
                if fp and os.path.isfile(fp):
                    os.remove(fp)
            except OSError:
                pass
            entries.pop(k, None)
            total_bytes -= sz
            changed = True

        if changed:
            valid_keys = set(entries.keys())
            for q_k, q_v in list(queries.items()):
                if q_v not in valid_keys:
                    queries.pop(q_k, None)
            await save_music_cache_index(index)

    async def get_cache_status(self) -> dict:
        """Return current cache configuration and usage statistics."""
        settings = await load_music_cache_settings()
        index = await load_music_cache_index()
        entries = index.get("entries", {})
        fav_keys, fav_urls = await self._get_favorite_keys_and_urls()

        total_bytes = 0
        track_count = 0
        fav_count = 0
        pruned = False

        for k, entry in list(entries.items()):
            fp = entry.get("file_path", "")
            if not fp or not os.path.isfile(fp):
                entries.pop(k, None)
                pruned = True
                continue
            try:
                sz = os.path.getsize(fp)
                entry["size_bytes"] = sz
            except OSError:
                entries.pop(k, None)
                pruned = True
                continue
            total_bytes += sz
            track_count += 1
            if k in fav_keys or entry.get("original_url") in fav_urls:
                fav_count += 1

        if pruned:
            await save_music_cache_index(index)

        max_size_gb = float(settings.get("max_size_gb", 10.0))
        return {
            "enabled": bool(settings.get("enabled", True)),
            "max_duration_minutes": int(settings.get("max_duration_minutes", 30)),
            "max_size_gb": max_size_gb,
            "track_count": track_count,
            "favorite_track_count": fav_count,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "max_bytes": int(max_size_gb * (1024 ** 3)),
        }

    async def update_cache_settings(
        self,
        *,
        enabled: bool | None = None,
        max_duration_minutes: int | None = None,
        max_size_gb: float | None = None,
    ) -> dict:
        """Update cache settings, enforce new size limits immediately, and return new status."""
        settings = await load_music_cache_settings()
        if enabled is not None:
            settings["enabled"] = bool(enabled)
        if max_duration_minutes is not None:
            settings["max_duration_minutes"] = max(1, int(max_duration_minutes))
        if max_size_gb is not None:
            settings["max_size_gb"] = round(max(0.1, float(max_size_gb)), 2)
        await save_music_cache_settings(settings)
        await self._enforce_cache_limits()
        return await self.get_cache_status()

    async def clear_cache(self, keep_favorites: bool = True) -> tuple[int, int]:
        """Delete cached audio files from disk and index. Returns (removed_count, freed_bytes)."""
        index = await load_music_cache_index()
        entries = index.get("entries", {})
        queries = index.get("queries", {})
        fav_keys, fav_urls = await self._get_favorite_keys_and_urls()
        active_paths = {
            getattr(t, "file_path", None)
            for t in self.current_track.values()
            if t and not getattr(t, "finished", True)
        }

        removed_count = 0
        freed_bytes = 0
        for k, entry in list(entries.items()):
            fp = entry.get("file_path", "")
            if fp in active_paths:
                continue
            is_fav = k in fav_keys or entry.get("original_url") in fav_urls
            if keep_favorites and is_fav:
                continue
            sz = entry.get("size_bytes", 0)
            if fp and os.path.isfile(fp):
                try:
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                except OSError:
                    pass
            entries.pop(k, None)
            removed_count += 1
            freed_bytes += sz

        valid_keys = set(entries.keys())
        for q_k, q_v in list(queries.items()):
            if q_v not in valid_keys:
                queries.pop(q_k, None)
        await save_music_cache_index(index)
        return removed_count, freed_bytes

    async def _queue_single_track(self, guild_id: str, query: str, requester) -> tuple[discord.Embed | None, bool]:
        """Full yt-dlp extraction (or local cache hit) + blacklist check + queue append for one track.
        Returns (embed, already_playing). If something is already playing, embed is the
        'Added to Queue' embed and already_playing is True — the caller must send/edit it
        and call _update_dashboard_for_guild, and must NOT call _finalize_play. If nothing
        is playing, embed is None and already_playing is False — the caller must call
        _finalize_play. Raises MusicLookupError (an expected condition, not an unexpected
        failure) if extraction finds nothing playable or the track is blacklisted."""
        self.queue.setdefault(guild_id, [])

        cached = await self._get_cached_entry(query)
        if cached:
            original_url = cached.get('original_url', query)
            if original_url in self.blacklist or query in self.blacklist:
                raise MusicLookupError(f"❌ **{cached.get('title', 'That track')}** is blacklisted.")
            song_info = {
                'title': cached.get('title', 'Unknown'),
                'url': cached['file_path'],
                'cached_path': cached['file_path'],
                'is_cached': True,
                'original_url': original_url,
                'thumbnail': cached.get('thumbnail', ''),
                'duration': cached.get('duration'),
                'requested_by': requester.display_name,
                'needs_resolve': False,
                'query': query,
            }
        else:
            opts = _ytdl_opts_with_cookies(YTDL_BASE)
            def _extract_single():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(query, download=False)

            try:
                info = await asyncio.wait_for(
                    self.bot.loop.run_in_executor(None, _extract_single),
                    timeout=35.0,
                )
            except asyncio.TimeoutError:
                await self._send_error_log(
                    guild_id,
                    f"yt-dlp extraction timed out after 35s for query: `{query[:150]}`",
                )
                raise MusicLookupError("❌ Timed out resolving YouTube track (took >35s). Try again.")

            if not info:
                raise MusicLookupError("❌ No results found.")

            if 'entries' in info:
                entry = next((e for e in info['entries'] if e), None)
                if not entry:
                    raise MusicLookupError("❌ No playable result found.")
                info = entry

            original_url = info.get('webpage_url', info.get('url', ''))
            if original_url in self.blacklist:
                raise MusicLookupError(f"❌ **{info.get('title', 'That track')}** is blacklisted.")

            cached_by_url = await self._get_cached_entry(original_url) if original_url else None
            if cached_by_url:
                index = await load_music_cache_index()
                index.setdefault("queries", {})[query.strip().lower()] = cached_by_url["key"]
                await save_music_cache_index(index)
                song_info = {
                    'title': cached_by_url.get('title', info.get('title', 'Unknown')),
                    'url': cached_by_url['file_path'],
                    'cached_path': cached_by_url['file_path'],
                    'is_cached': True,
                    'original_url': original_url,
                    'thumbnail': cached_by_url.get('thumbnail', info.get('thumbnail', '')),
                    'duration': cached_by_url.get('duration', info.get('duration')),
                    'requested_by': requester.display_name,
                    'needs_resolve': False,
                    'query': query,
                }
            else:
                song_info = {
                    'title': info.get('title', 'Unknown'),
                    'url': info.get('url', ''),
                    'original_url': original_url,
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration'),
                    'requested_by': requester.display_name,
                    'needs_resolve': False,
                    'query': query,
                }

        self.queue[guild_id].append(song_info)

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
            embed.set_footer(text=f"Requested by {requester.display_name}")
            if song_info['thumbnail']:
                embed.set_thumbnail(url=song_info['thumbnail'])
            return embed, True

        return None, False

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
            self._last_bg_error["last"] = f"resolve_stream_url({webpage_url}): {type(e).__name__}: {e}"
            return None

    def _on_track_finish(self, guild_id: str):
        """Called from audio thread when a track naturally ends."""
        coro = self._process_queue(guild_id)
        asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

    def _on_player_error(self, guild_id: str, error: Exception | None):
        """Called by discord.VoiceClient's AudioPlayer thread if playback terminates with an error."""
        if not error:
            return
        print(f"[Music] Voice error in guild {guild_id}: {error}")
        track = self.current_track.get(guild_id)
        coro = self._send_error_log(
            guild_id,
            f"VoiceClient player error: `{type(error).__name__}: {error}`",
            track=track,
        )
        asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

    def _fade_or_finish_track(self, track, duration_sec: float = 0.8):
        """Start a smooth fade-out on a real mixer Track (detaching its on_finish callback),
        or mark finished immediately on a mock/non-Track."""
        if isinstance(track, Track):
            track.start_fade_out(duration_sec)
        else:
            track.finished = True

    async def _process_queue(self, guild_id: str):
        """Advance to next song or update dashboard when queue is empty."""
        track = self.current_track.get(guild_id)
        if track and (track.finished or getattr(track, '_fade_out_total_chunks', 0) > 0):
            # If the track ended naturally (not faded out by skip/stop) prematurely or with an error,
            # send a diagnostic error log so FFmpeg / stream / voice errors are visible in PM.
            was_faded = getattr(track, '_fade_out_total_chunks', 0) > 0
            if not was_faded and isinstance(track, Track):
                dur = (getattr(track, 'metadata', None) or {}).get('duration')
                ended_early = isinstance(dur, (int, float)) and dur > 15 and track.elapsed < (dur - 5)
                if track.chunks_read < 25 or track.read_error or ended_early:
                    await self._send_error_log(
                        guild_id,
                        f"Track ended prematurely at `{track.elapsed:.1f}s` / `{dur or '?'}s` "
                        f"after `{track.chunks_read}` audio chunks (`{track.chunks_read * 0.02:.2f}s` read from FFmpeg).",
                        track=track,
                    )
            if self.loop_mode.get(guild_id) == "queue" and track.metadata:
                recycled = dict(track.metadata)
                recycled['needs_resolve'] = True
                self.queue.setdefault(guild_id, []).append(recycled)
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

        # 1. Check if this song is already in the local audio cache
        cached_path = song_info.get('cached_path')
        lookup_url = song_info.get('original_url') or song_info.get('webpage_url')
        cached_entry = None
        if cached_path and os.path.isfile(cached_path):
            cached_entry = await self._get_cached_entry(lookup_url or cached_path)
        elif lookup_url:
            cached_entry = await self._get_cached_entry(lookup_url)
            if cached_entry:
                cached_path = cached_entry['file_path']

        play_from_cache = bool(
            cached_path and os.path.isfile(cached_path) and os.path.getsize(cached_path) > 0
        )

        if play_from_cache:
            song_info['cached_path'] = cached_path
            song_info['url'] = cached_path
            song_info['is_cached'] = True
            song_info['needs_resolve'] = False
            if cached_entry:
                cached_entry['last_played'] = time.time()
                index = await load_music_cache_index()
                await save_music_cache_index(index)
        else:
            song_info['is_cached'] = False
            song_info.pop('cached_path', None)
            # Lazy resolution for playlist tracks that only have webpage_url
            if song_info.get('needs_resolve'):
                info = await self._resolve_stream_url(song_info['webpage_url'])
                if not info:
                    print(f"[Music] Could not resolve track: {song_info.get('title')}, skipping.")
                    await self._send_error_log(
                        guild_id,
                        f"Could not resolve YouTube stream URL for **{song_info.get('title', 'Unknown')}**.",
                        extra=self._last_bg_error.get("last"),
                    )
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
            vc.play(source, after=partial(self._on_player_error, guild_id))

        music_vol = self._get_volume(guild_id)
        track = mixer.add_track(
            file_path=cached_path if play_from_cache else song_info['url'],
            is_url=not play_from_cache,
            metadata=song_info,
            volume=_pct_to_vol(round(music_vol * 100)),
            loop=(self.loop_mode.get(guild_id) == "track"),
            before_options=None if play_from_cache else FFMPEG_OPTIONS['before_options'],
            options=FFMPEG_OPTIONS['options'],
            on_finish=partial(self._on_track_finish, guild_id),
            fade_in_sec=1.0,
        )
        self.current_track[guild_id] = track
        self.last_track[guild_id] = track

        await self._update_dashboard_for_guild(guild_id)
        dashboard_msg = self.dashboard_messages.get(guild_id)
        if dashboard_msg:
            try:
                await dashboard_msg.clear_reactions()
                await dashboard_msg.add_reaction(self.FAVORITE_EMOJI)
            except Exception:
                pass

        # Schedule background download if streaming and eligible for cache
        if not play_from_cache:
            self._schedule_background_cache(song_info, query=song_info.get('query'))

        # Lookahead: pre-resolve and pre-cache the next track in queue so transitions are instant
        self._schedule_prefetch_next(guild_id)

    def _schedule_prefetch_next(self, guild_id: str):
        """If the next song in the guild queue needs yt-dlp resolution, pre-resolve and
        pre-cache it in the background while the current song is playing."""
        q = self.queue.get(guild_id)
        if not q:
            return
        next_song = q[0]
        if not next_song.get('needs_resolve') or next_song.get('is_cached') or next_song.get('_prefetching'):
            if not next_song.get('is_cached') and next_song.get('duration'):
                self._schedule_background_cache(next_song, query=next_song.get('query'))
            return
        if not next_song.get('webpage_url'):
            return

        next_song['_prefetching'] = True

        async def _delayed_prefetch():
            await asyncio.sleep(2.0)
            async with self._bg_ytdl_semaphore:
                await self._prefetch_track_in_background(guild_id, next_song)

        task = asyncio.create_task(_delayed_prefetch())
        self._cache_tasks.add(task)
        task.add_done_callback(self._cache_tasks.discard)

    async def _prefetch_track_in_background(self, guild_id: str, song_info: dict):
        """Background lookahead resolver + cacher for the next song in queue."""
        try:
            webpage_url = song_info.get('webpage_url') or song_info.get('original_url')
            if not webpage_url:
                return
            cached = await self._get_cached_entry(webpage_url)
            if cached:
                song_info['cached_path'] = cached['file_path']
                song_info['url'] = cached['file_path']
                song_info['is_cached'] = True
                song_info['needs_resolve'] = False
                return

            info = await self._resolve_stream_url(webpage_url)
            if not info or not info.get('url'):
                return
            song_info['url'] = info['url']
            song_info['thumbnail'] = info.get('thumbnail', song_info.get('thumbnail', ''))
            song_info['duration'] = info.get('duration', song_info.get('duration'))
            song_info['needs_resolve'] = False
            self._schedule_background_cache(song_info, query=song_info.get('query'))
        except Exception as e:
            print(f"[Music] Prefetch error for {song_info.get('title')}: {e}")
        finally:
            song_info.pop('_prefetching', None)

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

    async def ensure_voice_for_channel(self, guild_id: str, channel_id: str | None = None) -> tuple[discord.VoiceClient | None, str | None]:
        """Connect or move the bot to `channel_id` (or reuse active voice connection / auto-pick
        a populated voice channel in `guild_id`). Used by Web Dashboard playback and Ambience Scenes."""
        guild = self.bot.get_guild(int(guild_id)) if str(guild_id).isdigit() else None
        if not guild:
            return None, "Guild not found"

        self._intentional_disconnects.discard(str(guild_id))
        vc = guild.voice_client
        target_channel = None

        if channel_id and str(channel_id).isdigit():
            target_channel = guild.get_channel(int(channel_id))
            if not target_channel:
                return None, "Voice channel not found"
        elif vc and vc.is_connected() and vc.channel:
            target_channel = vc.channel
        else:
            # Auto-select first voice channel with human members, or first voice channel
            for ch in guild.voice_channels:
                if any(not m.bot for m in ch.members):
                    target_channel = ch
                    break
            if not target_channel and guild.voice_channels:
                target_channel = guild.voice_channels[0]

        if not target_channel:
            return None, "No voice channel available in guild"

        try:
            if vc and vc.is_connected():
                if vc.channel.id != target_channel.id:
                    await vc.move_to(target_channel)
                return vc, None

            if vc and not vc.is_connected():
                try:
                    await vc.disconnect(force=True)
                except Exception:
                    pass

            vc = await asyncio.wait_for(
                target_channel.connect(timeout=12, reconnect=True),
                timeout=14,
            )
            return vc, None
        except asyncio.TimeoutError:
            return None, f"Timed out connecting to voice channel #{target_channel.name}"
        except Exception as e:
            return None, f"Could not connect to voice: {e}"

    async def play_from_dashboard(
        self,
        guild_id: str,
        query: str,
        channel_id: str | None = None,
        play_next: bool = False,
        replace_current: bool = False,
    ) -> dict:
        """Queue and/or immediately start a YouTube URL, playlist, or search query from the Web Dashboard."""
        guild_id = str(guild_id)
        query = (query or "").strip()
        if not query:
            return {"status": "error", "message": "Missing query or URL"}

        vc, err = await self.ensure_voice_for_channel(guild_id, channel_id)
        if err or not vc:
            return {"status": "error", "message": err or "Could not join voice channel"}

        self.queue.setdefault(guild_id, [])
        if not self.blacklist:
            self.blacklist = await load_music_blacklist() or []

        requester = SimpleNamespace_requester = type("DashboardRequester", (), {"display_name": "Web Dashboard"})()

        try:
            if _is_playlist_url(query) and not play_next and not replace_current:
                opts, extract_url = _prepare_playlist_extraction(query)
                def _extract_pl():
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        res = ydl.extract_info(extract_url, download=False)
                        if res and 'entries' in res and res['entries'] is not None:
                            res['entries'] = list(res['entries'])
                        return res

                info = await asyncio.wait_for(
                    self.bot.loop.run_in_executor(None, _extract_pl),
                    timeout=35.0,
                )
                entries = [e for e in ((info or {}).get('entries') or []) if e and e.get('url')]
                if not entries:
                    return {"status": "error", "message": "No playable tracks found in playlist"}
                playlist_title = (info or {}).get('title', 'Playlist')
                await self._queue_playlist_entries(guild_id, entries, playlist_title, requester)
                current = self.current_track.get(guild_id)
                if (not current or current.finished) and self.queue.get(guild_id):
                    next_song = self.queue[guild_id].pop(0)
                    await self._play_song(guild_id, next_song)
                else:
                    await self._update_dashboard_for_guild(guild_id)
                return {"status": "success", "title": playlist_title, "queued": len(entries)}

            embed, already_playing = await self._queue_single_track(guild_id, query, requester)
            added_song = self.queue[guild_id][-1] if self.queue.get(guild_id) else {}

            if (play_next or replace_current) and len(self.queue.get(guild_id, [])) > 1:
                # Move the newly appended track to the front of the queue
                song = self.queue[guild_id].pop()
                self.queue[guild_id].insert(0, song)

            current = self.current_track.get(guild_id)
            if replace_current and current and not current.finished:
                self._fade_or_finish_track(current)
                await self._process_queue(guild_id)
            elif (not current or current.finished) and self.queue.get(guild_id):
                next_song = self.queue[guild_id].pop(0)
                await self._play_song(guild_id, next_song)
            else:
                await self._update_dashboard_for_guild(guild_id)

            return {
                "status": "success",
                "title": added_song.get("title", "Track"),
                "already_playing": already_playing and not replace_current,
            }
        except MusicLookupError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"{type(e).__name__}: {str(e)[:200]}"}

    async def activate_ambience_scene(
        self,
        guild_id: str,
        scene: dict,
        channel_id: str | None = None,
    ) -> dict:
        """Activate a Scenic Preset (Ambience Scene) in `guild_id`:
        - Connects to voice channel if needed
        - Crossfades out any previous soundboard loops (or replaces all soundboard tracks)
        - Starts all configured soundboard tracks in the scene
        - Optionally starts/replaces the YouTube music track and sets music volume & loop mode."""
        guild_id = str(guild_id)
        vc, err = await self.ensure_voice_for_channel(guild_id, channel_id)
        if err or not vc:
            return {"status": "error", "message": err or "Could not join voice channel"}

        mixer = guild_mixers.get(guild_id)
        if not mixer:
            mixer = MixingAudioSource()
            guild_mixers[guild_id] = mixer

        # Ensure mixer is playing on voice client
        if not vc.is_playing() or not (
            isinstance(vc.source, discord.PCMVolumeTransformer)
            and vc.source.original is mixer
        ):
            vc.stop()
            source = discord.PCMVolumeTransformer(mixer, volume=1.0)
            vc.play(source, after=partial(self._on_player_error, guild_id))

        # 1. Smoothly fade out existing soundboard tracks in mixer
        with mixer.lock:
            existing_sb = [
                t for t in mixer.tracks
                if not t.finished and t.metadata.get("type") == "soundboard"
            ]
        for t in existing_sb:
            t.start_fade_out(0.8)

        # 2. Start scene's soundboard tracks
        sb_master = server_volumes.get(guild_id, {'music': 1.0, 'soundboard': 0.5}).get('soundboard', 0.5)
        sb_started = 0
        raw_sb_list = scene.get("soundboard_tracks") or scene.get("soundboard") or []
        for sb_item in raw_sb_list:
            rel_path = (sb_item.get("file_path") or sb_item.get("file") or "").strip()
            if not rel_path or ".." in rel_path:
                continue
            full_path = os.path.abspath(os.path.join(SOUNDBOARD_FOLDER, rel_path))
            if os.path.commonpath([full_path, os.path.abspath(SOUNDBOARD_FOLDER)]) != os.path.abspath(SOUNDBOARD_FOLDER):
                continue
            if not os.path.isfile(full_path):
                continue
            vol_mod = max(0.0, min(1.0, float(sb_item.get("volume", 100)) / 100.0))
            loop_flag = bool(sb_item.get("loop", True))
            mixer.add_track(
                full_path,
                volume=sb_master * vol_mod,
                loop=loop_flag,
                metadata={
                    "type": "soundboard",
                    "volume_modifier": vol_mod,
                    "scene_id": scene.get("id") or scene.get("scene_id"),
                },
                fade_in_sec=0.8,
            )
            sb_started += 1

        # 3. Update music volume & loop mode if specified by scene
        music_vol_pct = scene.get("music_volume")
        if music_vol_pct is not None:
            clamped = max(0, min(100, int(music_vol_pct)))
            server_volumes.setdefault(guild_id, {'music': 1.0, 'soundboard': 0.5})['music'] = clamped / 100.0
            await save_server_volumes(server_volumes)
            cur = self.current_track.get(guild_id)
            if cur and not cur.finished:
                cur.volume = _pct_to_vol(clamped)

        music_loop = scene.get("music_loop")
        if music_loop in ("off", "track", "queue"):
            self.loop_mode[guild_id] = music_loop
            cur = self.current_track.get(guild_id)
            if cur and not cur.finished:
                cur.loop = (music_loop == "track")

        # 4. Play scene's YouTube track/query if specified
        music_query = (scene.get("music_query") or scene.get("music_url") or "").strip()
        music_res = None
        if music_query:
            music_res = await self.play_from_dashboard(
                guild_id,
                music_query,
                channel_id=channel_id,
                replace_current=True,
            )
            if music_res.get("status") == "error":
                return {
                    "status": "error",
                    "message": f"Scene soundboard started ({sb_started}), but music failed: {music_res.get('message')}",
                }

        return {
            "status": "success",
            "scene_name": scene.get("name", "Scene"),
            "soundboard_started": sb_started,
            "music": music_res,
        }

    async def _seek(self, guild_id: str, target_seconds: float) -> discord.Embed:
        """Seek the currently playing track to target_seconds (already resolved to absolute
        seconds by the caller — this method does no relative-vs-absolute interpretation).
        Raises MusicLookupError if nothing is playing or the track is no longer active."""
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            raise MusicLookupError("❌ Nothing is playing.")

        mixer = guild_mixers.get(guild_id)
        if not mixer or not mixer.seek_track(track.id, target_seconds):
            raise MusicLookupError("❌ Could not seek — track is no longer active.")

        await self._update_dashboard_for_guild(guild_id)
        dur = track.metadata.get('duration')
        return discord.Embed(
            description=f"⏩ Seeked to **{_fmt_duration(track.elapsed)}**" + (f" / {_fmt_duration(dur)}" if dur else ""),
            color=discord.Color.blurple(),
        )

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
                    if getattr(interaction, "message", None) is None:
                        try:
                            await interaction.delete_original_response()
                        except Exception:
                            pass
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
        self._fade_or_finish_track(track)
        await self._process_queue(guild_id)

    async def stop_music(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        self._intentional_disconnects.add(guild_id)
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
        current_mode = self.loop_mode.get(guild_id, "off")
        _cycle = {"off": "track", "track": "queue", "queue": "off"}
        new_mode = _cycle[current_mode]
        self.loop_mode[guild_id] = new_mode

        track = self.current_track.get(guild_id)
        if track and not track.finished:
            track.loop = (new_mode == "track")

        _labels = {"off": "🔁 Loop OFF", "track": "🔂 Loop: Track", "queue": "🔁 Loop: Queue"}
        if not interaction.response.is_done():
            await interaction.response.send_message(_labels[new_mode], ephemeral=True)
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

    async def adjust_volume(self, interaction: discord.Interaction, delta_pct: int):
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if track and not track.finished:
            current_pct = _vol_to_pct(track.volume)
        else:
            current_pct = round(self._get_volume(guild_id) * 100)

        clamped = max(0, min(100, current_pct + delta_pct))
        new_vol = clamped / 100.0

        if guild_id not in server_volumes:
            server_volumes[guild_id] = {'music': 1.0, 'soundboard': 0.5}
        server_volumes[guild_id]['music'] = new_vol
        await save_server_volumes(server_volumes)

        if track and not track.finished:
            track.volume = _pct_to_vol(clamped)

        await self.refresh_dashboard(interaction)

    async def toggle_favorite_button(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            if not interaction.response.is_done():
                await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return

        url = track.metadata.get('original_url', '')
        title = track.metadata.get('title', 'Unknown')
        if not url:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Cannot favorite a track without a URL.", ephemeral=True)
            return

        favorites = await load_music_favorites()
        user_favs = favorites.get(guild_id, {}).get(user_id, [])
        if any(f.get('url') == url for f in user_favs):
            await self._remove_favorite(guild_id, user_id, url)
            msg = f"💔 Removed **{title}** from your favorites."
        else:
            await self._add_favorite(guild_id, user_id, track.metadata)
            msg = f"❤️ Added **{title}** to your favorites."

        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)

    async def _query_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest songs from the user's ❤️ Favorites, guild Favorites, and local Audio Cache."""
        guild_id = str(interaction.guild.id) if interaction.guild else ""
        user_id = str(interaction.user.id) if interaction.user else ""

        favorites = await load_music_favorites()
        index = await load_music_cache_index()
        blacklist_set = set(self.blacklist or [])

        candidates: list[tuple[str, str, str]] = []  # (search_title, display_label, url)
        seen_urls: set[str] = set()

        def _add_candidate(title: str, url: str, prefix: str):
            url = (url or "").strip()
            if not url or len(url) > 100 or url in seen_urls or url in blacklist_set:
                return
            seen_urls.add(url)
            clean_title = (title or url).strip()
            label = f"{prefix} {clean_title}"[:100]
            candidates.append((clean_title, label, url))

        # 1. Calling user's favorites first
        guild_favs = favorites.get(guild_id, {}) if isinstance(favorites, dict) else {}
        if isinstance(guild_favs, dict):
            for f in guild_favs.get(user_id, []):
                if isinstance(f, dict):
                    _add_candidate(f.get("title", ""), f.get("url", ""), "❤️")
            # 2. Other guild members' favorites
            for uid, ufavs in guild_favs.items():
                if uid == user_id or not isinstance(ufavs, list):
                    continue
                for f in ufavs:
                    if isinstance(f, dict):
                        _add_candidate(f.get("title", ""), f.get("url", ""), "❤️")

        # 3. Local audio cache entries (most recently played first)
        entries = index.get("entries", {}) if isinstance(index, dict) else {}
        if isinstance(entries, dict):
            sorted_entries = sorted(
                (e for e in entries.values() if isinstance(e, dict)),
                key=lambda e: e.get("last_played", 0.0),
                reverse=True,
            )
            for e in sorted_entries:
                _add_candidate(e.get("title", ""), e.get("original_url", ""), "💾")

        if not candidates:
            return []

        q = (current or "").strip()
        if not q:
            return [
                app_commands.Choice(name=label, value=url)
                for _, label, url in candidates[:25]
            ]

        titles = [c[0] for c in candidates]
        matches = process.extract(q, titles, scorer=fuzz.WRatio, limit=25, score_cutoff=35)
        return [
            app_commands.Choice(name=candidates[idx][1], value=candidates[idx][2])
            for _, _, idx in matches
        ]

    # ── Slash commands ────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="▶️ Play a song or playlist by URL or search query.")
    @app_commands.describe(query="YouTube URL, playlist URL, or search terms")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.guild:
            return await interaction.response.send_message("Servers only.", ephemeral=True)

        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        if not interaction.response.is_done():
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
                opts, extract_url = _prepare_playlist_extraction(query)
                def _extract_playlist():
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        res = ydl.extract_info(extract_url, download=False)
                        if res and 'entries' in res and res['entries'] is not None:
                            res['entries'] = list(res['entries'])
                        return res

                try:
                    info = await asyncio.wait_for(
                        self.bot.loop.run_in_executor(None, _extract_playlist),
                        timeout=35.0,
                    )
                except asyncio.TimeoutError:
                    await self._send_error_log(
                        guild_id,
                        f"yt-dlp playlist extraction timed out after 35s for URL: `{extract_url[:150]}`",
                    )
                    return await interaction.followup.send("❌ Timed out loading playlist (took >35s). Try again.")

                if not info:
                    return await interaction.followup.send("❌ Could not load that playlist.")

                entries = info.get('entries') or []
                entries = [e for e in entries if e and e.get('url')]

                if not entries:
                    return await interaction.followup.send("❌ No playable tracks found in that playlist.")

                playlist_title = info.get('title', 'Playlist')

                if len(entries) <= 1:
                    embed, _already_playing = await self._queue_playlist_entries(
                        guild_id, entries, playlist_title, interaction.user
                    )
                    msg = await interaction.followup.send(embed=embed)
                    interaction._followup_sent = True
                    asyncio.create_task(_delete_after(msg, 10))
                else:
                    has_explicit_video = _query_has_explicit_video(query)
                    single_query = query if has_explicit_video else entries[0]['url']
                    view = PlaylistChoiceView(
                        cog=self, guild_id=guild_id, requester_id=interaction.user.id,
                        single_query=single_query, has_explicit_video=has_explicit_video,
                        entries=entries, playlist_title=playlist_title,
                    )
                    prompt_embed = discord.Embed(
                        title="📀 Playlist link detected",
                        description=(
                            f"**{playlist_title}** — {len(entries)} tracks\n"
                            f"First track: **{entries[0].get('title', 'Unknown')}**\n\n"
                            "Queue the whole playlist, or just one song?"
                        ),
                        color=discord.Color.blurple(),
                    )
                    view.message = await interaction.followup.send(embed=prompt_embed, view=view)
                    return

            else:
                embed, already_playing = await self._queue_single_track(guild_id, query, interaction.user)
                if already_playing:
                    msg = await interaction.followup.send(embed=embed)
                    asyncio.create_task(_delete_after(msg, 15))
                    await self._update_dashboard_for_guild(guild_id)
                    return  # Don't replace dashboard; just update queue section

            await self._finalize_play(interaction, guild_id)

        except MusicLookupError as e:
            return await interaction.followup.send(str(e))
        except yt_dlp.utils.DownloadError as e:
            content, embed, view, ephemeral = _format_download_error(e)
            await self._send_error_log(
                guild_id,
                f"yt-dlp DownloadError during `/play`: `{str(e)[:300]}`",
            )
            return await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
        except Exception as e:
            await self._send_error_log(
                guild_id,
                f"Unexpected exception during `/play`: `{type(e).__name__}: {str(e)[:300]}`",
            )
            return await interaction.followup.send(f"❌ Unexpected error: {type(e).__name__}: {str(e)[:200]}")

    @play.autocomplete('query')
    async def play_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._query_autocomplete(interaction, current)

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

        if not interaction.response.is_done():
            await interaction.response.defer()

        guild_id = str(interaction.guild.id)
        if guild_id not in self.queue:
            self.queue[guild_id] = []

        if not self.blacklist:
            self.blacklist = await load_music_blacklist() or []

        try:
            cached = await self._get_cached_entry(query)
            if cached:
                original_url = cached.get('original_url', query)
                if original_url in self.blacklist or query in self.blacklist:
                    return await interaction.followup.send(
                        f"❌ **{cached.get('title', 'That track')}** is blacklisted."
                    )
                song_info = {
                    'title': cached.get('title', 'Unknown'),
                    'url': cached['file_path'],
                    'cached_path': cached['file_path'],
                    'is_cached': True,
                    'original_url': original_url,
                    'thumbnail': cached.get('thumbnail', ''),
                    'duration': cached.get('duration'),
                    'requested_by': interaction.user.display_name,
                    'needs_resolve': False,
                    'query': query,
                }
            else:
                opts = _ytdl_opts_with_cookies(YTDL_BASE)
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
                if original_url in self.blacklist:
                    return await interaction.followup.send(
                        f"❌ **{info.get('title', 'That track')}** is blacklisted."
                    )

                cached_by_url = await self._get_cached_entry(original_url) if original_url else None
                if cached_by_url:
                    index = await load_music_cache_index()
                    index.setdefault("queries", {})[query.strip().lower()] = cached_by_url["key"]
                    await save_music_cache_index(index)
                    song_info = {
                        'title': cached_by_url.get('title', info.get('title', 'Unknown')),
                        'url': cached_by_url['file_path'],
                        'cached_path': cached_by_url['file_path'],
                        'is_cached': True,
                        'original_url': original_url,
                        'thumbnail': cached_by_url.get('thumbnail', info.get('thumbnail', '')),
                        'duration': cached_by_url.get('duration', info.get('duration')),
                        'requested_by': interaction.user.display_name,
                        'needs_resolve': False,
                        'query': query,
                    }
                else:
                    song_info = {
                        'title': info.get('title', 'Unknown'),
                        'url': info.get('url', ''),
                        'original_url': original_url,
                        'thumbnail': info.get('thumbnail', ''),
                        'duration': info.get('duration'),
                        'requested_by': interaction.user.display_name,
                        'needs_resolve': False,
                        'query': query,
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

            current = self.current_track.get(guild_id)
            if not current or current.finished:
                next_song = self.queue[guild_id].pop(0)
                await self._play_song(guild_id, next_song)

        except yt_dlp.utils.DownloadError as e:
            content, embed, view, ephemeral = _format_download_error(e)
            await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {type(e).__name__}: {str(e)[:200]}")

    @playnext.autocomplete('query')
    async def playnext_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._query_autocomplete(interaction, current)

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
        self._fade_or_finish_track(track)
        await self._process_queue(guild_id)
        if getattr(interaction, "message", None) is None:
            try:
                await interaction.delete_original_response()
            except Exception:
                pass

    @app_commands.command(name="stop", description="⏹️ Stop music and disconnect from voice.")
    async def stop(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        self._intentional_disconnects.add(guild_id)
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
            track.volume = _pct_to_vol(clamped)

        await interaction.response.send_message(
            f"🔊 Volume set to **{clamped}%**", ephemeral=True
        )
        await self._update_dashboard_for_guild(guild_id)

    @app_commands.command(name="seek", description="⏩ Jump to a time in the current track, or skip +/- seconds.")
    @app_commands.describe(position="Absolute: 90, 1:30, 1:02:03 — Relative: +30, -15")
    async def seek(self, interaction: discord.Interaction, position: str):
        if not interaction.guild:
            return
        guild_id = str(interaction.guild.id)
        track = self.current_track.get(guild_id)
        if not track or track.finished:
            return await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

        try:
            seconds, is_relative = _parse_seek_position(position)
        except ValueError as e:
            return await interaction.response.send_message(str(e), ephemeral=True)

        if is_relative:
            target = track.elapsed + seconds
        else:
            if not track.metadata.get('duration'):
                return await interaction.response.send_message(
                    "❌ This track's duration is unknown (likely a livestream) — use a relative "
                    "skip like `+30` or `-15` instead.", ephemeral=True
                )
            target = seconds

        await interaction.response.defer()
        try:
            embed = await self._seek(guild_id, target)
        except MusicLookupError as e:
            return await interaction.followup.send(str(e))
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="loop", description="🔁 Cycle loop mode: Off → Track → Queue → Off")
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

        self._fade_or_finish_track(track)
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
                was_intentional = guild_id in self._intentional_disconnects
                self._intentional_disconnects.discard(guild_id)
                active_track = self.current_track.get(guild_id) or self.last_track.get(guild_id)
                print(f"[Music] Disconnected from {before.channel.name} in {before.channel.guild.name}")
                await self._cleanup_guild(guild_id)
                await self._update_dashboard_for_guild(guild_id)
                if not was_intentional:
                    await self._send_error_log(
                        guild_id,
                        f"Bot was unexpectedly disconnected from voice channel **#{before.channel.name}**.",
                        track=active_track,
                    )
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

    # ── Favorites ────────────────────────────────────────────────────────────

    FAVORITE_EMOJI = "❤️"

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != self.FAVORITE_EMOJI:
            return
        guild_id = str(payload.guild_id) if payload.guild_id else None
        if not guild_id:
            return

        dashboard_msg = self.dashboard_messages.get(guild_id)
        if not dashboard_msg or dashboard_msg.id != payload.message_id:
            return

        track = self.current_track.get(guild_id)
        if not track or track.finished:
            return

        await self._add_favorite(guild_id, str(payload.user_id), track.metadata)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != self.FAVORITE_EMOJI:
            return
        guild_id = str(payload.guild_id) if payload.guild_id else None
        if not guild_id:
            return

        dashboard_msg = self.dashboard_messages.get(guild_id)
        if not dashboard_msg or dashboard_msg.id != payload.message_id:
            return

        track = self.current_track.get(guild_id)
        if not track or track.finished:
            return

        await self._remove_favorite(guild_id, str(payload.user_id), track.metadata.get('original_url', ''))

    async def _add_favorite(self, guild_id: str, user_id: str, metadata: dict):
        url = metadata.get('original_url', '')
        if not url:
            return
        favorites = await load_music_favorites()
        favorites.setdefault(guild_id, {}).setdefault(user_id, [])
        user_favs = favorites[guild_id][user_id]
        if any(f['url'] == url for f in user_favs):
            return
        user_favs.append({
            'url': url,
            'title': metadata.get('title', 'Unknown'),
            'thumbnail': metadata.get('thumbnail', ''),
            'duration': metadata.get('duration'),
        })
        await save_music_favorites(favorites)

    async def _remove_favorite(self, guild_id: str, user_id: str, url: str):
        if not url:
            return
        favorites = await load_music_favorites()
        user_favs = favorites.get(guild_id, {}).get(user_id)
        if not user_favs:
            return
        new_favs = [f for f in user_favs if f['url'] != url]
        if len(new_favs) == len(user_favs):
            return
        favorites[guild_id][user_id] = new_favs
        await save_music_favorites(favorites)

    favorites_group = app_commands.Group(name="favorites", description="❤️ Manage your favorite songs")

    @favorites_group.command(name="play", description="▶️ Queue all of your favorited songs.")
    async def favorites_play(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Servers only.", ephemeral=True)

        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        if not interaction.response.is_done():
            await interaction.response.defer()

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        favorites = await load_music_favorites()
        user_favs = favorites.get(guild_id, {}).get(user_id, [])

        if not user_favs:
            return await interaction.followup.send(
                "❌ You don't have any favorited songs yet. React ❤️ on the now-playing panel to save one."
            )

        if not self.blacklist:
            self.blacklist = await load_music_blacklist() or []

        entries = [
            {'url': f['url'], 'title': f['title'], 'thumbnail': f['thumbnail'], 'duration': f['duration']}
            for f in user_favs
        ]
        embed, _already_playing = await self._queue_playlist_entries(
            guild_id, entries, f"❤️ {interaction.user.display_name}'s Favorites", interaction.user
        )
        msg = await interaction.followup.send(embed=embed)
        interaction._followup_sent = True
        asyncio.create_task(_delete_after(msg, 10))
        await self._finalize_play(interaction, guild_id)

    @favorites_group.command(name="list", description="📋 Show your favorited songs.")
    async def favorites_list(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Servers only.", ephemeral=True)

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        favorites = await load_music_favorites()
        user_favs = favorites.get(guild_id, {}).get(user_id, [])

        embed = discord.Embed(title="❤️ Your Favorites", color=discord.Color.red())
        if not user_favs:
            embed.description = "No favorited songs yet. React ❤️ on the now-playing panel to save one."
        else:
            lines = []
            for i, f in enumerate(user_favs[:10], 1):
                dur = f" `{_fmt_duration(f['duration'])}`" if f.get('duration') else ""
                lines.append(f"`{i}.` [{f['title']}]({f['url']}){dur}")
            if len(user_favs) > 10:
                lines.append(f"*…and {len(user_favs) - 10} more*")
            embed.description = "\n".join(lines)
            embed.set_footer(text=f"Total: {len(user_favs)} songs")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @favorites_group.command(name="remove", description="🗑️ Remove a favorited song by its number in /favorites list.")
    @app_commands.describe(position="Position from /favorites list (1 = first)")
    async def favorites_remove(self, interaction: discord.Interaction, position: int):
        if not interaction.guild:
            return await interaction.response.send_message("Servers only.", ephemeral=True)

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        favorites = await load_music_favorites()
        user_favs = favorites.get(guild_id, {}).get(user_id, [])

        if not user_favs:
            return await interaction.response.send_message("You don't have any favorited songs.", ephemeral=True)
        if position < 1 or position > len(user_favs):
            return await interaction.response.send_message(f"Position must be 1–{len(user_favs)}.", ephemeral=True)

        removed = user_favs.pop(position - 1)
        favorites[guild_id][user_id] = user_favs
        await save_music_favorites(favorites)
        await interaction.response.send_message(f"🗑️ Removed **{removed['title']}** from your favorites.", ephemeral=True)

    @favorites_group.command(name="clear", description="🧹 Clear all of your favorited songs.")
    async def favorites_clear(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Servers only.", ephemeral=True)

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        favorites = await load_music_favorites()
        if guild_id in favorites and user_id in favorites[guild_id]:
            favorites[guild_id][user_id] = []
            await save_music_favorites(favorites)

        await interaction.response.send_message("🧹 Your favorites have been cleared.", ephemeral=True)

    # ── Audio Cache Slash Commands (Admin) ───────────────────────────────────

    musiccache_group = app_commands.Group(
        name="musiccache",
        description="💾 Manage the local YouTube audio cache (Admin)",
        default_permissions=discord.Permissions(administrator=True),
    )

    @musiccache_group.command(name="status", description="📊 Show YouTube audio cache usage and limits.")
    @app_commands.checks.has_permissions(administrator=True)
    async def musiccache_status(self, interaction: discord.Interaction):
        status = await self.get_cache_status()
        enabled_str = "✅ Enabled" if status["enabled"] else "⏸️ Disabled"
        used_mb = status["total_mb"]
        max_gb = status["max_size_gb"]
        pct = min(100.0, (status["total_bytes"] / status["max_bytes"] * 100.0)) if status["max_bytes"] > 0 else 0.0

        embed = discord.Embed(
            title="💾 YouTube Audio Cache",
            color=discord.Color.green() if status["enabled"] else discord.Color.orange(),
        )
        embed.add_field(name="Status", value=enabled_str, inline=True)
        embed.add_field(
            name="Cached Tracks",
            value=f"**{status['track_count']}** ({status['favorite_track_count']} ❤️ favs)",
            inline=True,
        )
        embed.add_field(
            name="Max Track Length",
            value=f"**{status['max_duration_minutes']} min**",
            inline=True,
        )
        embed.add_field(
            name="Disk Usage",
            value=f"**{used_mb:.1f} MB** / **{max_gb:.1f} GB** ({pct:.1f}%)",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @musiccache_group.command(name="settings", description="⚙️ Configure YouTube audio cache limits (Admin).")
    @app_commands.describe(
        max_duration_minutes="Max track length to cache in minutes (default: 30)",
        max_size_gb="Maximum total cache size in GB (default: 10)",
        enabled="Enable or disable caching",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def musiccache_settings(
        self,
        interaction: discord.Interaction,
        max_duration_minutes: int | None = None,
        max_size_gb: float | None = None,
        enabled: bool | None = None,
    ):
        status = await self.update_cache_settings(
            enabled=enabled,
            max_duration_minutes=max_duration_minutes,
            max_size_gb=max_size_gb,
        )
        embed = discord.Embed(
            title="⚙️ Audio Cache Settings Updated",
            description=(
                f"**Enabled:** {'Yes' if status['enabled'] else 'No'}\n"
                f"**Max Track Duration:** {status['max_duration_minutes']} min\n"
                f"**Max Cache Size:** {status['max_size_gb']:.1f} GB\n"
                f"**Current Usage:** {status['total_mb']:.1f} MB ({status['track_count']} tracks)"
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @musiccache_group.command(name="clear", description="🧹 Clear cached audio files from disk (Admin).")
    @app_commands.describe(keep_favorites="Preserve cached songs that are in someone's ❤️ Favorites (default: True)")
    @app_commands.checks.has_permissions(administrator=True)
    async def musiccache_clear(self, interaction: discord.Interaction, keep_favorites: bool = True):
        removed, freed_bytes = await self.clear_cache(keep_favorites=keep_favorites)
        freed_mb = freed_bytes / (1024 * 1024)
        note = " (❤️ Favorites preserved)" if keep_favorites else " (including ❤️ Favorites)"
        await interaction.response.send_message(
            f"🧹 Cleared **{removed}** cached track(s), freeing **{freed_mb:.1f} MB**{note}.",
            ephemeral=True,
        )

    @app_commands.command(name="musicdiag", description="🩺 Send a live music & voice diagnostic report to your DM.")
    async def musicdiag(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id) if interaction.guild else "0"
        if getattr(interaction, "user", None):
            self.last_requester[guild_id] = interaction.user
        if getattr(interaction, "channel", None):
            self.last_text_channel[guild_id] = interaction.channel
        track = self.current_track.get(guild_id) or self.last_track.get(guild_id)
        await interaction.response.defer(ephemeral=True)
        await self._send_error_log(
            guild_id,
            "Manual diagnostic snapshot requested via `/musicdiag`.",
            track=track,
        )
        await interaction.followup.send("🩺 Diagnostic report sent (check your DMs).", ephemeral=True)

    # ── Ambience Scene Mini-Controller (Discord) ─────────────────────────────

    def get_active_ambience_summary(self, guild_id: str) -> str:
        """Return a human-readable summary of active soundboard loops in `guild_id`."""
        mixer = guild_mixers.get(str(guild_id))
        if not mixer:
            return ""
        items = []
        for t in getattr(mixer, "tracks", []):
            if not t.finished and (t.metadata or {}).get("type") == "soundboard":
                bname = os.path.basename(t.file_path)
                vol_pct = round((t.metadata or {}).get("volume_modifier", 1.0) * 100)
                loop_tag = " · LOOP" if t.loop else ""
                items.append(f"`{bname}` ({vol_pct}%{loop_tag})")
        return ", ".join(items)

    def fade_out_guild_ambience(self, guild_id: str) -> int:
        """Smoothly fade out all active soundboard tracks in `guild_id`. Returns count."""
        mixer = guild_mixers.get(str(guild_id))
        if not mixer:
            return 0
        with mixer.lock:
            sb_list = [
                t for t in mixer.tracks
                if not t.finished and (t.metadata or {}).get("type") == "soundboard"
            ]
        for t in sb_list:
            t.start_fade_out(0.8)
        return len(sb_list)

    async def adjust_ambience_volume(self, guild_id: str, delta_pct: int) -> int:
        """Adjust soundboard master volume for `guild_id` by `delta_pct` (-100..+100)."""
        guild_id = str(guild_id)
        vols = server_volumes.setdefault(guild_id, {"music": 1.0, "soundboard": 0.5})
        cur_pct = round(float(vols.get("soundboard", 0.5)) * 100)
        new_pct = max(0, min(100, cur_pct + int(delta_pct)))
        new_master = new_pct / 100.0
        vols["soundboard"] = new_master
        await save_server_volumes(server_volumes)

        mixer = guild_mixers.get(guild_id)
        if mixer:
            for t in getattr(mixer, "tracks", []):
                if not t.finished and (t.metadata or {}).get("type") == "soundboard":
                    mod = float((t.metadata or {}).get("volume_modifier", 1.0))
                    t.volume = new_master * mod
        return new_pct

    async def _get_or_seed_scenes(self) -> list[dict]:
        """Load saved Ambience Scenes, seeding starter Lovecraftian presets if empty."""
        scenes_data = await load_ambience_scenes()
        scenes = scenes_data.get("scenes")
        if isinstance(scenes, dict):
            scenes = [{"id": k, **v} for k, v in scenes.items()]
        if not scenes:
            scenes = [
                {
                    "id": "arkham_rain_jazz",
                    "name": "Deštivý Arkham (1920s Noir)",
                    "icon": "🌧️",
                    "music_query": "1920s dark jazz noir detective ambience instrumental",
                    "music_url": "1920s dark jazz noir detective ambience instrumental",
                    "music_volume": 30,
                    "music_loop": "track",
                    "soundboard_tracks": [],
                    "soundboard": [],
                },
                {
                    "id": "occult_ritual_crypt",
                    "name": "Okultní Rituál v Kryptě",
                    "icon": "🕯️",
                    "music_query": "Call of Cthulhu dark ritual drone ambient music",
                    "music_url": "Call of Cthulhu dark ritual drone ambient music",
                    "music_volume": 35,
                    "music_loop": "track",
                    "soundboard_tracks": [],
                    "soundboard": [],
                },
                {
                    "id": "eldritch_combat",
                    "name": "Střet s Mýtem (Boj / Útěk)",
                    "icon": "⚔️",
                    "music_query": "dark orchestral horror combat ost",
                    "music_url": "dark orchestral horror combat ost",
                    "music_volume": 55,
                    "music_loop": "track",
                    "soundboard_tracks": [],
                    "soundboard": [],
                },
            ]
            scenes_data["scenes"] = scenes
            await save_ambience_scenes(scenes_data)
        return scenes

    async def open_scene_controller(self, interaction: discord.Interaction):
        """Open the interactive Scene Mini-Controller in Discord."""
        if not interaction.guild:
            return await interaction.response.send_message("❌ Pouze na serveru.", ephemeral=True)
        guild_id = str(interaction.guild.id)
        scenes = await self._get_or_seed_scenes()
        view = SceneControllerView(self, guild_id, scenes)
        await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=False)

    async def _scene_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        scenes = await self._get_or_seed_scenes()
        cur_low = (current or "").lower()
        choices = []
        for sc in scenes:
            sc_id = str(sc.get("id") or sc.get("scene_id") or sc.get("name"))
            label = f"{sc.get('icon', '🕯️')} {sc.get('name', sc_id)}"
            if not cur_low or cur_low in label.lower() or cur_low in sc_id.lower():
                choices.append(app_commands.Choice(name=label[:100], value=sc_id[:100]))
        return choices[:25]

    @app_commands.command(
        name="scene",
        description="🕯️ Otevře mini-ovladač scénických presetů nebo rovnou spustí vybranou scénu.",
    )
    @app_commands.describe(preset="Volitelně: rovnou vyberte scénický preset k okamžitému spuštění")
    @app_commands.autocomplete(preset=_scene_autocomplete)
    async def scene_cmd(self, interaction: discord.Interaction, preset: str | None = None):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Pouze na serveru.", ephemeral=True)
        guild_id = str(interaction.guild.id)
        scenes = await self._get_or_seed_scenes()

        if not preset:
            view = SceneControllerView(self, guild_id, scenes)
            return await interaction.response.send_message(embed=view.get_embed(), view=view)

        chosen = next(
            (
                s for s in scenes
                if str(s.get("id") or s.get("scene_id") or "").lower() == preset.lower()
                or str(s.get("name") or "").lower() == preset.lower()
            ),
            None,
        )
        if not chosen:
            return await interaction.response.send_message(
                f"❌ Scénický preset `{preset}` nebyl nalezen.", ephemeral=True
            )

        user_vc = getattr(getattr(interaction.user, "voice", None), "channel", None)
        ch_id = str(user_vc.id) if user_vc else None
        await interaction.response.defer()
        res = await self.activate_ambience_scene(guild_id, chosen, channel_id=ch_id)
        if res.get("status") == "error":
            return await interaction.followup.send(f"❌ {res.get('message')}", ephemeral=True)

        view = SceneControllerView(self, guild_id, scenes)
        note = f"✅ Aktivována scéna: {chosen.get('name', preset)}"
        await interaction.followup.send(embed=view.get_embed(status_note=note), view=view)


async def setup(bot):
    await bot.add_cog(Music(bot))
