import math
import discord
from discord.ui import View, Button, Select


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
        self.btn_vol_down.disabled = not is_active
        self.btn_vol_up.disabled = not is_active
        self.btn_fav.disabled = not is_active

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

    @discord.ui.button(label="Scenes", emoji="🕯️", custom_id="music_scenes",
                       style=discord.ButtonStyle.secondary, row=0)
    async def btn_scenes(self, interaction: discord.Interaction, button: Button):
        await self.cog.open_scene_controller(interaction)

    # ── Row 1 ────────────────────────────────────────────────────────────────

    @discord.ui.button(label="Loop: OFF", emoji="🔁", custom_id="music_loop",
                       style=discord.ButtonStyle.secondary, row=1)
    async def btn_loop(self, interaction: discord.Interaction, button: Button):
        await self.cog.toggle_loop(interaction)

    @discord.ui.button(label="Shuffle", emoji="🔀", custom_id="music_shuffle",
                       style=discord.ButtonStyle.secondary, row=1)
    async def btn_shuffle(self, interaction: discord.Interaction, button: Button):
        await self.cog.shuffle_queue(interaction)

    @discord.ui.button(label="-10%", emoji="🔉", custom_id="music_vol_down",
                       style=discord.ButtonStyle.secondary, row=1)
    async def btn_vol_down(self, interaction: discord.Interaction, button: Button):
        await self.cog.adjust_volume(interaction, -10)

    @discord.ui.button(label="+10%", emoji="🔊", custom_id="music_vol_up",
                       style=discord.ButtonStyle.secondary, row=1)
    async def btn_vol_up(self, interaction: discord.Interaction, button: Button):
        await self.cog.adjust_volume(interaction, 10)

    @discord.ui.button(label="Favorite", emoji="❤️", custom_id="music_favorite",
                       style=discord.ButtonStyle.secondary, row=1)
    async def btn_fav(self, interaction: discord.Interaction, button: Button):
        await self.cog.toggle_favorite_button(interaction)

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
            vol_line = f"**Volume:** {vol_pct}%"
            if meta.get('is_cached'):
                vol_line += " · 💾 **Cached**"
            lines.append(vol_line)

            if hasattr(self.cog, "get_active_ambience_summary"):
                amb = self.cog.get_active_ambience_summary(self.guild_id)
                if amb:
                    lines.append(f"🕯️ **Ambience:** {amb}")

            embed.description = "\n".join(l for l in lines if l)
        else:
            embed.title = "🔇 No Music Playing"
            desc = "Use `/play` to add songs or `/scene` to launch an Ambience Scene."
            if hasattr(self.cog, "get_active_ambience_summary"):
                amb = self.cog.get_active_ambience_summary(self.guild_id)
                if amb:
                    desc += f"\n🕯️ **Active Ambience:** {amb}"
            embed.description = desc

        if queue:
            q_lines = []
            for i, song in enumerate(queue[:10], 1):
                t = song.get('title', 'Unknown')
                if len(t) > 45:
                    t = t[:42] + "…"
                t_esc = t.replace('[', '(').replace(']', ')')
                dur = song.get('duration')
                dur_str = f" `{_fmt_duration(dur)}`" if dur else ""
                cache_icon = " 💾" if song.get('is_cached') else ""
                url = song.get('original_url', '')
                if url:
                    q_lines.append(f"`{i}.` [{t_esc}]({url}){dur_str}{cache_icon}")
                else:
                    q_lines.append(f"`{i}.` {t_esc}{dur_str}{cache_icon}")

            if len(queue) > 10:
                q_lines.append(f"*…and {len(queue) - 10} more*")

            total_dur = sum(s.get('duration', 0) or 0 for s in queue)
            field_title = f"📚 Queue — {len(queue)} song{'s' if len(queue) != 1 else ''}"
            if total_dur:
                field_title += f" · {_fmt_duration(total_dur)}"

            embed.add_field(name=field_title, value="\n".join(q_lines), inline=False)
        else:
            if is_active:
                embed.set_footer(text="Queue empty · /play or 🕯️ Scenes")

        return embed


