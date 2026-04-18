import discord
import struct
import uuid
import os
import threading
import time

# Discord audio constants
SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2  # 16-bit signed PCM
CHUNK_SIZE = 3840  # 20ms of stereo audio: 48000 * 0.02 * 2 channels * 2 bytes


def _apply_volume(data: bytes, volume: float) -> bytes:
    """Scale PCM samples by volume factor with clipping."""
    n = len(data) // SAMPLE_WIDTH
    fmt = f'<{n}h'
    samples = struct.unpack(fmt, data[:n * SAMPLE_WIDTH])
    return struct.pack(fmt, *(max(-32768, min(32767, int(s * volume))) for s in samples))


def _mix_pcm(a: bytes, b: bytes) -> bytes:
    """Sum two 16-bit PCM buffers with clipping."""
    n = len(a) // SAMPLE_WIDTH
    fmt = f'<{n}h'
    sa = struct.unpack(fmt, a)
    sb = struct.unpack(fmt, b)
    return struct.pack(fmt, *(max(-32768, min(32767, x + y)) for x, y in zip(sa, sb)))


class Track:
    def __init__(self, file_path, volume=0.5, loop=False, is_url=False,
                 metadata=None, before_options=None, options=None, on_finish=None):
        self.id = str(uuid.uuid4())
        self.file_path = file_path
        self.volume = volume
        self.loop = loop
        self.is_url = is_url
        self.metadata = metadata or {}
        self.before_options = before_options
        self.options = options
        self.finished = False
        self.on_finish = on_finish

        # Time tracking for progress bar
        self.started_at: float | None = None
        self._paused_duration: float = 0.0
        self._paused_since: float | None = None
        self._paused = False  # backing field — use .paused property

        self.source = self._create_source()

    @property
    def paused(self) -> bool:
        return self._paused

    @paused.setter
    def paused(self, value: bool):
        now = time.monotonic()
        if value and not self._paused:
            # Entering pause — record when
            self._paused_since = now
        elif not value and self._paused:
            # Leaving pause — accumulate paused duration
            if self._paused_since is not None:
                self._paused_duration += now - self._paused_since
                self._paused_since = None
        self._paused = value

    @property
    def elapsed(self) -> float:
        """Playback elapsed seconds, excluding paused time."""
        if self.started_at is None:
            return 0.0
        total = time.monotonic() - self.started_at - self._paused_duration
        if self._paused_since is not None:
            total -= time.monotonic() - self._paused_since
        return max(0.0, total)

    def _create_source(self) -> discord.FFmpegPCMAudio:
        if not self.is_url and not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        return discord.FFmpegPCMAudio(
            self.file_path,
            before_options=self.before_options,
            options=self.options
        )

    def read(self) -> bytes:
        if self._paused:
            return b'\x00' * CHUNK_SIZE

        if self.finished:
            return b''

        # Mark start time on first real read
        if self.started_at is None:
            self.started_at = time.monotonic()

        try:
            data = self.source.read()
        except Exception as e:
            print(f"[Track] Read error: {e}")
            self._mark_finished()
            return b''

        if not data:
            if self.loop:
                try:
                    self.source.cleanup()
                    self.source = self._create_source()
                    self.started_at = time.monotonic()
                    self._paused_duration = 0.0
                    self._paused_since = None
                    data = self.source.read()
                    if not data:
                        self._mark_finished()
                        return b''
                except Exception as e:
                    print(f"[Track] Loop restart error: {e}")
                    self._mark_finished()
                    return b''
            else:
                self._mark_finished()
                return b''

        if len(data) < CHUNK_SIZE:
            data += b'\x00' * (CHUNK_SIZE - len(data))

        return _apply_volume(data, self.volume) if self.volume != 1.0 else data

    def _mark_finished(self):
        self.finished = True
        if self.on_finish:
            try:
                self.on_finish()
            except Exception as e:
                print(f"[Track] on_finish error: {e}")

    def cleanup(self):
        try:
            if self.source:
                self.source.cleanup()
        except Exception:
            pass


class MixingAudioSource(discord.AudioSource):
    def __init__(self):
        self.tracks: list[Track] = []
        self.lock = threading.Lock()

    def add_track(self, file_path, volume=0.5, loop=False, is_url=False,
                  metadata=None, before_options=None, options=None, on_finish=None) -> Track:
        track = Track(file_path, volume, loop, is_url, metadata,
                      before_options, options, on_finish)
        with self.lock:
            self.tracks.append(track)
        return track

    def remove_track(self, track_id: str) -> bool:
        with self.lock:
            track = next((t for t in self.tracks if t.id == track_id), None)
            if track:
                track.cleanup()
                self.tracks.remove(track)
                return True
            return False

    def get_track(self, track_id: str) -> 'Track | None':
        with self.lock:
            return next((t for t in self.tracks if t.id == track_id), None)

    def read(self) -> bytes:
        mixed = bytearray(b'\x00' * CHUNK_SIZE)
        to_remove: set[Track] = set()

        with self.lock:
            for track in self.tracks:
                if track.finished:
                    to_remove.add(track)
                    continue
                data = track.read()
                if data and len(data) == CHUNK_SIZE:
                    mixed = bytearray(_mix_pcm(bytes(mixed), data))
                if track.finished:
                    to_remove.add(track)

            for track in to_remove:
                track.cleanup()
                if track in self.tracks:
                    self.tracks.remove(track)

        return bytes(mixed)

    def cleanup(self):
        with self.lock:
            for track in self.tracks:
                track.cleanup()
            self.tracks.clear()
