import discord
import audioop
import uuid
import os
import threading

# Constants for Discord Audio
SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2 # 16-bit
# Bytes per second = 48000 * 2 * 2 = 192000
BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH
CHUNK_SIZE = 3840 # 20ms of audio: 48000 * 0.02 * 2 * 2

class Track:
    def __init__(self, file_path, volume=0.5, loop=False, is_url=False, metadata=None, before_options=None, options=None, on_finish=None, duration=None):
        self.id = str(uuid.uuid4())
        self.file_path = file_path
        self.volume = volume
        self.loop = loop
        self.is_url = is_url
        self.metadata = metadata or {}
        self.before_options = before_options
        self.options = options
        self.paused = False
        self.finished = False
        self.on_finish = on_finish
        self.duration = duration
        self.bytes_read = 0
        self.source = self._create_source()

    def _create_source(self):
        # We use FFmpegPCMAudio.
        # Note: We rely on the caller (bot) having ffmpeg installed.
        if not self.is_url and not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")

        return discord.FFmpegPCMAudio(
            self.file_path,
            before_options=self.before_options,
            options=self.options
        )

    @property
    def position(self):
        # Calculate position in seconds
        return self.bytes_read / BYTES_PER_SECOND

    def read(self):
        if self.paused:
            return b'\x00' * CHUNK_SIZE

        if self.finished:
            return b''

        try:
            data = self.source.read()
        except Exception as e:
            # Source might be cleaned up or closed
            print(f"Error reading from source: {e}")
            self.finished = True
            if self.on_finish:
                try: self.on_finish()
                except: pass
            return b''

        if not data:
            if self.loop:
                # Restart the source
                try:
                    self.source.cleanup()
                    self.source = self._create_source()
                    self.bytes_read = 0 # Reset for accurate loop position tracking relative to file start?
                    # Or keep incrementing for total played time?
                    # Usually for a progress bar, we want position in the file.
                    data = self.source.read()
                    if not data: # Still empty? File might be empty/broken
                        self.finished = True
                        if self.on_finish:
                            try: self.on_finish()
                            except: pass
                        return b''
                except Exception as e:
                    print(f"Error restarting loop: {e}")
                    self.finished = True
                    if self.on_finish:
                        try: self.on_finish()
                        except: pass
                    return b''
            else:
                self.finished = True
                if self.on_finish:
                    try: self.on_finish()
                    except: pass
                return b''

        self.bytes_read += len(data)

        # If we got less data than CHUNK_SIZE (end of file), pad with silence
        if len(data) < CHUNK_SIZE:
            data += b'\x00' * (CHUNK_SIZE - len(data))

        # Apply volume
        if self.volume != 1.0:
            try:
                data = audioop.mul(data, SAMPLE_WIDTH, self.volume)
            except Exception as e:
                print(f"Error applying volume: {e}")

        return data

    def cleanup(self):
        if self.source:
            self.source.cleanup()

class MixingAudioSource(discord.AudioSource):
    def __init__(self):
        self.tracks = []
        self._finished = False
        self.lock = threading.Lock()

    def add_track(self, file_path, volume=0.5, loop=False, is_url=False, metadata=None, before_options=None, options=None, on_finish=None, duration=None):
        track = Track(file_path, volume, loop, is_url, metadata, before_options, options, on_finish, duration)
        with self.lock:
            self.tracks.append(track)
        return track

    def remove_track(self, track_id):
        with self.lock:
            track_to_remove = next((t for t in self.tracks if t.id == track_id), None)
            if track_to_remove:
                track_to_remove.cleanup()
                # Double check existence just in case, though lock should guarantee it
                if track_to_remove in self.tracks:
                    self.tracks.remove(track_to_remove)
                return True
            return False

    def get_track(self, track_id):
        with self.lock:
            return next((t for t in self.tracks if t.id == track_id), None)

    def read(self):
        # Start with silence
        mixed = bytearray(b'\x00' * CHUNK_SIZE)

        with self.lock:
            active_tracks = [t for t in self.tracks if not t.finished]

            if not active_tracks:
                return bytes(mixed)

            for track in active_tracks:
                data = track.read()
                if data:
                    mixed = audioop.add(mixed, data, SAMPLE_WIDTH)

            # Clean up finished tracks
            for track in self.tracks[:]:
                if track.finished:
                    track.cleanup()
                    if track in self.tracks:
                        self.tracks.remove(track)

        return bytes(mixed)

    def cleanup(self):
        with self.lock:
            for track in self.tracks:
                track.cleanup()
            self.tracks.clear()
