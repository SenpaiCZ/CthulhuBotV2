import discord
import asyncio
import os
import time
from typing import Dict, Optional, Any
from dashboard.audio_mixer import MixingAudioSource
from models.database import SessionLocal
from services.settings_service import SettingsService

class AudioService:
    _guild_mixers: Dict[int, MixingAudioSource] = {}
    _server_volumes: Dict[int, Dict[str, float]] = {}
    _bot: Optional[discord.Client] = None
    _idle_timers: Dict[int, float] = {}

    def __init__(self, bot: discord.Client = None):
        if bot:
            AudioService._bot = bot
        self._load_volumes()

    @classmethod
    def _load_volumes(cls):
        """Loads all server volumes from the database on startup."""
        db = SessionLocal()
        try:
            results = SettingsService.get_all_guild_settings(db, "server_volumes")
            for guild_id_str, volumes in results.items():
                try:
                    cls._server_volumes[int(guild_id_str)] = volumes
                except (ValueError, TypeError):
                    continue
        finally:
            db.close()

    @classmethod
    def get_mixer(cls, guild_id: int) -> MixingAudioSource:
        """Retrieves or creates a MixingAudioSource for a guild."""
        gid = int(guild_id)
        if gid not in cls._guild_mixers:
            cls._guild_mixers[gid] = MixingAudioSource()
        return cls._guild_mixers[gid]

    @classmethod
    async def connect_to_voice(cls, guild: discord.Guild, channel_id: int):
        """Handles connection to a voice channel and initializes the mixer if needed."""
        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
             return None, "Voice channel not found."

        voice_client = guild.voice_client

        try:
            if voice_client:
                if not voice_client.is_connected():
                    try:
                        await voice_client.disconnect(force=True)
                    except Exception:
                        pass
                    voice_client = await channel.connect(timeout=60.0, reconnect=True)
                elif voice_client.channel.id != channel.id:
                    await voice_client.move_to(channel)
            else:
                voice_client = await channel.connect(timeout=60.0, reconnect=True)
        except asyncio.TimeoutError:
            return None, "Connection timed out. Check network/UDP ports."
        except Exception as e:
            return None, str(e)

        if not voice_client or not voice_client.is_connected():
            return None, "Failed to establish a stable connection."

        # Ensure mixer is playing if not already
        mixer = cls.get_mixer(guild.id)
        is_playing_mixer = False
        if voice_client.is_playing() and isinstance(voice_client.source, discord.PCMVolumeTransformer):
             if voice_client.source.original == mixer:
                 is_playing_mixer = True

        if not is_playing_mixer:
            if voice_client.is_playing():
                voice_client.stop()
            
            # Mixer handles volume per track now
            source = discord.PCMVolumeTransformer(mixer, volume=1.0)
            voice_client.play(source)

        # Update last_voice_channel_id in DB
        db = SessionLocal()
        try:
            SettingsService.set_setting(db, str(guild.id), "last_voice_channel_id", str(channel_id))
        finally:
            db.close()

        return voice_client, None

    @classmethod
    async def disconnect_from_voice(cls, guild: discord.Guild):
        """Disconnects from voice and cleans up the mixer."""
        if guild.voice_client:
            await guild.voice_client.disconnect()
        
        gid = guild.id
        mixer = cls._guild_mixers.pop(gid, None)
        if mixer:
            mixer.cleanup()
        
        if gid in cls._idle_timers:
            del cls._idle_timers[gid]
        
        # Update last_voice_channel_id in DB
        db = SessionLocal()
        try:
            SettingsService.set_setting(db, str(gid), "last_voice_channel_id", None)
        finally:
            db.close()

    @classmethod
    def play_soundboard(cls, guild_id: int, sound_path: str, loop: bool = False, volume_modifier: float = 1.0):
        """Plays a sound from the soundboard via the guild's mixer."""
        gid = int(guild_id)
        mixer = cls.get_mixer(gid)
        
        # Get master soundboard volume
        volumes = cls._server_volumes.get(gid, {'music': 1.0, 'soundboard': 0.5})
        sb_vol = volumes.get('soundboard', 0.5)
        
        final_vol = sb_vol * volume_modifier

        return mixer.add_track(
            sound_path,
            volume=final_vol,
            loop=loop,
            metadata={
                'type': 'soundboard',
                'volume_modifier': volume_modifier
            }
        )

    @classmethod
    async def set_volume(cls, guild_id: int, volume: float):
        """Sets the master soundboard volume for a guild."""
        gid = int(guild_id)
        vol_float = max(0.0, min(1.0, volume))
        
        if gid not in cls._server_volumes:
            cls._server_volumes[gid] = {'music': 1.0, 'soundboard': 0.5}
        
        cls._server_volumes[gid]['soundboard'] = vol_float
        
        # Update DB
        db = SessionLocal()
        try:
            SettingsService.set_setting(db, str(gid), "server_volumes", cls._server_volumes[gid])
        finally:
            db.close()
        
        # Update active tracks in mixer
        mixer = cls._guild_mixers.get(gid)
        if mixer:
            with mixer.lock:
                for track in mixer.tracks:
                    if track.metadata.get('type') == 'soundboard':
                        mod = track.metadata.get('volume_modifier', 1.0)
                        track.volume = vol_float * mod

    @classmethod
    async def idle_timeout_task(cls):
        """Background task to disconnect from voice after 10 minutes of silence."""
        while True:
            await asyncio.sleep(60) # Check every minute
            
            if cls._bot is None:
                continue

            # Use a list of guild_ids to iterate to avoid "dictionary changed size during iteration"
            guild_ids = list(cls._guild_mixers.keys())
            
            for gid in guild_ids:
                guild = cls._bot.get_guild(gid)
                if not guild or not guild.voice_client:
                    # Cleanup mixer if bot not in voice
                    mixer = cls._guild_mixers.pop(gid, None)
                    if mixer: mixer.cleanup()
                    if gid in cls._idle_timers:
                        del cls._idle_timers[gid]
                    continue

                mixer = cls._guild_mixers.get(gid)
                if not mixer: continue

                # Check if any tracks are active (not finished)
                active_tracks = [t for t in mixer.tracks if not t.finished]
                
                if not active_tracks:
                    # Track idle time
                    if gid not in cls._idle_timers:
                        cls._idle_timers[gid] = time.time()
                    
                    idle_duration = time.time() - cls._idle_timers[gid]
                    if idle_duration >= 600: # 10 minutes
                        print(f"[AudioService] Idle timeout for guild {gid}. Disconnecting.")
                        await cls.disconnect_from_voice(guild)
                else:
                    # Reset idle timer if tracks are playing
                    if gid in cls._idle_timers:
                        del cls._idle_timers[gid]
