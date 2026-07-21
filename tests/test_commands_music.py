import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
import yt_dlp
from discord.ext import tasks

from commands.music import Music, _query_has_explicit_video, MusicLookupError, _format_download_error, CookieView, PlaylistChoiceView


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
