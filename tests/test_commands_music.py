import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
import yt_dlp
from discord.ext import tasks

from commands.music import Music, _query_has_explicit_video, MusicLookupError, _format_download_error, CookieView, PlaylistChoiceView, _parse_seek_position
from dashboard.audio_mixer import MixingAudioSource


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


class TestFinalizePlay:
    @pytest.mark.asyncio
    async def test_sends_new_dashboard_and_starts_playback_when_idle(self):
        cog = make_music_cog()
        guild_id = "123"
        cog.queue[guild_id] = [{"title": "Next Song"}]
        cog._play_song = AsyncMock()
        interaction = make_interaction()
        sent_msg = MagicMock()
        interaction.followup.send = AsyncMock(return_value=sent_msg)

        await cog._finalize_play(interaction, guild_id)

        interaction.followup.send.assert_awaited_once()
        assert cog.dashboard_messages[guild_id] is sent_msg
        cog._play_song.assert_awaited_once_with(guild_id, {"title": "Next Song"})
        assert cog.queue[guild_id] == []

    @pytest.mark.asyncio
    async def test_edits_existing_dashboard_and_does_not_start_playback_when_already_playing(self):
        cog = make_music_cog()
        guild_id = "123"
        old_msg = MagicMock()
        old_msg.edit = AsyncMock()
        cog.dashboard_messages[guild_id] = old_msg
        track_mock = MagicMock()
        track_mock.finished = False
        track_mock.paused = False
        track_mock.volume = 0.5
        track_mock.metadata = {"title": "Current Song", "original_url": "https://youtu.be/xyz"}
        cog.current_track[guild_id] = track_mock
        cog.queue[guild_id] = [{"title": "Waiting Song"}]
        cog._play_song = AsyncMock()
        interaction = make_interaction()

        await cog._finalize_play(interaction, guild_id)

        old_msg.edit.assert_awaited_once()
        interaction.followup.send.assert_not_called()
        cog._play_song.assert_not_called()
        assert cog.queue[guild_id] == [{"title": "Waiting Song"}]  # untouched

    @pytest.mark.asyncio
    async def test_falls_back_to_new_message_when_old_dashboard_message_not_found(self):
        cog = make_music_cog()
        guild_id = "123"
        old_msg = MagicMock()
        old_msg.edit = AsyncMock(
            side_effect=discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "Unknown Message")
        )
        cog.dashboard_messages[guild_id] = old_msg
        cog.queue[guild_id] = []
        interaction = make_interaction()
        sent_msg = MagicMock()
        interaction.followup.send = AsyncMock(return_value=sent_msg)

        await cog._finalize_play(interaction, guild_id)

        assert cog.dashboard_messages[guild_id] is sent_msg


