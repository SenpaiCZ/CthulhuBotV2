import discord
from discord.ui import View, Button

class MusicView(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = str(guild_id)
        self.update_buttons()

    def update_buttons(self):
        # Get current state
        track = self.cog.current_track.get(self.guild_id)
        is_playing = track and not track.paused and not track.finished
        is_looping = track and track.loop

        # Play/Pause
        self.btn_play_pause.style = discord.ButtonStyle.secondary
        self.btn_play_pause.emoji = "⏸️" if is_playing else "▶️"
        self.btn_play_pause.label = "Pause" if is_playing else "Resume"
        self.btn_play_pause.disabled = not track

        # Loop
        self.btn_loop.style = discord.ButtonStyle.success if is_looping else discord.ButtonStyle.secondary
        self.btn_loop.disabled = not track

        # Other buttons enabled if track exists
        queue_len = len(self.cog.queue.get(self.guild_id, []))
        self.btn_skip.disabled = not track
        self.btn_stop.disabled = not track
        self.btn_shuffle.disabled = queue_len < 2

    @discord.ui.button(custom_id="music_play_pause", style=discord.ButtonStyle.secondary, emoji="⏯️", row=0)
    async def btn_play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.toggle_pause(interaction)

    @discord.ui.button(custom_id="music_skip", style=discord.ButtonStyle.secondary, emoji="⏭️", row=0)
    async def btn_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.skip_track(interaction)

    @discord.ui.button(custom_id="music_stop", style=discord.ButtonStyle.danger, emoji="⏹️", row=0)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.stop_music(interaction)

    @discord.ui.button(custom_id="music_loop", style=discord.ButtonStyle.secondary, emoji="🔁", row=1)
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.toggle_loop(interaction)

    @discord.ui.button(custom_id="music_shuffle", style=discord.ButtonStyle.secondary, emoji="🔀", row=1)
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.shuffle_queue(interaction)

    @discord.ui.button(custom_id="music_refresh", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.refresh_dashboard(interaction)

    def get_embed(self):
        track = self.cog.current_track.get(self.guild_id)
        queue = self.cog.queue.get(self.guild_id, [])

        embed = discord.Embed(color=discord.Color.blurple())

        if track:
            status = "▶️ Now Playing"
            if track.paused: status = "⏸️ Paused"

            title = track.metadata.get('title', 'Unknown Title')
            url = track.metadata.get('original_url', '')
            req = track.metadata.get('requested_by', 'Unknown')
            thumb = track.metadata.get('thumbnail', '')
            duration = track.metadata.get('duration') # Seconds

            embed.title = f"{status}: {title}"
            embed.url = url
            if thumb: embed.set_thumbnail(url=thumb)

            desc = f"**Requested by:** {req}\n"

            if duration:
                try:
                    m, s = divmod(int(duration), 60)
                    desc += f"**Duration:** {m:02d}:{s:02d}\n"
                except: pass

            desc += f"**Volume:** {int(track.volume * 100)}% | **Loop:** {'ON' if track.loop else 'OFF'}"
            embed.description = desc
        else:
            embed.title = "🔇 No Music Playing"
            embed.description = "Queue is empty. Use `/play` to add songs!"

        # Queue Field
        if queue:
            q_text = ""
            for i, song in enumerate(queue[:5], 1):
                title_esc = song['title'].replace('[', '(').replace(']', ')')
                q_text += f"`{i}.` [{title_esc[:40]}]({song['original_url']})\n"

            if len(queue) > 5:
                q_text += f"*...and {len(queue)-5} more*"

            embed.add_field(name=f"📚 Queue ({len(queue)})", value=q_text, inline=False)
        else:
            if not track:
                embed.set_footer(text="Ready to play!")
            else:
                embed.set_footer(text="Queue empty.")

        return embed
