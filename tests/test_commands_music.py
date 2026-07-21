import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
import yt_dlp
from discord.ext import tasks

from commands.music import Music, _query_has_explicit_video, MusicLookupError, _format_download_error, CookieView


def make_interaction(user=None):
    interaction = MagicMock()
    interaction.guild = MagicMock(id=123)
    interaction.user = user or MagicMock(id=999, display_name="Tester")
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.message = MagicMock()
    interaction.message.edit = AsyncMock()
    return interaction


def make_music_cog():
    bot = MagicMock()
    bot.loop.run_in_executor = AsyncMock()
    cog = Music(bot)
    # Music.__init__ starts two tasks.Loop instances (idle-disconnect, dashboard-refresh) --
    # cancel them immediately so they never run against this MagicMock bot in the background,
    # same as tests/test_commands_cog_load.py already does for every cog.
    for attr_name in dir(cog):
        attr = getattr(cog, attr_name, None)
        if isinstance(attr, tasks.Loop):
            attr.cancel()
    return cog


@pytest.fixture(autouse=True)
def _no_delete_after(monkeypatch):
    # play()/helpers schedule asyncio.create_task(_delete_after(msg, N)) after sending a
    # confirmation message. Patch it to a no-op so tests don't leave a real N-second sleep
    # task pending when the test (and its event loop) ends.
    monkeypatch.setattr("commands.music._delete_after", AsyncMock())


class TestQueryHasExplicitVideo:
    def test_watch_url_with_list_has_explicit_video(self):
        url = "https://www.youtube.com/watch?v=abc123&list=PLxyz"
        assert _query_has_explicit_video(url) is True

    def test_bare_playlist_url_has_no_explicit_video(self):
        url = "https://www.youtube.com/playlist?list=PLxyz"
        assert _query_has_explicit_video(url) is False

    def test_youtu_be_short_link_has_explicit_video(self):
        url = "https://youtu.be/abc123?list=PLxyz"
        assert _query_has_explicit_video(url) is True

    def test_search_query_has_no_explicit_video(self):
        assert _query_has_explicit_video("some random search terms") is False


class TestFormatDownloadError:
    def test_age_restricted_returns_cookie_embed_and_view_ephemeral(self):
        e = yt_dlp.utils.DownloadError("Sign in to confirm your age")
        content, embed, view, ephemeral = _format_download_error(e)
        assert content is None
        assert embed.title == "🔞 Age-Restricted Content"
        assert isinstance(view, CookieView)
        assert ephemeral is True

    def test_private_video_returns_plain_message(self):
        e = yt_dlp.utils.DownloadError("Private video")
        content, embed, view, ephemeral = _format_download_error(e)
        assert content == "❌ That video is private."
        assert embed is None and view is None and ephemeral is False

    def test_unavailable_video_returns_plain_message(self):
        e = yt_dlp.utils.DownloadError("Video unavailable")
        content, embed, view, ephemeral = _format_download_error(e)
        assert content == "❌ Video is unavailable."
        assert embed is None and view is None and ephemeral is False

    def test_generic_download_error_truncated_to_200_chars(self):
        e = yt_dlp.utils.DownloadError("x" * 300)
        content, embed, view, ephemeral = _format_download_error(e)
        assert content == f"❌ Download error: {'x' * 200}"
        assert embed is None and view is None and ephemeral is False


class TestPlayDownloadErrorHandling:
    @pytest.mark.asyncio
    async def test_play_sends_cookie_prompt_on_age_restricted_download_error(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog.bot.loop.run_in_executor = AsyncMock(
            side_effect=yt_dlp.utils.DownloadError("Sign in to confirm your age")
        )
        interaction = make_interaction()

        await Music.play.callback(cog, interaction, "https://youtu.be/abc123")

        interaction.followup.send.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert kwargs["embed"].title == "🔞 Age-Restricted Content"
        assert isinstance(kwargs["view"], CookieView)
        assert kwargs["ephemeral"] is True
