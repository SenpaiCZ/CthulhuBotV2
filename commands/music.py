import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
import random
from functools import partial
from dashboard.app import guild_mixers, server_volumes
from dashboard.audio_mixer import MixingAudioSource
from loadnsave import load_music_blacklist, save_music_blacklist, load_server_volumes, save_server_volumes
from views.music_player import MusicPlayerView
from services.music_service import MusicService
from services.audio_service import AudioService

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Music"
        # Dashboards
        self.dashboard_messages = {}
        # List of banned URLs
        self.blacklist = []

        # Initialize AudioService with bot
        AudioService(bot)
        # Expose self to bot for dashboard access
        self.bot.music_cog = self

    async def cog_load(self):
        loaded = await load_music_blacklist()
        if isinstance(loaded, list):
            self.blacklist = loaded
        else:
            self.blacklist = []

        # Load server volumes into shared dict (sync with AudioService)
        volumes = await load_server_volumes()
        for gid, vols in volumes.items():
            try:
                AudioService._server_volumes[int(gid)] = vols
            except: pass

    def cog_unload(self):
        pass

    # --- Dashboard Helpers ---

    async def refresh_dashboard(self, interaction=None, guild_id=None):
        if interaction:
            guild_id = interaction.guild.id

        if not guild_id: return

        # 1. Update Existing Message
        message = self.dashboard_messages.get(str(guild_id))
        view = MusicPlayerView(guild_id)
        embed = view.get_embed()

        if message:
            try:
                await message.edit(embed=embed, view=view)
            except discord.NotFound:
                self.dashboard_messages.pop(str(guild_id), None)
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
                    self.dashboard_messages[str(guild_id)] = await interaction.original_response()

    # --- Slash Commands ---

    @app_commands.command(name="play", description="▶️ Plays a song from YouTube.")
    @app_commands.describe(query="The song name or URL to play")
    async def play(self, interaction: discord.Interaction, query: str):
        """🎵 Plays a song from YouTube."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.")
            return

        # Defer immediately
        await interaction.response.defer()

        # Connect using AudioService
        if not interaction.guild.voice_client or not interaction.guild.voice_client.is_connected():
            if interaction.user.voice:
                vc, error = await AudioService.connect_to_voice(interaction.guild, interaction.user.voice.channel.id)
                if error:
                    await interaction.followup.send(f"❌ {error}")
                    return
            else:
                await interaction.followup.send("You are not connected to a voice channel.")
                return

        try:
            # Resolve and add to queue via MusicService
            song_info = await MusicService.add_to_queue(interaction.guild.id, query)
            
            if song_info.get('original_url') in self.blacklist:
                # Remove from queue if blacklisted
                q = MusicService.get_queue(interaction.guild.id)
                if q: q.pop()
                await interaction.followup.send(f"❌ This song is blacklisted: {song_info['title']}")
                return

            song_info['requested_by'] = interaction.user.display_name

            # Send Dashboard
            guild_id = interaction.guild.id
            view = MusicPlayerView(guild_id)
            embed = view.get_embed()

            # If we already have a dashboard, delete it to send a fresh one at bottom
            old_msg = self.dashboard_messages.get(str(guild_id))
            if old_msg:
                try: await old_msg.delete()
                except: pass

            msg = await interaction.followup.send(embed=embed, view=view)
            self.dashboard_messages[str(guild_id)] = msg

            # Trigger play if nothing is playing
            if not MusicService.get_current_track(interaction.guild.id):
                await MusicService.process_queue(interaction.guild.id)

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}")

    @app_commands.command(name="skip", description="⏭️ Skips the current song.")
    async def skip(self, interaction: discord.Interaction):
        """⏭️ Skips the current song."""
        guild_id = interaction.guild.id
        track = MusicService.get_current_track(guild_id)
        if track or MusicService.get_queue(guild_id):
            MusicService.skip_track(guild_id)
            await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)
            await self.refresh_dashboard(guild_id=guild_id)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @app_commands.command(name="stop", description="🛑 Stops music, clears queue, and disconnects.")
    async def stop(self, interaction: discord.Interaction):
        """🛑 Stops music, clears queue, and disconnects."""
        guild_id = interaction.guild.id
        MusicService.stop_music(guild_id)
        await AudioService.disconnect_from_voice(interaction.guild)
        await interaction.response.send_message("🛑 Stopped.", ephemeral=True)
        await self.refresh_dashboard(guild_id=guild_id)

    @app_commands.command(name="pause", description="⏸️ Pauses the current song.")
    async def pause(self, interaction: discord.Interaction):
        """⏸️ Pauses the current song."""
        guild_id = interaction.guild.id
        state = MusicService.toggle_pause(guild_id)
        if state is not None:
            msg = "Paused" if state else "Resumed"
            await interaction.response.send_message(f"⏸️ {msg}.", ephemeral=True)
            await self.refresh_dashboard(guild_id=guild_id)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="▶️ Resumes the current song.")
    async def resume(self, interaction: discord.Interaction):
        """▶️ Resumes the current song."""
        guild_id = interaction.guild.id
        state = MusicService.toggle_pause(guild_id)
        if state is not None:
            msg = "Resumed" if not state else "Paused"
            await interaction.response.send_message(f"▶️ {msg}.", ephemeral=True)
            await self.refresh_dashboard(guild_id=guild_id)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @app_commands.command(name="shuffle", description="🔀 Shuffles the queue.")
    async def shuffle(self, interaction: discord.Interaction):
        """🔀 Shuffles the queue."""
        guild_id = interaction.guild.id
        q = MusicService.get_queue(guild_id)
        if len(q) > 1:
            MusicService.shuffle_queue(guild_id)
            await interaction.response.send_message("🔀 Queue shuffled.", ephemeral=True)
            await self.refresh_dashboard(guild_id=guild_id)
        else:
            await interaction.response.send_message("Not enough songs to shuffle.", ephemeral=True)

    @app_commands.command(name="volume", description="🔊 Sets the music volume (0-100). Persists per server.")
    @app_commands.describe(vol="Volume level (0-100)")
    async def volume(self, interaction: discord.Interaction, vol: int):
        """🔊 Sets the music volume (0-100). Persists per server."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        new_vol = max(0, min(100, vol)) / 100

        # Update AudioService volumes
        if guild_id not in AudioService._server_volumes:
            AudioService._server_volumes[guild_id] = {'music': 1.0, 'soundboard': 0.5}
        
        AudioService._server_volumes[guild_id]['music'] = new_vol
        
        # Save to database
        from models.database import SessionLocal
        from services.settings_service import SettingsService
        db = SessionLocal()
        try:
            SettingsService.set_setting(db, str(guild_id), "server_volumes", AudioService._server_volumes[guild_id])
        finally:
            db.close()

        track = MusicService.get_current_track(guild_id)
        if track:
            track.volume = new_vol
            await interaction.response.send_message(f"🔊 Music volume set to {vol}%", ephemeral=True)
            await self.refresh_dashboard(guild_id=guild_id)
        else:
            await interaction.response.send_message(f"🔊 Music volume set to {vol}% (will apply to next song)", ephemeral=True)

    @app_commands.command(name="loop", description="🔁 Toggles loop for the current song.")
    async def loop(self, interaction: discord.Interaction):
        """🔁 Toggles loop for the current song."""
        guild_id = interaction.guild.id
        state = MusicService.toggle_loop(guild_id)
        msg = "ON" if state else "OFF"
        await interaction.response.send_message(f"🔁 Loop {msg}.", ephemeral=True)
        await self.refresh_dashboard(guild_id=guild_id)

    @app_commands.command(name="queue", description="🎼 Shows the current queue.")
    async def queue(self, interaction: discord.Interaction):
        """🎼 Shows the current queue."""
        guild_id = interaction.guild.id
        view = MusicPlayerView(guild_id)
        embed = view.get_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="nowplaying", description="🎵 Shows the currently playing song.")
    async def nowplaying(self, interaction: discord.Interaction):
        """💿 Shows the currently playing song."""
        guild_id = interaction.guild.id
        view = MusicPlayerView(guild_id)
        embed = view.get_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Music(bot))
