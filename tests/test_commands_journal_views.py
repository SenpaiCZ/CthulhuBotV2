import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._journal_views import (
    JournalEntryModal,
    DeleteConfirmationView,
    ImageManageView,
    DeleteImageConfirmationView,
    JournalView,
    ClueTargetSelect,
    ClueDestinationView,
)


def make_interaction(user=None, guild_id=111, admin=False):
    interaction = MagicMock()
    interaction.user = user or MagicMock(id=222)
    interaction.guild_id = guild_id
    interaction.permissions = MagicMock(administrator=admin)
    interaction.user.guild_permissions = MagicMock(administrator=admin)
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup.send = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


class TestJournalEntryModal:
    @pytest.mark.asyncio
    async def test_personal_new_entry_is_appended_and_parent_refreshed(self):
        parent_view = MagicMock()
        parent_view.external_refresh = AsyncMock()
        modal = JournalEntryModal(MagicMock(), mode="personal", parent_view=parent_view)
        modal.entry_title._value = "Day One"
        modal.entry_content._value = "We arrived in Arkham."

        interaction = make_interaction(guild_id=111)
        journal_data = {}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)), \
             patch("commands._journal_views.save_journal_data", new=AsyncMock()) as mock_save:
            await modal.on_submit(interaction)

        entries = journal_data["111"]["personal"]["222"]["entries"]
        assert len(entries) == 1
        assert entries[0]["title"] == "Day One"
        assert entries[0]["content"] == "We arrived in Arkham."
        mock_save.assert_awaited_once()
        parent_view.external_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_master_mode_requires_admin_permissions(self):
        modal = JournalEntryModal(MagicMock(), mode="master")
        modal.entry_title._value = "GM note"
        modal.entry_content._value = "Something lurks."

        interaction = make_interaction(admin=False)
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value={})):
            await modal.on_submit(interaction)

        interaction.followup.send.assert_awaited_once()
        assert "Only Game Masters" in interaction.followup.send.call_args.args[0]

    @pytest.mark.asyncio
    async def test_editing_existing_entry_preserves_timestamp_and_author(self):
        original_entry = {"title": "Old", "content": "Old content", "author_id": "999", "timestamp": 123.0, "images": []}
        modal = JournalEntryModal(MagicMock(), mode="personal", entry_index=0, original_entry=original_entry)
        modal.entry_title._value = "New Title"
        modal.entry_content._value = "New content"

        interaction = make_interaction(guild_id=111)
        journal_data = {"111": {"personal": {"222": {"entries": [dict(original_entry)]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)), \
             patch("commands._journal_views.save_journal_data", new=AsyncMock()):
            await modal.on_submit(interaction)

        updated = journal_data["111"]["personal"]["222"]["entries"][0]
        assert updated["title"] == "New Title"
        assert updated["author_id"] == "999"
        assert updated["timestamp"] == 123.0

    @pytest.mark.asyncio
    async def test_inspect_mode_requires_admin(self):
        modal = JournalEntryModal(MagicMock(), mode="inspect", target_user_id="555")
        modal.entry_title._value = "Clue"
        modal.entry_content._value = "A note"

        interaction = make_interaction(admin=False)
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value={})):
            await modal.on_submit(interaction)

        interaction.followup.send.assert_awaited_once()
        assert "Only Game Masters" in interaction.followup.send.call_args.args[0]


class TestDeleteConfirmationView:
    @pytest.mark.asyncio
    async def test_confirm_removes_personal_entry_and_refreshes(self):
        parent_view = MagicMock()
        parent_view.external_refresh = AsyncMock()
        view = DeleteConfirmationView("personal", "222", entry_index=0, parent_view=parent_view)
        interaction = make_interaction(guild_id=111)

        journal_data = {"111": {"personal": {"222": {"entries": [{"title": "A"}]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)), \
             patch("commands._journal_views.save_journal_data", new=AsyncMock()) as mock_save:
            await view.confirm.callback(interaction)

        assert journal_data["111"]["personal"]["222"]["entries"] == []
        mock_save.assert_awaited_once()
        parent_view.external_refresh.assert_awaited_once()
        assert view.is_finished()

    @pytest.mark.asyncio
    async def test_confirm_reports_error_when_entry_not_found(self):
        view = DeleteConfirmationView("master", None, entry_index=5, parent_view=MagicMock())
        interaction = make_interaction()

        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value={})):
            await view.confirm.callback(interaction)

        interaction.followup.send.assert_awaited_once()
        assert "Could not find entry" in interaction.followup.send.call_args.args[0]

    @pytest.mark.asyncio
    async def test_cancel_sends_message_and_stops(self):
        view = DeleteConfirmationView("personal", "222", 0, MagicMock())
        interaction = make_interaction()

        await view.cancel.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("❌ Deletion cancelled.", ephemeral=True)
        assert view.is_finished()


