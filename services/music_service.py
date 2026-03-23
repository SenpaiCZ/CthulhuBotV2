import discord
import yt_dlp
import asyncio
import os
import random
from functools import partial
from typing import Dict, List, Optional, Any
from services.audio_service import AudioService
from dashboard.audio_mixer import MixingAudioSource, Track

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
    'socket_timeout': 30,
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -reconnect_on_network_error 1 -reconnect_on_http_error 4xx,5xx -timeout 10000000',
    'options': '-vn',
}

class MusicService:
    _queues: Dict[int, List[dict]] = {}
    _current_tracks: Dict[int, Track] = {}
    _looping: Dict[int, bool] = {}
    _shuffling: Dict[int, bool] = {}

    @classmethod
    async def add_to_queue(cls, guild_id: int, query: str) -> dict:
        """Resolve the track via yt-dlp and add to _queues dictionary."""
        opts = YTDL_OPTIONS.copy()
        if os.path.isfile('cookies/cookies.txt'):
            opts['cookiefile'] = 'cookies/cookies.txt'

        with yt_dlp.YoutubeDL(opts) as ydl:
            # Use the bot's loop if available from AudioService
            loop = AudioService._bot.loop if AudioService._bot else asyncio.get_event_loop()
            
            info = await loop.run_in_executor(
                None,
                partial(ydl.extract_info, query, download=False)
            )

            if 'entries' in info:
                info = info['entries'][0]

            song_info = {
                'title': info['title'],
                'url': info['url'],
                'original_url': info.get('webpage_url', info['url']),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration'),
                'type': 'music'
            }

            if guild_id not in cls._queues:
                cls._queues[guild_id] = []
            
            cls._queues[guild_id].append(song_info)
            return song_info

    @classmethod
    def get_next_track(cls, guild_id: int) -> Optional[dict]:
        """Get the next song info based on looping/shuffling settings."""
        if guild_id not in cls._queues or not cls._queues[guild_id]:
            return None
        
        if cls._shuffling.get(guild_id, False):
            idx = random.randrange(len(cls._queues[guild_id]))
            return cls._queues[guild_id].pop(idx)
        
        return cls._queues[guild_id].pop(0)

    @classmethod
    def play_song(cls, guild_id: int, track_info: dict) -> Track:
        """Adds a track to the guild's mixer and starts playback."""
        mixer = AudioService.get_mixer(guild_id)
        
        # Retrieve music volume from AudioService
        volumes = AudioService._server_volumes.get(guild_id, {'music': 1.0, 'soundboard': 0.5})
        music_vol = volumes.get('music', 1.0)

        # We pass the parameters directly to mixer.add_track as it expects them
        track = mixer.add_track(
            file_path=track_info['url'],
            is_url=True,
            metadata=track_info,
            volume=music_vol,
            loop=cls._looping.get(guild_id, False),
            before_options=FFMPEG_OPTIONS['before_options'],
            options=FFMPEG_OPTIONS['options'],
            on_finish=partial(cls._on_track_finish, guild_id)
        )
        cls._current_tracks[guild_id] = track
        return track

    @classmethod
    def _on_track_finish(cls, guild_id: int):
        """Callback triggered when a track finishes playing."""
        if AudioService._bot:
            asyncio.run_coroutine_threadsafe(cls.process_queue(guild_id), AudioService._bot.loop)

    @classmethod
    async def process_queue(cls, guild_id: int):
        """Processes the next item in the queue for a guild."""
        next_info = cls.get_next_track(guild_id)
        if next_info:
            cls.play_song(guild_id, next_info)
        else:
            cls._current_tracks.pop(guild_id, None)

    @classmethod
    def skip_track(cls, guild_id: int) -> None:
        """Stop the current track and start the next."""
        current = cls._current_tracks.get(guild_id)
        if current:
            current.finished = True
            # The on_finish callback will be triggered by the mixer reading thread

    @classmethod
    def get_queue(cls, guild_id: int) -> List[dict]:
        """Return the current queue for a guild."""
        return cls._queues.get(int(guild_id), [])

    @classmethod
    def get_current_track(cls, guild_id: int) -> Optional[Track]:
        """Return the currently playing track for a guild."""
        return cls._current_tracks.get(int(guild_id))

    @classmethod
    def toggle_loop(cls, guild_id: int) -> bool:
        """Toggles loop for the current guild."""
        cls._looping[guild_id] = not cls._looping.get(guild_id, False)
        # Update current track if it exists
        current = cls._current_tracks.get(guild_id)
        if current:
            current.loop = cls._looping[guild_id]
        return cls._looping[guild_id]

    @classmethod
    def toggle_shuffle(cls, guild_id: int) -> bool:
        """Toggles shuffle for the current guild."""
        cls._shuffling[guild_id] = not cls._shuffling.get(guild_id, False)
        return cls._shuffling[guild_id]

    @classmethod
    def shuffle_queue(cls, guild_id: int):
        """Shuffles the current queue for a guild."""
        if guild_id in cls._queues:
            random.shuffle(cls._queues[guild_id])

    @classmethod
    def toggle_pause(cls, guild_id: int) -> Optional[bool]:
        """Toggles pause for the current track."""
        current = cls._current_tracks.get(guild_id)
        if current:
            current.paused = not current.paused
            return current.paused
        return None

    @classmethod
    def stop_music(cls, guild_id: int):
        """Stops music, clears queue, and cleans up mixer."""
        if guild_id in cls._queues:
            cls._queues[guild_id].clear()
        
        current = cls._current_tracks.pop(guild_id, None)
        if current:
            current.finished = True
        
        # We don't disconnect here as AudioService handles that,
        # but we can cleanup the mixer if we want.
        # Actually, AudioService.disconnect_from_voice is better.

    @classmethod
    def clear_queue(cls, guild_id: int):
        """Clears the queue for a guild."""
        if guild_id in cls._queues:
            cls._queues[guild_id].clear()
        cls._current_tracks.pop(guild_id, None)
