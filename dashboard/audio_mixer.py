import discord
import audioop
import uuid
import os

# Constants for Discord Audio
SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2 # 16-bit
CHUNK_SIZE = 3840 # 20ms of audio: 48000 * 0.02 * 2 * 2

class Track:
    def __init__(self, file_path, volume=0.5, loop=False):
        self.id = str(uuid.uuid4())
        self.file_path = file_path
        self.volume = volume
        self.loop = loop
        self.paused = False
        self.finished = False
        self.source = self._create_source()

    def _create_source(self):
        # We use FFmpegPCMAudio.
        # Note: We rely on the caller (bot) having ffmpeg installed.
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        return discord.FFmpegPCMAudio(self.file_path)

    def read(self):
        if self.paused:
            return b'\x00' * CHUNK_SIZE

        if self.finished:
            return b''

        data = self.source.read()

        if not data:
            if self.loop:
                # Restart the source
                self.source.cleanup()
                self.source = self._create_source()
                data = self.source.read()
                if not data: # Still empty? File might be empty/broken
                    self.finished = True
                    return b''
            else:
                self.finished = True
                return b''

        # If we got less data than CHUNK_SIZE (end of file), pad with silence
        if len(data) < CHUNK_SIZE:
            data += b'\x00' * (CHUNK_SIZE - len(data))

        # Apply volume
        # audioop.mul throws error if volume is not float? No, it takes factor.
        # But for 'mul', factor is a float?
        # audioop.mul(fragment, width, factor)
        # Check python docs: audioop.mul(fragment, width, factor) -> factor is float.
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

    def add_track(self, file_path, volume=0.5, loop=False):
        track = Track(file_path, volume, loop)
        self.tracks.append(track)
        return track

    def remove_track(self, track_id):
        track_to_remove = next((t for t in self.tracks if t.id == track_id), None)
        if track_to_remove:
            track_to_remove.cleanup()
            self.tracks.remove(track_to_remove)
            return True
        return False

    def get_track(self, track_id):
        return next((t for t in self.tracks if t.id == track_id), None)

    def read(self):
        # Start with silence
        mixed = bytearray(b'\x00' * CHUNK_SIZE)

        # We need to iterate over a copy because tracks might finish and be removed (optional)
        # For now, we just mark them finished.

        # Actually, let's filter out finished non-looping tracks first?
        # Or just read and cleanup later.

        active_tracks = [t for t in self.tracks if not t.finished]

        if not active_tracks:
            # If no tracks playing, we return silence to keep the connection open?
            # Or we return b'' to stop?
            # If we return b'', Discord disconnects or stops playing.
            # But we want the mixer to stay alive so we can add sounds later.
            # So return silence.
            return bytes(mixed)

        for track in active_tracks:
            data = track.read()
            if data:
                # audioop.add returns bytes, we want to sum into our mixed accumulator
                # But audioop.add takes two fragments.
                # mixed = audioop.add(mixed, data, SAMPLE_WIDTH)
                # Note: audioop.add handles wrapping.
                # To minimize clipping, users should manage volume.
                mixed = audioop.add(mixed, data, SAMPLE_WIDTH)

        # Clean up finished tracks
        for track in self.tracks[:]:
            if track.finished:
                track.cleanup()
                self.tracks.remove(track)

        return bytes(mixed)

    def cleanup(self):
        for track in self.tracks:
            track.cleanup()
        self.tracks.clear()
