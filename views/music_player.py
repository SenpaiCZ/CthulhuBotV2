import discord
import asyncio
from discord.ui import View, Button
from services.music_service import MusicService
from services.audio_service import AudioService
from typing import Optional

class MusicPlayerView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.update_buttons()

    def update_buttons(self):
        """Updates the visual state of the buttons based on the current track and queue."""
        track = MusicService.get_current_track(self.guild_id)
        queue = MusicService.get_queue(self.guild_id)
        
        is_playing = track and not track.paused and not track.finished
        is_looping = track and track.loop if track else False

        # Play/Pause
        self.btn_play_pause.style = discord.ButtonStyle.secondary
        self.btn_play_pause.emoji = "⏸️" if is_playing else "▶️"
        self.btn_play_pause.label = "Pause" if is_playing else "Resume"
        self.btn_play_pause.disabled = not track

        # Loop
        self.btn_loop.style = discord.ButtonStyle.success if is_looping else discord.ButtonStyle.secondary
        self.btn_loop.disabled = not track

        # Other buttons enabled if track exists or queue is not empty
        self.btn_skip.disabled = not track and not queue
        self.btn_stop.disabled = not track
        self.btn_shuffle.disabled = len(queue) < 2
        self.btn_queue.disabled = not track and not queue

    @discord.ui.button(custom_id="music_play_pause", style=discord.ButtonStyle.secondary, emoji="⏯️", row=0)
    async def btn_play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = MusicService.toggle_pause(self.guild_id)
        if state is not None:
            msg = "Paused" if state else "Resumed"
            await interaction.response.send_message(f"⏯️ {msg}.", ephemeral=True)
            await self.refresh_view(interaction)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @discord.ui.button(custom_id="music_skip", style=discord.ButtonStyle.secondary, emoji="⏭️", row=0)
    async def btn_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        track = MusicService.get_current_track(self.guild_id)
        if track or MusicService.get_queue(self.guild_id):
            MusicService.skip_track(self.guild_id)
            await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)
            # If nothing was playing but queue had items, skip_track might not trigger process_queue immediately
            # because it sets track.finished = True. The mixer thread will handle it.
            # We wait a bit or just refresh.
            await asyncio.sleep(0.5)
            await self.refresh_view(interaction)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @discord.ui.button(custom_id="music_stop", style=discord.ButtonStyle.danger, emoji="⏹️", row=0)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        MusicService.stop_music(self.guild_id)
        await AudioService.disconnect_from_voice(interaction.guild)
        await interaction.response.send_message("⏹️ Stopped and disconnected.", ephemeral=True)
        await self.refresh_view(interaction)

    @discord.ui.button(custom_id="music_loop", style=discord.ButtonStyle.secondary, emoji="🔁", row=1)
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = MusicService.toggle_loop(self.guild_id)
        msg = "ON" if state else "OFF"
        await interaction.response.send_message(f"🔁 Loop {msg}.", ephemeral=True)
        await self.refresh_view(interaction)

    @discord.ui.button(custom_id="music_shuffle", style=discord.ButtonStyle.secondary, emoji="🔀", row=1)
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = MusicService.get_queue(self.guild_id)
        if len(queue) > 1:
            MusicService.shuffle_queue(self.guild_id)
            await interaction.response.send_message("🔀 Queue shuffled.", ephemeral=True)
            await self.refresh_view(interaction)
        else:
            await interaction.response.send_message("Not enough songs to shuffle.", ephemeral=True)

    @discord.ui.button(custom_id="music_queue", style=discord.ButtonStyle.secondary, emoji="🎼", row=1)
    async def btn_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.get_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(custom_id="music_refresh", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.refresh_view(interaction)

    async def refresh_view(self, interaction: discord.Interaction):
        """Updates the message with the latest embed and view state."""
        self.update_buttons()
        embed = self.get_embed()
        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            print(f"Error refreshing music view: {e}")

    def get_embed(self) -> discord.Embed:
        track = MusicService.get_current_track(self.guild_id)
        queue = MusicService.get_queue(self.guild_id)

        embed = discord.Embed(color=discord.Color.blurple())

        if track:
            status = "▶️ Now Playing"
            if track.paused: status = "⏸️ Paused"

            title = track.metadata.get('title', 'Unknown Title')
            url = track.metadata.get('original_url', '')
            req = track.metadata.get('requested_by', 'Unknown')
            thumb = track.metadata.get('thumbnail', '')
            duration = track.metadata.get('duration')

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
