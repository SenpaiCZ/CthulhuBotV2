import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._karma_views import (
    KarmaActionsView,
    KarmaRoleSetupMainView,
    KarmaRoleSelectView,
    KarmaThresholdModal,
    KarmaRoleRemoveView,
    KarmaRoleRemoveSelect,
    LeaderboardView,
    KarmaSetupChannelView,
    KarmaSetupEmojiModal,
    KarmaSetupNotifyView,
)


def make_interaction(user=None, guild_id=111):
    interaction = MagicMock()
    interaction.user = user or MagicMock(id=222)
    interaction.guild_id = guild_id
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    return interaction


class TestKarmaActionsView:
    def test_dead_code_shape_only(self):
        # KarmaActionsView is confirmed dead code (never instantiated by production callers).
        # We only verify it still constructs and exposes its two documented buttons, so a
        # future accidental deletion/behavior change is caught without over-investing here.
        view = KarmaActionsView(MagicMock(), MagicMock())
        labels = {c.label for c in view.children}
        assert labels == {"Check Karma", "View Rank Card"}


class TestKarmaRoleSetupMainView:
    @pytest.mark.asyncio
    async def test_add_role_opens_role_select_view(self):
        user = MagicMock()
        view = KarmaRoleSetupMainView(MagicMock(), user)
        interaction = make_interaction(user=user)

        await view.add_role.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], KarmaRoleSelectView)

    @pytest.mark.asyncio
    async def test_remove_role_with_no_roles_configured(self):
        user = MagicMock()
        view = KarmaRoleSetupMainView(MagicMock(), user)
        interaction = make_interaction(user=user)

        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value={})):
            await view.remove_role.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("No roles configured yet.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_remove_role_shows_select_when_roles_exist(self):
        user = MagicMock()
        view = KarmaRoleSetupMainView(MagicMock(), user)
        interaction = make_interaction(user=user, guild_id=111)
        interaction.guild = MagicMock()
        interaction.guild.get_role = MagicMock(return_value=MagicMock(name="Cultist"))

        settings = {"111": {"roles": {"10": "555"}}}
        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value=settings)):
            await view.remove_role.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], KarmaRoleRemoveView)

    @pytest.mark.asyncio
    async def test_interaction_check_only_allows_owning_user(self):
        user = MagicMock(id=1)
        view = KarmaRoleSetupMainView(MagicMock(), user)
        interaction = make_interaction(user=MagicMock(id=2))

        assert await view.interaction_check(interaction) is False


class TestKarmaThresholdModal:
    @pytest.mark.asyncio
    async def test_valid_amount_saves_role_threshold(self):
        role = MagicMock(id=555, name="Cultist")
        bot = MagicMock()
        bot.get_cog = MagicMock(return_value=None)
        modal = KarmaThresholdModal(role, bot)
        modal.amount.component._value = "25"

        interaction = make_interaction(guild_id=111)
        settings = {}
        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value=settings)), \
             patch("commands._karma_views.save_karma_settings", new=AsyncMock()) as mock_save:
            await modal.on_submit(interaction)

        assert settings["111"]["roles"]["25"] == 555
        mock_save.assert_awaited_once_with(settings)
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_amount_rejected(self):
        role = MagicMock(id=555)
        modal = KarmaThresholdModal(role, MagicMock())
        modal.amount.component._value = "not-a-number"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "❌ Invalid number. Please enter a valid integer.", ephemeral=True
        )