class _ScenePresetSelect(Select):
    def __init__(self, parent_view: "SceneControllerView", scenes: list[dict]):
        self.parent_view = parent_view
        options = []
        for sc in scenes[:25]:
            sc_id = str(sc.get("id") or sc.get("scene_id") or sc.get("name"))
            icon = (sc.get("icon") or "🕯️").strip()
            name = (sc.get("name") or sc_id)[:90]
            sb_list = sc.get("soundboard_tracks") or sc.get("soundboard") or []
            mq = (sc.get("music_query") or sc.get("music_url") or "No music")[:55]
            desc = f"♪ {mq} | ◐ {len(sb_list)} sound layer(s)"
            options.append(
                discord.SelectOption(
                    label=name,
                    value=sc_id,
                    emoji=icon if len(icon) <= 2 else "🕯️",
                    description=desc[:100],
                )
            )
        super().__init__(
            placeholder="🕯️ Vyberte scénický preset k okamžitému spuštění...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.on_select_scene(interaction, self.values[0])


class SceneControllerView(View):
    """Interactive Discord mini-controller for Ambience Scenes & Soundboard layers."""

    def __init__(self, cog, guild_id: str, scenes: list[dict]):
        super().__init__(timeout=600)
        self.cog = cog
        self.guild_id = str(guild_id)
        self.scenes = scenes or []
        if self.scenes:
            self.add_item(_ScenePresetSelect(self, self.scenes))

    def get_embed(self, status_note: str | None = None) -> discord.Embed:
        embed = discord.Embed(
            title="🕯️ Mini-Ovladač Scény (Ambience Controller)",
            description=(
                "Přepínejte kompletní zvukové scény (YouTube hudba + nekonečné Soundboard smyčky "
                "s plynulým prolínáním) přímo z Discordu."
            ),
            color=discord.Color.dark_teal(),
        )
        track = self.cog.current_track.get(self.guild_id)
        if track and not track.finished:
            t_title = track.metadata.get("title", "Unknown")
            vol_pct = _vol_to_pct(track.volume)
            embed.add_field(
                name="▶️ Aktuální Hudba",
                value=f"**{t_title}** ({vol_pct}% · Loop: `{self.cog.loop_mode.get(self.guild_id, 'off')}`)",
                inline=False,
            )
        else:
            embed.add_field(name="▶️ Aktuální Hudba", value="*Nic nehraje*", inline=False)

        amb = (
            self.cog.get_active_ambience_summary(self.guild_id)
            if hasattr(self.cog, "get_active_ambience_summary")
            else ""
        )
        embed.add_field(
            name="◐ Aktivní Soundboard Smyčky",
            value=amb or "*Žádná aktivní ambientní smyčka*",
            inline=False,
        )

        if self.scenes:
            sc_lines = []
            for sc in self.scenes[:8]:
                icon = sc.get("icon") or "🕯️"
                name = sc.get("name") or sc.get("id")
                sb_count = len(sc.get("soundboard_tracks") or sc.get("soundboard") or [])
                m_vol = sc.get("music_volume", 35)
                sc_lines.append(f"{icon} **{name}** — ♪ {m_vol}% · ◐ {sb_count} vrstvy")
            embed.add_field(
                name=f"📜 Dostupné Scény ({len(self.scenes)})",
                value="\n".join(sc_lines),
                inline=False,
            )

        if status_note:
            embed.set_footer(text=status_note)
        else:
            embed.set_footer(text="Tip: Další scény a vrstvy můžete upravovat na Web Dashboardu (/admin/music)")
        return embed

    async def on_select_scene(self, interaction: discord.Interaction, scene_id: str):
        scene = next(
            (s for s in self.scenes if str(s.get("id") or s.get("scene_id") or s.get("name")) == scene_id),
            None,
        )
        if not scene:
            return await interaction.response.send_message("❌ Scéna nebyla nalezena.", ephemeral=True)

        user_vc = getattr(getattr(interaction.user, "voice", None), "channel", None)
        ch_id = str(user_vc.id) if user_vc else None
        await interaction.response.defer()
        res = await self.cog.activate_ambience_scene(self.guild_id, scene, channel_id=ch_id)
        if res.get("status") == "error":
            await interaction.followup.send(f"❌ {res.get('message')}", ephemeral=True)
            return
        note = f"✅ Aktivována scéna: {scene.get('name', scene_id)}"
        await interaction.edit_original_response(embed=self.get_embed(status_note=note), view=self)

    @discord.ui.button(label="Utlumit Ambience", emoji="🔇", style=discord.ButtonStyle.secondary, row=1)
    async def btn_fade_ambience(self, interaction: discord.Interaction, button: Button):
        count = self.cog.fade_out_guild_ambience(self.guild_id)
        note = f"🔇 Utlumeno {count} ambientních smyček." if count else "ℹ️ Žádné ambientní smyčky neběžely."
        await interaction.response.edit_message(embed=self.get_embed(status_note=note), view=self)

    @discord.ui.button(label="Ambience -15%", emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def btn_amb_down(self, interaction: discord.Interaction, button: Button):
        new_pct = await self.cog.adjust_ambience_volume(self.guild_id, -15)
        await interaction.response.edit_message(
            embed=self.get_embed(status_note=f"🔉 Hlasitost Ambience: {new_pct}%"),
            view=self,
        )

    @discord.ui.button(label="Ambience +15%", emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def btn_amb_up(self, interaction: discord.Interaction, button: Button):
        new_pct = await self.cog.adjust_ambience_volume(self.guild_id, +15)
        await interaction.response.edit_message(
            embed=self.get_embed(status_note=f"🔊 Hlasitost Ambience: {new_pct}%"),
            view=self,
        )

    @discord.ui.button(label="Hudba Pause/Play", emoji="⏯️", style=discord.ButtonStyle.primary, row=1)
    async def btn_toggle_music(self, interaction: discord.Interaction, button: Button):
        track = self.cog.current_track.get(self.guild_id)
        if not track or track.finished:
            return await interaction.response.send_message("ℹ️ Momentálně nehraje žádná YouTube skladba.", ephemeral=True)
        track.paused = not track.paused
        state_txt = "⏸️ Hudba pozastavena" if track.paused else "▶️ Hudba pokračuje"
        await self.cog._update_dashboard_for_guild(self.guild_id)
        await interaction.response.edit_message(embed=self.get_embed(status_note=state_txt), view=self)