class TestQueuePlaylistEntries:
    @pytest.mark.asyncio
    async def test_appends_all_non_blacklisted_entries_and_returns_embed(self):
        cog = make_music_cog()
        cog.queue["g1"] = []
        cog.blacklist = ["blocked-url"]
        entries = [
            {"title": "Song A", "url": "url-a", "thumbnail": "thumb-a", "duration": 100},
            {"title": "Song B", "url": "blocked-url", "thumbnail": "", "duration": 50},
            {"title": "Song C", "url": "url-c", "thumbnail": "", "duration": 200},
        ]
        requester = MagicMock(display_name="Alice")

        embed, already_playing = await cog._queue_playlist_entries("g1", entries, "My Playlist", requester)

        assert already_playing is False
        assert len(cog.queue["g1"]) == 2
        assert cog.queue["g1"][0] == {
            "title": "Song A", "url": None, "webpage_url": "url-a", "original_url": "url-a",
            "thumbnail": "thumb-a", "duration": 100, "requested_by": "Alice", "needs_resolve": True,
        }
        assert cog.queue["g1"][1]["title"] == "Song C"
        assert "My Playlist" in embed.description
        assert "2 tracks queued" in embed.description
        assert embed.title == "📥 Playlist Added"

    @pytest.mark.asyncio
    async def test_play_command_single_entry_playlist_queues_directly_no_prompt(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog._finalize_play = AsyncMock()
        flat_info = {
            "title": "My Playlist",
            "entries": [{"title": "Song A", "url": "url-a", "thumbnail": "", "duration": 100}],
        }
        cog.bot.loop.run_in_executor = AsyncMock(return_value=flat_info)
        interaction = make_interaction()

        await Music.play.callback(cog, interaction, "https://www.youtube.com/playlist?list=PL1")

        assert len(cog.queue["123"]) == 1
        assert cog.queue["123"][0]["title"] == "Song A"
        cog._finalize_play.assert_awaited_once()
        # followup.send called once for the "Playlist Added" embed, no view kwarg (no prompt)
        interaction.followup.send.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert "view" not in kwargs


class TestQueueSingleTrack:
    @pytest.mark.asyncio
    async def test_queues_track_and_returns_none_embed_when_nothing_playing(self):
        cog = make_music_cog()
        cog.queue["g1"] = []
        cog.bot.loop.run_in_executor = AsyncMock(return_value={
            "title": "Song A", "webpage_url": "url-a", "url": "stream-a",
            "thumbnail": "thumb-a", "duration": 120,
        })
        requester = MagicMock(display_name="Alice")

        embed, already_playing = await cog._queue_single_track("g1", "url-a", requester)

        assert embed is None
        assert already_playing is False
        assert len(cog.queue["g1"]) == 1
        assert cog.queue["g1"][0]["title"] == "Song A"
        assert cog.queue["g1"][0]["requested_by"] == "Alice"
        assert cog.queue["g1"][0]["needs_resolve"] is False

    @pytest.mark.asyncio
    async def test_returns_added_to_queue_embed_when_something_already_playing(self):
        cog = make_music_cog()
        cog.queue["g1"] = []
        cog.current_track["g1"] = MagicMock(finished=False)
        cog.bot.loop.run_in_executor = AsyncMock(return_value={
            "title": "Song A", "webpage_url": "url-a", "url": "stream-a",
            "thumbnail": "", "duration": 120,
        })
        requester = MagicMock(display_name="Alice")

        embed, already_playing = await cog._queue_single_track("g1", "url-a", requester)

        assert already_playing is True
        assert embed.title == "📥 Added to Queue"
        assert len(cog.queue["g1"]) == 1

    @pytest.mark.asyncio
    async def test_raises_lookup_error_when_no_results(self):
        cog = make_music_cog()
        cog.queue["g1"] = []
        cog.bot.loop.run_in_executor = AsyncMock(return_value=None)

        with pytest.raises(MusicLookupError, match="No results found"):
            await cog._queue_single_track("g1", "nonsense query", MagicMock(display_name="Alice"))

    @pytest.mark.asyncio
    async def test_raises_lookup_error_when_blacklisted(self):
        cog = make_music_cog()
        cog.queue["g1"] = []
        cog.blacklist = ["url-a"]
        cog.bot.loop.run_in_executor = AsyncMock(return_value={
            "title": "Song A", "webpage_url": "url-a", "url": "stream-a",
        })

        with pytest.raises(MusicLookupError, match="is blacklisted"):
            await cog._queue_single_track("g1", "url-a", MagicMock(display_name="Alice"))

    @pytest.mark.asyncio
    async def test_raises_lookup_error_when_no_playable_entry(self):
        cog = make_music_cog()
        cog.queue["g1"] = []
        cog.bot.loop.run_in_executor = AsyncMock(return_value={"entries": [None, None]})

        with pytest.raises(MusicLookupError, match="No playable result found"):
            await cog._queue_single_track("g1", "some query", MagicMock(display_name="Alice"))


class TestPlaySingleTrackBranch:
    @pytest.mark.asyncio
    async def test_play_queues_and_finalizes_when_nothing_playing(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog._finalize_play = AsyncMock()
        cog.bot.loop.run_in_executor = AsyncMock(return_value={
            "title": "Song A", "webpage_url": "url-a", "url": "stream-a", "duration": 100,
        })
        interaction = make_interaction()

        await Music.play.callback(cog, interaction, "url-a")

        assert len(cog.queue["123"]) == 1
        cog._finalize_play.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_play_sends_added_to_queue_and_updates_dashboard_when_already_playing(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog._finalize_play = AsyncMock()
        cog._update_dashboard_for_guild = AsyncMock()
        cog.current_track["123"] = MagicMock(finished=False)
        cog.bot.loop.run_in_executor = AsyncMock(return_value={
            "title": "Song A", "webpage_url": "url-a", "url": "stream-a", "duration": 100,
        })
        interaction = make_interaction()

        await Music.play.callback(cog, interaction, "url-a")

        interaction.followup.send.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert kwargs["embed"].title == "📥 Added to Queue"
        cog._update_dashboard_for_guild.assert_awaited_once_with("123")
        cog._finalize_play.assert_not_called()

    @pytest.mark.asyncio
    async def test_play_sends_lookup_error_message_on_no_results(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog.bot.loop.run_in_executor = AsyncMock(return_value=None)
        interaction = make_interaction()

        await Music.play.callback(cog, interaction, "nonsense query")

        interaction.followup.send.assert_awaited_once_with("❌ No results found.")


class TestPlaylistChoiceViewConstruction:
    def test_explicit_video_link_labels_just_one_as_this_song(self):
        entries = [{"title": "A", "url": "a"}, {"title": "B", "url": "b"}]
        view = PlaylistChoiceView(
            cog=MagicMock(), guild_id="123", requester_id=999,
            single_query="https://www.youtube.com/watch?v=abc&list=PL1",
            has_explicit_video=True, entries=entries, playlist_title="My Playlist",
        )
        assert view.just_one.label == "🎵 Just this song"
        assert view.whole_playlist.label == "📥 Whole playlist (2)"

    def test_bare_playlist_link_labels_just_one_as_first_song(self):
        entries = [{"title": "A", "url": "a"}, {"title": "B", "url": "b"}, {"title": "C", "url": "c"}]
        view = PlaylistChoiceView(
            cog=MagicMock(), guild_id="123", requester_id=999,
            single_query="a", has_explicit_video=False,
            entries=entries, playlist_title="My Playlist",
        )
        assert view.just_one.label == "🎵 Just the first song"
        assert view.whole_playlist.label == "📥 Whole playlist (3)"

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_non_requester(self):
        view = PlaylistChoiceView(
            cog=MagicMock(), guild_id="123", requester_id=999,
            single_query="a", has_explicit_video=False,
            entries=[{"title": "A", "url": "a"}, {"title": "B", "url": "b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=111))

        result = await view.interaction_check(interaction)

        assert result is False
        interaction.response.send_message.assert_awaited_once_with(
            "This choice isn't for you.", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_interaction_check_accepts_requester(self):
        view = PlaylistChoiceView(
            cog=MagicMock(), guild_id="123", requester_id=999,
            single_query="a", has_explicit_video=False,
            entries=[{"title": "A", "url": "a"}, {"title": "B", "url": "b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        result = await view.interaction_check(interaction)

        assert result is True
        interaction.response.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_timeout_disables_buttons_and_edits_message(self):
        view = PlaylistChoiceView(
            cog=MagicMock(), guild_id="123", requester_id=999,
            single_query="a", has_explicit_video=False,
            entries=[{"title": "A", "url": "a"}, {"title": "B", "url": "b"}],
            playlist_title="P",
        )
        view.message = MagicMock()
        view.message.edit = AsyncMock()

        await view.on_timeout()

        assert all(c.disabled for c in view.children)
        view.message.edit.assert_awaited_once()


class TestPlayAmbiguousPlaylistBranch:
    @pytest.mark.asyncio
    async def test_play_sends_choice_view_when_entries_exceed_one(self):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        flat_info = {
            "title": "My Playlist",
            "entries": [
                {"title": "Song A", "url": "url-a"},
                {"title": "Song B", "url": "url-b"},
            ],
        }
        cog.bot.loop.run_in_executor = AsyncMock(return_value=flat_info)
        interaction = make_interaction()

        await Music.play.callback(
            cog, interaction, "https://www.youtube.com/watch?v=url-a&list=PL1"
        )

        assert cog.queue["123"] == []  # nothing queued yet -- waiting on the button click
        interaction.followup.send.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert isinstance(kwargs["view"], PlaylistChoiceView)
        assert kwargs["view"].just_one.label == "🎵 Just this song"


class TestJustOneButton:
    @pytest.mark.asyncio
    async def test_explicit_video_case_queues_via_original_query_and_finalizes(self):
        cog = make_music_cog()
        cog._queue_single_track = AsyncMock(return_value=(None, False))
        cog._finalize_play = AsyncMock()
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="https://www.youtube.com/watch?v=abc&list=PL1",
            has_explicit_video=True,
            entries=[{"title": "A", "url": "a"}, {"title": "B", "url": "b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.just_one.callback(interaction)

        cog._queue_single_track.assert_awaited_once_with(
            "123", "https://www.youtube.com/watch?v=abc&list=PL1", interaction.user
        )
        interaction.message.edit.assert_awaited_once()
        _, kwargs = interaction.message.edit.call_args
        assert kwargs["view"] is None
        cog._finalize_play.assert_awaited_once_with(interaction, "123")

    @pytest.mark.asyncio
    async def test_bare_playlist_case_queues_via_first_entry_url(self):
        cog = make_music_cog()
        cog._queue_single_track = AsyncMock(return_value=(None, False))
        cog._finalize_play = AsyncMock()
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="url-a", has_explicit_video=False,
            entries=[{"title": "A", "url": "url-a"}, {"title": "B", "url": "url-b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.just_one.callback(interaction)

        cog._queue_single_track.assert_awaited_once_with("123", "url-a", interaction.user)

    @pytest.mark.asyncio
    async def test_already_playing_edits_added_to_queue_embed_and_updates_dashboard_only(self):
        cog = make_music_cog()
        added_embed = discord.Embed(title="📥 Added to Queue")
        cog._queue_single_track = AsyncMock(return_value=(added_embed, True))
        cog._finalize_play = AsyncMock()
        cog._update_dashboard_for_guild = AsyncMock()
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="url-a", has_explicit_video=False,
            entries=[{"title": "A", "url": "url-a"}, {"title": "B", "url": "url-b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.just_one.callback(interaction)

        interaction.message.edit.assert_awaited_once_with(embed=added_embed, view=None)
        cog._update_dashboard_for_guild.assert_awaited_once_with("123")
        cog._finalize_play.assert_not_called()

    @pytest.mark.asyncio
    async def test_lookup_error_edits_message_with_error_and_does_not_finalize(self):
        cog = make_music_cog()
        cog._queue_single_track = AsyncMock(side_effect=MusicLookupError("❌ No results found."))
        cog._finalize_play = AsyncMock()
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="url-a", has_explicit_video=False,
            entries=[{"title": "A", "url": "url-a"}, {"title": "B", "url": "url-b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.just_one.callback(interaction)

        interaction.message.edit.assert_awaited_once_with(
            content="❌ No results found.", embed=None, view=None
        )
        cog._finalize_play.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_error_edits_message_via_format_download_error(self):
        cog = make_music_cog()
        cog._queue_single_track = AsyncMock(
            side_effect=yt_dlp.utils.DownloadError("Private video")
        )
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="url-a", has_explicit_video=False,
            entries=[{"title": "A", "url": "url-a"}, {"title": "B", "url": "url-b"}],
            playlist_title="P",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.just_one.callback(interaction)

        interaction.message.edit.assert_awaited_once_with(
            content="❌ That video is private.", embed=None, view=None
        )


class TestWholePlaylistButton:
    @pytest.mark.asyncio
    async def test_queues_all_entries_and_finalizes(self):
        cog = make_music_cog()
        playlist_embed = discord.Embed(title="📥 Playlist Added")
        cog._queue_playlist_entries = AsyncMock(return_value=(playlist_embed, False))
        cog._finalize_play = AsyncMock()
        entries = [{"title": "A", "url": "url-a"}, {"title": "B", "url": "url-b"}]
        view = PlaylistChoiceView(
            cog=cog, guild_id="123", requester_id=999,
            single_query="url-a", has_explicit_video=False,
            entries=entries, playlist_title="My Playlist",
        )
        interaction = make_interaction(user=MagicMock(id=999))

        await view.whole_playlist.callback(interaction)

        cog._queue_playlist_entries.assert_awaited_once_with(
            "123", entries, "My Playlist", interaction.user
        )
        interaction.message.edit.assert_awaited_once_with(embed=playlist_embed, view=None)
        cog._finalize_play.assert_awaited_once_with(interaction, "123")


class TestQueueGuardsAgainstMissingGuildId:
    @pytest.mark.asyncio
    async def test_queue_single_track_creates_queue_if_missing(self):
        cog = make_music_cog()
        requester = MagicMock(display_name="Tester")
        # Don't initialize guild_id in queue — simulate guild disconnecting after /play prompt
        assert "guild-123" not in cog.queue

        # Mock yt_dlp extraction to return a valid single track
        def _extract():
            return {"title": "Test Track", "url": "http://example.com", "webpage_url": "http://example.com"}
        cog.bot.loop.run_in_executor = AsyncMock(side_effect=lambda *args, **kw: _extract())

        embed, already_playing = await cog._queue_single_track("guild-123", "test query", requester)

        # Should create the queue entry without raising KeyError
        assert "guild-123" in cog.queue
        assert len(cog.queue["guild-123"]) == 1
        assert already_playing is False

    @pytest.mark.asyncio
    async def test_queue_playlist_entries_creates_queue_if_missing(self):
        cog = make_music_cog()
        requester = MagicMock(display_name="Tester")
        # Don't initialize guild_id in queue — simulate guild disconnecting after /play prompt
        assert "guild-456" not in cog.queue

        entries = [
            {"title": "Track 1", "url": "http://example.com/1"},
            {"title": "Track 2", "url": "http://example.com/2"},
        ]

        embed, already_playing = await cog._queue_playlist_entries("guild-456", entries, "Test Playlist", requester)

        # Should create the queue entry and add all non-blacklisted tracks without raising KeyError
        assert "guild-456" in cog.queue
        assert len(cog.queue["guild-456"]) == 2
        assert already_playing is False


class TestParseSeekPosition:
    def test_plain_seconds_is_absolute(self):
        assert _parse_seek_position("90") == (90.0, False)

    def test_mm_ss_is_absolute(self):
        assert _parse_seek_position("1:30") == (90.0, False)

    def test_h_mm_ss_is_absolute(self):
        assert _parse_seek_position("1:02:03") == (3723.0, False)

    def test_relative_forward_plain_seconds(self):
        assert _parse_seek_position("+30") == (30.0, True)

    def test_relative_backward_plain_seconds(self):
        assert _parse_seek_position("-15") == (-15.0, True)

    def test_relative_forward_mm_ss(self):
        assert _parse_seek_position("+1:30") == (90.0, True)

    def test_relative_backward_mm_ss(self):
        assert _parse_seek_position("-1:30") == (-90.0, True)

    def test_invalid_text_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_seek_position("not-a-time")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_seek_position("")

    def test_too_many_colon_segments_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_seek_position("1:2:3:4")

    def test_bare_sign_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_seek_position("+")


class TestMusicSeek:
    @pytest.mark.asyncio
    async def test_seek_raises_lookup_error_when_nothing_playing(self):
        cog = make_music_cog()
        with pytest.raises(MusicLookupError, match="Nothing is playing"):
            await cog._seek("g1", 30.0)

    @pytest.mark.asyncio
    async def test_seek_raises_lookup_error_when_track_finished(self):
        cog = make_music_cog()
        cog.current_track["g1"] = MagicMock(finished=True)
        with pytest.raises(MusicLookupError, match="Nothing is playing"):
            await cog._seek("g1", 30.0)

    @pytest.mark.asyncio
    async def test_seek_raises_lookup_error_when_no_mixer(self, monkeypatch):
        monkeypatch.setattr("commands.music.guild_mixers", {})
        cog = make_music_cog()
        track = MagicMock(finished=False, id="t1")
        cog.current_track["g1"] = track
        with pytest.raises(MusicLookupError, match="Could not seek"):
            await cog._seek("g1", 30.0)

    @pytest.mark.asyncio
    async def test_seek_raises_lookup_error_when_mixer_reports_track_gone(self, monkeypatch):
        mixer = MagicMock()
        mixer.seek_track.return_value = False
        monkeypatch.setattr("commands.music.guild_mixers", {"g1": mixer})
        cog = make_music_cog()
        track = MagicMock(finished=False, id="t1")
        cog.current_track["g1"] = track
        with pytest.raises(MusicLookupError, match="Could not seek"):
            await cog._seek("g1", 30.0)

    @pytest.mark.asyncio
    async def test_seek_success_calls_mixer_and_updates_dashboard(self, monkeypatch):
        mixer = MagicMock()
        mixer.seek_track.return_value = True
        monkeypatch.setattr("commands.music.guild_mixers", {"g1": mixer})
        cog = make_music_cog()
        cog._update_dashboard_for_guild = AsyncMock()
        track = MagicMock(finished=False, id="t1", elapsed=30.0, metadata={"duration": 200})
        cog.current_track["g1"] = track

        embed = await cog._seek("g1", 30.0)

        mixer.seek_track.assert_called_once_with("t1", 30.0)
        cog._update_dashboard_for_guild.assert_awaited_once_with("g1")
        # _fmt_duration zero-pads minutes (e.g. 30s -> "00:30", 200s -> "03:20") -- assert
        # the exact strings, not a substring, so this doesn't silently pass on a format change.
        assert "00:30" in embed.description
        assert "03:20" in embed.description

    @pytest.mark.asyncio
    async def test_seek_success_omits_total_duration_when_unknown(self, monkeypatch):
        mixer = MagicMock()
        mixer.seek_track.return_value = True
        monkeypatch.setattr("commands.music.guild_mixers", {"g1": mixer})
        cog = make_music_cog()
        cog._update_dashboard_for_guild = AsyncMock()
        track = MagicMock(finished=False, id="t1", elapsed=30.0, metadata={})
        cog.current_track["g1"] = track

        embed = await cog._seek("g1", 30.0)

        assert "00:30" in embed.description
        assert "/" not in embed.description


class TestSeekCommand:
    @pytest.mark.asyncio
    async def test_relative_seek_adds_to_elapsed(self, monkeypatch):
        cog = make_music_cog()
        cog._seek = AsyncMock(return_value=discord.Embed(description="ok"))
        track = MagicMock(finished=False, elapsed=40.0, metadata={"duration": 200})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "+30")

        cog._seek.assert_awaited_once_with("123", 70.0)
        interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_absolute_seek_uses_position_directly(self, monkeypatch):
        cog = make_music_cog()
        cog._seek = AsyncMock(return_value=discord.Embed(description="ok"))
        track = MagicMock(finished=False, elapsed=40.0, metadata={"duration": 200})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "1:30")

        cog._seek.assert_awaited_once_with("123", 90.0)

    @pytest.mark.asyncio
    async def test_absolute_seek_rejected_when_duration_unknown(self):
        cog = make_music_cog()
        cog._seek = AsyncMock()
        track = MagicMock(finished=False, elapsed=40.0, metadata={})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "1:30")

        cog._seek.assert_not_called()
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.call_args
        assert "duration is unknown" in args[0]

    @pytest.mark.asyncio
    async def test_relative_seek_allowed_when_duration_unknown(self):
        cog = make_music_cog()
        cog._seek = AsyncMock(return_value=discord.Embed(description="ok"))
        track = MagicMock(finished=False, elapsed=40.0, metadata={})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "+10")

        cog._seek.assert_awaited_once_with("123", 50.0)

    @pytest.mark.asyncio
    async def test_nothing_playing_rejected(self):
        cog = make_music_cog()
        cog._seek = AsyncMock()
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "+10")

        cog._seek.assert_not_called()
        interaction.response.send_message.assert_awaited_once_with("❌ Nothing is playing.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_unparseable_position_rejected(self):
        cog = make_music_cog()
        cog._seek = AsyncMock()
        track = MagicMock(finished=False, elapsed=40.0, metadata={"duration": 200})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "garbage")

        cog._seek.assert_not_called()
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lookup_error_from_seek_sent_as_followup(self):
        cog = make_music_cog()
        cog._seek = AsyncMock(side_effect=MusicLookupError("❌ Could not seek — track is no longer active."))
        track = MagicMock(finished=False, elapsed=40.0, metadata={"duration": 200})
        cog.current_track["123"] = track
        interaction = make_interaction()

        await Music.seek.callback(cog, interaction, "+10")

        interaction.followup.send.assert_awaited_once_with("❌ Could not seek — track is no longer active.")


def make_reaction_payload(user_id=999, guild_id=123, message_id=555, emoji="❤️"):
    return SimpleNamespace(user_id=user_id, guild_id=guild_id, message_id=message_id, emoji=emoji)


class TestAddRemoveFavorite:
    @pytest.mark.asyncio
    async def test_add_favorite_saves_new_entry(self, monkeypatch):
        cog = make_music_cog()
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._add_favorite("g1", "u1", {
            "original_url": "url-a", "title": "Song A", "thumbnail": "thumb-a", "duration": 100,
        })

        save_mock.assert_awaited_once()
        saved = save_mock.call_args[0][0]
        assert saved["g1"]["u1"] == [{"url": "url-a", "title": "Song A", "thumbnail": "thumb-a", "duration": 100}]

    @pytest.mark.asyncio
    async def test_add_favorite_is_noop_when_url_missing(self, monkeypatch):
        cog = make_music_cog()
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._add_favorite("g1", "u1", {"title": "No URL"})

        save_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_favorite_dedupes_by_url(self, monkeypatch):
        cog = make_music_cog()
        existing = {"g1": {"u1": [{"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100}]}}
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=existing))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._add_favorite("g1", "u1", {"original_url": "url-a", "title": "Song A (dup)"})

        save_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_favorite_removes_matching_url(self, monkeypatch):
        cog = make_music_cog()
        existing = {"g1": {"u1": [
            {"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100},
            {"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50},
        ]}}
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=existing))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._remove_favorite("g1", "u1", "url-a")

        save_mock.assert_awaited_once()
        saved = save_mock.call_args[0][0]
        assert saved["g1"]["u1"] == [{"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50}]

    @pytest.mark.asyncio
    async def test_remove_favorite_is_noop_when_url_absent(self, monkeypatch):
        cog = make_music_cog()
        existing = {"g1": {"u1": [{"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100}]}}
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=existing))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._remove_favorite("g1", "u1", "url-does-not-exist")

        save_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_favorite_is_noop_for_unknown_guild_or_user(self, monkeypatch):
        cog = make_music_cog()
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)

        await cog._remove_favorite("g1", "u1", "url-a")

        save_mock.assert_not_called()


class TestReactionListeners:
    @pytest.mark.asyncio
    async def test_add_ignores_bot_own_reaction(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=999)
        cog._add_favorite = AsyncMock()
        payload = make_reaction_payload(user_id=999)

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_ignores_non_heart_emoji(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._add_favorite = AsyncMock()
        payload = make_reaction_payload(user_id=999, emoji="👍")

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_ignores_reaction_on_non_dashboard_message(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._add_favorite = AsyncMock()
        cog.dashboard_messages["123"] = MagicMock(id=555)
        payload = make_reaction_payload(guild_id=123, message_id=999)  # different message id

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_ignores_when_nothing_playing(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._add_favorite = AsyncMock()
        cog.dashboard_messages["123"] = MagicMock(id=555)
        payload = make_reaction_payload(guild_id=123, message_id=555)

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_ignores_finished_track(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._add_favorite = AsyncMock()
        cog.dashboard_messages["123"] = MagicMock(id=555)
        cog.current_track["123"] = MagicMock(finished=True)
        payload = make_reaction_payload(guild_id=123, message_id=555)

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_calls_add_favorite_with_current_track_metadata(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._add_favorite = AsyncMock()
        cog.dashboard_messages["123"] = MagicMock(id=555)
        track = MagicMock(finished=False, metadata={"original_url": "url-a", "title": "Song A"})
        cog.current_track["123"] = track
        payload = make_reaction_payload(user_id=999, guild_id=123, message_id=555)

        await cog.on_raw_reaction_add(payload)

        cog._add_favorite.assert_awaited_once_with("123", "999", track.metadata)

    @pytest.mark.asyncio
    async def test_remove_calls_remove_favorite_with_current_track_original_url(self):
        cog = make_music_cog()
        cog.bot.user = MagicMock(id=1)
        cog._remove_favorite = AsyncMock()
        cog.dashboard_messages["123"] = MagicMock(id=555)
        track = MagicMock(finished=False, metadata={"original_url": "url-a", "title": "Song A"})
        cog.current_track["123"] = track
        payload = make_reaction_payload(user_id=999, guild_id=123, message_id=555)

        await cog.on_raw_reaction_remove(payload)

        cog._remove_favorite.assert_awaited_once_with("123", "999", "url-a")


def make_playable_guild(cog, guild_id, mixer):
    """Wire up cog.bot.get_guild(...) and guild_mixers so _play_song's existing setup path
    (mixer lookup, voice-client-already-playing-this-mixer check) is satisfied without
    constructing any real discord.py audio objects or spawning FFmpeg."""
    fake_source = MagicMock(spec=discord.PCMVolumeTransformer)
    fake_source.original = mixer
    fake_vc = MagicMock()
    fake_vc.is_connected.return_value = True
    fake_vc.is_playing.return_value = True
    fake_vc.source = fake_source

    fake_guild = MagicMock()
    fake_guild.voice_client = fake_vc
    cog.bot.get_guild = MagicMock(return_value=fake_guild)


class TestPlaySongClearsReactions:
    @pytest.mark.asyncio
    async def test_clears_reactions_on_dashboard_message_when_new_track_starts(self, monkeypatch):
        cog = make_music_cog()
        dashboard_msg = MagicMock()
        dashboard_msg.clear_reactions = AsyncMock()
        dashboard_msg.add_reaction = AsyncMock()
        cog.dashboard_messages["123"] = dashboard_msg
        cog._update_dashboard_for_guild = AsyncMock()

        fake_mixer = MagicMock(spec=MixingAudioSource)
        fake_track = MagicMock(id="track-1")
        fake_mixer.add_track = MagicMock(return_value=fake_track)
        monkeypatch.setattr("commands.music.guild_mixers", {"123": fake_mixer})
        make_playable_guild(cog, "123", fake_mixer)

        await cog._play_song("123", {"url": "stream-a", "needs_resolve": False, "title": "Song A"})

        dashboard_msg.clear_reactions.assert_awaited_once()
        dashboard_msg.add_reaction.assert_awaited_once_with(cog.FAVORITE_EMOJI)
        assert cog.current_track["123"] is fake_track

    @pytest.mark.asyncio
    async def test_no_dashboard_message_is_noop_no_error(self, monkeypatch):
        cog = make_music_cog()
        cog._update_dashboard_for_guild = AsyncMock()

        fake_mixer = MagicMock(spec=MixingAudioSource)
        fake_mixer.add_track = MagicMock(return_value=MagicMock(id="track-1"))
        monkeypatch.setattr("commands.music.guild_mixers", {"123": fake_mixer})
        make_playable_guild(cog, "123", fake_mixer)

        await cog._play_song("123", {"url": "stream-a", "needs_resolve": False, "title": "Song A"})
        # No dashboard message registered for this guild -- must not raise.

    @pytest.mark.asyncio
    async def test_clear_reactions_failure_does_not_prevent_playback(self, monkeypatch):
        cog = make_music_cog()
        dashboard_msg = MagicMock()
        dashboard_msg.clear_reactions = AsyncMock(
            side_effect=discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Missing Permissions")
        )
        dashboard_msg.add_reaction = AsyncMock()
        cog.dashboard_messages["123"] = dashboard_msg
        cog._update_dashboard_for_guild = AsyncMock()

        fake_mixer = MagicMock(spec=MixingAudioSource)
        fake_track = MagicMock(id="track-1")
        fake_mixer.add_track = MagicMock(return_value=fake_track)
        monkeypatch.setattr("commands.music.guild_mixers", {"123": fake_mixer})
        make_playable_guild(cog, "123", fake_mixer)

        await cog._play_song("123", {"url": "stream-a", "needs_resolve": False, "title": "Song A"})

        assert cog.current_track["123"] is fake_track  # playback still proceeded
        cog._update_dashboard_for_guild.assert_awaited_once_with("123")

    @pytest.mark.asyncio
    async def test_pre_adds_favorite_reaction_after_clearing(self, monkeypatch):
        cog = make_music_cog()
        dashboard_msg = MagicMock()
        dashboard_msg.clear_reactions = AsyncMock()
        dashboard_msg.add_reaction = AsyncMock()
        cog.dashboard_messages["123"] = dashboard_msg
        cog._update_dashboard_for_guild = AsyncMock()

        fake_mixer = MagicMock(spec=MixingAudioSource)
        fake_track = MagicMock(id="track-1")
        fake_mixer.add_track = MagicMock(return_value=fake_track)
        monkeypatch.setattr("commands.music.guild_mixers", {"123": fake_mixer})
        make_playable_guild(cog, "123", fake_mixer)

        await cog._play_song("123", {"url": "stream-a", "needs_resolve": False, "title": "Song A"})

        dashboard_msg.add_reaction.assert_awaited_once_with("❤️")

    @pytest.mark.asyncio
    async def test_add_reaction_failure_does_not_prevent_playback(self, monkeypatch):
        cog = make_music_cog()
        dashboard_msg = MagicMock()
        dashboard_msg.clear_reactions = AsyncMock()
        dashboard_msg.add_reaction = AsyncMock(
            side_effect=discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Missing Permissions")
        )
        cog.dashboard_messages["123"] = dashboard_msg
        cog._update_dashboard_for_guild = AsyncMock()

        fake_mixer = MagicMock(spec=MixingAudioSource)
        fake_track = MagicMock(id="track-1")
        fake_mixer.add_track = MagicMock(return_value=fake_track)
        monkeypatch.setattr("commands.music.guild_mixers", {"123": fake_mixer})
        make_playable_guild(cog, "123", fake_mixer)

        await cog._play_song("123", {"url": "stream-a", "needs_resolve": False, "title": "Song A"})

        assert cog.current_track["123"] is fake_track  # playback still proceeded
        cog._update_dashboard_for_guild.assert_awaited_once_with("123")


class TestFavoritesPlay:
    @pytest.mark.asyncio
    async def test_no_favorites_sends_message(self, monkeypatch):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        interaction = make_interaction()

        await Music.favorites_play.callback(cog, interaction)

        interaction.followup.send.assert_awaited_once()
        args, kwargs = interaction.followup.send.call_args
        assert "don't have any favorited" in args[0]

    @pytest.mark.asyncio
    async def test_queues_all_favorites_and_finalizes(self, monkeypatch):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=MagicMock())
        cog._finalize_play = AsyncMock()
        favorites = {"123": {"999": [
            {"url": "url-a", "title": "Song A", "thumbnail": "thumb-a", "duration": 100},
            {"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50},
        ]}}
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=favorites))
        embed = discord.Embed(title="📥 Playlist Added")
        cog._queue_playlist_entries = AsyncMock(return_value=(embed, False))
        interaction = make_interaction()

        await Music.favorites_play.callback(cog, interaction)

        cog._queue_playlist_entries.assert_awaited_once()
        call_args = cog._queue_playlist_entries.call_args[0]
        assert call_args[0] == "123"
        assert call_args[1] == [
            {"url": "url-a", "title": "Song A", "thumbnail": "thumb-a", "duration": 100},
            {"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50},
        ]
        cog._finalize_play.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_voice_channel_aborts_early(self, monkeypatch):
        cog = make_music_cog()
        cog._ensure_voice = AsyncMock(return_value=None)
        cog._queue_playlist_entries = AsyncMock()
        interaction = make_interaction()

        await Music.favorites_play.callback(cog, interaction)

        cog._queue_playlist_entries.assert_not_called()


class TestFavoritesList:
    @pytest.mark.asyncio
    async def test_empty_favorites_shows_message(self, monkeypatch):
        cog = make_music_cog()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        interaction = make_interaction()

        await Music.favorites_list.callback(cog, interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert "No favorited songs yet" in kwargs["embed"].description

    @pytest.mark.asyncio
    async def test_lists_favorites_with_truncation(self, monkeypatch):
        cog = make_music_cog()
        favs = [{"url": f"url-{i}", "title": f"Song {i}", "thumbnail": "", "duration": 60} for i in range(12)]
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={"123": {"999": favs}}))
        interaction = make_interaction()

        await Music.favorites_list.callback(cog, interaction)

        _, kwargs = interaction.response.send_message.call_args
        desc = kwargs["embed"].description
        assert "Song 0" in desc
        assert "Song 9" in desc
        assert "Song 10" not in desc
        assert "and 2 more" in desc


class TestFavoritesRemove:
    @pytest.mark.asyncio
    async def test_no_favorites_shows_message(self, monkeypatch):
        cog = make_music_cog()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        interaction = make_interaction()

        await Music.favorites_remove.callback(cog, interaction, 1)

        interaction.response.send_message.assert_awaited_once_with(
            "You don't have any favorited songs.", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_out_of_range_position_rejected(self, monkeypatch):
        cog = make_music_cog()
        favs = [{"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100}]
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={"123": {"999": favs}}))
        interaction = make_interaction()

        await Music.favorites_remove.callback(cog, interaction, 5)

        interaction.response.send_message.assert_awaited_once_with("Position must be 1–1.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_removes_correct_entry_and_saves(self, monkeypatch):
        cog = make_music_cog()
        favs = [
            {"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100},
            {"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50},
        ]
        data = {"123": {"999": favs}}
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=data))
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)
        interaction = make_interaction()

        await Music.favorites_remove.callback(cog, interaction, 1)

        save_mock.assert_awaited_once()
        saved = save_mock.call_args[0][0]
        assert saved["123"]["999"] == [{"url": "url-b", "title": "Song B", "thumbnail": "", "duration": 50}]
        interaction.response.send_message.assert_awaited_once_with(
            "🗑️ Removed **Song A** from your favorites.", ephemeral=True
        )


class TestFavoritesClear:
    @pytest.mark.asyncio
    async def test_clears_existing_favorites(self, monkeypatch):
        cog = make_music_cog()
        data = {"123": {"999": [{"url": "url-a", "title": "Song A", "thumbnail": "", "duration": 100}]}}
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value=data))
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)
        interaction = make_interaction()

        await Music.favorites_clear.callback(cog, interaction)

        save_mock.assert_awaited_once()
        saved = save_mock.call_args[0][0]
        assert saved["123"]["999"] == []
        interaction.response.send_message.assert_awaited_once_with(
            "🧹 Your favorites have been cleared.", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_clearing_when_no_favorites_exist_does_not_raise(self, monkeypatch):
        cog = make_music_cog()
        monkeypatch.setattr("commands.music.load_music_favorites", AsyncMock(return_value={}))
        save_mock = AsyncMock()
        monkeypatch.setattr("commands.music.save_music_favorites", save_mock)
        interaction = make_interaction()

        await Music.favorites_clear.callback(cog, interaction)

        save_mock.assert_not_called()
        interaction.response.send_message.assert_awaited_once_with(
            "🧹 Your favorites have been cleared.", ephemeral=True
        )