class TestKarmaRoleRemoveSelect:
    @pytest.mark.asyncio
    async def test_callback_removes_threshold_from_settings(self):
        guild = MagicMock()
        guild.get_role = MagicMock(return_value=MagicMock(name="Cultist"))
        bot = MagicMock()
        bot.get_cog = MagicMock(return_value=None)
        view = KarmaRoleRemoveView(bot, MagicMock(), {"10": "555"}, guild)
        select = view.children[0]
        assert isinstance(select, KarmaRoleRemoveSelect)
        select._values = ["10"]

        interaction = make_interaction(guild_id=111)
        settings = {"111": {"roles": {"10": "555"}}}
        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value=settings)), \
             patch("commands._karma_views.save_karma_settings", new=AsyncMock()) as mock_save:
            await select.callback(interaction)

        assert "10" not in settings["111"]["roles"]
        mock_save.assert_awaited_once()
        interaction.response.send_message.assert_awaited_once()
        assert "Removed threshold" in interaction.response.send_message.call_args.args[0]

    @pytest.mark.asyncio
    async def test_callback_reports_error_if_threshold_missing(self):
        guild = MagicMock()
        view = KarmaRoleRemoveView(MagicMock(), MagicMock(), {"10": "555"}, guild)
        select = view.children[0]
        select._values = ["10"]

        interaction = make_interaction(guild_id=111)
        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value={})):
            await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("❌ Error finding threshold.", ephemeral=True)


class TestLeaderboardView:
    def test_pagination_bounds(self):
        interaction = make_interaction()
        users = [(str(i), 100 - i) for i in range(25)]
        view = LeaderboardView(interaction, users, items_per_page=10)

        assert view.total_pages == 3
        assert view.previous_page.disabled is True
        assert view.next_page.disabled is False

    @pytest.mark.asyncio
    async def test_next_page_advances_and_updates_buttons(self):
        interaction = make_interaction()
        interaction.guild = MagicMock()
        interaction.guild.get_member = MagicMock(return_value=MagicMock(display_name="Jane"))
        users = [(str(i), 100 - i) for i in range(15)]
        view = LeaderboardView(interaction, users, items_per_page=10)

        await view.next_page.callback(interaction)

        assert view.current_page == 2
        assert view.next_page.disabled is True
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_other_users(self):
        owner_interaction = make_interaction(user=MagicMock(id=1))
        view = LeaderboardView(owner_interaction, [("1", 10)])
        other = make_interaction(user=MagicMock(id=2))

        assert await view.interaction_check(other) is False
        other.response.send_message.assert_awaited_once_with("This isn't your leaderboard!", ephemeral=True)


class TestKarmaSetupFlow:
    @pytest.mark.asyncio
    async def test_channel_select_opens_emoji_modal(self):
        user = MagicMock()
        view = KarmaSetupChannelView(MagicMock(), user)
        channel = MagicMock(id=333)
        view.select_channel._values = [channel]
        interaction = make_interaction(user=user)

        await view.select_channel.callback(interaction)

        assert view.channel_id == 333
        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], KarmaSetupEmojiModal)

    @pytest.mark.asyncio
    async def test_emoji_modal_submits_to_notify_view(self):
        modal = KarmaSetupEmojiModal(MagicMock(), MagicMock(), channel_id=333)
        modal.upvote.component._value = "👍"
        modal.downvote.component._value = "👎"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        notify_view = kwargs["view"]
        assert isinstance(notify_view, KarmaSetupNotifyView)
        assert notify_view.data == {"channel_id": 333, "upvote_emoji": "👍", "downvote_emoji": "👎"}

    @pytest.mark.asyncio
    async def test_finish_setup_preserves_existing_roles(self):
        view = KarmaSetupNotifyView(MagicMock(), MagicMock(), channel_id=333, up="👍", down="👎")
        interaction = make_interaction(guild_id=111)

        settings = {"111": {"roles": {"10": "555"}}}
        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value=settings)), \
             patch("commands._karma_views.save_karma_settings", new=AsyncMock()) as mock_save:
            await view.finish_setup(interaction, notify_id=999)

        saved = mock_save.call_args.args[0]
        assert saved["111"]["roles"] == {"10": "555"}
        assert saved["111"]["notification_channel_id"] == 999
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_button_finishes_with_no_notification_channel(self):
        view = KarmaSetupNotifyView(MagicMock(), MagicMock(), channel_id=333, up="👍", down="👎")
        interaction = make_interaction(guild_id=111)

        with patch("commands._karma_views.load_karma_settings", new=AsyncMock(return_value={})), \
             patch("commands._karma_views.save_karma_settings", new=AsyncMock()) as mock_save:
            await view.skip.callback(interaction)

        saved = mock_save.call_args.args[0]
        assert saved["111"]["notification_channel_id"] is None
