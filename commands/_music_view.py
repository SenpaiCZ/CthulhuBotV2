import math
import discord
from discord.ui import View, Button


def _pct_to_vol(pct: int) -> float:
    """Convert 0-100 slider percent to 0.0-1.0 linear amplitude (quadratic curve for log feel)."""
    if pct <= 0: return 0.0
    if pct >= 100: return 1.0
    return (pct / 100.0) ** 2

def _vol_to_pct(vol: float) -> int:
    """Inverse: 0.0-1.0 linear amplitude back to 0-100 slider percent."""
    if vol <= 0: return 0
    if vol >= 1.0: return 100
    return round(math.sqrt(vol) * 100)


def _fmt_duration(seconds) -> str:
    """Format seconds → mm:ss or h:mm:ss."""
    try:
        s = int(seconds)
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{sec:02d}"
        return f"{m:02d}:{sec:02d}"
    except Exception:
        return "?:??"


def _progress_bar(elapsed: float, duration: float, width: int = 20) -> str:
    """Return a Unicode block progress bar string."""
    frac = max(0.0, min(1.0, elapsed / duration)) if duration > 0 else 0.0
    filled = int(frac * width)
    return "█" * filled + "░" * (width - filled)


class MusicView(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = str(guild_id)
        self._build_buttons()

    def _build_buttons(self):
        track = self.cog.current_track.get(self.guild_id)
        queue = self.cog.queue.get(self.guild_id, [])
        is_active = track and not track.finished
        is_playing = is_active and not track.paused
        loop_mode = self.cog.loop_mode.get(self.guild_id, "off")

        # Row 0: primary controls
        self.btn_pause.emoji = "⏸️" if is_playing else "▶️"
        self.btn_pause.label = "Pause" if is_playing else "Resume"
        self.btn_pause.style = discord.ButtonStyle.primary if is_playing else discord.ButtonStyle.secondary
        self.btn_pause.disabled = not is_active

        self.btn_skip.disabled = not is_active
        self.btn_stop.disabled = not is_active

        # Row 1: queue controls
        _loop_styles = {"off": discord.ButtonStyle.secondary, "track": discord.ButtonStyle.success, "queue": discord.ButtonStyle.primary}
        _loop_labels = {"off": "Loop: OFF", "track": "🔂 Loop: Track", "queue": "🔁 Loop: Queue"}
        self.btn_loop.style = _loop_styles[loop_mode]
        self.btn_loop.label = _loop_labels[loop_mode]
        self.btn_loop.disabled = not is_active and len(queue) == 0

        self.btn_shuffle.disabled = len(queue) < 2

    # ── Row 0 ────────────────────────────────────────────────────────────────

    @discord.ui.button(label="Pause", emoji="⏸️", custom_id="music_pause", row=0)
    async def btn_pause(self, interaction: discord.Interaction, button: Button):
        await self.cog.toggle_pause(interaction)

    @discord.ui.button(label="Skip", emoji="⏭️", custom_id="music_skip",
                       style=discord.ButtonStyle.secondary, row=0)
    async def btn_skip(self, interaction: discord.Interaction, button: Button):
        await self.cog.skip_track(interaction)

    @discord.ui.button(label="Stop", emoji="⏹️", custom_id="music_stop",
                       style=discord.ButtonStyle.danger, row=0)
    async def btn_stop(self, interaction: discord.Interaction, button: Button):
        await self.cog.stop_music(interaction)

    # ── Row 1 ────────────────────────────────────────────────────────────────

    @discord.ui.button(label="Loop: OFF", emoji="🔁", custom_id="music_loop",
                       style=discord.ButtonStyle.secondary, row=1)
    async def btn_loop(self, interaction: discord.Interaction, button: Button):
        await self.cog.toggle_loop(interaction)

    @discord.ui.button(label="Shuffle", emoji="🔀", custom_id="music_shuffle",
                       style=discord.ButtonStyle.secondary, row=1)
    async def btn_shuffle(self, interaction: discord.Interaction, button: Button):
        await self.cog.shuffle_queue(interaction)

    # ── Embed ────────────────────────────────────────────────────────────────

    def get_embed(self) -> discord.Embed:
        track = self.cog.current_track.get(self.guild_id)
        queue = self.cog.queue.get(self.guild_id, [])

        is_active = track and not track.finished

        if is_active:
            color = discord.Color.yellow() if track.paused else discord.Color.green()
        else:
            color = discord.Color.greyple()

        embed = discord.Embed(color=color)

        if is_active:
            meta = track.metadata
            title = meta.get('title', 'Unknown')
            orig_url = meta.get('original_url', '')
            thumbnail = meta.get('thumbnail', '')
            duration = meta.get('duration')
            req = meta.get('requested_by', 'Unknown')
            _lm = self.cog.loop_mode.get(self.guild_id, "off")
            loop_icon = {"off": "", "track": "🔂 ", "queue": "🔁 "}.get(_lm, "")
            status = "⏸️ Paused" if track.paused else "▶️ Now Playing"

            embed.title = f"{status} — {loop_icon}{title}"
            if orig_url:
                embed.url = orig_url
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)

            lines = [f"**Requested by:** {req}"]

            if duration and duration > 0:
                elapsed = track.elapsed
                bar = _progress_bar(elapsed, duration)
                lines.append(
                    f"`{_fmt_duration(elapsed)}` `{bar}` `{_fmt_duration(duration)}`"
                )
            else:
                # Livestream or unknown duration
                lines.append("🔴 **Live**" if not duration else "")

            vol_pct = _vol_to_pct(track.volume)
            lines.append(f"**Volume:** {vol_pct}%")

            embed.description = "\n".join(l for l in lines if l)
        else:
            embed.title = "🔇 No Music Playing"
            embed.description = "Use `/play` to add songs to the queue."

        if queue:
            q_lines = []
            for i, song in enumerate(queue[:10], 1):
                t = song.get('title', 'Unknown')
                if len(t) > 45:
                    t = t[:42] + "…"
                t_esc = t.replace('[', '(').replace(']', ')')
                dur = song.get('duration')
                dur_str = f" `{_fmt_duration(dur)}`" if dur else ""
                url = song.get('original_url', '')
                if url:
                    q_lines.append(f"`{i}.` [{t_esc}]({url}){dur_str}")
                else:
                    q_lines.append(f"`{i}.` {t_esc}{dur_str}")

            if len(queue) > 10:
                q_lines.append(f"*…and {len(queue) - 10} more*")

            total_dur = sum(s.get('duration', 0) or 0 for s in queue)
            field_title = f"📚 Queue — {len(queue)} song{'s' if len(queue) != 1 else ''}"
            if total_dur:
                field_title += f" · {_fmt_duration(total_dur)}"

            embed.add_field(name=field_title, value="\n".join(q_lines), inline=False)
        else:
            if is_active:
                embed.set_footer(text="Queue empty · /play to add more")

        return embed