class TestImageManageView:
    @pytest.mark.asyncio
    async def test_select_callback_removes_chosen_image(self):
        parent_view = MagicMock()
        parent_view.external_refresh = AsyncMock()
        view = ImageManageView("personal", "222", entry_index=0, images=["a.png", "b.png"], parent_view=parent_view)
        view.select_menu._values = ["1"]
        interaction = make_interaction(guild_id=111)

        journal_data = {"111": {"personal": {"222": {"entries": [{"images": ["a.png", "b.png"]}]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)), \
             patch("commands._journal_views.save_journal_data", new=AsyncMock()) as mock_save, \
             patch("commands._journal_views.os.path.exists", return_value=False):
            await view.select_callback(interaction)

        assert journal_data["111"]["personal"]["222"]["entries"][0]["images"] == ["a.png"]
        mock_save.assert_awaited_once()
        parent_view.external_refresh.assert_awaited_once()


class TestDeleteImageConfirmationView:
    @pytest.mark.asyncio
    async def test_confirm_removes_named_image(self):
        parent_view = MagicMock()
        parent_view.external_refresh = AsyncMock()
        view = DeleteImageConfirmationView("master", None, entry_index=0, image_filename="a.png", parent_view=parent_view)
        interaction = make_interaction(guild_id=111)

        journal_data = {"111": {"master": {"entries": [{"images": ["a.png"]}]}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)), \
             patch("commands._journal_views.save_journal_data", new=AsyncMock()) as mock_save, \
             patch("commands._journal_views.os.path.exists", return_value=False):
            await view.confirm.callback(interaction)

        assert journal_data["111"]["master"]["entries"][0]["images"] == []
        mock_save.assert_awaited_once()
        parent_view.external_refresh.assert_awaited_once()


class TestJournalView:
    @pytest.mark.asyncio
    async def test_load_entries_personal_mode(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")

        journal_data = {"111": {"personal": {"222": {"entries": [{"title": "A"}]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)):
            entries = await view.load_entries()

        assert entries == [{"title": "A"}]

    @pytest.mark.asyncio
    async def test_get_embed_empty_journal(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")

        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value={})):
            embed = await view.get_embed()

        assert "empty" in embed.description

    @pytest.mark.asyncio
    async def test_prev_next_buttons_change_page(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")
        view.message = MagicMock()

        journal_data = {"111": {"personal": {"222": {"entries": [
            {"title": "A", "content": "First", "timestamp": 1},
            {"title": "B", "content": "Second", "timestamp": 2},
        ]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)):
            await view.next_button.callback(interaction)
            assert view.current_page == 1
            await view.prev_button.callback(interaction)
            assert view.current_page == 0

    @pytest.mark.asyncio
    async def test_add_entry_button_opens_modal(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")

        await view.add_entry_button.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_entry_button_blocked_for_inspect_non_admin(self):
        interaction = make_interaction(guild_id=111, admin=False)
        view = JournalView(MagicMock(), interaction, mode="inspect", target_user_id="999")

        await view.add_entry_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "cannot write" in interaction.response.send_message.call_args.args[0]
        interaction.response.send_modal.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_button_opens_confirmation_with_real_index(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")
        view.current_page = 0

        journal_data = {"111": {"personal": {"222": {"entries": [{"title": "A"}, {"title": "B"}]}}}}
        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value=journal_data)):
            await view.delete_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        confirm_view = kwargs["view"]
        assert isinstance(confirm_view, DeleteConfirmationView)
        # newest-first display means page 0 (newest = "B") maps to real_index 1
        assert confirm_view.entry_index == 1

    def test_update_buttons_switch_label_toggles_by_mode(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")
        view._update_buttons([])
        assert view.switch_button.label == "Switch to Master Journal"

        view.mode = "master"
        view._update_buttons([])
        assert view.switch_button.label == "Switch to Personal Journal"

    def test_update_buttons_disables_edit_delete_without_entries(self):
        interaction = make_interaction(guild_id=111)
        view = JournalView(MagicMock(), interaction, mode="personal")
        view._update_buttons([])
        assert view.edit_button.disabled is True
        assert view.delete_button.disabled is True

    @pytest.mark.asyncio
    async def test_switch_button_denies_master_access_without_permission(self):
        interaction = make_interaction(guild_id=111, admin=False)
        view = JournalView(MagicMock(), interaction, mode="personal")

        with patch("commands._journal_views.load_journal_data", new=AsyncMock(return_value={"111": {"master": {"access": []}}})):
            await view.switch_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "do not have access" in interaction.response.send_message.call_args.args[0]
        assert view.mode == "personal"


class TestClueTargetSelectAndDestinationView:
    @pytest.mark.asyncio
    async def test_clue_target_select_opens_inspect_modal_for_target(self):
        target_user = MagicMock(id=777)
        select = ClueTargetSelect(MagicMock(), original_entry={"title": "Clue"}, image_attachments=[])
        select._values = [target_user]
        interaction = make_interaction()

        await select.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.call_args.args[0]
        assert modal.mode == "inspect"
        assert modal.target_user_id == "777"

    @pytest.mark.asyncio
    async def test_give_button_swaps_view_to_user_select(self):
        view = ClueDestinationView(MagicMock(), original_entry={"title": "Clue"}, image_attachments=[])
        interaction = make_interaction()

        await view.give.callback(interaction)

        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        assert any(isinstance(c, ClueTargetSelect) for c in kwargs["view"].children)

    @pytest.mark.asyncio
    async def test_personal_button_opens_modal_and_stops(self):
        view = ClueDestinationView(MagicMock(), original_entry={"title": "Clue"}, image_attachments=[])
        interaction = make_interaction()

        await view.personal.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], JournalEntryModal)
        assert view.is_finished()
