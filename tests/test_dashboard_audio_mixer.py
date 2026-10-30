from unittest.mock import MagicMock

import pytest

from dashboard.audio_mixer import Track, MixingAudioSource


@pytest.fixture(autouse=True)
def mock_ffmpeg(monkeypatch):
    """Replace discord.FFmpegPCMAudio with a factory returning a fresh MagicMock per call,
    so tests can construct real Track/MixingAudioSource objects without spawning ffmpeg."""
    def _factory(*args, **kwargs):
        source = MagicMock()
        source.read.return_value = b""
        return source
    mock = MagicMock(side_effect=_factory)
    monkeypatch.setattr("dashboard.audio_mixer.discord.FFmpegPCMAudio", mock)
    return mock


def make_track(**overrides):
    kwargs = dict(
        file_path="http://example.com/stream",
        is_url=True,
        metadata={},
        before_options="-reconnect 1",
        options="-vn",
    )
    kwargs.update(overrides)
    return Track(**kwargs)


class TestTrackSeek:
    def test_seek_clamps_negative_to_zero(self):
        track = make_track(metadata={"duration": 200})
        track.seek(-50)
        assert track.elapsed == pytest.approx(0, abs=0.05)

    def test_seek_clamps_overshoot_to_duration_minus_3(self):
        track = make_track(metadata={"duration": 200})
        track.seek(9999)
        assert track.elapsed == pytest.approx(197, abs=0.05)

    def test_seek_unclamped_when_duration_unknown(self):
        track = make_track(metadata={})
        track.seek(500)
        assert track.elapsed == pytest.approx(500, abs=0.05)

    def test_seek_rebuilds_source_and_cleans_up_old_one(self, mock_ffmpeg):
        track = make_track(metadata={"duration": 200})
        old_source = track.source

        track.seek(30)

        assert track.source is not old_source
        old_source.cleanup.assert_called_once()

    def test_seek_injects_ss_into_before_options(self, mock_ffmpeg):
        track = make_track(metadata={"duration": 200}, before_options="-reconnect 1")
        mock_ffmpeg.reset_mock()

        track.seek(30)

        _, kwargs = mock_ffmpeg.call_args
        assert kwargs["before_options"] == "-ss 30.00 -reconnect 1"

    def test_seek_preserves_paused_state(self):
        track = make_track(metadata={"duration": 200})
        track.paused = True

        track.seek(50)

        assert track.paused is True
        assert track.elapsed == pytest.approx(50, abs=0.05)

    def test_seek_resumes_normal_elapsed_tracking_when_not_paused(self):
        track = make_track(metadata={"duration": 200})
        track.seek(50)
        assert track.elapsed == pytest.approx(50, abs=0.1)


class TestMixingAudioSourceSeekTrack:
    def test_seek_track_returns_false_for_unknown_id(self):
        mixer = MixingAudioSource()
        assert mixer.seek_track("nonexistent", 30) is False

    def test_seek_track_delegates_to_track_seek_and_returns_true(self):
        mixer = MixingAudioSource()
        track = mixer.add_track(file_path="http://x", is_url=True, metadata={"duration": 200})

        result = mixer.seek_track(track.id, 50)

        assert result is True
        assert track.elapsed == pytest.approx(50, abs=0.05)


class TestTrackFadeInOut:
    def test_fade_in_ramps_amplitude_up_over_configured_duration(self):
        import struct

        track = make_track(volume=1.0, fade_in_sec=0.1)  # 0.1s = 5 chunks of 20ms
        full_chunk = struct.pack('<1920h', *([10000] * 1920))
        track.source.read.return_value = full_chunk

        first_out = struct.unpack('<1920h', track.read())
        # First chunk should be scaled to ~1/5 of 10000 = 2000
        assert first_out[0] == pytest.approx(2000, abs=5)

        for _ in range(4):
            last_out = struct.unpack('<1920h', track.read())
        assert last_out[0] == pytest.approx(10000, abs=5)

    def test_start_fade_out_detaches_on_finish_and_marks_finished_after_ramp(self):
        import struct

        on_finish = MagicMock()
        track = make_track(volume=1.0, on_finish=on_finish)
        full_chunk = struct.pack('<1920h', *([10000] * 1920))
        track.source.read.return_value = full_chunk

        track.start_fade_out(duration_sec=0.06)  # 3 chunks
        assert track.on_finish is None
        assert track.finished is False

        c1 = struct.unpack('<1920h', track.read())
        assert 0 < c1[0] < 10000
        assert track.finished is False

        c2 = struct.unpack('<1920h', track.read())
        assert 0 <= c2[0] < c1[0]

        c3 = track.read()
        assert c3 == b""
        assert track.finished is True
        on_finish.assert_not_called()


class TestPcmHelpersRPi5Optimization:
    def test_apply_volume_fast_paths_and_scaling(self):
        import struct
        from dashboard.audio_mixer import _apply_volume, CHUNK_SIZE

        raw = struct.pack('<1920h', *([10000] * 1920))
        # volume <= 0 returns all zeros
        assert _apply_volume(raw, 0.0) == b'\x00' * CHUNK_SIZE
        # volume == 1.0 returns original slice without re-packing
        assert _apply_volume(raw, 1.0) == raw
        # 0 < volume < 1 scales without overflow
        half = struct.unpack('<1920h', _apply_volume(raw, 0.5))
        assert half[0] == 5000
        # volume > 1 clips at 32767
        clipped = struct.unpack('<1920h', _apply_volume(raw, 5.0))
        assert clipped[0] == 32767

    def test_mix_pcm_sums_and_clips_at_int16_bounds(self):
        import struct
        from dashboard.audio_mixer import _mix_pcm

        a = struct.pack('<1920h', *([25000] * 960 + [-25000] * 960))
        b = struct.pack('<1920h', *([15000] * 960 + [-15000] * 960))
        mixed = struct.unpack('<1920h', _mix_pcm(a, b))
        assert mixed[0] == 32767
        assert mixed[-1] == -32768
