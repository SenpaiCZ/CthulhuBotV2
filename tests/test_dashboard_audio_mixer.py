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
